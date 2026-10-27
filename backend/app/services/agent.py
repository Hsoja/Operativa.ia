"""Módulo del Agente Conversacional - Operativa.ia

Conexión en tiempo real con la API de Groq (Llama 3) para la atención de pacientes.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# Buscar el archivo .env tanto en la raíz como en la carpeta backend
base_dir = Path(__file__).resolve().parent.parent.parent
env_root = base_dir / ".env"
env_backend = base_dir / "backend" / ".env"

if env_backend.exists():
    load_dotenv(dotenv_path=env_backend)
elif env_root.exists():
    load_dotenv(dotenv_path=env_root)
else:
    load_dotenv()

# Obtener la API key
api_key = os.getenv("GROQ_API_KEY")

SYSTEM_PROMPT_CLINICA = """
Eres Sofía, la asistente virtual de Inteligencia Artificial de la 'Clínica Dental Sonrisas'.
Tu objetivo es atender a pacientes las 24 horas del día, resolver sus dudas sobre tratamientos
y facilitar el agendamiento de sus citas.

Reglas de comportamiento:
1. Sé siempre amable, profesional, empática y concisa en tus respuestas.
2. Atiende consultas sobre servicios comunes (limpieza dental, blanqueamiento, ortodoncia, revisión general).
3. Para agendar una cita, solicita amablemente:
   - Nombre completo del paciente.
   - Teléfono de contacto.
   - Tratamiento de interés.
   - Fecha y horario preferido.
4. Si el paciente pregunta algo fuera del ámbito de la clínica, aclara cortésmente que solo gestionas información de la Clínica Dental Sonrisas.
"""


def get_system_prompt() -> str:
    """Devuelve el System Prompt configurado para el agente."""
    return SYSTEM_PROMPT_CLINICA.strip()


def process_patient_message(message: str) -> dict:
    """Envía el mensaje del paciente a Groq (Llama 3) y retorna la respuesta generada por la IA."""
    if not api_key:
        return {
            "status": "error",
            "user_message": message,
            "agent_response": (
                "⚠️ No se encontró la variable GROQ_API_KEY en tu archivo .env. "
                "Por favor verifica que el archivo exista y contenga tu clave."
            ),
        }

    try:
        groq_client = Groq(api_key=api_key)
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_CLINICA},
                {"role": "user", "content": message},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        agent_response = completion.choices[0].message.content

        return {
            "status": "success",
            "user_message": message,
            "agent_response": agent_response,
        }
    except Exception as e:
        return {
            "status": "error",
            "user_message": message,
            "agent_response": f"Lo siento, ocurrió un error al procesar tu solicitud: {str(e)}",
        }