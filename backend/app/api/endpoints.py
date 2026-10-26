"""Rutas de la API (Endpoints) - Operativa.ia

Maneja las peticiones de chat y consulta de configuración del agente de IA.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from app.services.agent import get_system_prompt, process_patient_message

router = APIRouter(prefix="/api/v1", tags=["Agente Conversacional"])


class ChatRequest(BaseModel):
    message: str


@router.get("/agent/prompt")
def read_agent_prompt():
    """Retorna el System Prompt actual del agente de la clínica."""
    return {"system_prompt": get_system_prompt()}


@router.post("/chat")
def chat_with_agent(payload: ChatRequest):
    """Endpoint para enviar un mensaje de un paciente y recibir la respuesta del agente."""
    if not payload.message.strip():
        return {"error": "El mensaje no puede estar vacío."}
    return process_patient_message(payload.message)
