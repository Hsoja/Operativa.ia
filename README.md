# Operativa.ia

Sistema de atención 24/7, agenda y seguimiento automático para PYMES de servicios. Esta web es el prototipo: Sofía (IA) explica los planes y agenda demos reales en Google Calendar.

## Estructura
- `backend/` API FastAPI (`app/main.py`, `api/endpoints.py`, `services/agent.py`, `services/calendar_service.py`)
- `frontend/` Vite + React + TypeScript + Tailwind + Framer Motion
- `secrets/` (ignorada por git) aquí va `credentials.json` de Google
- `.env` (ignorado por git) se crea desde `.env.example`

## Puesta en marcha (local)
1. `copy .env.example .env` y pega tu `GEMINI_API_KEY`.
2. Google Cloud: habilita Calendar API, crea credenciales OAuth tipo "Aplicación de escritorio" y guarda el JSON como `secrets/credentials.json`.
3. Backend:
   ```
   cd backend
   python -m venv .venv && .venv\Scripts\activate
   pip install -r requirements.txt
   python -m app.services.calendar_service   # solo la primera vez: abre el navegador para autorizar
   uvicorn app.main:app --reload --port 8000
   ```
4. Frontend (otra terminal): `cd frontend && npm install && npm run dev` → http://localhost:5173

## Seguridad
Secretos solo en `.env`/`secrets/`; CORS limitado a localhost; validación y límites en el API; límite de peticiones por IP; errores genéricos al cliente.
