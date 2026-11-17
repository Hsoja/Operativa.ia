"""WhatsApp Cloud API (Meta) - Operativa.ia

Captación 24/7: un mensaje de texto que llega al número de un negocio se responde con Sofía.
- Apagado salvo que estén WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN y WHATSAPP_ACCESS_TOKEN.
- Cada POST se verifica con X-Hub-Signature-256 (HMAC-SHA256 del cuerpo exacto con el App Secret).
- Idempotencia por id de mensaje y rechazo de mensajes viejos.
- El número del cliente nunca se guarda ni se registra en claro.
"""

import hashlib
import hmac
import re
import time
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.core.logs import hash_identifier, security_event
from app.core.validation import clean_text
from app.services import agent, channels

GRAPH_HOST = "https://graph.facebook.com"
WA_ID = re.compile(r"^\d{6,20}$")
MAX_TEXT = 2000
NON_TEXT_REPLY = "Por ahora solo puedo leer mensajes de texto. ¿Me escribes tu consulta?"


# Modelos de lectura: Meta agrega campos con el tiempo, así que se ignoran los desconocidos,
# pero los que usamos se validan con tipo y largo.
class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Text(_Lenient):
    body: Annotated[str, Field(max_length=4096)]


class _Message(_Lenient):
    id: Annotated[str, Field(min_length=1, max_length=256)]
    from_: Annotated[str, Field(alias="from", pattern=WA_ID.pattern)]
    timestamp: Annotated[str, Field(pattern=r"^\d{1,12}$")]
    type: Annotated[str, Field(max_length=32)]
    text: _Text | None = None


class _Metadata(_Lenient):
    phone_number_id: Annotated[str, Field(pattern=r"^\d{5,32}$")]


class _Value(_Lenient):
    messaging_product: Literal["whatsapp"]
    metadata: _Metadata
    messages: Annotated[list[_Message], Field(max_length=50)] = []


class _Change(_Lenient):
    field: str
    value: _Value | dict


class _Entry(_Lenient):
    changes: Annotated[list[_Change], Field(max_length=50)] = []


class WebhookPayload(_Lenient):
    object: Literal["whatsapp_business_account"]
    entry: Annotated[list[_Entry], Field(max_length=50)]


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def verify_subscription(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Handshake de Meta al registrar el webhook. Devuelve el challenge solo si todo coincide."""
    expected = get_settings().whatsapp_verify_token
    if mode != "subscribe" or not token or not expected or not challenge:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", challenge):
        return None
    return challenge if hmac.compare_digest(token.encode(), expected.encode()) else None


def _conversation_token(tenant_id: int, wa_id: str) -> str:
    """Identificador estable por cliente y negocio sin guardar el número: HMAC con el App Secret."""
    key = get_settings().whatsapp_app_secret.encode()
    return hmac.new(key, f"wa:{tenant_id}:{wa_id}".encode(), hashlib.sha256).hexdigest()


def send_text(phone_number_id: str, to: str, body: str) -> bool:
    settings = get_settings()
    # Ambos valores ya pasaron por patrones de solo dígitos: no pueden alterar la ruta ni el host
    if not channels.PHONE_NUMBER_ID.fullmatch(phone_number_id) or not WA_ID.fullmatch(to):
        return False
    url = f"{GRAPH_HOST}/{settings.whatsapp_graph_version}/{phone_number_id}/messages"
    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": body[:4096]}},
            timeout=10.0,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        security_event("whatsapp_send_error", "ERROR", error=type(exc).__name__)
        return False
    if response.status_code >= 400:
        security_event("whatsapp_send_error", "ERROR", status=response.status_code)
        return False
    return True


def extract_messages(payload: dict) -> list[tuple[str, _Message]]:
    """Devuelve [(phone_number_id, mensaje)] de un payload ya autenticado. Estructura inválida: lista vacía."""
    try:
        parsed = WebhookPayload.model_validate(payload)
    except ValidationError as exc:
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()][:10]
        security_event("whatsapp_payload_rejected", "WARNING", fields=fields)
        return []
    found = []
    for entry in parsed.entry:
        for change in entry.changes:
            if change.field != "messages" or not isinstance(change.value, _Value):
                continue  # estados de entrega, etc.: no requieren respuesta
            for message in change.value.messages:
                found.append((change.value.metadata.phone_number_id, message))
    return found


def handle_message(phone_number_id: str, message: _Message, now: int | None = None) -> str:
    """Procesa un mensaje entrante. Devuelve el resultado para el log y las pruebas."""
    settings = get_settings()
    now = int(time.time()) if now is None else now
    sender = hash_identifier(f"wa:{message.from_}")

    if now - int(message.timestamp) > settings.whatsapp_max_age_seconds:
        security_event("whatsapp_message_stale", "WARNING", client=sender)
        return "stale"
    if not channels.register_event("whatsapp", message.id):
        security_event("whatsapp_message_duplicate", client=sender)
        return "duplicate"
    tenant = channels.tenant_for_whatsapp(phone_number_id)
    if tenant is None:
        security_event("whatsapp_unknown_number", "WARNING")
        return "unknown_number"
    if message.type != "text" or message.text is None:
        send_text(phone_number_id, message.from_, NON_TEXT_REPLY)
        return "non_text"

    text = clean_text(message.text.body)[:MAX_TEXT]
    if not text:
        return "empty"
    result = agent.process_message(
        tenant,
        text,
        _conversation_token(tenant["id"], message.from_),
        f"wa:{message.from_}",
        channel="whatsapp",
        server_token=True,
    )
    sent = send_text(phone_number_id, message.from_, result["agent_response"])
    security_event("whatsapp_message_handled", tenant=tenant["slug"], status=result["status"], sent=sent, client=sender)
    return "replied" if sent else "send_failed"
