"""Rutas de administración - Operativa.ia"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import StringConstraints
from typing import Annotated

from app.api.deps import require_admin, require_admin_csrf, require_csrf
from app.core.config import get_settings
from app.core.logs import security_event
from app.core.ratelimit import admin_rate, client_ip, ip_session_key, limiter, login_rate
from app.core.validation import StrictModel
from app.services import auth

router = APIRouter(prefix="/api/v1/admin", tags=["Administración"])

Username = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{3,64}$")]
Password = Annotated[str, StringConstraints(min_length=1, max_length=auth.MAX_PASSWORD_LENGTH)]


class LoginRequest(StrictModel):
    username: Username
    password: Password


def _set_cookie(response: Response, name: str, value: str, *, http_only: bool, max_age: int | None = None) -> None:
    settings = get_settings()
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/",
        httponly=http_only,
        secure=settings.is_production,
        samesite="strict",
    )


@router.get("/csrf")
@limiter.limit(admin_rate, key_func=ip_session_key)
def issue_csrf(request: Request, response: Response):
    """Entrega el token que se debe reenviar en X-CSRF-Token al iniciar sesión."""
    token = secrets.token_urlsafe(32)
    _set_cookie(response, get_settings().csrf_cookie, token, http_only=False)
    return {"csrf_token": token}


@router.post("/login", dependencies=[Depends(require_csrf)])
@limiter.limit(login_rate)
def login(request: Request, response: Response, payload: LoginRequest):
    settings = get_settings()
    user = auth.authenticate(payload.username, payload.password, client_ip(request))
    if user is None:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    # Rotación: una sesión previa enviada por el navegador deja de ser válida
    previous = request.cookies.get(settings.session_cookie)
    if previous:
        auth.revoke_session(previous)
    token, csrf = auth.create_session(user["id"])
    _set_cookie(response, settings.session_cookie, token, http_only=True, max_age=settings.session_ttl_minutes * 60)
    _set_cookie(response, settings.csrf_cookie, csrf, http_only=False)
    return {"username": user["username"], "role": user["role"], "csrf_token": csrf}


@router.post("/logout", dependencies=[Depends(require_admin_csrf)])
@limiter.limit(admin_rate, key_func=ip_session_key)
def logout(request: Request, response: Response):
    settings = get_settings()
    auth.revoke_session(request.cookies.get(settings.session_cookie, ""))
    response.delete_cookie(settings.session_cookie, path="/")
    response.delete_cookie(settings.csrf_cookie, path="/")
    security_event("logout")
    return {"status": "ok"}


@router.get("/me")
@limiter.limit(admin_rate, key_func=ip_session_key)
def me(request: Request, session: dict = Depends(require_admin)):
    return {"username": session["username"], "role": session["role"]}
