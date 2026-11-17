"""Rutas públicas por negocio - Operativa.ia

Las usa el sitio o el widget de cada PYME, sin sesión. El negocio se identifica con el `slug` de la URL
y solo se aceptan negocios activos. No usan cookies, así que no necesitan CSRF.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import StringConstraints

from app.api.deps import public_tenant
from app.core.logs import security_event
from app.core.ratelimit import chat_rate, client_ip, contact_rate, limiter
from app.core.validation import CleanStr, StrictModel
from app.services import agent, leads, tenants

router = APIRouter(prefix="/api/v1/public/{slug}", tags=["Público"])

ConversationToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{16,64}$")]


class ChatRequest(StrictModel):
    message: CleanStr(max_length=2000)
    conversation_id: ConversationToken | None = None


@router.get("/profile")
@limiter.limit(chat_rate)
def read_profile(request: Request, tenant: dict = Depends(public_tenant)):
    """Nombre y datos públicos del negocio para el encabezado del widget."""
    profile = tenants.public_profile(tenant)
    return {"slug": profile["slug"], "name": profile["name"], "business_type": profile["business_type"]}


@router.post("/chat")
@limiter.limit(chat_rate)
def chat_with_agent(request: Request, payload: ChatRequest, tenant: dict = Depends(public_tenant)):
    """Mensaje de un cliente del negocio; la respuesta trae el identificador de la conversación."""
    return agent.process_message(tenant, payload.message, payload.conversation_id, client_ip(request))


@router.post("/contact", status_code=201)
@limiter.limit(contact_rate)
def submit_contact(request: Request, payload: leads.LeadIn, tenant: dict = Depends(public_tenant)):
    """Solicitud de contacto o demo. Requiere consentimiento; el contenido nunca va al log."""
    leads.create_lead(tenant["id"], payload)
    security_event("lead_received", tenant=tenant["slug"], source=payload.source)
    return JSONResponse(status_code=201, content={"status": "received"})
