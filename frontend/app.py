"""Panel de control de cada negocio (Streamlit) - Operativa.ia

Solo escucha en localhost (ver .streamlit/config.toml); en producción se usa por túnel SSH.
Todo lo que muestra pertenece al negocio del usuario que inició sesión.
Nada se agenda solo: una cita se crea únicamente desde el formulario y con confirmación explícita.
"""

import sys
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path

import streamlit as st

# Conectar la carpeta backend para reutilizar sus servicios. Debe ir primero en la ruta:
# este archivo también se llama "app" y taparía al paquete del backend.
BASE_DIR = Path(__file__).resolve().parent.parent
backend_path = BASE_DIR / "backend"

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import get_settings
from app.core.logs import configure_logging, hash_identifier, security_event
from app.services import agent, auth, conversations, leads, metrics, tenants
from app.services.calendar_service import (
    CalendarDisabledError,
    create_appointment,
    get_calendar_service,
)

MAX_CHAT_CHARS = 1900

st.set_page_config(page_title="Operativa.ia - Panel", page_icon="🤖", layout="wide")


def _fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


SESSION_KEYS = ("user", "admin_started_at", "preview_messages", "preview_conversation")


def _logout() -> None:
    # Solo las claves propias: borrar todo el estado también vaciaría los campos del formulario de login
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)


