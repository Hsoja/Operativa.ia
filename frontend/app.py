"""Panel de Control (Frontend) - Operativa.ia

Interfaz interactiva en Streamlit integrada con Google Calendar y chat en tiempo real.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

# Conectar la carpeta backend/app directamente para evitar conflictos de nombres
BASE_DIR = Path(__file__).resolve().parent.parent
backend_app_path = BASE_DIR / "backend" / "app"

if str(backend_app_path) not in sys.path:
    sys.path.append(str(backend_app_path))

from services.calendar_service import create_appointment, get_calendar_service

# Configuración de la página
st.set_page_config(
    page_title="Operativa.ia - Panel de Control",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Operativa.ia - Panel de Control")

# 1. Métricas Principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Llamadas Atendidas", "42")
col2.metric("Citas Agendadas", "18")
col3.metric("Tasa de Conversión", "42.8%")
col4.metric("Ingresos Salvados", "$2,150 USD")

st.divider()

# 2. Vista de Citas Próximas desde Google Calendar
st.subheader("📅 Citas Agendadas Recientemente")

try:
    service = get_calendar_service()
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            maxResults=5,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if events:
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            st.write(f"📌 **{event.get('summary', 'Sin título')}** — {start}")
    else:
        st.info("No hay citas agendadas próximas en tu calendario.")
except Exception as e:
    st.error(f"Error al cargar citas de Google Calendar: {e}")

st.divider()

# 3. Interfaz de Chat interactiva con Sofía
st.subheader("💬 Chat con Sofía (Asistente Virtual)")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "¡Hola! Soy Sofía de Operativa.ia. ¿En qué puedo ayudarte hoy?",
        }
    ]

# Mostrar historial de conversación
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Cuadro de entrada de texto
if prompt := st.chat_input("Escribe un mensaje a Sofía..."):
    # Guardar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Respuesta de Sofía y agendamiento automático
    with st.chat_message("assistant"):
        with st.spinner("Sofía está procesando tu solicitud..."):
            prompt_lower = prompt.lower()
            if "agendar" in prompt_lower or "cita" in prompt_lower:
                # Hora sugerida para mañana a las 11:00 AM
                start_time = (datetime.now() + timedelta(days=1)).strftime(
                    "%Y-%m-%dT11:00:00"
                )
                res = create_appointment(
                    summary=f"Cita: {prompt[:30]}...",
                    description=f"Agendado automáticamente vía Sofía Chat: {prompt}",
                    start_time_iso=start_time,
                )
                if res.get("status") == "success":
                    reply = (
                        f"✅ **¡Cita agendada exitosamente en tu Google Calendar!**\n\n"
                        f"📌 **Resumen:** {res['summary']}\n"
                        f"📅 **Fecha y Hora:** {res['start']}"
                    )
                else:
                    reply = f"⚠️ No se pudo registrar en el calendario: {res.get('message')}"
            else:
                reply = (
                    f"Hola, recibí tu mensaje: '{prompt}'. Si deseas agendar una cita, "
                    f"dime algo como 'Quiero agendar una cita para mañana'."
                )

            st.write(reply)
            st.session_state.messages.append(
                {"role": "assistant", "content": reply}
            )