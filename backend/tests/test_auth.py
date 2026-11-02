"""Login, Argon2id, bloqueo, sesiones, CSRF y CLI (puntos 1, 3, 8, 13, 16, 17)."""

import time

import pytest
from argon2 import PasswordHasher

from app import cli
from app.core.config import get_settings
from app.core.db import get_connection
from app.core.ratelimit import limiter
from app.services import auth

ORIGIN = {"Origin": "http://localhost:8501"}
PASSWORD = "-".join(["contrasena", "de", "prueba", "1"])


@pytest.fixture(autouse=True)
def clean_db(client):
    limiter.reset()
    with get_connection() as db:
        for table in ("sessions", "login_attempts", "admin_users"):
            db.execute(f"DELETE FROM {table}")  # nosec B608 - nombres fijos de la prueba
    auth.create_admin("admin", PASSWORD)


def csrf_headers(c):
    token = c.get("/api/v1/admin/csrf").json()["csrf_token"]
    return {**ORIGIN, "X-CSRF-Token": token}


def do_login(c, username="admin", password=PASSWORD):
    return c.post("/api/v1/admin/login", json={"username": username, "password": password}, headers=csrf_headers(c))


def test_password_stored_as_argon2id():
    with get_connection() as db:
        stored = db.execute("SELECT password_hash FROM admin_users").fetchone()["password_hash"]
    assert stored.startswith("$argon2id$") and PASSWORD not in stored


def test_rehash_on_login_when_params_change(client):
    weak = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    with get_connection() as db:
        db.execute("UPDATE admin_users SET password_hash = ?", (weak,))
    assert do_login(client).status_code == 200
    with get_connection() as db:
        stored = db.execute("SELECT password_hash FROM admin_users").fetchone()["password_hash"]
    assert stored != weak and "m=65536,t=3,p=4" in stored


def test_no_default_admin_exists_on_fresh_db():
    with get_connection() as db:
        db.execute("DELETE FROM admin_users")
    assert auth.authenticate("admin", "admin") is None


def test_login_and_me(client):
    r = do_login(client)
    assert r.status_code == 200 and r.json()["username"] == "admin"
    assert client.get("/api/v1/admin/me").json() == {"username": "admin", "role": "admin"}


def test_admin_routes_require_session(client):
    assert client.get("/api/v1/admin/me").status_code == 401
    assert client.get("/api/v1/agent/prompt").status_code == 401
    do_login(client)
    assert "Sofía" in client.get("/api/v1/agent/prompt").json()["system_prompt"]


def test_no_user_enumeration(client):
    wrong = do_login(client, password="incorrecta-incorrecta")
    missing = do_login(client, username="no-existe")
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_unknown_user_still_verifies_a_hash(monkeypatch):
    calls = []
    real = auth.hasher.verify
    monkeypatch.setattr(auth, "hasher", type("H", (), {
        "verify": lambda self, h, p: calls.append(h) or real(h, p),
        "check_needs_rehash": lambda self, h: False,
    })())
    auth.authenticate("no-existe", "x")
    assert calls == [auth._DUMMY_HASH]


def test_lockout_blocks_even_correct_password(client):
    for _ in range(auth.LOCK_AFTER_FAILURES):
        assert do_login(client, password="incorrecta-incorrecta").status_code == 401
    assert do_login(client).status_code == 401


def test_lock_response_same_for_unknown_user(client):
    for _ in range(auth.LOCK_AFTER_FAILURES + 1):
        r = do_login(client, username="no-existe")
    assert r.status_code == 401 and r.json()["detail"] == "Credenciales inválidas."


def test_lockout_backoff_grows_and_expires(client):
    key = auth.hash_token("admin")
    for _ in range(auth.LOCK_AFTER_FAILURES):
        do_login(client, password="incorrecta-incorrecta")
    with get_connection() as db:
        first = db.execute("SELECT locked_until FROM login_attempts WHERE key_hash = ?", (key,)).fetchone()[0]
        db.execute("UPDATE login_attempts SET locked_until = 0 WHERE key_hash = ?", (key,))
    assert first - time.time() == pytest.approx(auth.BASE_LOCK_SECONDS, abs=5)
    do_login(client, password="incorrecta-incorrecta")
    with get_connection() as db:
        second = db.execute("SELECT locked_until FROM login_attempts WHERE key_hash = ?", (key,)).fetchone()[0]
        db.execute("UPDATE login_attempts SET locked_until = 0 WHERE key_hash = ?", (key,))
    assert second - time.time() == pytest.approx(auth.BASE_LOCK_SECONDS * 2, abs=5)
    assert do_login(client).status_code == 200


def test_login_rate_limit(make_client):
    c = make_client(LOGIN_RATE="2/minute")
    headers = csrf_headers(c)
    body = {"username": "admin", "password": "x" * 20}
    codes = [c.post("/api/v1/admin/login", json=body, headers=headers).status_code for _ in range(3)]
    assert codes == [401, 401, 429]


@pytest.mark.parametrize(
    "body",
    [
        {"username": "admin"},
        {"username": "a", "password": "x"},
        {"username": "admin' OR '1'='1", "password": "x"},
        {"username": "admin", "password": "x" * 257},
        {"username": "admin", "password": "x", "role": "admin"},
    ],
)
def test_login_validation(client, body):
    assert client.post("/api/v1/admin/login", json=body, headers=csrf_headers(client)).status_code == 422