def main() -> None:
    # --- Sesión: nada se renderiza sin iniciar sesión -----------------------------------------------
    configure_logging()
    session_ttl = get_settings().session_ttl_minutes * 60
    started_at = st.session_state.get("admin_started_at")
    user = st.session_state.get("user")
    expired = started_at is None or user is None or time.time() - started_at > session_ttl
    # El negocio se vuelve a comprobar en cada recarga: si se desactiva, el panel se cierra al instante
    tenant = None if expired else tenants.get(user["tenant_id"])
    if expired or tenant is None or not tenant["active"]:
        _logout()
        st.title("🤖 Operativa.ia - Panel de Control")
        with st.form("login"):
            username = st.text_input("Usuario", max_chars=64)
            password = st.text_input("Contraseña", type="password", max_chars=auth.MAX_PASSWORD_LENGTH)
            submitted = st.form_submit_button("Iniciar sesión")
        if submitted:
            found = auth.authenticate(username, password, client="panel")
            if found:
                st.session_state["user"] = found
                st.session_state["admin_started_at"] = time.time()
                st.rerun()
            st.error("Credenciales inválidas.")
        return

    st.title(f"🤖 {tenant['name']} - Panel de Control")
    st.caption(f"Usuario: {user['username']} · Rol: {user['role']} · Zona horaria: {tenant['timezone']}")
    if st.button("Cerrar sesión"):
        _logout()
        st.rerun()

    # --- Métricas reales del negocio ------------------------------------------------------------------
    summary = metrics.tenant_summary(tenant["id"])
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Leads (total)", summary["leads_total"])
    col2.metric("Leads (7 días)", summary["leads_week"])
    col3.metric("Conversaciones (7 días)", summary["conversations_week"])
    col4.metric("Mensajes de clientes (7 días)", summary["messages_week"])

    st.divider()
    tab_agenda, tab_leads, tab_conversations, tab_sofia = st.tabs(
        ["📅 Agenda", "📥 Leads", "💬 Conversaciones", "🤖 Probar a Sofía"]
    )

    # --- Agenda -------------------------------------------------------------------------------------
    with tab_agenda:
        st.subheader("Próximas citas en Google Calendar")
        try:
            service = get_calendar_service()
            events = (
                service.events()
                .list(calendarId="primary", maxResults=5, singleEvents=True, orderBy="startTime")
                .execute()
                .get("items", [])
            )
            if events:
                for event in events:
                    start = event["start"].get("dateTime", event["start"].get("date"))
                    # st.text no interpreta Markdown: el título del evento puede venir de un cliente
                    st.text(f"📌 {event.get('summary', 'Sin título')} — {start}")
            else:
                st.info("No hay citas próximas en el calendario.")
        except CalendarDisabledError:
            st.info("Google Calendar está desactivado. Actívalo con CALENDAR_ENABLED=true.")
        except Exception as e:
            security_event("calendar_error", "ERROR", error=type(e).__name__)
            st.error("No se pudieron cargar las citas de Google Calendar.")

        st.subheader("Agendar una cita")
        with st.form("appointment", clear_on_submit=False):
            customer = st.text_input("Nombre del cliente", max_chars=80)
            service_name = st.text_input("Servicio", max_chars=100)
            day = st.date_input("Fecha", min_value=date.today(), value=date.today() + timedelta(days=1))
            hour = st.time_input("Hora", value=dtime(10, 0), step=900)
            duration = st.number_input("Duración (minutos)", min_value=15, max_value=240, value=45, step=15)
            notes = st.text_area("Notas (sin datos de salud ni de pago)", max_chars=500)
            confirmed = st.checkbox("Confirmo que el cliente aceptó esta fecha y hora")
            book = st.form_submit_button("Agendar cita")
        if book:
            if not confirmed:
                st.error("Marca la confirmación antes de agendar.")
            elif len(customer.strip()) < 2 or len(service_name.strip()) < 2:
                st.error("Escribe el nombre del cliente y el servicio.")
            else:
                result = create_appointment(
                    summary=f"{service_name.strip()} - {customer.strip()}",
                    description=notes,
                    start_time_iso=datetime.combine(day, hour).strftime("%Y-%m-%dT%H:%M:%S"),
                    duration_minutes=int(duration),
                    timezone=tenant["timezone"],
                )
                security_event(
                    "appointment_requested",
                    tenant=tenant["slug"],
                    status=result.get("status"),
                    user=hash_identifier(user["username"].lower()),
                )
                if result.get("status") == "success":
                    st.success(f"Cita agendada: {result['summary']} · {result['start']}")
                else:
                    st.error(result.get("message", "No se pudo agendar la cita."))

    # --- Leads ---------------------------------------------------------------------------------------
    with tab_leads:
        st.subheader("Solicitudes de contacto")
        rows = leads.list_leads(tenant["id"], limit=100)
        if rows:
            # st.dataframe muestra cada celda como texto plano
            st.dataframe(
                [
                    {
                        "Fecha": _fmt(r["created_at"]),
                        "Nombre": r["name"],
                        "Correo": r["email"],
                        "Negocio": r["business"],
                        "Tema": r["topic"],
                        "Mensaje": r["message"],
                        "Origen": r["source"],
                    }
                    for r in rows
                ],
                hide_index=True,
            )
        else:
            st.info("Todavía no hay solicitudes.")

    # --- Conversaciones ------------------------------------------------------------------------------
    with tab_conversations:
        st.subheader("Conversaciones recientes")
        recent = conversations.list_conversations(tenant["id"], limit=50)
        if recent:
            labels = {f"#{c['id']} · {_fmt(c['last_at'])} · {c['messages']} mensajes": c["id"] for c in recent}
            choice = st.selectbox("Conversación", list(labels))
            for message in conversations.get_messages(tenant["id"], labels[choice]) or []:
                with st.chat_message("user" if message["role"] == "user" else "assistant"):
                    st.text(message["content"])
        else:
            st.info("Todavía no hay conversaciones.")

    # --- Probar a Sofía --------------------------------------------------------------------------------
    with tab_sofia:
        st.subheader("Probar a Sofía con los datos de este negocio")
        st.caption("Las pruebas se guardan como una conversación más. Sofía nunca agenda ni cobra por su cuenta.")
        history = st.session_state.setdefault("preview_messages", [])
        for msg in history:
            with st.chat_message(msg["role"]):
                st.text(msg["content"])
        if prompt := st.chat_input("Escribe un mensaje a Sofía...", max_chars=MAX_CHAT_CHARS):
            history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.text(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Sofía está pensando..."):
                    result = agent.process_message(tenant, prompt, st.session_state.get("preview_conversation"), "panel")
                st.session_state["preview_conversation"] = result["conversation_id"]
                st.text(result["agent_response"])
            history.append({"role": "assistant", "content": result["agent_response"]})


main()
