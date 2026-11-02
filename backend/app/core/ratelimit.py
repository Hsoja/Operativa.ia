"""Límite de peticiones - Operativa.ia

La IP real solo se toma de X-Forwarded-For si la conexión viene de un proxy configurado.
Con RATE_LIMIT_STORAGE=redis://... el contador se comparte entre procesos.
"""

import hashlib
import ipaddress

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.logs import hash_identifier, security_event


def _is_trusted(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in get_settings().trusted_proxies)


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not _is_trusted(peer):
        return peer
    # Se recorre de derecha a izquierda: lo de la izquierda lo escribe el cliente
    forwarded = request.headers.get("x-forwarded-for", "")
    for hop in reversed([h.strip() for h in forwarded.split(",") if h.strip()]):
        try:
            ipaddress.ip_address(hop)
        except ValueError:
            return peer
        if not _is_trusted(hop):
            return hop
    return peer


def ip_session_key(request: Request) -> str:
    """Clave por IP y sesión para rutas de administración."""
    session = request.cookies.get(get_settings().session_cookie, "")
    digest = hashlib.sha256(session.encode()).hexdigest()[:16] if session else "anon"
    return f"{client_ip(request)}:{digest}"


limiter = Limiter(key_func=client_ip, storage_uri=get_settings().rate_limit_storage)


def chat_rate() -> str:
    return get_settings().chat_rate


def login_rate() -> str:
    return get_settings().login_rate


def admin_rate() -> str:
    return get_settings().admin_rate


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    security_event(
        "rate_limit_hit", "WARNING", path=request.url.path, client=hash_identifier(client_ip(request))
    )
    return JSONResponse(status_code=429, content={"detail": "Demasiadas peticiones. Intenta más tarde."})