@pytest.mark.parametrize(
    "payload",
    ["' OR '1'='1", "admin'; DROP TABLE admin_users;--", '" OR ""="', "x' UNION SELECT 1,2,3,4,5--"],
)
def test_sql_injection_payloads_are_inert(payload):
    assert auth.authenticate(payload, payload) is None
    assert auth.reset_password(payload, "x" * 20) is False
    assert auth.get_session(payload) is None
    with get_connection() as db:
        assert db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0] == 1


def test_login_requires_csrf_token(client):
    body = {"username": "admin", "password": PASSWORD}
    assert client.post("/api/v1/admin/login", json=body, headers=ORIGIN).status_code == 403


def test_csrf_rejects_mismatch_and_bad_origin(client, security_log):
    body = {"username": "admin", "password": PASSWORD}
    good = csrf_headers(client)
    assert client.post("/api/v1/admin/login", json=body, headers={**good, "X-CSRF-Token": "otro"}).status_code == 403
    assert client.post("/api/v1/admin/login", json=body, headers={**good, "Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/v1/admin/login", json=body, headers={"X-CSRF-Token": good["X-CSRF-Token"]}).status_code == 403
    assert security_log()[-1]["event"] == "csrf_rejected"


def test_csrf_accepts_allowed_referer(client):
    token = csrf_headers(client)["X-CSRF-Token"]
    r = client.post(
        "/api/v1/admin/login",
        json={"username": "admin", "password": PASSWORD},
        headers={"X-CSRF-Token": token, "Referer": "http://localhost:8501/login"},
    )
    assert r.status_code == 200


def test_logout_requires_token_bound_to_session(client):
    do_login(client)
    # Doble envío correcto, pero con un token que no pertenece a esta sesión
    other = client.get("/api/v1/admin/csrf").json()["csrf_token"]
    r = client.post("/api/v1/admin/logout", headers={**ORIGIN, "X-CSRF-Token": other})
    assert r.status_code == 403
    assert client.get("/api/v1/admin/me").status_code == 200


def test_logout_invalidates_on_server(client):
    csrf = do_login(client).json()["csrf_token"]
    stolen = client.cookies.get("session")
    assert client.post("/api/v1/admin/logout", headers={**ORIGIN, "X-CSRF-Token": csrf}).status_code == 200
    client.cookies.clear()
    client.cookies.set("session", stolen)
    assert client.get("/api/v1/admin/me").status_code == 401


def test_session_token_stored_hashed_and_rotated_on_login(client):
    do_login(client)
    first = client.cookies.get("session")
    with get_connection() as db:
        stored = db.execute("SELECT token_hash FROM sessions").fetchall()
    assert [r["token_hash"] for r in stored] == [auth.hash_token(first)]
    do_login(client)
    assert client.cookies.get("session") != first
    assert auth.get_session(first) is None


def test_session_expires(client):
    do_login(client)
    with get_connection() as db:
        db.execute("UPDATE sessions SET expires_at = 1")
    assert client.get("/api/v1/admin/me").status_code == 401


def test_cookie_flags_in_production(make_client):
    c = make_client(ENV="production", ALLOWED_ORIGINS="https://app.example.com")
    c.base_url = "https://testserver"
    r = c.get("/api/v1/admin/csrf")
    token = r.json()["csrf_token"]
    assert "__Host-csrf=" in r.headers["set-cookie"] and "Secure" in r.headers["set-cookie"]
    r = c.post(
        "/api/v1/admin/login",
        json={"username": "admin", "password": PASSWORD},
        headers={"Origin": "https://app.example.com", "X-CSRF-Token": token},
    )
    assert r.status_code == 200
    cookies = r.headers.get_list("set-cookie")
    session = next(v for v in cookies if v.startswith("__Host-session="))
    for flag in ("HttpOnly", "Secure", "SameSite=strict", "Path=/", "Max-Age=1800"):
        assert flag in session


def _answers(monkeypatch, *answers):
    values = iter(answers)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(values))


def test_cli_create_admin(monkeypatch):
    _answers(monkeypatch, "otra-clave-larga-1", "otra-clave-larga-1")
    assert cli.main(["create-admin", "--username", "segundo"]) == 0
    assert auth.authenticate("segundo", "otra-clave-larga-1")


def test_cli_rejects_short_mismatch_and_duplicate(monkeypatch):
    _answers(monkeypatch, "corta", "corta")
    assert cli.main(["create-admin", "--username", "tercero"]) == 2
    _answers(monkeypatch, "otra-clave-larga-1", "distinta-clave-larga")
    assert cli.main(["create-admin", "--username", "tercero"]) == 2
    _answers(monkeypatch, "otra-clave-larga-1", "otra-clave-larga-1")
    assert cli.main(["create-admin", "--username", "admin"]) == 1


def test_cli_reset_password_invalidates_sessions_and_unlocks(client, monkeypatch):
    do_login(client)
    token = client.cookies.get("session")
    _answers(monkeypatch, "clave-nueva-larga-1", "clave-nueva-larga-1")
    assert cli.main(["reset-password", "--username", "admin"]) == 0
    assert auth.get_session(token) is None
    assert auth.authenticate("admin", PASSWORD) is None
    assert auth.authenticate("admin", "clave-nueva-larga-1")


def test_cli_reset_unknown_user(monkeypatch):
    _answers(monkeypatch, "clave-nueva-larga-1", "clave-nueva-larga-1")
    assert cli.main(["reset-password", "--username", "nadie"]) == 1


def test_settings_cookie_names_dev():
    assert get_settings().session_cookie == "session"
