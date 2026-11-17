"""Plantillas por vertical - Operativa.ia (P2.12)

Una plantilla deja un negocio listo para operar en minutos: perfil, servicios con depósito, horario,
reglas de cobertura y un texto de reactivación. Son archivos JSON versionados en `app/templates/`:
solo datos (nunca código), validados con los mismos modelos estrictos que usa la API.

Aplicar una plantilla nunca pisa lo que el negocio ya configuró: solo completa lo que está vacío.
Los depósitos y las aseguradoras son valores de ejemplo que el negocio debe revisar.
"""

import json
import re
from pathlib import Path
from typing import Annotated

from pydantic import Field

from app.core.db import get_connection
from app.core.validation import CleanStr, StrictModel
from app.services import booking, coverage, tenants

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
KEY_PATTERN = re.compile(r"^[a-z]{3,20}$")
MAX_FILE_BYTES = 64 * 1024


class TemplateProfile(StrictModel):
    business_type: CleanStr(min_length=2, max_length=80)
    services: CleanStr(min_length=2, max_length=1500)
    hours: CleanStr(min_length=2, max_length=300)


class TemplateCampaign(StrictModel):
    subject: CleanStr(min_length=3, max_length=120)
    body: CleanStr(min_length=20, max_length=2000)


class Template(StrictModel):
    key: Annotated[str, Field(pattern=KEY_PATTERN.pattern)]
    version: Annotated[int, Field(ge=1)]
    label: CleanStr(min_length=2, max_length=80)
    profile: TemplateProfile
    services: Annotated[list[booking.ServiceIn], Field(min_length=1, max_length=30)]
    hours: Annotated[list[booking.HoursRange], Field(min_length=1, max_length=28)]
    coverage: coverage.CoverageRules
    campaign: TemplateCampaign


class TemplateError(ValueError):
    """Plantilla inexistente o con un formato inválido."""


def available(directory: Path = TEMPLATES_DIR) -> list[str]:
    return sorted(p.stem for p in directory.glob("*.json") if KEY_PATTERN.fullmatch(p.stem))


def load(key: str, directory: Path = TEMPLATES_DIR) -> Template:
    """Carga y valida una plantilla. La clave se valida antes de tocar el disco (sin rutas arbitrarias)."""
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) or key not in available(directory):
        raise TemplateError("Plantilla desconocida.")
    path = directory / f"{key}.json"
    if path.stat().st_size > MAX_FILE_BYTES:
        raise TemplateError("Plantilla demasiado grande.")
    try:
        template = Template.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError as exc:  # incluye ValidationError y JSON inválido
        raise TemplateError(f"Plantilla inválida: {key}.") from exc
    if template.key != key:
        raise TemplateError("La clave de la plantilla no coincide con el archivo.")
    try:
        booking.WeeklyHours(ranges=template.hours)  # mismas reglas de solape que el panel
    except ValueError as exc:
        raise TemplateError(f"Horario inválido en la plantilla: {key}.") from exc
    return template


def apply(tenant_id: int, key: str) -> dict:
    """Completa lo que el negocio tiene vacío. Devuelve qué se aplicó."""
    template = load(key)
    tenant = tenants.get(tenant_id)
    if tenant is None:
        raise TemplateError("Negocio inexistente.")
    applied = {"profile": [], "services": [], "hours": False, "coverage": False}

    profile = tenants.TenantProfile(
        name=tenant["name"],
        business_type=tenant["business_type"] or template.profile.business_type,
        services=tenant["services"] or template.profile.services,
        hours=tenant["hours"] or template.profile.hours,
        location=tenant["location"],
        timezone=tenant["timezone"],
    )
    applied["profile"] = [f for f in ("business_type", "services", "hours") if not tenant[f]]
    tenants.update_profile(tenant_id, profile)

    existing = {coverage.normalize_name(s["name"]) for s in booking.list_services(tenant_id, only_active=False)}
    for service in template.services:
        if coverage.normalize_name(service.name) not in existing:
            booking.create_service(tenant_id, service)
            applied["services"].append(service.name)

    if not booking.get_hours(tenant_id):
        booking.set_hours(tenant_id, booking.WeeklyHours(ranges=template.hours))
        applied["hours"] = True

    if not coverage.has_rules(tenant_id) and any(template.coverage.model_dump().values()):
        coverage.set_rules(tenant_id, template.coverage)
        applied["coverage"] = True

    with get_connection() as db:
        db.execute("UPDATE tenants SET template = ? WHERE id = ?", (key, tenant_id))
    return applied


def campaign_suggestion(tenant: dict) -> TemplateCampaign | None:
    try:
        return load(tenant.get("template", "")).campaign
    except TemplateError:
        return None
