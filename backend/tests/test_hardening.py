"""CORS, cabeceras, debug, tamaño del cuerpo y registro de seguridad (puntos 6, 14, 15, 18, 19)."""

import pytest

from app.core.config import get_settings
from app.core.logs import security_event

ORIGIN = "http://localhost:8501"
PROD = {"ENV": "production", "ALLOWED_ORIGINS": "https://app.example.com"}


def test_cors_allows_only_configured_origin(client):
    ok = client.options(
        "/api/v1/chat",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
    )
    assert ok.headers["access-control-allow-origin"] == ORIGIN
    bad = client.options(
        "/api/v1/chat",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in bad.headers
    assert "access-control-allow-origin" not in client.get("/", headers={"Origin": "https://evil.example"}).headers


def test_cors_rejects_disallowed_method_and_header(client):
    r = client.options(
        "/api/v1/chat",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "DELETE"},
    )
    assert r.status_code == 400
    r = client.options(
        "/api/v1/chat",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Evil",
        },
    )
    assert r.status_code == 400


@pytest.mark.parametrize("origins", ["*", "https://*.example.com"])
def test_wildcard_origins_refuse_to_start(make_client, origins):
    with pytest.raises(ValueError):
        make_client(ALLOWED_ORIGINS=origins)


def test_production_requires_https_origins(make_client):
    with pytest.raises(ValueError):
        make_client(ENV="production", ALLOWED_ORIGINS="http://app.example.com")


def test_security_headers_present(client):
    h = client.get("/").headers
    assert h["content-security-policy"].startswith("default-src 'none'")
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer"
    assert "camera=()" in h["permissions-policy"]
    assert h["cross-origin-opener-policy"] == "same-origin"
    assert h["cross-origin-resource-policy"] == "same-origin"
    assert h["x-request-id"]
    assert "strict-transport-security" not in h


def test_hsts_only_in_production(make_client):
    assert "max-age" in make_client(**PROD).get("/").headers["strict-transport-security"]


def test_headers_also_on_404_and_413(client):
    assert client.get("/no-existe").headers["x-content-type-options"] == "nosniff"
    big = client.post("/api/v1/chat", content=b"x" * 70000, headers={"Content-Type": "application/json"})
    assert big.status_code == 413
    assert big.headers["x-content-type-options"] == "nosniff"


def test_chunked_body_over_limit_rejected(client):
    def chunks():
        for _ in range(8):
            yield b"x" * 10000

    assert client.post("/api/v1/chat", content=chunks()).status_code == 413


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_disabled_in_production(make_client, path):
    assert make_client(**PROD).get(path).status_code == 404


def test_docs_available_in_development(client):
    assert client.get("/docs").status_code == 200


def test_unhandled_errors_are_generic(make_client):
    c = make_client(**PROD)

    @c.app.get("/boom")
    def boom():
        raise RuntimeError("detalle-interno-secreto")

    r = c.get("/boom")
    assert r.status_code == 500
    assert "detalle-interno-secreto" not in r.text
    assert "RuntimeError" not in r.text
    assert r.headers["x-content-type-options"] == "nosniff"


def test_log_is_json_without_sensitive_fields(client, security_log):
    security_event("login_failed", password="hunter2", email="a@b.c", ip="1.2.3.4", path="/x")
    record = security_log()[-1]
    assert record["event"] == "login_failed" and record["path"] == "/x"
    text = str(record)
    assert "hunter2" not in text and "a@b.c" not in text and "1.2.3.4" not in text


def test_log_escapes_newlines(client):
    security_event("x", path="/a\n{\"event\":\"falso\"}")
    lines = (get_settings().log_dir / "security.jsonl").read_text(encoding="utf-8").splitlines()
    assert not any(line.startswith('{"event":"falso"') for line in lines)


def test_alert_fires_at_threshold(make_client, security_log):
    make_client(ALERT_THRESHOLD="3")
    for _ in range(3):
        security_event("login_failed")
    alerts = [r for r in security_log() if r["event"] == "security_alert"]
    assert len(alerts) == 1 and alerts[0]["trigger"] == "login_failed"
