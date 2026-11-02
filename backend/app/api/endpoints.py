"""Rutas de la API (Endpoints) - Operativa.ia

Maneja las peticiones de chat y consulta de configuración del agente de IA.
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import require_admin
from app.core.ratelimit import admin_rate, chat_rate, client_ip, ip_session_key, limiter
from app.core.validation import CleanStr, StrictModel
from app.services.agent import get_system_prompt, process_patient_message

router = APIRouter(prefix="/api/v1", tags=["Agente Conversacional"])


class ChatRequest(StrictModel):
    message: CleanStr(max_length=2000)


@router.get("/agent/prompt", dependencies=[Depends(require_admin)])
@limiter.limit(admin_rate, key_func=ip_session_key)
def read_agent_prompt(request: Request):
    """Retorna el System Prompt actual del agente de la clínica (solo administradores)."""
    return {"system_prompt": get_system_prompt()}


@router.post("/chat")
@limiter.limit(chat_rate)
def chat_with_agent(request: Request, payload: ChatRequest):
    """Endpoint para enviar un mensaje de un paciente y recibir la respuesta del agente."""
    return process_patient_message(payload.message, client_ip(request))
