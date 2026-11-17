"""Base de datos local (SQLite) - Operativa.ia

Todas las consultas usan marcadores `?`; nunca se construye SQL con datos de entrada.
Multi-tenant: toda tabla con datos de un negocio lleva `tenant_id` y toda consulta filtra por él.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.config import get_settings

SCHEMA_VERSION = 6

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
CREATE TABLE IF NOT EXISTS tenant_channels (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('whatsapp')),
    external_id TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE (channel, external_id)
);
CREATE TABLE IF NOT EXISTS webhook_events (
    provider TEXT NOT NULL,
    event_id TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    PRIMARY KEY (provider, event_id)
);
CREATE TABLE IF NOT EXISTS coverage_areas (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('postal_prefix', 'city')),
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    UNIQUE (tenant_id, kind, value)
);
CREATE TABLE IF NOT EXISTS coverage_insurers (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    value TEXT NOT NULL,
    label TEXT NOT NULL,
    UNIQUE (tenant_id, value)
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL CHECK (duration_minutes BETWEEN 5 AND 480),
    deposit_cents INTEGER NOT NULL CHECK (deposit_cents BETWEEN 0 AND 100000),
    currency TEXT NOT NULL CHECK (currency IN ('cad', 'usd', 'mxn', 'eur')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (tenant_id, name)
);
CREATE TABLE IF NOT EXISTS business_hours (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    open_minute INTEGER NOT NULL CHECK (open_minute BETWEEN 0 AND 1439),
    close_minute INTEGER NOT NULL CHECK (close_minute BETWEEN 1 AND 1440),
    CHECK (open_minute < close_minute)
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id),
    starts_at INTEGER NOT NULL,
    ends_at INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending_payment', 'confirmed', 'cancelled', 'expired', 'needs_refund')),
    source TEXT NOT NULL CHECK (source IN ('web', 'panel')),
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL DEFAULT '',
    deposit_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    ref_hash TEXT NOT NULL UNIQUE,
    hold_expires_at INTEGER,
    stripe_session_id TEXT UNIQUE,
    created_at INTEGER NOT NULL,
    confirmed_at INTEGER,
    CHECK (starts_at < ends_at)
);
CREATE INDEX IF NOT EXISTS appointments_tenant ON appointments (tenant_id, starts_at);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    marketing_consent INTEGER NOT NULL DEFAULT 0 CHECK (marketing_consent IN (0, 1)),
    consent_at INTEGER,
    consent_source TEXT CHECK (consent_source IN ('contact-form', 'sofia', 'booking')),
    unsubscribed_at INTEGER,
    last_activity_at INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE (tenant_id, email)
);
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    inactive_days INTEGER NOT NULL,
    subject TEXT NOT NULL,
    recipients INTEGER NOT NULL DEFAULT 0,
    sent INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_sends (
    id INTEGER PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    unsubscribe_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at INTEGER
);
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
    if version not in (0, 2, 3, 4, 5):
        raise SchemaVersionError("Versión de base de datos desconocida.")
    # De v2 en adelante solo se agregan tablas (CREATE ... IF NOT EXISTS): el mismo script sirve de migración
    connection.executescript(SCHEMA)
    connection.execute("PRAGMA user_version = 6")


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
