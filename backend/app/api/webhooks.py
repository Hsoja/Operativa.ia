"""Webhooks de proveedores - Operativa.ia

Sin sesión ni CSRF: la autenticidad se prueba con la firma del proveedor sobre el cuerpo exacto.
Si la integración no está configurada, las rutas responden 404 (fail-closed).
"""

import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.core.config import get_settings
from app.core.logs import security_event
from app.services import whatsapp

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
