"""Calificación de coberturas - Operativa.ia (P2.9)

Dos dimensiones, configurables por negocio:
- Zona de servicio: prefijos de código postal (p. ej. "N2L") y/o ciudades.
- Aseguradoras o planes aceptados (solo el nombre: nunca número de póliza ni datos de salud).
Una dimensión sin reglas no aplica. El resultado es determinista: el LLM nunca decide si alguien califica.
Las consultas no se guardan.
"""

import re
import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from app.core.db import get_connection
from app.core.validation import CleanStr, StrictModel

MAX_AREAS = 200
MAX_INSURERS = 100
Result = Literal["covered", "not_covered", "missing", "not_applicable"]


def normalize_postal(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 &.-]", " ", plain)).strip()


def _postal_prefix(value: str) -> str:
    normalized = normalize_postal(value)
    if not 1 <= len(normalized) <= 10:
        raise ValueError("Prefijo postal inválido.")
    return value


def _named(value: str) -> str:
    if not normalize_name(value):
        raise ValueError("Nombre inválido.")
    return value


PostalPrefix = Annotated[CleanStr(min_length=1, max_length=12), AfterValidator(_postal_prefix)]
Name = Annotated[CleanStr(min_length=2, max_length=80), AfterValidator(_named)]


class CoverageRules(StrictModel):
    postal_prefixes: Annotated[list[PostalPrefix], Field(max_length=MAX_AREAS)] = []
    cities: Annotated[list[Name], Field(max_length=MAX_AREAS)] = []
    insurers: Annotated[list[Name], Field(max_length=MAX_INSURERS)] = []


class CoverageQuery(StrictModel):
    """Lo que puede preguntar un cliente (o Sofía en su nombre). Todos los campos son opcionales."""

    postal_code: CleanStr(min_length=3, max_length=12) | None = None
    city: CleanStr(min_length=2, max_length=80) | None = None
    insurer: CleanStr(min_length=2, max_length=80) | None = None


def _dedupe(items: list[str], key) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for item in items:
        seen.setdefault(key(item), item.strip())
    return list(seen.items())


def set_rules(tenant_id: int, rules: CoverageRules) -> None:
    """Reemplaza todas las reglas del negocio en una sola transacción."""
    with get_connection() as db:
        db.execute("DELETE FROM coverage_areas WHERE tenant_id = ?", (tenant_id,))
        db.execute("DELETE FROM coverage_insurers WHERE tenant_id = ?", (tenant_id,))
        for value, label in _dedupe(rules.postal_prefixes, normalize_postal):
            db.execute(
                "INSERT INTO coverage_areas (tenant_id, kind, value, label) VALUES (?, 'postal_prefix', ?, ?)",
                (tenant_id, value, label.upper()),
            )
        for value, label in _dedupe(rules.cities, normalize_name):
            db.execute(
                "INSERT INTO coverage_areas (tenant_id, kind, value, label) VALUES (?, 'city', ?, ?)",
                (tenant_id, value, label),
            )
        for value, label in _dedupe(rules.insurers, normalize_name):
            db.execute(
                "INSERT INTO coverage_insurers (tenant_id, value, label) VALUES (?, ?, ?)", (tenant_id, value, label)
            )


def get_rules(tenant_id: int) -> dict:
    with get_connection() as db:
        areas = db.execute(
            "SELECT kind, label FROM coverage_areas WHERE tenant_id = ? ORDER BY label", (tenant_id,)
        ).fetchall()
        insurers = db.execute(
            "SELECT label FROM coverage_insurers WHERE tenant_id = ? ORDER BY label", (tenant_id,)
        ).fetchall()
    return {
        "postal_prefixes": [a["label"] for a in areas if a["kind"] == "postal_prefix"],
        "cities": [a["label"] for a in areas if a["kind"] == "city"],
        "insurers": [i["label"] for i in insurers],
    }


def has_rules(tenant_id: int) -> bool:
    rules = get_rules(tenant_id)
    return any(rules.values())


def check(tenant_id: int, query: CoverageQuery) -> dict:
    with get_connection() as db:
        areas = db.execute("SELECT kind, value FROM coverage_areas WHERE tenant_id = ?", (tenant_id,)).fetchall()
        insurers = {r["value"] for r in db.execute("SELECT value FROM coverage_insurers WHERE tenant_id = ?", (tenant_id,))}
    prefixes = [a["value"] for a in areas if a["kind"] == "postal_prefix"]
    cities = {a["value"] for a in areas if a["kind"] == "city"}

    area: Result
    if not prefixes and not cities:
        area = "not_applicable"
    elif not query.postal_code and not query.city:
        area = "missing"
    else:
        postal = normalize_postal(query.postal_code or "")
        by_postal = bool(postal) and any(postal.startswith(p) for p in prefixes)
        by_city = bool(query.city) and normalize_name(query.city) in cities
        area = "covered" if by_postal or by_city else "not_covered"

    insurance: Result
    if not insurers:
        insurance = "not_applicable"
    elif not query.insurer:
        insurance = "missing"
    else:
        insurance = "covered" if normalize_name(query.insurer) in insurers else "not_covered"

    results = (area, insurance)
    qualifies = None if "missing" in results else "not_covered" not in results
    return {"area": area, "insurance": insurance, "qualifies": qualifies}


def describe(result: dict) -> str:
    """Texto fijo para el cliente según el resultado (el LLM puede reformularlo, no cambiarlo)."""
    if result["qualifies"] is True:
        return "Sí: el negocio atiende tu zona y acepta tu plan (según lo que indicaste)."
    if result["qualifies"] is False:
        reasons = []
        if result["area"] == "not_covered":
            reasons.append("tu zona no está dentro del área de servicio")
        if result["insurance"] == "not_covered":
            reasons.append("tu aseguradora o plan no está en la lista aceptada")
        return "Por ahora no: " + " y ".join(reasons) + ". El equipo puede confirmarlo contigo."
    missing = []
    if result["area"] == "missing":
        missing.append("tu código postal o ciudad")
    if result["insurance"] == "missing":
        missing.append("el nombre de tu aseguradora o plan")
    return "Para confirmarlo necesito " + " y ".join(missing) + "."
