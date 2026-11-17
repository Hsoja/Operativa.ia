"""Base de datos local (SQLite) - Operativa.ia

Todas las consultas usan marcadores `?`; nunca se construye SQL con datos de entrada.
Multi-tenant: toda tabla con datos de un negocio lleva `tenant_id` y toda consulta filtra por él.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import get_settings

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    business_type TEXT NOT NULL DEFAULT '',
    services TEXT NOT NULL DEFAULT '',
    hours TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    timezone TEXT NOT NULL DEFAULT 'America/Toronto',
    template TEXT NOT NULL DEFAULT 'general',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'staff')),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS users_tenant ON users (tenant_id);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_hash TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
    key_hash TEXT PRIMARY KEY,
    failures INTEGER NOT NULL,
    locked_until INTEGER NOT NULL,
    last_failure_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS llm_usage (
    day TEXT NOT NULL,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    client_hash TEXT NOT NULL,
    tokens INTEGER NOT NULL,
    PRIMARY KEY (day, tenant_id, client_hash)
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    channel TEXT NOT NULL DEFAULT 'web' CHECK (channel IN ('web', 'whatsapp')),
    created_at INTEGER NOT NULL,
    last_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_tenant ON conversations (tenant_id, last_at);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages (tenant_id, conversation_id, id);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    business TEXT NOT NULL DEFAULT '',
    topic TEXT NOT NULL,
    message TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('contact-form', 'sofia')),
    consent_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS leads_tenant ON leads (tenant_id, created_at);
"""

LEGACY_TABLE_QUERY = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'admin_users'"


class SchemaVersionError(RuntimeError):
    """La base de datos es de una versión anterior y no se puede usar sin migrarla."""


def _initialize(connection: sqlite3.Connection) -> None:
    """Crea el esquema si hace falta. Fail-closed ante bases de una versión anterior o desconocida."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == SCHEMA_VERSION:
        return
    if version == 0 and connection.execute(LEGACY_TABLE_QUERY).fetchone():
        raise SchemaVersionError(
            "La base de datos es de la versión sin multi-tenant. Respáldala, bórrala y crea "
            "los negocios y usuarios de nuevo con `python -m app.cli` (ver README)."
        )
    if version != 0:
        raise SchemaVersionError("Versión de base de datos desconocida.")
    connection.executescript(SCHEMA)
    connection.execute("PRAGMA user_version = 2")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        _initialize(connection)
        with connection:
            yield connection
    finally:
        connection.close()
    path.chmod(0o600)
