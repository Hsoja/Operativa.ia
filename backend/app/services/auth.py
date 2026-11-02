"""Autenticación de administradores - Operativa.ia

Argon2id, bloqueo progresivo y sesiones del lado del servidor (solo se guarda el hash del token).
"""

import hashlib
import secrets
import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings
from app.core.db import get_connection
from app.core.logs import hash_identifier, security_event

# time_cost=3, 64 MiB, 4 hilos: perfil recomendado de bajo consumo (RFC 9106)
hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)
_DUMMY_HASH = hasher.hash(secrets.token_urlsafe(16))

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
LOCK_AFTER_FAILURES = 5
BASE_LOCK_SECONDS = 60
MAX_LOCK_SECONDS = 3600


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _validate_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(f"La contraseña debe tener entre {MIN_PASSWORD_LENGTH} y {MAX_PASSWORD_LENGTH} caracteres.")


def create_admin(username: str, password: str) -> None:
    _validate_password(password)
    with get_connection() as db:
        db.execute(
            "INSERT INTO admin_users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
            (username, hasher.hash(password), int(time.time())),
        )


def reset_password(username: str, password: str) -> bool:
    """Cambia la contraseña e invalida todas las sesiones de ese usuario."""
    _validate_password(password)
    with get_connection() as db:
        row = db.execute("SELECT id FROM admin_users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return False
        db.execute("UPDATE admin_users SET password_hash = ? WHERE id = ?", (hasher.hash(password), row["id"]))
        db.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
        db.execute("DELETE FROM login_attempts WHERE key_hash = ?", (hash_token(username.lower()),))
    return True


def _is_locked(db, key: str, now: int) -> bool:
    row = db.execute("SELECT locked_until FROM login_attempts WHERE key_hash = ?", (key,)).fetchone()
    return row is not None and row["locked_until"] > now


def _register_failure(db, key: str, now: int) -> None:
    row = db.execute("SELECT failures FROM login_attempts WHERE key_hash = ?", (key,)).fetchone()
    failures = (row["failures"] if row else 0) + 1
    locked_until = 0
    if failures >= LOCK_AFTER_FAILURES:
        seconds = min(BASE_LOCK_SECONDS * 2 ** (failures - LOCK_AFTER_FAILURES), MAX_LOCK_SECONDS)
        locked_until = now + seconds
    db.execute(
        "INSERT INTO login_attempts (key_hash, failures, locked_until) VALUES (?, ?, ?) "
        "ON CONFLICT (key_hash) DO UPDATE SET failures = excluded.failures, locked_until = excluded.locked_until",
        (key, failures, locked_until),
    )


def authenticate(username: str, password: str, client: str = "unknown") -> dict | None:
    """Devuelve el usuario si las credenciales son válidas.

    Los intentos se cuentan también para usuarios inexistentes y siempre se verifica un hash,
    de modo que ni la respuesta, ni el bloqueo, ni el tiempo revelan si el usuario existe.
    """
    key = hash_token(username.lower())
    now = int(time.time())
    with get_connection() as db:
        locked = _is_locked(db, key, now)
        row = db.execute("SELECT * FROM admin_users WHERE username = ?", (username,)).fetchone()

    stored = row["password_hash"] if row else _DUMMY_HASH
    try:
        valid = hasher.verify(stored, password) and row is not None and not locked
    except (VerificationError, InvalidHashError):
        valid = False

    with get_connection() as db:
        if not valid:
            # Durante el bloqueo no se acumulan fallos: evita alargarlo sin límite desde fuera
            if not locked:
                _register_failure(db, key, now)
            security_event(
                "login_failed", "WARNING", user=hash_identifier(username.lower()), client=hash_identifier(client), locked=locked
            )
            return None
        db.execute("DELETE FROM login_attempts WHERE key_hash = ?", (key,))
        if hasher.check_needs_rehash(stored):
            db.execute("UPDATE admin_users SET password_hash = ? WHERE id = ?", (hasher.hash(password), row["id"]))

    security_event("login_succeeded", user=hash_identifier(username.lower()), client=hash_identifier(client))
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


def create_session(user_id: int) -> tuple[str, str]:
    """Crea una sesión y devuelve (token de sesión, token CSRF)."""
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = int(time.time())
    expires_at = now + get_settings().session_ttl_minutes * 60
    with get_connection() as db:
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        db.execute(
            "INSERT INTO sessions (token_hash, user_id, csrf_hash, expires_at) VALUES (?, ?, ?, ?)",
            (hash_token(token), user_id, hash_token(csrf), expires_at),
        )
    return token, csrf


def get_session(token: str) -> dict | None:
    with get_connection() as db:
        row = db.execute(
            "SELECT s.csrf_hash, s.user_id, u.username, u.role FROM sessions s "
            "JOIN admin_users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ?",
            (hash_token(token), int(time.time())),
        ).fetchone()
    return dict(row) if row else None


def revoke_session(token: str) -> None:
    with get_connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
