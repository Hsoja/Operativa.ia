"""Webhooks de proveedores - Operativa.ia

Sin sesión ni CSRF: la autenticidad se prueba con la firma del proveedor sobre el cuerpo exacto.
Si la integración no está configurada, las rutas responden 404 (fail-closed).
"""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.logs import security_event
from app.services import booking, channels, payments, tenants, whatsapp
from app.services.calendar_service import create_appointment

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])


def _require_whatsapp() -> None:
    if not get_settings().whatsapp_enabled:
        raise HTTPException(status_code=404, detail="No encontrado.")


@router.get("/whatsapp", response_class=PlainTextResponse)
def whatsapp_verify(request: Request):
    _require_whatsapp()
    params = request.query_params
    challenge = whatsapp.verify_subscription(
        params.get("hub.mode"), params.get("hub.verify_token"), params.get("hub.challenge")
    )
    if challenge is None:
        security_event("whatsapp_verify_rejected", "WARNING")
        raise HTTPException(status_code=403, detail="Solicitud rechazada.")
    return PlainTextResponse(challenge)


@router.post("/whatsapp")
async def whatsapp_receive(request: Request, background: BackgroundTasks):
    _require_whatsapp()
    raw = await request.body()
    if not whatsapp.verify_signature(raw, request.headers.get("x-hub-signature-256")):
        security_event("webhook_signature_invalid", "WARNING", provider="whatsapp")
        raise HTTPException(status_code=401, detail="Firma inválida.")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        security_event("whatsapp_payload_rejected", "WARNING", fields=["json"])
        raise HTTPException(status_code=400, detail="Cuerpo inválido.") from None
    messages = whatsapp.extract_messages(payload) if isinstance(payload, dict) else []
    # Se responde 200 enseguida; Meta reintenta si tarda. La idempotencia evita respuestas dobles.
    for phone_number_id, message in messages:
        background.add_task(whatsapp.handle_message, phone_number_id, message)
    return {"status": "ok"}


def _require_stripe() -> None:
    if not get_settings().stripe_enabled:
        raise HTTPException(status_code=404, detail="No encontrado.")


def _sync_calendar(tenant_id: int, appointment_id: int) -> None:
    """Copia la cita confirmada a Google Calendar si está activo. Un fallo no deshace la cita."""
    appointment = booking.get_appointment(tenant_id, appointment_id)
    tenant = tenants.get(tenant_id)
    if not appointment or not tenant:
        return
    local = datetime.fromtimestamp(appointment["starts_at"], ZoneInfo(tenant["timezone"]))
    create_appointment(
        summary=f"{appointment['service']} - {appointment['customer_name']}",
        description="Reservada en línea con depósito pagado.",
        start_time_iso=local.strftime("%Y-%m-%dT%H:%M:%S"),
        duration_minutes=appointment["duration_minutes"],
        timezone=tenant["timezone"],
    )


@router.post("/stripe")
async def stripe_receive(request: Request, background: BackgroundTasks):
    _require_stripe()
    raw = await request.body()
    if not payments.verify_signature(raw, request.headers.get("stripe-signature")):
        security_event("webhook_signature_invalid", "WARNING", provider="stripe")
        raise HTTPException(status_code=401, detail="Firma inválida.")
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Cuerpo inválido.") from None
    event = payments.parse_event(payload) if isinstance(payload, dict) else None
    if event is None:
        return {"status": "ignored"}
    if not channels.register_event("stripe", event.id):
        return {"status": "duplicate"}
    if event.type not in ("checkout.session.completed", "checkout.session.expired") or isinstance(event.data, dict):
        return {"status": "ignored"}

    session = event.data.object
    tenant_id, appointment_id = int(session.metadata.tenant_id), int(session.metadata.appointment_id)
    if event.type == "checkout.session.expired":
        booking.expire_session(tenant_id, appointment_id, session.id)
        security_event("payment_expired", tenant_id=tenant_id)
        return {"status": "ok"}
    if session.payment_status != "paid" or session.amount_total is None or not session.currency:
        security_event("payment_not_paid", "WARNING", tenant_id=tenant_id)
        return {"status": "ok"}
    result = booking.confirm_payment(tenant_id, appointment_id, session.id, session.amount_total, session.currency)
    level = "INFO" if result in ("confirmed", "already_confirmed") else "WARNING"
    security_event("payment_processed", level, tenant_id=tenant_id, result=result)
    if result == "confirmed":
        background.add_task(_sync_calendar, tenant_id, appointment_id)
    return {"status": "ok"}
