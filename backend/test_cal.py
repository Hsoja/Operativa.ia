"""Script de Prueba de Autenticación con Google Calendar - Operativa.ia

Verifica la conexión con la API de Google Calendar e inicia la autenticación OAuth 2.0.
"""

import sys
from pathlib import Path

# Asegurar que Python encuentre los módulos dentro de la carpeta 'backend'
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from app.services.calendar_service import get_calendar_service

if __name__ == "__main__":
    print("Iniciando prueba de autenticación con Google Calendar...")
    service = get_calendar_service()
    print("¡Autenticación con Google Calendar exitosa!")