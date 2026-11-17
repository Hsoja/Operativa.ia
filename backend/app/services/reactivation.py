"""Reactivación de clientes por correo, con CASL - Operativa.ia (P2.11)

Reglas (Ley canadiense antispam, CASL):
- Solo consentimiento EXPLÍCITO: una casilla desmarcada por defecto, guardada con fecha y origen.
  Una casilla sin marcar nunca revoca ni concede nada.
- Cada mensaje identifica al negocio (nombre y dirección física) e incluye una baja de un clic.
- La baja se aplica al instante y para siempre, salvo que la persona vuelva a marcar la casilla.
- Frecuencia: una campaña por negocio cada 24 h y como máximo un correo por contacto cada 30 días.
"""

import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.core.config import get_settings
from app.core.db import get_connection
from app.core.logs import security_event
from app.core.validation import CleanStr, StrictModel
from app.services.auth import hash_token

DAY = 86400
CAMPAIGN_COOLDOWN = DAY
CONTACT_COOLDOWN = 30 * DAY
TOKEN_PATTERN = r"^[A-Za-z0-9_-]{30,64}$"


class CampaignBlocked(RuntimeError):
    """La campaña no se puede enviar (motivo legible para el panel)."""


def _single_line(value: str) -> str:
    if "\r" in value or "\n" in value:
        raise ValueError("El asunto debe ser una sola línea.")
    return value


class CampaignIn(StrictModel):
    inactive_days: Annotated[int, Field(ge=30, le=730)]
    subject: Annotated[CleanStr(min_length=3, max_length=120), AfterValidator(_single_line)]
    body: CleanStr(min_length=20, max_length=2000)
    confirm: Literal[True]


class PreviewIn(StrictModel):
    inactive_days: Annotated[int, Field(ge=30, le=730)]


# --- Contactos y consentimiento --------------------------------------------------------------------

def record_contact(tenant_id: int, email: str, name: str, marketing_consent: bool, source: str, now: int | None = None) -> None:
    """Registra actividad del contacto. Solo una casilla MARCADA cambia el consentimiento (y anula una baja previa)."""
    now = int(time.time()) if now is None else now
    email = email.strip().lower()
    with get_connection() as db:
        db.execute(
            "INSERT INTO contacts (tenant_id, email, name, last_activity_at, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (tenant_id, email) DO UPDATE SET name = excluded.name, last_activity_at = excluded.last_activity_at",
            (tenant_id, email, name, now, now),
        )
        if marketing_consent:
            db.execute(
                "UPDATE contacts SET marketing_consent = 1, consent_at = ?, consent_source = ?, unsubscribed_at = NULL "
                "WHERE tenant_id = ? AND email = ?",
                (now, source, tenant_id, email),
            )


