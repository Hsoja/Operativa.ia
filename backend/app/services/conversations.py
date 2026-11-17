"""Conversaciones del chat - Operativa.ia

El historial vive en el servidor: el navegador solo guarda un identificador aleatorio y el
servidor guarda su hash. Así el cliente no puede inventar turnos de la asistente.
"""

import secrets
import time

from app.core.db import get_connection
from app.services.auth import hash_token

HISTORY_MESSAGES = 10


def open_conversation(
    tenant_id: int, token: str | None, channel: str = "web", server_token: bool = False
) -> tuple[int, str]:
    """Devuelve (id, token). Un token desconocido o de otro negocio abre una conversación nueva.

    `server_token=True` solo para identificadores que calcula el servidor (WhatsApp: HMAC del número):
    entonces la conversación nueva se crea con ese mismo token. Un token enviado por un navegador
    nunca se adopta: se reemplaza por uno aleatorio.
    """
    now = int(time.time())
    with get_connection() as db:
        if token:
            row = db.execute(
                "SELECT id FROM conversations WHERE token_hash = ? AND tenant_id = ?", (hash_token(token), tenant_id)
            ).fetchone()
            if row:
                db.execute("UPDATE conversations SET last_at = ? WHERE id = ?", (now, row["id"]))
                return int(row["id"]), token
        if not (server_token and token):
            token = secrets.token_urlsafe(24)
        cursor = db.execute(
            "INSERT INTO conversations (tenant_id, token_hash, channel, created_at, last_at) VALUES (?, ?, ?, ?, ?)",
            (tenant_id, hash_token(token), channel, now, now),
        )
        return int(cursor.lastrowid), token


def count_messages(tenant_id: int, conversation_id: int) -> int:
    with get_connection() as db:
        return db.execute(
            "SELECT COUNT(*) FROM messages WHERE tenant_id = ? AND conversation_id = ?", (tenant_id, conversation_id)
        ).fetchone()[0]


def recent_history(tenant_id: int, conversation_id: int, limit: int = HISTORY_MESSAGES) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT role, content FROM messages WHERE tenant_id = ? AND conversation_id = ? ORDER BY id DESC LIMIT ?",
            (tenant_id, conversation_id, limit),
        ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def add_message(tenant_id: int, conversation_id: int, role: str, content: str) -> None:
    with get_connection() as db:
        db.execute(
            "INSERT INTO messages (tenant_id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (tenant_id, conversation_id, role, content, int(time.time())),
        )


def list_conversations(tenant_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT c.id, c.channel, c.created_at, c.last_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id AND m.tenant_id = c.tenant_id) AS messages "
            "FROM conversations c WHERE c.tenant_id = ? ORDER BY c.last_at DESC, c.id DESC LIMIT ? OFFSET ?",
            (tenant_id, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages(tenant_id: int, conversation_id: int) -> list[dict] | None:
    """None si la conversación no existe o es de otro negocio (misma respuesta en ambos casos)."""
    with get_connection() as db:
        exists = db.execute(
            "SELECT 1 FROM conversations WHERE id = ? AND tenant_id = ?", (conversation_id, tenant_id)
        ).fetchone()
        if not exists:
            return None
        rows = db.execute(
            "SELECT role, content, created_at FROM messages WHERE tenant_id = ? AND conversation_id = ? ORDER BY id",
            (tenant_id, conversation_id),
        ).fetchall()
    return [dict(r) for r in rows]


def purge_older_than(days: int, now: int | None = None) -> int:
    """Retención: borra conversaciones (y sus mensajes) sin actividad en `days` días."""
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        return db.execute("DELETE FROM conversations WHERE last_at < ?", (now - days * 86400,)).rowcount
