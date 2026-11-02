"""Módulo de Integración con Google Calendar - Operativa.ia

Maneja la autenticación OAuth 2.0 y la creación automática de eventos/citas.
"""

from datetime import datetime, timedelta
from typing import Annotated

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pydantic import Field, ValidationError, field_validator

from app.core.config import get_settings
from app.core.logs import security_event
from app.core.validation import CleanStr, StrictModel, is_safe_https_url

# Permiso mínimo: leer y escribir eventos, sin administrar calendarios
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

MAX_DAYS_AHEAD = 365


class CalendarDisabledError(RuntimeError):
    """Google Calendar está desactivado (CALENDAR_ENABLED=false)."""


class AppointmentArgs(StrictModel):
    """Argumentos de una cita: pueden provenir de texto de un usuario."""

    summary: CleanStr(max_length=200)
    description: CleanStr(min_length=0, max_length=2000)
    start_time_iso: Annotated[str, Field(max_length=40)]
    duration_minutes: Annotated[int, Field(ge=5, le=480)] = 45

    @field_validator("start_time_iso")
    @classmethod
    def _start_in_valid_range(cls, value: str) -> str:
        start = datetime.fromisoformat(value)
        now = datetime.now(start.tzinfo)
        if not now <= start <= now + timedelta(days=MAX_DAYS_AHEAD):
            raise ValueError("La fecha de la cita está fuera de rango.")
        return value


def get_calendar_service():
    """Autentica al usuario y devuelve el servicio de la API de Google Calendar."""
    settings = get_settings()
    if not settings.calendar_enabled:
        raise CalendarDisabledError("Google Calendar está desactivado.")

    CREDENTIALS_PATH = settings.secrets_dir / "credentials.json"
    TOKEN_PATH = settings.secrets_dir / "token.json"
    creds = None

    # El archivo token.json almacena los tokens de acceso del usuario
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Si no hay credenciales válidas disponibles, solicitar inicio de sesión
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    "No se encontró credentials.json. "
                    "Asegúrate de haberlo guardado en la carpeta secrets/."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Guardar el token para futuras ejecuciones
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        TOKEN_PATH.chmod(0o600)

    return build("calendar", "v3", credentials=creds)


def create_appointment(
    summary: str,
    description: str,
    start_time_iso: str,
    duration_minutes: int = 45,
) -> dict:
    """Agenda una cita en el calendario principal de Google.

    Args:
        summary: Título del evento (ej. "Cita Limpieza Dental - María García").
        description: Detalles de contacto y tratamiento.
        start_time_iso: Fecha y hora de inicio en formato ISO (ej. "2026-10-28T10:00:00").
        duration_minutes: Duración de la cita en minutos.
    """
    try:
        args = AppointmentArgs(
            summary=summary,
            description=description,
            start_time_iso=start_time_iso,
            duration_minutes=duration_minutes,
        )
    except ValidationError as e:
        fields = [".".join(str(p) for p in err["loc"]) for err in e.errors()]
        security_event("tool_args_rejected", "WARNING", tool="create_appointment", fields=fields)
        return {"status": "error", "message": "Los datos de la cita no son válidos."}

    try:
        service = get_calendar_service()
        start_dt = datetime.fromisoformat(args.start_time_iso)
        end_dt = start_dt + timedelta(minutes=args.duration_minutes)

        event = {
            "summary": args.summary,
            "description": args.description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "America/Mexico_City",  # Ajusta según tu zona horaria
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "America/Mexico_City",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 24 * 60},  # Recordatorio 1 día antes
                    {"method": "popup", "minutes": 60},       # Recordatorio 1 hora antes
                ],
            },
        }

        created_event = (
            service.events().insert(calendarId="primary", body=event).execute()
        )

        html_link = created_event.get("htmlLink")
        return {
            "status": "success",
            "event_id": created_event.get("id"),
            "html_link": html_link if is_safe_https_url(html_link) else None,
            "summary": args.summary,
            "start": start_dt.strftime("%Y-%m-%d %H:%M"),
        }
    except CalendarDisabledError:
        return {"status": "disabled", "message": "La agenda de Google Calendar no está activada."}
    except Exception as e:
        security_event("calendar_error", "ERROR", error=type(e).__name__)
        return {"status": "error", "message": "No se pudo registrar la cita en Google Calendar."}
