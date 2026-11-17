"""Controles del LLM - Operativa.ia

El texto del usuario y la respuesta del modelo se tratan como no confiables.
Topes de tokens por cliente (IP seudonimizada), por negocio y globales.
"""

import re
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.db import get_connection

INJECTION_PATTERNS = re.compile(
    r"ignor\w*\s+(all\s+|the\s+|todas?\s+|las?\s+|tus\s+)*(previous|prior|above|instrucciones|instructions|anteriores)"
    r"|system\s+prompt|prompt\s+del\s+sistema|tus\s+instrucciones"
    r"|reveal\s+your|revela\s+tu|jailbreak|developer\s+mode|modo\s+desarrollador"
    r"|you\s+are\s+now|ahora\s+eres|\bact[uú]a\s+como|\bact\s+as\b",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"[$€£]\s?\d|\d[\d.,]*\s?(usd|mxn|eur|cad|pesos?|d[oó]lar(es)?|euros?)\b", re.IGNORECASE
)
SECRET_PATTERN = re.compile(r"gsk_[A-Za-z0-9]{8,}|AIza[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{8,}|AQ\.[A-Za-z0-9_-]{8,}")

PRICE_REPLY = "No puedo confirmar precios por este medio. El equipo del negocio te dará el costo exacto."
BLOCKED_REPLY = "Lo siento, no puedo ayudarte con eso. ¿Te gustaría solicitar una cita?"


def looks_like_injection(text: str) -> bool:
    return bool(INJECTION_PATTERNS.search(text))


def filter_reply(reply, protected_text: str) -> tuple[str, str | None]:
    """Valida la salida del modelo. Devuelve (texto, motivo del bloqueo o None).

    `protected_text` son las reglas internas del prompt: copiarlas en la respuesta es una filtración.
    Los datos públicos del negocio (servicios, horario) no se protegen: la asistente debe poder citarlos.
    """
    if not isinstance(reply, str) or not reply.strip():
        return BLOCKED_REPLY, "empty_reply"
    if SECRET_PATTERN.search(reply):
        return BLOCKED_REPLY, "secret_pattern"
    for line in protected_text.splitlines():
        line = line.strip()
        if len(line) >= 40 and line.lower() in reply.lower():
            return BLOCKED_REPLY, "system_prompt_leak"
    if PRICE_PATTERN.search(reply):
        return PRICE_REPLY, "invented_price"
    return reply, None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def budget_available(tenant_id: int, client_hash: str) -> bool:
    settings = get_settings()
    with get_connection() as db:
        db.execute("DELETE FROM llm_usage WHERE day < ?", (_today(),))
        row = db.execute(
            "SELECT COALESCE(SUM(tokens), 0) AS total, "
            "COALESCE(SUM(CASE WHEN tenant_id = ? THEN tokens END), 0) AS tenant, "
            # El tope por cliente cuenta todos los negocios: cambiar de slug no da más tokens
            "COALESCE(SUM(CASE WHEN client_hash = ? THEN tokens END), 0) AS own "
            "FROM llm_usage WHERE day = ?",
            (tenant_id, client_hash, _today()),
        ).fetchone()
    return (
        row["own"] < settings.llm_daily_tokens_per_ip
        and row["tenant"] < settings.llm_daily_tokens_per_tenant
        and row["total"] < settings.llm_daily_tokens_global
    )


def record_usage(tenant_id: int, client_hash: str, tokens: int) -> None:
    with get_connection() as db:
        db.execute(
            "INSERT INTO llm_usage (day, tenant_id, client_hash, tokens) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (day, tenant_id, client_hash) DO UPDATE SET tokens = tokens + excluded.tokens",
            (_today(), tenant_id, client_hash, tokens),
        )
