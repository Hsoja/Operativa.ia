"""Negocios (tenants) - Operativa.ia

Cada PYME es un tenant. Su `id` nunca viene del cliente: en las rutas privadas sale de la sesión
y en las públicas del `slug` de la URL, que se resuelve aquí solo si el negocio está activo.
"""

import re
import time
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator

from app.core.db import get_connection
from app.core.validation import CleanStr, StrictModel

SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
PROFILE_FIELDS = ("name", "business_type", "services", "hours", "location", "timezone", "notify_email")
# Mismo patrón que leads.EMAIL; se duplica aquí para no crear una dependencia entre módulos.
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
# Delimitadores del bloque de datos del negocio dentro del prompt: no pueden venir en los datos
_DELIMITERS = re.compile(r"<<<|>>>")


def _valid_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Zona horaria desconocida.") from None
    return value


def _no_delimiters(value: str) -> str:
    return _DELIMITERS.sub("", value).strip()


def _valid_notify_email(value: str) -> str:
    """Vacío = sin aviso por correo (apagado). Si se da un valor, debe parecer un correo real."""
    if value and not _EMAIL.fullmatch(value):
        raise ValueError("Correo de aviso inválido.")
    return value.lower()


Timezone = Annotated[CleanStr(min_length=3, max_length=64), AfterValidator(_valid_timezone)]
NotifyEmail = Annotated[CleanStr(min_length=0, max_length=254), AfterValidator(_valid_notify_email)]


def ProfileText(max_length: int, min_length: int = 0):
    return Annotated[CleanStr(min_length=min_length, max_length=max_length), AfterValidator(_no_delimiters)]


class TenantProfile(StrictModel):
    """Datos que el negocio edita y que alimentan el prompt de Sofía."""

    name: ProfileText(120, min_length=2)
    business_type: ProfileText(80) = ""
    services: ProfileText(1500) = ""
    hours: ProfileText(300) = ""
    location: ProfileText(200) = ""
    timezone: Timezone = "America/Toronto"
    # Dónde avisar de un lead nuevo (/contact). Vacío = apagado; nunca se expone por la ruta pública.
    notify_email: NotifyEmail = ""


def is_valid_slug(slug: str) -> bool:
    return isinstance(slug, str) and bool(SLUG_PATTERN.fullmatch(slug))


def create_tenant(slug: str, profile: TenantProfile, template: str = "general") -> int:
    if not is_valid_slug(slug):
        raise ValueError("Slug inválido: 3 a 40 letras minúsculas, números o guiones.")
    with get_connection() as db:
        cursor = db.execute(
            "INSERT INTO tenants (slug, name, business_type, services, hours, location, timezone, "
            "notify_email, template, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                slug,
                profile.name,
                profile.business_type,
                profile.services,
                profile.hours,
                profile.location,
                profile.timezone,
                profile.notify_email,
                template,
                int(time.time()),
            ),
        )
        return int(cursor.lastrowid)


def _row_to_dict(row) -> dict | None:
    return dict(row) if row else None


def get_active_by_slug(slug: str) -> dict | None:
    if not is_valid_slug(slug):
        return None
    with get_connection() as db:
        row = db.execute("SELECT * FROM tenants WHERE slug = ? AND active = 1", (slug,)).fetchone()
    return _row_to_dict(row)


def get_by_slug(slug: str) -> dict | None:
    if not is_valid_slug(slug):
        return None
    with get_connection() as db:
        return _row_to_dict(db.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone())


def get(tenant_id: int) -> dict | None:
    with get_connection() as db:
        return _row_to_dict(db.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone())


def public_profile(tenant: dict) -> dict:
    return {"slug": tenant["slug"], **{field: tenant[field] for field in PROFILE_FIELDS}}


def update_profile(tenant_id: int, profile: TenantProfile) -> None:
    with get_connection() as db:
        db.execute(
            "UPDATE tenants SET name = ?, business_type = ?, services = ?, hours = ?, location = ?, "
            "timezone = ?, notify_email = ? WHERE id = ?",
            (
                profile.name,
                profile.business_type,
                profile.services,
                profile.hours,
                profile.location,
                profile.timezone,
                profile.notify_email,
                tenant_id,
            ),
        )


def set_active(slug: str, active: bool) -> bool:
    """Desactivar un negocio corta su chat público y las sesiones de su equipo al instante."""
    with get_connection() as db:
        cursor = db.execute("UPDATE tenants SET active = ? WHERE slug = ?", (1 if active else 0, slug))
        return cursor.rowcount == 1
