"""Configuración central - Operativa.ia

Lee las variables de entorno una sola vez y rechaza valores inseguros al arrancar.
"""

import ipaddress
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BACKEND_DIR.parent

load_dotenv(dotenv_path=ROOT_DIR / ".env")

VALID_ENVS = {"development", "staging", "production"}
DEFAULT_ORIGINS = "http://localhost:8501,http://127.0.0.1:8501"
WHATSAPP_VARS = ("WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_ACCESS_TOKEN")
SMTP_VARS = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")


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
    llm_daily_tokens_per_tenant: int
    contact_rate: str
    browse_rate: str
    chat_max_messages: int
    conversation_retention_days: int
    alert_threshold: int
    calendar_enabled: bool
    groq_api_key: str
    ip_hash_salt: str
    whatsapp_app_secret: str
    whatsapp_verify_token: str
    whatsapp_access_token: str
    whatsapp_graph_version: str
    whatsapp_max_age_seconds: int
    stripe_secret_key: str
    stripe_webhook_secret: str
    public_site_url: str
    booking_hold_minutes: int
    booking_lead_minutes: int
    booking_days_ahead: int
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_from: str
    campaign_max_recipients: int

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.whatsapp_app_secret and self.whatsapp_verify_token and self.whatsapp_access_token)

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

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


def _positive_int(name: str, default: str) -> int:
    raw = os.getenv(name, default).strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError(f"{name} debe ser un entero positivo.")
    return int(raw)


def _parse_proxies(raw: str):
    return tuple(ipaddress.ip_network(p.strip()) for p in raw.split(",") if p.strip())


