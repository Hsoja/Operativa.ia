"""Módulo de Integración con Google Calendar - Operativa.ia

Maneja la autenticación OAuth 2.0 y la creación automática de eventos/citas.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Permisos requeridos para leer y escribir eventos en Google Calendar
SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Rutas de credenciales
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_PATH = BASE_DIR / "credentials.json"
TOKEN_PATH = BASE_DIR / "token.json"


def get_calendar_service():
    """Autentica al usuario y devuelve el servicio de la API de Google Calendar."""
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
                    f"No se encontró el archivo {CREDENTIALS_PATH}. "
                    "Asegúrate de haberlo guardado en la carpeta del proyecto."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Guardar el token para futuras ejecuciones
        with open(TOKEN_PATH, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

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
        service = get_calendar_service()
        start_dt = datetime.fromisoformat(start_time_iso)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": summary,
            "description": description,
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

        return {
            "status": "success",
            "event_id": created_event.get("id"),
            "html_link": created_event.get("htmlLink"),
            "summary": summary,
            "start": start_dt.strftime("%Y-%m-%d %H:%M"),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al agendar en Google Calendar: {str(e)}",
        }