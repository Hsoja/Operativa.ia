"""Panel de Control (Frontend) - Operativa.ia

Interfaz interactiva en Streamlit integrada con Google Calendar y chat en tiempo real.
"""

import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st

# Conectar la carpeta backend para reutilizar sus servicios. Debe ir primero en la ruta:
# este archivo también se llama "app" y taparía al paquete del backend.
BASE_DIR = Path(__file__).resolve().parent.parent
backend_path = BASE_DIR / "backend"

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import get_settings
from app.core.logs import configure_logging, security_event
from app.services import auth
from app.services.calendar_service import (
    CalendarDisabledError,
    create_appointment,
    get_calendar_service,
)

MAX_CHAT_CHARS = 1900

# Configuración de la página
st.set_page_config(
    page_title="Operativa.ia - Panel de Control",
    page_icon="🤖",
    layout="wide",
)

# Este panel muestra citas y crea eventos: nada se renderiza sin iniciar sesión
configure_logging()
session_ttl = get_settings().session_ttl_minutes * 60
started_at = st.session_state.get("admin_started_at")
if started_at is None or time.time() - started_at > session_ttl:
    st.session_state.pop("admin_started_at", None)
    st.title("🤖 Operativa.ia - Panel de Control")
    with st.form("login"):
        username = st.text_input("Usuario", max_chars=64)
        password = st.text_input("Contraseña", type="password", max_chars=auth.MAX_PASSWORD_LENGTH)
        submitted = st.form_submit_button("Iniciar sesión")
    if submitted:
        if auth.authenticate(username, password, client="panel"):
            st.session_state["admin_started_at"] = time.time()
            st.rerun()
        st.error("Credenciales inválidas.")
    st.stop()

st.title("🤖 Operativa.ia - Panel de Control")
if st.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()

# 1. Métricas Principales (datos ilustrativos del prototipo)
st.caption("Métricas ilustrativas del prototipo, no son datos reales.")
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
            # st.text no interpreta Markdown: el título del evento puede venir de un usuario
            st.text(f"📌 {event.get('summary', 'Sin título')} — {start}")
    else:
        st.info("No hay citas agendadas próximas en tu calendario.")
except CalendarDisabledError:
    st.info("Google Calendar está desactivado. Actívalo con CALENDAR_ENABLED=true.")
except Exception as e:
    security_event("calendar_error", "ERROR", error=type(e).__name__)
    st.error("No se pudieron cargar las citas de Google Calendar.")

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
        st.text(msg["content"])

# Cuadro de entrada de texto
if prompt := st.chat_input("Escribe un mensaje a Sofía...", max_chars=MAX_CHAT_CHARS):
    # Guardar y mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.text(prompt)

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
                        f"✅ ¡Cita agendada exitosamente en tu Google Calendar!\n\n"
                        f"📌 Resumen: {res['summary']}\n"
                        f"📅 Fecha y Hora: {res['start']}"
                    )
                else:
                    reply = f"⚠️ No se pudo registrar en el calendario: {res.get('message')}"
            else:
                reply = (
                    f"Hola, recibí tu mensaje: '{prompt}'. Si deseas agendar una cita, "
                    f"dime algo como 'Quiero agendar una cita para mañana'."
                )

            st.text(reply)
            st.session_state.messages.append(
                {"role": "assistant", "content": reply}
            )