def contact_stats(tenant_id: int) -> dict:
    with get_connection() as db:
        row = db.execute(
            "SELECT COUNT(*) AS total, "
            "COALESCE(SUM(CASE WHEN marketing_consent = 1 AND unsubscribed_at IS NULL THEN 1 ELSE 0 END), 0) AS opted_in, "
            "COALESCE(SUM(CASE WHEN unsubscribed_at IS NOT NULL THEN 1 ELSE 0 END), 0) AS unsubscribed "
            "FROM contacts WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
    return dict(row)


def _eligible(db, tenant_id: int, inactive_days: int, now: int, limit: int):
    return db.execute(
        "SELECT c.id, c.email, c.name FROM contacts c WHERE c.tenant_id = ? AND c.marketing_consent = 1 "
        "AND c.unsubscribed_at IS NULL AND c.last_activity_at <= ? "
        "AND NOT EXISTS (SELECT 1 FROM campaign_sends s WHERE s.contact_id = c.id AND s.tenant_id = c.tenant_id "
        "AND s.status = 'sent' AND s.sent_at > ?) ORDER BY c.id LIMIT ?",
        (tenant_id, now - inactive_days * DAY, now - CONTACT_COOLDOWN, limit),
    ).fetchall()


def preview(tenant_id: int, inactive_days: int, now: int | None = None) -> int:
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        return len(_eligible(db, tenant_id, inactive_days, now, get_settings().campaign_max_recipients))


# --- Campañas -----------------------------------------------------------------------------------------

def list_campaigns(tenant_id: int) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT id, inactive_days, subject, recipients, sent, failed, created_at FROM campaigns "
            "WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 50",
            (tenant_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_campaign(tenant: dict, campaign: CampaignIn, now: int | None = None) -> tuple[int, list[tuple[int, str, str, str]]]:
    """Valida las reglas CASL y de frecuencia y prepara los envíos. Devuelve (id, [(send_id, email, nombre, token)])."""
    settings = get_settings()
    now = int(time.time()) if now is None else now
    if not settings.smtp_enabled:
        raise CampaignBlocked("El envío de correo no está configurado.")
    if not tenant.get("location", "").strip():
        raise CampaignBlocked("Agrega la dirección física del negocio en el perfil: CASL la exige en cada mensaje.")
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        recent = db.execute(
            "SELECT 1 FROM campaigns WHERE tenant_id = ? AND created_at > ?", (tenant["id"], now - CAMPAIGN_COOLDOWN)
        ).fetchone()
        if recent:
            raise CampaignBlocked("Ya se envió una campaña en las últimas 24 horas.")
        recipients = _eligible(db, tenant["id"], campaign.inactive_days, now, settings.campaign_max_recipients)
        if not recipients:
            raise CampaignBlocked("No hay contactos con consentimiento que cumplan el filtro.")
        campaign_id = int(
            db.execute(
                "INSERT INTO campaigns (tenant_id, inactive_days, subject, recipients, created_at) VALUES (?, ?, ?, ?, ?)",
                (tenant["id"], campaign.inactive_days, campaign.subject, len(recipients), now),
            ).lastrowid
        )
        sends = []
        for contact in recipients:
            token = secrets.token_urlsafe(32)
            send_id = db.execute(
                "INSERT INTO campaign_sends (tenant_id, campaign_id, contact_id, unsubscribe_hash, status) "
                "VALUES (?, ?, ?, ?, 'pending')",
                (tenant["id"], campaign_id, contact["id"], hash_token(token)),
            ).lastrowid
            sends.append((int(send_id), contact["email"], contact["name"], token))
    return campaign_id, sends


def unsubscribe_url(tenant: dict, token: str) -> str:
    return f"{get_settings().public_site_url}/#/unsubscribe/{tenant['slug']}/{token}"


def one_click_url(tenant: dict, token: str) -> str:
    """RFC 8058: el cliente de correo hace POST aquí al pulsar "Cancelar suscripción"."""
    return f"{get_settings().public_site_url}/api/v1/public/{tenant['slug']}/unsubscribe/{token}"


def build_message(tenant: dict, campaign: CampaignIn, email: str, name: str, token: str) -> EmailMessage:
    settings = get_settings()
    body = campaign.body.replace("{nombre}", name)
    footer = (
        "\n\n--\n"
        f"{tenant['name']}\n{tenant['location']}\n"
        f"Recibes este correo porque aceptaste recibir recordatorios y ofertas de {tenant['name']}.\n"
        f"Darte de baja (un clic): {unsubscribe_url(tenant, token)}"
    )
    message = EmailMessage()
    message["Subject"] = campaign.subject
    message["From"] = formataddr((tenant["name"], settings.smtp_from))
    message["To"] = email
    message["Message-ID"] = make_msgid()
    message["List-Unsubscribe"] = f"<{one_click_url(tenant, token)}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(body + footer)
    return message


def _smtp_connection():
    settings = get_settings()
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        # Nunca se envía en claro: si el servidor no ofrece STARTTLS, smtplib lanza una excepción
        server.starttls(context=context)
    if settings.smtp_username:
        server.login(settings.smtp_username, settings.smtp_password)
    return server


def deliver(tenant: dict, campaign_id: int, campaign: CampaignIn, sends: list[tuple[int, str, str, str]]) -> dict:
    """Envía los correos preparados. Una baja que llegue a mitad de envío se respeta."""
    sent = failed = 0
    try:
        server = _smtp_connection()
    except (OSError, smtplib.SMTPException) as exc:
        security_event("smtp_error", "ERROR", error=type(exc).__name__)
        server = None
    for send_id, email, name, token in sends:
        with get_connection() as db:
            still_ok = db.execute(
                "SELECT 1 FROM campaign_sends s JOIN contacts c ON c.id = s.contact_id "
                "WHERE s.id = ? AND c.unsubscribed_at IS NULL AND c.marketing_consent = 1",
                (send_id,),
            ).fetchone()
        ok = False
        if server is not None and still_ok:
            try:
                server.send_message(build_message(tenant, campaign, email, name, token))
                ok = True
            except (OSError, smtplib.SMTPException) as exc:
                security_event("smtp_error", "ERROR", error=type(exc).__name__)
        sent, failed = sent + ok, failed + (not ok)
        with get_connection() as db:
            db.execute(
                "UPDATE campaign_sends SET status = ?, sent_at = ? WHERE id = ?",
                ("sent" if ok else "failed", int(time.time()), send_id),
            )
    if server is not None:
        try:
            server.quit()
        except (OSError, smtplib.SMTPException):
            pass
    with get_connection() as db:
        db.execute("UPDATE campaigns SET sent = ?, failed = ? WHERE id = ?", (sent, failed, campaign_id))
    security_event("campaign_delivered", tenant=tenant["slug"], campaign=campaign_id, sent=sent, failed=failed)
    return {"sent": sent, "failed": failed}


def unsubscribe(tenant_id: int, token: str, now: int | None = None) -> bool:
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        row = db.execute(
            "SELECT contact_id FROM campaign_sends WHERE unsubscribe_hash = ? AND tenant_id = ?", (hash_token(token), tenant_id)
        ).fetchone()
        if row is None:
            return False
        db.execute(
            "UPDATE contacts SET unsubscribed_at = COALESCE(unsubscribed_at, ?), marketing_consent = 0 "
            "WHERE id = ? AND tenant_id = ?",
            (now, row["contact_id"], tenant_id),
        )
    return True
