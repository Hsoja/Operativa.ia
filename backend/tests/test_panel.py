"""El panel de Streamlit: login, datos solo del propio negocio y nada se agenda solo (puntos 1, 5; P1.6)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from app.services import calendar_service, leads, tenants
from helpers import PASSWORD, make_tenant, make_user, reset_db

PANEL = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "app.py")
LEAD = dict(name="Ana Sol", email="ana@sol.com", business="", topic="Book a demo", message="Mensaje de prueba largo", consent=True)


@pytest.fixture
def panel(client):
    reset_db()
    sol = make_tenant("demo", "Clínica Sol")
    luna = make_tenant("luna", "Salón Luna")
    make_user(sol, "admin", "owner")
    leads.create_lead(sol, leads.LeadIn(**LEAD))
    leads.create_lead(luna, leads.LeadIn(**{**LEAD, "name": "Beto Luna", "email": "beto@luna.com"}))
    return AppTest.from_file(PANEL, default_timeout=30).run()


def _login(panel, password):
    panel.text_input[0].set_value("admin")
    panel.text_input[1].set_value(password)
    return panel.button[0].click().run()


def _button(panel, label):
    return next(b for b in panel.button if b.label == label)


def test_panel_hides_everything_before_login(panel):
    assert not panel.exception
    assert len(panel.metric) == 0 and len(panel.chat_input) == 0 and len(panel.dataframe) == 0


def test_panel_rejects_wrong_password(panel):
    panel = _login(panel, "incorrecta-incorrecta")
    assert panel.error[0].value == "Credenciales inválidas." and len(panel.metric) == 0


def test_panel_shows_real_metrics_and_only_own_leads(panel):
    panel = _login(panel, PASSWORD)
    assert not panel.exception
    summary = {m.label: m.value for m in panel.metric}
    assert summary["Leads (total)"] == "1" and "Mensajes de clientes (7 días)" in summary
    table = panel.dataframe[0].value
    assert list(table["Correo"]) == ["ana@sol.com"]
    assert "Clínica Sol" in panel.title[0].value


def test_panel_chat_renders_as_plain_text(panel):
    panel = _login(panel, PASSWORD)
    assert panel.info[0].value.startswith("Google Calendar está desactivado")
    panel.chat_input[0].set_value("<img src=x onerror=alert(1)> **hola**").run()
    assert not panel.exception
    assert any("<img src=x onerror=alert(1)> **hola**" in t.value for t in panel.text)
    assert not any("onerror" in m.value for m in panel.markdown)


def test_chat_never_books_on_its_own(panel, monkeypatch):
    """Antes, escribir "cita" creaba un evento para mañana a las 11:00 sin confirmación."""
    spy = MagicMock()
    monkeypatch.setattr(calendar_service, "create_appointment", spy)
    panel = _login(panel, PASSWORD)
    panel.chat_input[0].set_value("Quiero agendar una cita mañana").run()
    assert not panel.exception
    spy.assert_not_called()
    assert not any("agendada" in t.value.lower() for t in panel.text)


def _with_service():
    from app.services import booking

    tenant = tenants.get_by_slug("demo")
    booking.create_service(tenant["id"], booking.ServiceIn(name="Limpieza", duration_minutes=60, deposit_cents=2500))
    booking.set_hours(
        tenant["id"],
        booking.WeeklyHours(ranges=[booking.HoursRange(weekday=d, open="09:00", close="12:00") for d in range(7)]),
    )


def test_booking_needs_services_first(panel):
    panel = _login(panel, PASSWORD)
    assert any("Configura servicios" in i.value for i in panel.info)


def test_booking_form_requires_confirmation_and_blocks_the_slot(panel, monkeypatch):
    from app.services import booking

    _with_service()
    spy = MagicMock(return_value={"status": "disabled"})
    monkeypatch.setattr(calendar_service, "create_appointment", spy)
    panel = _login(panel, PASSWORD)
    [t for t in panel.text_input if t.label == "Nombre del cliente"][0].set_value("Ana Sol")
    panel = _button(panel, "Agendar cita").click().run()
    assert any("confirmación" in e.value for e in panel.error)
    spy.assert_not_called()

    [c for c in panel.checkbox if c.label.startswith("Confirmo")][0].check()
    slot = [sb for sb in panel.selectbox if sb.label == "Hora"][0].value
    panel = _button(panel, "Agendar cita").click().run()
    assert not panel.exception and any("Cita agendada" in s.value for s in panel.success)
    assert spy.call_args.kwargs["timezone"] == "America/Toronto"
    tenant = tenants.get_by_slug("demo")
    appointments = booking.list_appointments(tenant["id"], since=0)
    assert len(appointments) == 1 and appointments[0]["status"] == "confirmed" and appointments[0]["deposit_cents"] == 0
    day = [d for d in panel.date_input if d.label == "Fecha"][0].value
    assert f"{day.isoformat()}T{slot}" not in booking.list_slots(tenant, booking.list_services(tenant["id"])[0], day)


def test_services_and_hours_from_panel(panel):
    from app.services import booking

    panel = _login(panel, PASSWORD)
    [t for t in panel.text_input if t.label == "Nombre del servicio"][0].set_value("Revisión")
    panel = _button(panel, "Agregar servicio").click().run()
    assert any("Servicio agregado" in s.value for s in panel.success)
    [t for t in panel.text_input if t.label == "Lunes"][0].set_value("09:00-13:00, 15:00-18:00")
    panel = _button(panel, "Guardar horario").click().run()
    assert any("Horario guardado" in s.value for s in panel.success)
    tenant = tenants.get_by_slug("demo")
    assert booking.get_hours(tenant["id"]) == [
        {"weekday": 0, "open": "09:00", "close": "13:00"},
        {"weekday": 0, "open": "15:00", "close": "18:00"},
    ]
    [t for t in panel.text_input if t.label == "Martes"][0].set_value("12:00-09:00")
    panel = _button(panel, "Guardar horario").click().run()
    assert any("Formato inválido" in e.value for e in panel.error)


def test_panel_closes_when_business_is_deactivated(panel):
    panel = _login(panel, PASSWORD)
    tenants.set_active("demo", False)
    panel = panel.run()
    assert len(panel.metric) == 0 and len(panel.dataframe) == 0


def test_panel_session_expires(panel):
    panel = _login(panel, PASSWORD)
    panel.session_state["admin_started_at"] = 1
    panel = panel.run()
    assert len(panel.metric) == 0


def test_panel_imports_backend_when_run_as_a_script():
    """Sin el pythonpath de pytest, frontend/app.py no debe taparse a sí mismo el paquete `app`."""
    result = subprocess.run([sys.executable, PANEL], capture_output=True, text=True, cwd=Path(PANEL).parent.parent)
    assert result.returncode == 0, result.stderr[-500:]


def _form_button(panel, label):
    return next(b for b in panel.button if b.label == label)


def test_panel_coverage_rules_and_quick_check(panel):
    panel = _login(panel, PASSWORD)
    areas = [t for t in panel.text_area if t.label.startswith("Prefijos")][0]
    insurers = [t for t in panel.text_area if t.label.startswith("Aseguradoras")][0]
    areas.set_value("N2L\nN2J")
    insurers.set_value("Sun Life")
    panel = _form_button(panel, "Guardar cobertura").click().run()
    assert any("Cobertura guardada" in s.value for s in panel.success)
    postal = [t for t in panel.text_input if t.label == "Código postal"][0]
    postal.set_value("N2L 3G1")
    [t for t in panel.text_input if t.label == "Aseguradora o plan"][0].set_value("Otra")
    panel = _form_button(panel, "Comprobar").click().run()
    assert any("aseguradora" in i.value for i in panel.info)


def test_staff_sees_coverage_read_only(client):
    reset_db()
    make_user(make_tenant("demo"), "admin", "staff")
    panel = _login(AppTest.from_file(PANEL, default_timeout=30).run(), PASSWORD)
    assert all(t.disabled for t in panel.text_area if t.label.startswith(("Prefijos", "Ciudades", "Aseguradoras")))
    assert _form_button(panel, "Guardar cobertura").disabled


def test_panel_reactivation_needs_confirmation_and_respects_casl(panel, monkeypatch):
    from app.services import reactivation

    sent = []
    monkeypatch.setattr(reactivation, "deliver", lambda *args: sent.append(args) or {"sent": 0, "failed": 0})
    panel = _login(panel, PASSWORD)
    [t for t in panel.text_input if t.label == "Asunto"][0].set_value("Te extrañamos")
    [t for t in panel.text_area if t.label.startswith("Mensaje")][0].set_value("Hola {nombre}, hace tiempo que no te vemos.")
    panel = _button(panel, "Enviar campaña").click().run()
    assert any("confirmación" in e.value for e in panel.error) and sent == []
    [c for c in panel.checkbox if c.label.startswith("Confirmo el envío")][0].check()
    panel = _button(panel, "Enviar campaña").click().run()
    # Sin SMTP configurado (ni contactos con consentimiento) la campaña se bloquea con un motivo claro
    assert any("correo no está configurado" in e.value for e in panel.error) and sent == []
