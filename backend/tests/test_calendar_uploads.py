"""Permisos de Calendar, argumentos de herramientas, enlaces y subidas (puntos 4, 5, 18; roadmap E)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.config import get_settings
from app.core.uploads import MAX_UPLOAD_BYTES, UploadRejected, save_upload
from app.core.validation import is_safe_https_url
from app.services import calendar_service as cal

FUTURE = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT11:00:00")


def test_scope_is_minimal():
    assert cal.SCOPES == ["https://www.googleapis.com/auth/calendar.events"]


def test_calendar_disabled_by_default(client):
    assert cal.create_appointment("Cita", "Detalle", FUTURE)["status"] == "disabled"
    with pytest.raises(cal.CalendarDisabledError):
        cal.get_calendar_service()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"summary": "", "description": "d", "start_time_iso": FUTURE},
        {"summary": "x" * 201, "description": "d", "start_time_iso": FUTURE},
        {"summary": "s", "description": "x" * 2001, "start_time_iso": FUTURE},
        {"summary": "s", "description": "d", "start_time_iso": "no-es-fecha"},
        {"summary": "s", "description": "d", "start_time_iso": "2001-01-01T10:00:00"},
        {"summary": "s", "description": "d", "start_time_iso": "2999-01-01T10:00:00"},
        {"summary": "s", "description": "d", "start_time_iso": FUTURE, "duration_minutes": 0},
        {"summary": "s", "description": "d", "start_time_iso": FUTURE, "duration_minutes": 100000},
    ],
)
def test_tool_argument_abuse_rejected(client, monkeypatch, security_log, kwargs):
    service = MagicMock(side_effect=AssertionError("no debe llegar a Google"))
    monkeypatch.setattr(cal, "get_calendar_service", service)
    result = cal.create_appointment(**kwargs)
    assert result == {"status": "error", "message": "Los datos de la cita no son válidos."}
    assert security_log()[-1]["event"] == "tool_args_rejected"


def _service_returning(event):
    service = MagicMock()
    service.events.return_value.insert.return_value.execute.return_value = event
    return service


def test_appointment_created_and_text_cleaned(client, monkeypatch):
    service = _service_returning({"id": "1", "htmlLink": "https://calendar.google.com/e/1"})
    monkeypatch.setattr(cal, "get_calendar_service", lambda: service)
    result = cal.create_appointment("Ci\x00ta", "Detalle", FUTURE)
    assert result["status"] == "success" and result["html_link"].startswith("https://")
    assert service.events.return_value.insert.call_args.kwargs["body"]["summary"] == "Cita"


def test_unsafe_link_from_provider_dropped(client, monkeypatch):
    service = _service_returning({"id": "1", "htmlLink": "javascript:alert(1)"})
    monkeypatch.setattr(cal, "get_calendar_service", lambda: service)
    assert cal.create_appointment("Cita", "Detalle", FUTURE)["html_link"] is None


def test_provider_errors_are_generic(client, monkeypatch):
    def fail():
        raise RuntimeError("detalle-interno")

    monkeypatch.setattr(cal, "get_calendar_service", fail)
    result = cal.create_appointment("Cita", "Detalle", FUTURE)
    assert result["status"] == "error" and "detalle-interno" not in result["message"]


def test_credentials_live_in_secrets_dir_only(client):
    assert get_settings().secrets_dir.name == "secrets"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://calendar.google.com/e/1", True),
        ("http://calendar.google.com", False),
        ("javascript:alert(1)", False),
        ("data:text/html,x", False),
        ("https://", False),
        ("https://user:pw@evil.example", False),
        (" https://a.example", False),
        ("https://a.example/\nx", False),
        (None, False),
    ],
)
def test_https_link_validation(url, expected):
    assert is_safe_https_url(url) is expected


def test_upload_saved_with_random_name_and_private_mode(tmp_path):
    path = save_upload(b"%PDF-1.7 datos", "../../etc/passwd.pdf", "application/pdf", tmp_path)
    assert path.parent == tmp_path.resolve() and path.suffix == ".pdf" and "passwd" not in path.name
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "data,name,mime",
    [
        (b"", "a.pdf", "application/pdf"),
        (b"x" * (MAX_UPLOAD_BYTES + 1), "a.txt", "text/plain"),
        (b"%PDF-", "a.exe", "application/pdf"),
        (b"%PDF-", "a.pdf.exe", "application/pdf"),
        (b"<script>", "a.pdf", "application/pdf"),
        (b"%PDF-", "a.pdf", "text/html"),
        (b"\x00\x01", "a.txt", "text/plain"),
        (b"\xff\xfe", "a.md", "text/markdown"),
    ],
)
def test_upload_rejections(tmp_path, data, name, mime):
    with pytest.raises(UploadRejected):
        save_upload(data, name, mime, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_upload_refuses_web_root():
    from app.core.uploads import WEB_ROOTS

    with pytest.raises(UploadRejected):
        save_upload(b"hola", "a.txt", "text/plain", WEB_ROOTS[0] / "static")
