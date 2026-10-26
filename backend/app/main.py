from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.endpoints import router

# Inicialización de la aplicación FastAPI
app = FastAPI(
    title="Operativa.ia API",
    description="Motor de automatización operativa y atención 24/7 para PYMEs de servicios",
    version="0.1.0",
)

# Configuración de CORS para permitir conexiones desde el Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectar las rutas del agente conversacional
app.include_router(router)


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
    """Endpoint de estado del sistema."""
    return {"status": "healthy", "database": "connected"}
