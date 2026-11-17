"""Solicitudes de contacto (leads) - Operativa.ia

Datos personales: nombre, correo y mensaje. Solo se guardan con consentimiento explícito,
nunca se escriben en el log y cada consulta filtra por tenant_id.
"""

import re
import time
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.core.db import get_connection
from app.core.validation import CleanStr, StrictModel

TOPICS = ("Book a demo", "Services question", "Partnership", "Something else")
EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")


def _valid_email(value: str) -> str:
    if not EMAIL.fullmatch(value):
        raise ValueError("Correo inválido.")
    return value.lower()


def _must_consent(value: bool) -> bool:
    if value is not True:
        raise ValueError("Se requiere consentimiento.")
    return value


class LeadIn(StrictModel):
    name: CleanStr(min_length=2, max_length=80)
    email: Annotated[CleanStr(min_length=6, max_length=254), AfterValidator(_valid_email)]
    business: CleanStr(min_length=0, max_length=120) = ""
    topic: Literal[TOPICS]
    message: CleanStr(min_length=10, max_length=2000)
    source: Literal["contact-form", "sofia"] = "contact-form"
    consent: Annotated[bool, AfterValidator(_must_consent)]
    # CASL: casilla aparte y desmarcada por defecto para recordatorios y ofertas
    marketing_consent: bool = False
    # Trampa para bots: un campo oculto que una persona nunca rellena
    website: Annotated[str, Field(max_length=0)] = ""


def create_lead(tenant_id: int, lead: LeadIn) -> int:
    now = int(time.time())
    with get_connection() as db:
        cursor = db.execute(
            "INSERT INTO leads (tenant_id, name, email, business, topic, message, source, consent_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tenant_id, lead.name, lead.email, lead.business, lead.topic, lead.message, lead.source, now, now),
        )
        return int(cursor.lastrowid)


def list_leads(tenant_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT id, name, email, business, topic, message, source, consent_at, created_at FROM leads "
            "WHERE tenant_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (tenant_id, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_lead(tenant_id: int, lead_id: int) -> bool:
    """Derecho de eliminación (PIPEDA): borra un lead solo dentro de su propio negocio."""
    with get_connection() as db:
        return db.execute("DELETE FROM leads WHERE id = ? AND tenant_id = ?", (lead_id, tenant_id)).rowcount == 1
