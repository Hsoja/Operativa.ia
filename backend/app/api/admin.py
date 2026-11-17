"""Rutas del panel de cada negocio - Operativa.ia

Matriz de permisos (el tenant siempre sale de la sesión):
    staff  -> ver perfil, cobertura, leads y conversaciones
    admin  -> lo anterior + editar perfil y cobertura, ver el prompt y el equipo, borrar leads
    owner  -> lo anterior + crear usuarios admin/staff de su negocio
Crear negocios y owners solo se puede por CLI en el servidor: no hay "superadmin" web.
"""

import secrets
import sqlite3
import time
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import StringConstraints

from app.api.deps import require_csrf, require_roles, require_roles_csrf, require_user, require_user_csrf
from app.core.config import get_settings
from app.core.logs import hash_identifier, security_event
from app.core.ratelimit import admin_rate, client_ip, ip_session_key, limiter, login_rate
from app.core.validation import StrictModel
from app.services import agent, auth, booking, conversations, coverage, leads, reactivation, tenants

router = APIRouter(prefix="/api/v1/admin", tags=["Panel"])

ALL_ROLES = ("owner", "admin", "staff")
MANAGERS = ("owner", "admin")

Username = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]{3,64}$")]
Password = Annotated[str, StringConstraints(min_length=1, max_length=auth.MAX_PASSWORD_LENGTH)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=100_000)]


class LoginRequest(StrictModel):
    username: Username
    password: Password


class NewUserRequest(StrictModel):
    username: Username
    password: Annotated[
        str, StringConstraints(min_length=auth.MIN_PASSWORD_LENGTH, max_length=auth.MAX_PASSWORD_LENGTH)
    ]
    role: Literal["admin", "staff"]


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
    return {"username": user["username"], "role": user["role"], "tenant": user["tenant_slug"], "csrf_token": csrf}


@router.post("/logout", dependencies=[Depends(require_user_csrf)])
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
def me(request: Request, session: dict = Depends(require_user)):
    return {"username": session["username"], "role": session["role"], "tenant": session["tenant_slug"]}


