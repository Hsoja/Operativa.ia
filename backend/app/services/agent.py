"""Módulo del Agente Conversacional - Operativa.ia

Define el comportamiento, personalidad y reglas del agente de IA para la clínica.
"""

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
    """Devuelve el System Prompt configurado para el agente de la clínica."""
    return SYSTEM_PROMPT_CLINICA.strip()


def process_patient_message(message: str) -> dict:
    """Estructura preliminar para procesar el mensaje del paciente.

    (Más adelante conectaremos este servicio con la API de Groq/OpenAI).
    """
    return {
        "user_message": message,
        "intent": "agendar_cita",
        "agent_response": (
            "¡Hola! Con gusto te ayudo a agendar tu cita. "
            "¿Cuál es tu nombre completo y qué día prefieres?"
        ),
    }
