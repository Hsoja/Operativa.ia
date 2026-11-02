"""Entorno aislado para las pruebas: base de datos y logs temporales, sin llaves reales."""

import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="operativa-tests-")
os.environ.update(
    ENV="development",
    ALLOWED_ORIGINS="http://localhost:8501",
    DB_PATH=str(Path(_tmp) / "test.db"),
    LOG_DIR=str(Path(_tmp) / "logs"),
    SECRETS_DIR=str(Path(_tmp) / "secrets"),
    GROQ_API_KEY="",
    CHAT_RATE="1000/minute",
    LOGIN_RATE="1000/minute",
    ADMIN_RATE="1000/minute",
    CALENDAR_ENABLED="false",
)
os.environ.pop("TRUSTED_PROXIES", None)

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture
def make_client(monkeypatch):
    """Crea un cliente con variables de entorno a medida, sin arrastrar estado entre pruebas."""

    def _make(**env):
        from app.main import create_app

        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(create_app(), raise_server_exceptions=False)

    yield _make
    monkeypatch.undo()
    get_settings.cache_clear()


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def security_log():
    def _read():
        import json

        path = get_settings().log_dir / "security.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    return _read
