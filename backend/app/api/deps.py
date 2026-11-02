"""Dependencias de autenticación y CSRF - Operativa.ia"""

import secrets
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings
from app.core.logs import hash_identifier, security_event
from app.core.ratelimit import client_ip
from app.services import auth


def _origin_allowed(request: Request) -> bool:
    allowed = get_settings().allowed_origins
    origin = request.headers.get("origin")
    if origin:
        return origin.rstrip("/") in allowed
    referer = request.headers.get("referer")
    if referer:
        parts = urlsplit(referer)
        return f"{parts.scheme}://{parts.netloc}" in allowed
    return False


def _reject_csrf(request: Request, reason: str) -> HTTPException:
    security_event(
        "csrf_rejected", "WARNING", reason=reason, path=request.url.path, client=hash_identifier(client_ip(request))
    )
    return HTTPException(status_code=403, detail="Solicitud rechazada.")


def require_csrf(request: Request) -> str:
    """Doble envío (cookie + cabecera) con verificación de Origin/Referer."""
    if not _origin_allowed(request):
        raise _reject_csrf(request, "origin")
    cookie = request.cookies.get(get_settings().csrf_cookie, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not secrets.compare_digest(cookie.encode(), header.encode()):
        raise _reject_csrf(request, "token")
    return header


def require_admin(request: Request) -> dict:
    token = request.cookies.get(get_settings().session_cookie, "")
    session = auth.get_session(token) if token else None
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return session


def require_admin_csrf(
    request: Request, session: dict = Depends(require_admin), csrf: str = Depends(require_csrf)
) -> dict:
    """Además del doble envío, el token debe ser el emitido para esta sesión."""
    if not secrets.compare_digest(auth.hash_token(csrf), session["csrf_hash"]):
        raise _reject_csrf(request, "session_token")
    return session
