"""Ayudas compartidas por las pruebas: negocios y usuarios de prueba sobre una base limpia."""

from app.core.db import get_connection
from app.services import auth, tenants

PASSWORD = "-".join(["contrasena", "de", "prueba", "1"])
ORIGIN = {"Origin": "http://localhost:8501"}
PROD = {"ENV": "production", "ALLOWED_ORIGINS": "https://app.example.com", "IP_HASH_SALT": "s" * 32}
TABLES = ("messages", "conversations", "leads", "llm_usage", "sessions", "login_attempts", "users", "tenants")


def reset_db() -> None:
    with get_connection() as db:
        for table in TABLES:
            db.execute(f"DELETE FROM {table}")  # nosec B608 - nombres fijos de la prueba


def make_tenant(slug: str = "demo", name: str = "Negocio Demo", **profile) -> int:
    return tenants.create_tenant(slug, tenants.TenantProfile(name=name, **profile))


def make_user(tenant_id: int, username: str, role: str = "owner", password: str = PASSWORD) -> int:
    return auth.create_user(tenant_id, username, password, role)


def csrf_headers(client) -> dict:
    token = client.get("/api/v1/admin/csrf").json()["csrf_token"]
    return {**ORIGIN, "X-CSRF-Token": token}


def login(client, username: str = "admin", password: str = PASSWORD):
    return client.post(
        "/api/v1/admin/login", json={"username": username, "password": password}, headers=csrf_headers(client)
    )
