# Operativa.ia

Sistema de atención 24/7, agenda y seguimiento automático para PYMES de servicios. Este prototipo incluye a Sofía (IA) para una clínica dental de ejemplo y un panel de control con agenda opcional en Google Calendar.

## Estructura
- `backend/` API FastAPI (`app/main.py`, `app/api/`, `app/core/`, `app/services/`) y pruebas (`tests/`)
- `frontend/app.py` panel de control en Streamlit
- `deploy/Caddyfile` proxy HTTPS para producción
- `secrets/` (ignorada por git) aquí va `credentials.json` de Google
- `.env` (ignorado por git) se crea desde `.env.example`

## Puesta en marcha (local)
Requiere Python 3.13.

1. Copia `.env.example` como `.env` en la raíz y pega tu `GROQ_API_KEY`.
2. Prepara el backend (en Windows, activa con `.venv\Scripts\activate`):
   ```
   cd backend
   python3.13 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
3. Crea el administrador. No hay credenciales por defecto y la contraseña debe tener al menos 12 caracteres:
   ```
   python -m app.cli create-admin --username TU_USUARIO
   ```
4. Inicia la API:
   ```
   uvicorn app.main:app --reload --port 8000
   ```
5. En otra terminal, desde la raíz del proyecto y con el entorno activado, inicia el panel en http://localhost:8501:
   ```
   streamlit run frontend/app.py
   ```

Sin `GROQ_API_KEY`, la API responde con un mensaje genérico de "no disponible".

### Google Calendar (opcional)
1. En Google Cloud, habilita Calendar API y crea credenciales OAuth de tipo "Aplicación de escritorio".
2. Guarda el JSON como `secrets/credentials.json` y define `CALENDAR_ENABLED=true` en `.env`.
3. Autoriza la app una vez, desde `backend/`, con `python test_cal.py`.

## Seguridad

### En desarrollo
- Los secretos van solo en `.env` y `secrets/`. Nunca los subas a Git ni los pegues en un chat.
- Antes de hacer un commit, ejecuta `python -m pytest -q` desde `backend/`.
- Para cambiar una contraseña: `python -m app.cli reset-password --username TU_USUARIO`. Esto cierra todas las sesiones de ese usuario.

### En producción
Configura `ENV=production`, `ALLOWED_ORIGINS=https://tu-dominio` y `TRUSTED_PROXIES=127.0.0.1`. Después, inicia cada servicio sin `--reload`:

```
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --no-server-header
```

```
streamlit run frontend/app.py
```

```
DOMAIN=tu-dominio caddy run --config deploy/Caddyfile
```

Usa `--no-proxy-headers` porque la app ya resuelve la IP real por su cuenta, y solo si la conexión viene de `TRUSTED_PROXIES`.

Consulta [docs/SECURITY.md](docs/SECURITY.md) para el modelo de amenazas, la rotación de llaves y las auditorías, y [SECURITY_REPORT.md](SECURITY_REPORT.md) para el estado de cada control.
