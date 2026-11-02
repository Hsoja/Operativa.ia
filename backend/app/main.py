from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.endpoints import router
from app.core.config import get_settings
from app.core.db import get_connection
from app.core.logs import configure_logging, security_event
from app.core.middleware import SecurityMiddleware
from app.core.ratelimit import limiter, rate_limit_handler


async def _validation_handler(request: Request, exc: RequestValidationError):
    """Responde sin repetir la entrada del cliente y registra solo los campos afectados."""
    fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
    security_event("validation_rejected", "WARNING", path=request.url.path, fields=fields)
    return JSONResponse(status_code=422, content={"detail": "Datos inválidos.", "fields": fields})


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    # Inicialización de la aplicación FastAPI
    docs_enabled = settings.env == "development"
    app = FastAPI(
        title="Operativa.ia API",
        description="Motor de automatización operativa y atención 24/7 para PYMEs de servicios",
        version="0.1.0",
        debug=False,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)

    # Configuración de CORS: solo orígenes explícitos, métodos y cabeceras mínimos
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    # Se agrega al final para quedar por fuera de CORS y cubrir todas las respuestas
    app.add_middleware(SecurityMiddleware)

    # Conectar las rutas del agente conversacional
    app.include_router(router)
    app.include_router(admin_router)

    @app.get("/")
    def read_root():
        """Ruta raíz para verificar que el servidor está en línea."""
        return {
            "system": "Operativa.ia API",
            "status": "online",
            "message": "Bienvenido al motor de automatización 24/7",
        }

    @app.get("/health")
    def health_check():
        """Endpoint de estado del sistema: comprueba de verdad la base de datos."""
        try:
            with get_connection() as db:
                db.execute("SELECT 1")
        except Exception as exc:
            security_event("health_db_failed", "ERROR", error=type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "unhealthy", "database": "unavailable"})
        return {"status": "healthy", "database": "connected"}

    return app


app = create_app()
