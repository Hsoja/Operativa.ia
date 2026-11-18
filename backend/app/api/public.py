"""Rutas públicas por negocio - Operativa.ia

Las usa el sitio o el widget de cada PYME, sin sesión. El negocio se identifica con el `slug` de la URL
y solo se aceptan negocios activos. No usan cookies, así que no necesitan CSRF.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import StringConstraints

from app.api.deps import public_tenant
from app.core.config import get_settings
from app.core.logs import security_event
from app.core.ratelimit import browse_rate, chat_rate, client_ip, contact_rate, limiter
from app.core.validation import CleanStr, StrictModel
from app.services import agent, booking, coverage, leads, payments, reactivation, tenants

router = APIRouter(prefix="/api/v1/public/{slug}", tags=["Público"])

ConversationToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,64}$")]


class ChatRequest(StrictModel):
    message: CleanStr(max_length=2000)
    conversation_id: ConversationToken | None = None


@router.get("/profile")
@limiter.limit(browse_rate)
def read_profile(request: Request, tenant: dict = Depends(public_tenant)):
    """Nombre y datos públicos del negocio para el encabezado del widget."""
    profile = tenants.public_profile(tenant)
    return {"slug": profile["slug"], "name": profile["name"], "business_type": profile["business_type"]}


@router.post("/chat")
@limiter.limit(chat_rate)
def chat_with_agent(request: Request, payload: ChatRequest, tenant: dict = Depends(public_tenant)):
    """Mensaje de un cliente del negocio; la respuesta trae el identificador de la conversación."""
    return agent.process_message(tenant, payload.message, payload.conversation_id, client_ip(request))


@router.post("/coverage")
@limiter.limit(chat_rate)
def check_coverage(request: Request, payload: coverage.CoverageQuery, tenant: dict = Depends(public_tenant)):
    """¿El negocio atiende mi zona y acepta mi aseguradora? Resultado determinista; no se guarda la consulta."""
    result = coverage.check(tenant["id"], payload)
    security_event("coverage_checked", tenant=tenant["slug"], via="api", area=result["area"], insurance=result["insurance"])
    return {**result, "message": coverage.describe(result)}


@router.get("/services")
@limiter.limit(browse_rate)
def read_services(request: Request, tenant: dict = Depends(public_tenant)):
    """Servicios reservables con su duración y depósito (montos en centavos)."""
    first, last = booking.bookable_days(tenant)
    services = [
        {k: s[k] for k in ("id", "name", "duration_minutes", "deposit_cents", "currency")}
        for s in booking.list_services(tenant["id"])
    ]
    return {"services": services, "timezone": tenant["timezone"], "first_day": first.isoformat(), "last_day": last.isoformat()}


@router.get("/slots")
@limiter.limit(browse_rate)
def read_slots(
    request: Request,
    service_id: Annotated[int, Query(ge=1)],
    day: Annotated[date, Query(alias="date")],
    tenant: dict = Depends(public_tenant),
):
    service = booking.get_service(tenant["id"], service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return {"slots": booking.list_slots(tenant, service, day)}


@router.post("/bookings", status_code=201)
@limiter.limit(contact_rate)
def create_booking(request: Request, payload: booking.BookingIn, tenant: dict = Depends(public_tenant)):
    """Reserva un horario. Con depósito devuelve la URL de Stripe Checkout; el monto lo fija el servidor."""
    service = booking.get_service(tenant["id"], payload.service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="No encontrado.")
    if service["deposit_cents"] > 0 and not get_settings().stripe_enabled:
        # Fail-closed: sin pagos configurados no se bloquean huecos que nadie podrá pagar
        raise HTTPException(status_code=503, detail="Las reservas con depósito no están disponibles.")
    try:
        created = booking.create_booking(tenant, payload)
    except booking.SlotTaken:
        raise HTTPException(status_code=409, detail="Ese horario ya no está disponible.") from None
    except booking.BookingError:
        raise HTTPException(status_code=422, detail="Datos inválidos.") from None
    reactivation.record_contact(tenant["id"], payload.email, payload.name, payload.marketing_consent, "booking")
    security_event("booking_created", tenant=tenant["slug"], status=created["status"])
    if created["status"] == "confirmed":
        return {"status": "confirmed", "ref": created["ref"]}
    try:
        session_id, url = payments.create_checkout(tenant, created, payload.email)
    except payments.PaymentError:
        booking.cancel(tenant["id"], created["id"])
        raise HTTPException(status_code=502, detail="No se pudo iniciar el pago. Intenta de nuevo.") from None
    booking.attach_session(tenant["id"], created["id"], session_id)
    return {"status": "pending_payment", "ref": created["ref"], "checkout_url": url}


@router.get("/bookings/{ref}")
@limiter.limit(browse_rate)
def read_booking(request: Request, ref: Annotated[str, StringConstraints(pattern=booking.REF_PATTERN)], tenant: dict = Depends(public_tenant)):
    """Estado de una reserva por su referencia secreta (sin datos del cliente)."""
    found = booking.status_by_ref(tenant["id"], ref)
    if found is None:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return {"status": found["status"], "service": found["service"], "starts_at": found["starts_at"]}


@router.post("/contact", status_code=201)
@limiter.limit(contact_rate)
def submit_contact(
    request: Request, payload: leads.LeadIn, background: BackgroundTasks, tenant: dict = Depends(public_tenant)
):
    """Solicitud de contacto o demo. Requiere consentimiento; el contenido nunca va al log."""
    leads.create_lead(tenant["id"], payload)
    reactivation.record_contact(tenant["id"], payload.email, payload.name, payload.marketing_consent, payload.source)
    security_event("lead_received", tenant=tenant["slug"], source=payload.source)
    # En segundo plano: un correo de aviso lento o fallido no debe retrasar ni romper la respuesta
    background.add_task(reactivation.notify_new_lead, tenant, payload)
    return JSONResponse(status_code=201, content={"status": "received"})


@router.post("/unsubscribe/{token}")
@limiter.limit(browse_rate)
def unsubscribe(request: Request, token: Annotated[str, StringConstraints(pattern=reactivation.TOKEN_PATTERN)], tenant: dict = Depends(public_tenant)):
    """Baja de un clic (CASL / RFC 8058). Solo POST: un escáner de enlaces que haga GET no da de baja a nadie."""
    if not reactivation.unsubscribe(tenant["id"], token):
        raise HTTPException(status_code=404, detail="No encontrado.")
    security_event("contact_unsubscribed", tenant=tenant["slug"])
    return {"status": "unsubscribed"}
