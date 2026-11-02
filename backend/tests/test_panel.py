"""El panel de Streamlit exige inicio de sesión y no muestra datos antes (puntos 1, 5)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.core.db import get_connection
from app.services import auth

PANEL = str(Path(__file__).resolve().parent.parent.parent / "frontend" / "app.py")
PASSWORD = "-".join(["contrasena", "de", "prueba", "1"])


@pytest.fixture
def panel(client):
    with get_connection() as db:
        db.execute("DELETE FROM login_attempts")
        db.execute("DELETE FROM admin_users")
    auth.create_admin("admin", PASSWORD)
    return AppTest.from_file(PANEL, default_timeout=30).run()


def _login(panel, password):
    panel.text_input[0].set_value("admin")
    panel.text_input[1].set_value(password)
    return panel.button[0].click().run()


def test_panel_hides_everything_before_login(panel):
    assert not panel.exception
    assert len(panel.metric) == 0 and len(panel.chat_input) == 0


def test_panel_rejects_wrong_password(panel):
    panel = _login(panel, "incorrecta-incorrecta")
    assert panel.error[0].value == "Credenciales inválidas." and len(panel.metric) == 0


def test_panel_login_then_chat_renders_as_plain_text(panel):
    panel = _login(panel, PASSWORD)
    assert not panel.exception and len(panel.metric) == 4
    assert panel.info[0].value.startswith("Google Calendar está desactivado")

    panel.chat_input[0].set_value("<img src=x onerror=alert(1)> **hola**").run()
    assert not panel.exception
    assert any("<img src=x onerror=alert(1)> **hola**" in t.value for t in panel.text)
    assert not any("onerror" in m.value for m in panel.markdown)


def test_panel_appointment_reports_disabled_calendar(panel):
    panel = _login(panel, PASSWORD)
    panel.chat_input[0].set_value("Quiero agendar una cita").run()
    assert any("No se pudo registrar" in t.value for t in panel.text)


def test_panel_session_expires(panel):
    panel = _login(panel, PASSWORD)
    panel.session_state["admin_started_at"] = 1
    panel = panel.run()
    assert len(panel.metric) == 0
