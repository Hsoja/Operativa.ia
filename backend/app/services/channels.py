"""Canales externos por negocio e idempotencia de webhooks - Operativa.ia"""

import re
import sqlite3
import time

from app.core.db import get_connection

PHONE_NUMBER_ID = re.compile(r"^\d{5,32}$")


def link_whatsapp(tenant_id: int, phone_number_id: str) -> None:
    """Asocia un número de WhatsApp Business (su phone_number_id de Meta) a un negocio."""
    if not PHONE_NUMBER_ID.fullmatch(phone_number_id):
        raise ValueError("phone_number_id inválido: solo dígitos.")
    with get_connection() as db:
        db.execute(
            "INSERT INTO tenant_channels (tenant_id, channel, external_id, created_at) VALUES (?, 'whatsapp', ?, ?)",
            (tenant_id, phone_number_id, int(time.time())),
        )


def unlink_whatsapp(phone_number_id: str) -> bool:
    with get_connection() as db:
        return (
            db.execute(
                "DELETE FROM tenant_channels WHERE channel = 'whatsapp' AND external_id = ?", (phone_number_id,)
            ).rowcount
            == 1
        )


def tenant_for_whatsapp(phone_number_id: str) -> dict | None:
    """Negocio activo dueño del número. Un número desconocido o de un negocio inactivo no se atiende."""
    if not isinstance(phone_number_id, str) or not PHONE_NUMBER_ID.fullmatch(phone_number_id):
        return None
    with get_connection() as db:
        row = db.execute(
            "SELECT t.* FROM tenant_channels c JOIN tenants t ON t.id = c.tenant_id "
            "WHERE c.channel = 'whatsapp' AND c.external_id = ? AND t.active = 1",
            (phone_number_id,),
        ).fetchone()
    return dict(row) if row else None


def register_event(provider: str, event_id: str) -> bool:
    """Idempotencia: True la primera vez que llega un evento; False si es repetido."""
    try:
        with get_connection() as db:
            db.execute(
                "INSERT INTO webhook_events (provider, event_id, received_at) VALUES (?, ?, ?)",
                (provider, event_id, int(time.time())),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def purge_events(older_than_days: int = 30, now: int | None = None) -> int:
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        return db.execute("DELETE FROM webhook_events WHERE received_at < ?", (now - older_than_days * 86400,)).rowcount
