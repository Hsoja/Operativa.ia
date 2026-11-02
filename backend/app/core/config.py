"""Configuración central - Operativa.ia

Lee las variables de entorno una sola vez y rechaza valores inseguros al arrancar.
"""

import ipaddress
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent

load_dotenv(dotenv_path=ROOT_DIR / ".env")

VALID_ENVS = {"development", "staging", "production"}
DEFAULT_ORIGINS = "http://localhost:8501,http://127.0.0.1:8501"


@dataclass(frozen=True)
class Settings:
    env: str
    allowed_origins: tuple[str, ...]
    trusted_proxies: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    db_path: Path
    log_dir: Path
    secrets_dir: Path
    max_body_bytes: int
    rate_limit_storage: str
    chat_rate: str
    login_rate: str
    admin_rate: str
    session_ttl_minutes: int
    llm_max_output_tokens: int
    llm_daily_tokens_per_ip: int
    llm_daily_tokens_global: int
    alert_threshold: int
    calendar_enabled: bool
    groq_api_key: str
    ip_hash_salt: str

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def session_cookie(self) -> str:
        return "__Host-session" if self.is_production else "session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-csrf" if self.is_production else "csrf"


def _parse_origins(raw: str, env: str) -> tuple[str, ...]:
    origins = tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
    for origin in origins:
        if "*" in origin:
            raise ValueError("ALLOWED_ORIGINS no admite comodines.")
        if not origin.startswith(("https://", "http://")):
            raise ValueError(f"Origen inválido en ALLOWED_ORIGINS: {origin}")
        if env == "production" and not origin.startswith("https://"):
            raise ValueError("En producción ALLOWED_ORIGINS solo admite https://.")
    return origins


def _parse_proxies(raw: str):
    return tuple(ipaddress.ip_network(p.strip()) for p in raw.split(",") if p.strip())


@lru_cache
def get_settings() -> Settings:
    env = os.getenv("ENV", "development").strip().lower()
    if env not in VALID_ENVS:
        raise ValueError(f"ENV debe ser uno de {sorted(VALID_ENVS)}.")

    return Settings(
        env=env,
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS), env),
        trusted_proxies=_parse_proxies(os.getenv("TRUSTED_PROXIES", "")),
        db_path=Path(os.getenv("DB_PATH", str(BACKEND_DIR / "data" / "operativa.db"))),
        log_dir=Path(os.getenv("LOG_DIR", str(BACKEND_DIR / "logs"))),
        secrets_dir=Path(os.getenv("SECRETS_DIR", str(ROOT_DIR / "secrets"))),
        max_body_bytes=int(os.getenv("MAX_BODY_BYTES", "65536")),
        rate_limit_storage=os.getenv("RATE_LIMIT_STORAGE", "memory://"),
        chat_rate=os.getenv("CHAT_RATE", "10/minute;100/day"),
        login_rate=os.getenv("LOGIN_RATE", "5/minute"),
        admin_rate=os.getenv("ADMIN_RATE", "60/minute"),
        session_ttl_minutes=int(os.getenv("SESSION_TTL_MINUTES", "30")),
        llm_max_output_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "500")),
        llm_daily_tokens_per_ip=int(os.getenv("LLM_DAILY_TOKENS_PER_IP", "20000")),
        llm_daily_tokens_global=int(os.getenv("LLM_DAILY_TOKENS_GLOBAL", "200000")),
        alert_threshold=int(os.getenv("ALERT_THRESHOLD", "20")),
        calendar_enabled=os.getenv("CALENDAR_ENABLED", "false").strip().lower() == "true",
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        ip_hash_salt=os.getenv("IP_HASH_SALT", ""),
    )