@lru_cache
def get_settings() -> Settings:
    env = os.getenv("ENV", "development").strip().lower()
    if env not in VALID_ENVS:
        raise ValueError(f"ENV debe ser uno de {sorted(VALID_ENVS)}.")

    ip_hash_salt = os.getenv("IP_HASH_SALT", "")
    whatsapp = {name: os.getenv(name, "").strip() for name in WHATSAPP_VARS}
    # Fail-closed: una integración a medio configurar no arranca (ni en desarrollo)
    if any(whatsapp.values()) and not all(whatsapp.values()):
        raise ValueError(f"WhatsApp requiere las tres variables: {', '.join(WHATSAPP_VARS)}.")
    if whatsapp["WHATSAPP_APP_SECRET"] and len(whatsapp["WHATSAPP_VERIFY_TOKEN"]) < 24:
        raise ValueError("WHATSAPP_VERIFY_TOKEN debe tener 24 caracteres o más.")
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    stripe_webhook = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    site_url = os.getenv("PUBLIC_SITE_URL", "").strip().rstrip("/")
    if bool(stripe_key) != bool(stripe_webhook):
        raise ValueError("Stripe requiere STRIPE_SECRET_KEY y STRIPE_WEBHOOK_SECRET juntas.")
    if stripe_key:
        if not stripe_key.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_")):
            raise ValueError("STRIPE_SECRET_KEY no tiene un formato válido.")
        if "_live_" in stripe_key and env != "production":
            raise ValueError("Una llave live de Stripe solo se acepta con ENV=production.")
        if not stripe_webhook.startswith("whsec_"):
            raise ValueError("STRIPE_WEBHOOK_SECRET debe empezar por whsec_.")
        if not site_url:
            raise ValueError("Con Stripe activo, PUBLIC_SITE_URL es obligatorio (URL de retorno del pago).")
    if site_url:
        _parse_origins(site_url, env)  # mismas reglas: sin comodines, https en producción
    smtp = {name: os.getenv(name, "").strip() for name in SMTP_VARS}
    if any(smtp.values()):
        if not (smtp["SMTP_HOST"] and smtp["SMTP_FROM"]):
            raise ValueError("El correo requiere al menos SMTP_HOST y SMTP_FROM.")
        if bool(smtp["SMTP_USERNAME"]) != bool(smtp["SMTP_PASSWORD"]):
            raise ValueError("SMTP_USERNAME y SMTP_PASSWORD van juntos.")
        if not re.fullmatch(r"[^@\s<>\r\n]+@[^@\s<>\r\n]+\.[A-Za-z]{2,}", smtp["SMTP_FROM"]):
            raise ValueError("SMTP_FROM debe ser una dirección de correo simple.")
        if not site_url:
            raise ValueError("Con correo activo, PUBLIC_SITE_URL es obligatorio (enlace de baja).")
    graph_version = os.getenv("WHATSAPP_GRAPH_VERSION", "v23.0").strip()
    if not re.fullmatch(r"v\d{1,3}\.\d{1,2}", graph_version):
        raise ValueError("WHATSAPP_GRAPH_VERSION debe tener la forma v23.0.")
    if env == "production" and len(ip_hash_salt) < 32:
        raise ValueError("En producción IP_HASH_SALT es obligatorio (32 caracteres o más).")

    return Settings(
        env=env,
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS", DEFAULT_ORIGINS), env),
        trusted_proxies=_parse_proxies(os.getenv("TRUSTED_PROXIES", "")),
        db_path=Path(os.getenv("DB_PATH", str(BACKEND_DIR / "data" / "operativa.db"))),
        log_dir=Path(os.getenv("LOG_DIR", str(BACKEND_DIR / "logs"))),
        secrets_dir=Path(os.getenv("SECRETS_DIR", str(ROOT_DIR / "secrets"))),
        max_body_bytes=_positive_int("MAX_BODY_BYTES", "65536"),
        rate_limit_storage=os.getenv("RATE_LIMIT_STORAGE", "memory://"),
        chat_rate=os.getenv("CHAT_RATE", "10/minute;100/day"),
        login_rate=os.getenv("LOGIN_RATE", "5/minute"),
        admin_rate=os.getenv("ADMIN_RATE", "60/minute"),
        session_ttl_minutes=_positive_int("SESSION_TTL_MINUTES", "30"),
        llm_max_output_tokens=_positive_int("LLM_MAX_OUTPUT_TOKENS", "500"),
        llm_daily_tokens_per_ip=_positive_int("LLM_DAILY_TOKENS_PER_IP", "20000"),
        llm_daily_tokens_global=_positive_int("LLM_DAILY_TOKENS_GLOBAL", "200000"),
        llm_daily_tokens_per_tenant=_positive_int("LLM_DAILY_TOKENS_PER_TENANT", "100000"),
        contact_rate=os.getenv("CONTACT_RATE", "5/minute;20/day"),
        browse_rate=os.getenv("BROWSE_RATE", "60/minute;1000/day"),
        chat_max_messages=_positive_int("CHAT_MAX_MESSAGES", "60"),
        conversation_retention_days=_positive_int("CONVERSATION_RETENTION_DAYS", "90"),
        alert_threshold=_positive_int("ALERT_THRESHOLD", "20"),
        calendar_enabled=os.getenv("CALENDAR_ENABLED", "false").strip().lower() == "true",
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        ip_hash_salt=ip_hash_salt,
        whatsapp_app_secret=whatsapp["WHATSAPP_APP_SECRET"],
        whatsapp_verify_token=whatsapp["WHATSAPP_VERIFY_TOKEN"],
        whatsapp_access_token=whatsapp["WHATSAPP_ACCESS_TOKEN"],
        whatsapp_graph_version=graph_version,
        whatsapp_max_age_seconds=_positive_int("WHATSAPP_MAX_AGE_SECONDS", "3600"),
        stripe_secret_key=stripe_key,
        stripe_webhook_secret=stripe_webhook,
        public_site_url=site_url,
        booking_hold_minutes=_positive_int("BOOKING_HOLD_MINUTES", "35"),
        booking_lead_minutes=_positive_int("BOOKING_LEAD_MINUTES", "60"),
        booking_days_ahead=_positive_int("BOOKING_DAYS_AHEAD", "60"),
        smtp_host=smtp["SMTP_HOST"],
        smtp_port=_positive_int("SMTP_PORT", "587"),
        smtp_username=smtp["SMTP_USERNAME"],
        smtp_password=smtp["SMTP_PASSWORD"],
        smtp_from=smtp["SMTP_FROM"],
        campaign_max_recipients=_positive_int("CAMPAIGN_MAX_RECIPIENTS", "500"),
    )
