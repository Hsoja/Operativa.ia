"""Registro de seguridad - Operativa.ia

Eventos en JSON con ID de petición, rotación de archivos y una alerta por umbral.
Nunca se registran mensajes, credenciales ni direcciones IP en claro.
"""

import hashlib
import json
import logging
import secrets
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger("operativa.security")
logger.propagate = False

# Campos que jamás deben llegar al log aunque alguien los pase por error
FORBIDDEN_FIELDS = {"password", "token", "secret", "api_key", "message", "email", "phone", "ip", "cookie"}
ALERT_WINDOW_SECONDS = 300
ALERTED_EVENTS = {
    "login_failed",
    "rate_limit_hit",
    "validation_rejected",
    "prompt_injection_suspected",
    "tool_args_rejected",
    "csrf_rejected",
}

_process_salt = secrets.token_hex(16)
_recent: dict[str, deque] = defaultdict(deque)


def hash_identifier(value: str) -> str:
    """Seudonimiza una IP o un usuario para poder correlacionar sin guardar el dato."""
    salt = get_settings().ip_hash_salt or _process_salt
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]


def configure_logging() -> None:
    settings = get_settings()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.log_dir / "security.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    _recent.clear()


def _maybe_alert(event: str, now: float) -> None:
    if event not in ALERTED_EVENTS:
        return
    window = _recent[event]
    window.append(now)
    while window and now - window[0] > ALERT_WINDOW_SECONDS:
        window.popleft()
    if len(window) == get_settings().alert_threshold:
        _emit("security_alert", "WARNING", {"trigger": event, "count": len(window)}, now)


def _emit(event: str, level: str, fields: dict, now: float) -> None:
    record = {
        "ts": round(now, 3),
        "level": level,
        "event": event,
        "request_id": request_id_var.get(),
    }
    record.update({k: v for k, v in fields.items() if k not in FORBIDDEN_FIELDS})
    logger.log(getattr(logging, level), json.dumps(record, ensure_ascii=False, default=str))


def security_event(event: str, level: str = "INFO", **fields) -> None:
    now = time.time()
    _emit(event, level, fields, now)
    _maybe_alert(event, now)
