"""Dependencias de autenticación, autorización por rol y CSRF - Operativa.ia

El tenant de una petición privada SIEMPRE sale de la sesión; ninguna ruta acepta un tenant_id del cliente.
"""

import secrets
from collections.abc import Callable
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request

from app.core.config import get_settings
from app.core.logs import hash_identifier, security_event
from app.core.ratelimit import client_ip
from app.services import auth, tenants


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


def require_user(request: Request) -> dict:
    token = request.cookies.get(get_settings().session_cookie, "")
    session = auth.get_session(token) if token else None
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado.")
    return session


def require_user_csrf(
    request: Request, session: dict = Depends(require_user), csrf: str = Depends(require_csrf)
) -> dict:
    """Además del doble envío, el token debe ser el emitido para esta sesión."""
    if not secrets.compare_digest(auth.hash_token(csrf), session["csrf_hash"]):
        raise _reject_csrf(request, "session_token")
    return session


def _check_role(request: Request, session: dict, roles: tuple[str, ...]) -> dict:
    if session["role"] not in roles:
        security_event(
            "role_denied",
            "WARNING",
            path=request.url.path,
            role=session["role"],
            user=hash_identifier(session["username"].lower()),
        )
        raise HTTPException(status_code=403, detail="No tienes permiso para esta acción.")
    return session


def require_roles(*roles: str) -> Callable[..., dict]:
    """Lectura: sesión válida y uno de los roles indicados."""

    def dependency(request: Request, session: dict = Depends(require_user)) -> dict:
        return _check_role(request, session, roles)

    return dependency


def require_roles_csrf(*roles: str) -> Callable[..., dict]:
    """Escritura: sesión, CSRF ligado a la sesión y uno de los roles indicados."""

    def dependency(request: Request, session: dict = Depends(require_user_csrf)) -> dict:
        return _check_role(request, session, roles)

    return dependency


def public_tenant(slug: str) -> dict:
    """Resuelve el negocio de una ruta pública. Inexistente o inactivo: el mismo 404."""
    tenant = tenants.get_active_by_slug(slug)
    if tenant is None:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return tenant
