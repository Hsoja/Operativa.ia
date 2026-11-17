"""Depósitos con Stripe Checkout - Operativa.ia (P2.10)

- Checkout alojado por Stripe: la tarjeta nunca pasa por este servidor.
- El monto y la moneda salen del servicio guardado en la base, nunca de la petición del cliente.
- Las URLs de retorno se construyen con PUBLIC_SITE_URL (configuración), no con datos del cliente.
- El webhook se verifica con Stripe-Signature (HMAC-SHA256 de "t.cuerpo") y una tolerancia de 5 minutos.
"""

import hashlib
import hmac
import time
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings
from app.core.logs import security_event
from app.core.validation import is_safe_https_url

STRIPE_API = "https://api.stripe.com/v1/checkout/sessions"
SIGNATURE_TOLERANCE_SECONDS = 300
CHECKOUT_MINUTES = 31  # Stripe exige entre 30 min y 24 h; el bloqueo del hueco dura un poco más


class PaymentError(RuntimeError):
    """No se pudo crear el cobro (el detalle va al log, no al cliente)."""


def _return_url(slug: str, ref: str, status: str) -> str:
    return f"{get_settings().public_site_url}/#/book/{slug}?status={status}&ref={ref}"


def _is_stripe_checkout_url(url) -> bool:
    if not is_safe_https_url(url):
        return False
    host = urlsplit(url).hostname or ""
    return host == "checkout.stripe.com" or host.endswith(".stripe.com")


def create_checkout(tenant: dict, appointment: dict, customer_email: str) -> tuple[str, str]:
    """Crea la sesión de Checkout y devuelve (session_id, url)."""
    settings = get_settings()
    service = appointment["service"]
    form = {
        "mode": "payment",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": service["currency"],
        "line_items[0][price_data][unit_amount]": str(service["deposit_cents"]),
        "line_items[0][price_data][product_data][name]": f"Depósito: {service['name']} - {tenant['name']}"[:250],
        "customer_email": customer_email,
        "client_reference_id": str(appointment["id"]),
        "metadata[appointment_id]": str(appointment["id"]),
        "metadata[tenant_id]": str(tenant["id"]),
        "expires_at": str(int(time.time()) + CHECKOUT_MINUTES * 60),
        "success_url": _return_url(tenant["slug"], appointment["ref"], "success"),
        "cancel_url": _return_url(tenant["slug"], appointment["ref"], "cancelled"),
    }
    try:
        response = httpx.post(
            STRIPE_API,
            data=form,
            auth=(settings.stripe_secret_key, ""),
            headers={"Idempotency-Key": f"appointment-{tenant['id']}-{appointment['id']}"},
            timeout=15.0,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        security_event("stripe_error", "ERROR", error=type(exc).__name__)
        raise PaymentError("network") from None
    if response.status_code >= 400:
        security_event("stripe_error", "ERROR", status=response.status_code)
        raise PaymentError("status")
    body = response.json()
    session_id, url = body.get("id"), body.get("url")
    if not isinstance(session_id, str) or not session_id.startswith("cs_") or not _is_stripe_checkout_url(url):
        security_event("stripe_error", "ERROR", reason="unexpected_response")
        raise PaymentError("response")
    return session_id, url


def verify_signature(raw_body: bytes, header: str | None, now: int | None = None) -> bool:
    secret = get_settings().stripe_webhook_secret
    if not secret or not header or len(header) > 2000:
        return False
    timestamp, signatures = None, []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t" and value.isdigit():
            timestamp = int(value)
        elif key == "v1":
            signatures.append(value)
    now = int(time.time()) if now is None else now
    if timestamp is None or not signatures or abs(now - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in signatures)


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Metadata(_Lenient):
    appointment_id: Annotated[str, Field(pattern=r"^\d{1,12}$")]
    tenant_id: Annotated[str, Field(pattern=r"^\d{1,12}$")]


class _Session(_Lenient):
    id: Annotated[str, Field(pattern=r"^cs_[A-Za-z0-9_]{1,250}$")]
    payment_status: str | None = None
    amount_total: int | None = None
    currency: Annotated[str, Field(max_length=3)] | None = None
    metadata: _Metadata


class _Data(_Lenient):
    object: _Session


class StripeEvent(_Lenient):
    id: Annotated[str, Field(pattern=r"^evt_[A-Za-z0-9_]{1,250}$")]
    type: Annotated[str, Field(max_length=100)]
    data: _Data | dict


def parse_event(payload: dict) -> StripeEvent | None:
    try:
        return StripeEvent.model_validate(payload)
    except ValidationError:
        security_event("stripe_payload_rejected", "WARNING")
        return None