@router.get("/tenant")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_tenant(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return tenants.public_profile(tenants.get(session["tenant_id"]))


@router.post("/tenant")
@limiter.limit(admin_rate, key_func=ip_session_key)
def update_tenant(request: Request, payload: tenants.TenantProfile, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    tenants.update_profile(session["tenant_id"], payload)
    security_event("tenant_profile_updated", tenant=session["tenant_slug"], user=hash_identifier(session["username"].lower()))
    return tenants.public_profile(tenants.get(session["tenant_id"]))


@router.get("/agent/prompt")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_agent_prompt(request: Request, session: dict = Depends(require_roles(*MANAGERS))):
    """Prompt que usa Sofía para este negocio (solo owner y admin)."""
    tenant_id = session["tenant_id"]
    names = agent.enabled_tools(tenant_id)
    prompt = agent.build_system_prompt(tenants.get(tenant_id), "check_coverage" in names, "list_available_slots" in names)
    return {"system_prompt": prompt}


@router.get("/coverage")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_coverage(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return coverage.get_rules(session["tenant_id"])


@router.post("/coverage")
@limiter.limit(admin_rate, key_func=ip_session_key)
def update_coverage(request: Request, payload: coverage.CoverageRules, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    """Reemplaza las reglas de zona y aseguradoras del negocio (owner y admin)."""
    coverage.set_rules(session["tenant_id"], payload)
    security_event("coverage_updated", tenant=session["tenant_slug"], user=hash_identifier(session["username"].lower()))
    return coverage.get_rules(session["tenant_id"])


@router.get("/users")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_users(request: Request, session: dict = Depends(require_roles(*MANAGERS))):
    return {"users": auth.list_users(session["tenant_id"])}


@router.post("/users", status_code=201)
@limiter.limit(admin_rate, key_func=ip_session_key)
def create_user(request: Request, payload: NewUserRequest, session: dict = Depends(require_roles_csrf("owner"))):
    """El owner agrega personal a SU negocio. No puede crear owners ni usuarios de otro negocio."""
    try:
        auth.create_user(session["tenant_id"], payload.username, payload.password, payload.role)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ese usuario no está disponible.") from None
    security_event("user_created", tenant=session["tenant_slug"], role=payload.role)
    return {"username": payload.username, "role": payload.role}


@router.get("/leads")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_leads(request: Request, limit: Limit = 50, offset: Offset = 0, session: dict = Depends(require_roles(*ALL_ROLES))):
    return {"leads": leads.list_leads(session["tenant_id"], limit, offset)}


@router.post("/leads/{lead_id}/delete")
@limiter.limit(admin_rate, key_func=ip_session_key)
def delete_lead(request: Request, lead_id: int,session: dict = Depends(require_roles_csrf(*MANAGERS))):
    if not leads.delete_lead(session["tenant_id"], lead_id):
        raise HTTPException(status_code=404, detail="No encontrado.")
    security_event("lead_deleted", tenant=session["tenant_slug"])
    return {"status": "deleted"}


@router.get("/conversations")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_conversations(
    request: Request, limit: Limit = 50, offset: Offset = 0, session: dict = Depends(require_roles(*ALL_ROLES))
):
    return {"conversations": conversations.list_conversations(session["tenant_id"], limit, offset)}


@router.get("/conversations/{conversation_id}")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_conversation(request: Request, conversation_id: int, session: dict = Depends(require_roles(*ALL_ROLES))):
    messages = conversations.get_messages(session["tenant_id"], conversation_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="No encontrado.")
    return {"id": conversation_id, "messages": messages}


# --- Agenda: servicios, horario y citas ------------------------------------------------------------

@router.get("/services")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_services(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return {"services": booking.list_services(session["tenant_id"], only_active=False)}


@router.post("/services", status_code=201)
@limiter.limit(admin_rate, key_func=ip_session_key)
def create_service(request: Request, payload: booking.ServiceIn, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    try:
        service_id = booking.create_service(session["tenant_id"], payload)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe un servicio con ese nombre.") from None
    security_event("service_saved", tenant=session["tenant_slug"])
    return booking.get_service(session["tenant_id"], service_id, only_active=False)


@router.post("/services/{service_id}")
@limiter.limit(admin_rate, key_func=ip_session_key)
def update_service(
    request: Request, service_id: int, payload: booking.ServiceIn, session: dict = Depends(require_roles_csrf(*MANAGERS))
):
    try:
        updated = booking.update_service(session["tenant_id"], service_id, payload)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Ya existe un servicio con ese nombre.") from None
    if not updated:
        raise HTTPException(status_code=404, detail="No encontrado.")
    security_event("service_saved", tenant=session["tenant_slug"])
    return booking.get_service(session["tenant_id"], service_id, only_active=False)


@router.get("/hours")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_hours(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return {"ranges": booking.get_hours(session["tenant_id"])}


@router.post("/hours")
@limiter.limit(admin_rate, key_func=ip_session_key)
def update_hours(request: Request, payload: booking.WeeklyHours, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    booking.set_hours(session["tenant_id"], payload)
    security_event("hours_saved", tenant=session["tenant_slug"])
    return {"ranges": booking.get_hours(session["tenant_id"])}


@router.get("/appointments")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_appointments(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return {"appointments": booking.list_appointments(session["tenant_id"], since=int(time.time()) - 86400)}


@router.post("/appointments/{appointment_id}/cancel")
@limiter.limit(admin_rate, key_func=ip_session_key)
def cancel_appointment(request: Request, appointment_id: int, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    """Cancela la cita y libera el hueco. El reembolso del depósito, si aplica, se hace en el panel de Stripe."""
    if not booking.cancel(session["tenant_id"], appointment_id):
        raise HTTPException(status_code=404, detail="No encontrado.")
    security_event("appointment_cancelled", tenant=session["tenant_slug"])
    return {"status": "cancelled"}


# --- Reactivación (CASL) -----------------------------------------------------------------------------

@router.get("/campaigns")
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_campaigns(request: Request, session: dict = Depends(require_roles(*ALL_ROLES))):
    return {
        "contacts": reactivation.contact_stats(session["tenant_id"]),
        "campaigns": reactivation.list_campaigns(session["tenant_id"]),
    }


@router.post("/campaigns/preview")
@limiter.limit(admin_rate, key_func=ip_session_key)
def preview_campaign(request: Request, payload: reactivation.PreviewIn, session: dict = Depends(require_roles_csrf(*MANAGERS))):
    """Cuántos contactos recibirían la campaña (solo con consentimiento explícito y sin baja)."""
    return {"eligible": reactivation.preview(session["tenant_id"], payload.inactive_days)}


@router.post("/campaigns", status_code=202)
@limiter.limit(admin_rate, key_func=ip_session_key)
def send_campaign(
    request: Request,
    payload: reactivation.CampaignIn,
    background: BackgroundTasks,
    session: dict = Depends(require_roles_csrf(*MANAGERS)),
):
    tenant = tenants.get(session["tenant_id"])
    try:
        campaign_id, sends = reactivation.create_campaign(tenant, payload)
    except reactivation.CampaignBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    security_event("campaign_created", tenant=session["tenant_slug"], recipients=len(sends), user=hash_identifier(session["username"].lower()))
    background.add_task(reactivation.deliver, tenant, campaign_id, payload, sends)
    return {"campaign_id": campaign_id, "recipients": len(sends)}
