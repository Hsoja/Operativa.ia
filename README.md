# Operativa.ia

**24/7 AI customer service, scheduling and follow-up for small service businesses.**

Operativa.ia answers customers around the clock, books appointments and follows up automatically, so small businesses (clinics, salons, workshops) never miss a client. This prototype includes **Sofía**, an AI assistant set up for a sample dental clinic, a public website and an admin dashboard with optional Google Calendar sync.

> 🚧 Work in progress — built and improved every week.

## Features

- 🤖 **AI assistant (Sofía)** that answers customer questions using the business's own information
- 📅 **Appointment scheduling** with optional Google Calendar integration
- 📊 **Admin dashboard** to manage conversations, leads and bookings
- 🌐 **Public website** with chat widget and contact form
- 🔐 **Security first**: hashed passwords (Argon2), rate limiting, strict CORS, HTTPS proxy and automated security tests

## Tech stack

| Layer | Technologies |
| --- | --- |
| Backend | Python 3.13, FastAPI, Pydantic, Uvicorn |
| AI | Groq API (LLM) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Motion |
| Dashboard | Streamlit |
| Integrations | Google Calendar API (OAuth) |
| Security & QA | Argon2, SlowAPI, pytest, Vitest, Bandit, pip-audit, Gitleaks |
| Deploy | Caddy (HTTPS reverse proxy) |

## Project structure

```
backend/    FastAPI API (app/main.py, api/, core/, services/) and tests
frontend/   Public website (React + Vite) and Streamlit dashboard (app.py)
deploy/     Caddyfile for production HTTPS
docs/       Architecture, competitive analysis and security model
```

## Run it locally

**Requirements:** Python 3.13 and Node 20+.

1. Copy `.env.example` to `.env` and add your `GROQ_API_KEY`.
2. Set up the backend:
   ```bash
   cd backend
   python3.13 -m venv .venv && source .venv/bin/activate
   pip install -r requirements-dev.txt
   python -m app.cli create-admin --username YOUR_USER
   uvicorn app.main:app --reload --port 8000
   ```
3. Start the dashboard (from the project root, with the venv active):
   ```bash
   streamlit run frontend/app.py   # http://localhost:8501
   ```
4. Start the website:
   ```bash
   cd frontend
   npm install
   npm run dev                     # http://localhost:5173
   ```

Run the tests with `python -m pytest -q` (backend) and `npm test` (frontend).

## Documentation

- [Architecture](docs/arquitectura.md)
- [Security model](docs/SECURITY.md) and [security report](SECURITY_REPORT.md)

## Author

Built by [Hsoja](https://github.com/Hsoja).
