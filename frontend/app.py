"""Panel de control de cada negocio (Streamlit) - Operativa.ia

Solo escucha en localhost (ver .streamlit/config.toml); en producción se usa por túnel SSH.
Todo lo que muestra pertenece al negocio del usuario que inició sesión.
Nada se agenda solo: una cita se crea únicamente desde el formulario y con confirmación explícita.
"""

import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

# Conectar la carpeta backend para reutilizar sus servicios. Debe ir primero en la ruta:
# este archivo también se llama "app" y taparía al paquete del backend.
BASE_DIR = Path(__file__).resolve().parent.parent
backend_path = BASE_DIR / "backend"

if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.config import get_settings
from app.core.logs import configure_logging, hash_identifier, security_event
from pydantic import ValidationError

from app.services import agent, auth, booking, conversations, coverage, leads, metrics, reactivation, templates, tenants
from app.services.calendar_service import (
    CalendarDisabledError,
    create_appointment,
    get_calendar_service,
)

MAX_CHAT_CHARS = 1900
WEEKDAYS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
STATUS_LABELS = {
    "pending_payment": "Esperando pago",
    "confirmed": "Confirmada",
    "cancelled": "Cancelada",
    "expired": "Vencida",
    "needs_refund": "Revisar reembolso",
}

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
    st.caption(
        f"Usuario: {user['username']} · Rol: {user['role']} · Zona horaria: {tenant['timezone']} · Plantilla: {tenant['template']}"
    )
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
    tab_agenda, tab_setup, tab_leads, tab_conversations, tab_coverage, tab_reactivation, tab_sofia = st.tabs(
        ["📅 Agenda", "⚙️ Servicios y horario", "📥 Leads", "💬 Conversaciones", "🗺️ Cobertura", "📣 Reactivación", "🤖 Probar a Sofía"]
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

        st.subheader("Citas reservadas")
        upcoming = booking.list_appointments(tenant["id"], since=int(time.time()) - 86400)
        if upcoming:
            st.dataframe(
                [
                    {
                        "Inicio": datetime.fromtimestamp(a["starts_at"], ZoneInfo(tenant["timezone"])).strftime("%Y-%m-%d %H:%M"),
                        "Servicio": a["service"],
                        "Cliente": a["customer_name"],
                        "Estado": STATUS_LABELS.get(a["status"], a["status"]),
                        "Depósito": f"{a['deposit_cents'] / 100:.2f} {a['currency'].upper()}" if a["deposit_cents"] else "-",
                    }
                    for a in upcoming
                ],
                hide_index=True,
            )
        else:
            st.info("No hay citas próximas.")

        st.subheader("Agendar una cita")
        services = booking.list_services(tenant["id"])
        if not services:
            st.info("Configura servicios y horario en la pestaña Servicios y horario para poder agendar.")
        else:
            by_name = {s["name"]: s for s in services}
            service = by_name[st.selectbox("Servicio", list(by_name), key="book_service")]
            first, last = booking.bookable_days(tenant)
            day = st.date_input("Fecha", min_value=first, max_value=last, value=first + timedelta(days=1), key="book_day")
            free = booking.list_slots(tenant, service, day)
            slot = st.selectbox("Hora", [s[11:] for s in free], key="book_slot") if free else None
            if not free:
                st.info("No hay horarios libres ese día.")
            customer = st.text_input("Nombre del cliente", max_chars=80, key="book_customer")
            confirmed = st.checkbox("Confirmo que el cliente aceptó esta fecha y hora", key="book_confirm")
            if st.button("Agendar cita", disabled=slot is None):
                if not confirmed:
                    st.error("Marca la confirmación antes de agendar.")
                elif len(customer.strip()) < 2:
                    st.error("Escribe el nombre del cliente.")
                else:
                    try:
                        created = booking.create_booking(
                            tenant,
                            booking.PanelBookingIn(service_id=service["id"], start=f"{day.isoformat()}T{slot}", name=customer),
                            source="panel",
                        )
                    except booking.BookingError:
                        st.error("Ese horario ya no está disponible.")
                    else:
                        sync = create_appointment(
                            summary=f"{service['name']} - {customer.strip()}",
                            description="Agendada desde el panel.",
                            start_time_iso=f"{day.isoformat()}T{slot}:00",
                            duration_minutes=service["duration_minutes"],
                            timezone=tenant["timezone"],
                        )
                        security_event(
                            "appointment_requested",
                            tenant=tenant["slug"],
                            status=created["status"],
                            calendar=sync.get("status"),
                            user=hash_identifier(user["username"].lower()),
                        )
                        st.success(f"Cita agendada: {service['name']} · {day.isoformat()} {slot}")

        if user["role"] in ("owner", "admin") and upcoming:
            st.subheader("Cancelar una cita")
            cancellable = {
                f"#{a['id']} · {a['service']} · {a['customer_name']}": a["id"]
                for a in upcoming
                if a["status"] in ("pending_payment", "confirmed")
            }
            if cancellable:
                choice = st.selectbox("Cita", list(cancellable), key="cancel_choice")
                if st.button("Cancelar cita"):
                    booking.cancel(tenant["id"], cancellable[choice])
                    security_event("appointment_cancelled", tenant=tenant["slug"])
                    st.success("Cita cancelada. Si hubo depósito, reembólsalo desde el panel de Stripe.")

    # --- Servicios y horario ---------------------------------------------------------------------------
    with tab_setup:
        can_edit = user["role"] in ("owner", "admin")

        st.subheader("Perfil del negocio")
        st.caption("Alimenta las respuestas de Sofía. El correo de aviso es opcional: sin él, nadie se entera de un lead nuevo salvo quien revise la pestaña Leads.")
        with st.form("business_profile"):
            p_name = st.text_input("Nombre del negocio", value=tenant["name"], max_chars=120, disabled=not can_edit)
            p_type = st.text_input("Tipo de negocio", value=tenant["business_type"], max_chars=80, disabled=not can_edit)
            p_services = st.text_area("Servicios (texto libre, para Sofía)", value=tenant["services"], max_chars=1500, disabled=not can_edit)
            p_hours = st.text_input("Horario (texto libre, para Sofía)", value=tenant["hours"], max_chars=300, disabled=not can_edit)
            p_location = st.text_input("Dirección física (CASL la exige para enviar correos de reactivación)", value=tenant["location"], max_chars=200, disabled=not can_edit)
            p_timezone = st.text_input("Zona horaria (IANA, p. ej. America/Toronto)", value=tenant["timezone"], max_chars=64, disabled=not can_edit)
            p_notify = st.text_input(
                "Correo de aviso de leads nuevos (vacío = apagado)",
                value=tenant["notify_email"],
                max_chars=254,
                disabled=not can_edit,
                help="Requiere que el servidor tenga SMTP configurado (SMTP_HOST, SMTP_FROM, ...).",
            )
            save_profile = st.form_submit_button("Guardar perfil", disabled=not can_edit)
        if save_profile and can_edit:
            try:
                tenants.update_profile(
                    tenant["id"],
                    tenants.TenantProfile(
                        name=p_name, business_type=p_type, services=p_services, hours=p_hours,
                        location=p_location, timezone=p_timezone, notify_email=p_notify,
                    ),
                )
                security_event("tenant_profile_updated", tenant=tenant["slug"], user=hash_identifier(user["username"].lower()))
                st.success("Perfil guardado.")
            except ValidationError:
                st.error("Revisa los datos: el correo de aviso o la zona horaria no son válidos, o un campo es muy largo.")

        st.subheader("Servicios")
        all_services = booking.list_services(tenant["id"], only_active=False)
        if all_services:
            st.dataframe(
                [
                    {
                        "Servicio": s["name"],
                        "Duración (min)": s["duration_minutes"],
                        "Depósito": f"{s['deposit_cents'] / 100:.2f} {s['currency'].upper()}",
                        "Activo": "Sí" if s["active"] else "No",
                    }
                    for s in all_services
                ],
                hide_index=True,
            )
        with st.form("new_service"):
            name = st.text_input("Nombre del servicio", max_chars=80, disabled=not can_edit)
            minutes = st.number_input("Duración (minutos)", min_value=5, max_value=480, value=60, step=5, disabled=not can_edit)
            deposit = st.number_input("Depósito (0 = sin depósito)", min_value=0.0, max_value=1000.0, value=0.0, step=5.0, disabled=not can_edit)
            currency = st.selectbox("Moneda", ["cad", "usd", "mxn", "eur"], disabled=not can_edit)
            add = st.form_submit_button("Agregar servicio", disabled=not can_edit)
        if add and can_edit:
            try:
                booking.create_service(
                    tenant["id"],
                    booking.ServiceIn(name=name, duration_minutes=int(minutes), deposit_cents=round(deposit * 100), currency=currency),
                )
                security_event("service_saved", tenant=tenant["slug"])
                st.success("Servicio agregado.")
            except (ValidationError, sqlite3.IntegrityError):
                st.error("Revisa el nombre (2 a 80 caracteres, sin repetir) y los valores.")

        st.subheader("Horario semanal")
        st.caption("Rangos separados por coma, por ejemplo 09:00-13:00, 15:00-19:00. Vacío = cerrado.")
        current = booking.get_hours(tenant["id"])
        with st.form("hours"):
            inputs = {}
            for weekday, label in enumerate(WEEKDAYS):
                value = ", ".join(f"{r['open']}-{r['close']}" for r in current if r["weekday"] == weekday)
                inputs[weekday] = st.text_input(label, value, max_chars=100, disabled=not can_edit)
            save_hours = st.form_submit_button("Guardar horario", disabled=not can_edit)
        if save_hours and can_edit:
            try:
                ranges = [
                    booking.HoursRange(weekday=weekday, open=span.split("-")[0].strip(), close=span.split("-")[1].strip())
                    for weekday, text in inputs.items()
                    for span in text.split(",")
                    if span.strip()
                ]
                booking.set_hours(tenant["id"], booking.WeeklyHours(ranges=ranges))
                security_event("hours_saved", tenant=tenant["slug"])
                st.success("Horario guardado.")
            except (ValidationError, IndexError):
                st.error("Formato inválido. Usa HH:MM-HH:MM y que los rangos no se solapen.")

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

    # --- Cobertura ---------------------------------------------------------------------------------
    with tab_coverage:
        rules = coverage.get_rules(tenant["id"])
        st.subheader("Zona de servicio y aseguradoras")
        st.caption("Una lista vacía significa que esa condición no se revisa. Nunca pidas números de póliza ni datos de salud.")
        can_edit = user["role"] in ("owner", "admin")
        with st.form("coverage_rules"):
            prefixes = st.text_area("Prefijos de código postal (uno por línea, p. ej. N2L)", "\n".join(rules["postal_prefixes"]), disabled=not can_edit)
            cities = st.text_area("Ciudades (una por línea)", "\n".join(rules["cities"]), disabled=not can_edit)
            insurers = st.text_area("Aseguradoras o planes aceptados (uno por línea)", "\n".join(rules["insurers"]), disabled=not can_edit)
            save = st.form_submit_button("Guardar cobertura", disabled=not can_edit)
        if save and can_edit:
            lines = lambda text: [line.strip() for line in text.splitlines() if line.strip()]
            try:
                coverage.set_rules(
                    tenant["id"],
                    coverage.CoverageRules(postal_prefixes=lines(prefixes), cities=lines(cities), insurers=lines(insurers)),
                )
                security_event("coverage_updated", tenant=tenant["slug"], user=hash_identifier(user["username"].lower()))
                st.success("Cobertura guardada.")
            except ValidationError:
                st.error("Revisa las listas: hay valores vacíos, demasiado largos o con caracteres no válidos.")

        st.subheader("Consulta rápida")
        with st.form("coverage_check"):
            q_postal = st.text_input("Código postal", max_chars=12)
            q_city = st.text_input("Ciudad", max_chars=80)
            q_insurer = st.text_input("Aseguradora o plan", max_chars=80)
            run_check = st.form_submit_button("Comprobar")
        if run_check:
            try:
                query = coverage.CoverageQuery(
                    postal_code=q_postal.strip() or None, city=q_city.strip() or None, insurer=q_insurer.strip() or None
                )
                st.info(coverage.describe(coverage.check(tenant["id"], query)))
            except ValidationError:
                st.error("Datos de consulta no válidos.")

    # --- Reactivación (CASL) ------------------------------------------------------------------------
    with tab_reactivation:
        stats = reactivation.contact_stats(tenant["id"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Contactos", stats["total"])
        c2.metric("Con consentimiento", stats["opted_in"])
        c3.metric("Dados de baja", stats["unsubscribed"])
        st.caption(
            "Solo reciben correos quienes marcaron la casilla de recordatorios y ofertas (consentimiento explícito, CASL). "
            "Cada correo incluye el nombre y la dirección del negocio y un enlace de baja."
        )
        if user["role"] in ("owner", "admin"):
            days = st.number_input("Clientes sin actividad desde hace (días)", min_value=30, max_value=730, value=90, step=15, key="react_days")
            st.text(f"Recibirían este correo: {reactivation.preview(tenant['id'], int(days))} contactos")
            suggestion = templates.campaign_suggestion(tenant)
            subject = st.text_input("Asunto", value=suggestion.subject if suggestion else "", max_chars=120, key="react_subject")
            body = st.text_area(
                "Mensaje (usa {nombre} para personalizar)", value=suggestion.body if suggestion else "", max_chars=2000, key="react_body"
            )
            sure = st.checkbox("Confirmo el envío a los contactos con consentimiento", key="react_confirm")
            if st.button("Enviar campaña"):
                if not sure:
                    st.error("Marca la confirmación antes de enviar.")
                else:
                    try:
                        campaign = reactivation.CampaignIn(inactive_days=int(days), subject=subject, body=body, confirm=True)
                        campaign_id, sends = reactivation.create_campaign(tenant, campaign)
                        result = reactivation.deliver(tenant, campaign_id, campaign, sends)
                        st.success(f"Campaña enviada: {result['sent']} enviados, {result['failed']} con error.")
                    except ValidationError:
                        st.error("Revisa el asunto (una línea, 3 a 120 caracteres) y el mensaje (20 a 2000).")
                    except reactivation.CampaignBlocked as exc:
                        st.error(str(exc))
        history = reactivation.list_campaigns(tenant["id"])
        if history:
            st.subheader("Historial")
            st.dataframe(
                [
                    {"Fecha": _fmt(c["created_at"]), "Asunto": c["subject"], "Destinatarios": c["recipients"], "Enviados": c["sent"], "Errores": c["failed"]}
                    for c in history
                ],
                hide_index=True,
            )

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
