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
    assert not panel.exception and len(panel.metric) == 4
    assert panel.metric[0].value == "1"
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


def test_booking_form_requires_confirmation(panel, monkeypatch):
    spy = MagicMock(return_value={"status": "disabled", "message": "La agenda de Google Calendar no está activada."})
    monkeypatch.setattr(calendar_service, "create_appointment", spy)
    panel = _login(panel, PASSWORD)
    panel.text_input[0].set_value("Ana Sol")
    panel.text_input[1].set_value("Limpieza")
    panel = _button(panel, "Agendar cita").click().run()
    assert any("confirmación" in e.value for e in panel.error)
    spy.assert_not_called()

    panel.checkbox[0].check()
    panel = _button(panel, "Agendar cita").click().run()
    spy.assert_called_once()
    assert spy.call_args.kwargs["timezone"] == "America/Toronto"
    assert spy.call_args.kwargs["summary"] == "Limpieza - Ana Sol"


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
