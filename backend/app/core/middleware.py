"""Middleware de seguridad - Operativa.ia

ID de petición, cabeceras de seguridad, límite de tamaño del cuerpo y errores genéricos.
Se implementa como ASGI puro para cubrir también las respuestas de error.
"""

import json
import uuid

from app.core.config import get_settings
from app.core.logs import request_id_var, security_event

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
DOCS_PATHS = ("/docs", "/redoc")


def _security_headers(path: str) -> list[tuple[bytes, bytes]]:
    settings = get_settings()
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Cache-Control": "no-store",
    }
    # Swagger necesita su CDN; estas rutas solo existen fuera de producción
    if not path.startswith(DOCS_PATHS):
        headers["Content-Security-Policy"] = API_CSP
    if settings.is_production:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return [(k.lower().encode(), v.encode()) for k, v in headers.items()]


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = False

        async def send_with_headers(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.lower() not in {b"server", b"cache-control"}
                ]
                headers += _security_headers(scope["path"])
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        async def respond(status: int, detail: str):
            body = json.dumps({"detail": detail, "request_id": request_id}).encode()
            await send_with_headers(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})

        try:
            replay = await self._read_body(scope, receive)
            if replay is None:
                security_event("body_too_large", "WARNING", path=scope["path"])
                await respond(413, "Petición demasiado grande.")
                return
            await self.app(scope, replay, send_with_headers)
        except Exception as exc:
            security_event("unhandled_error", "ERROR", path=scope["path"], error=type(exc).__name__)
            if not started:
                await respond(500, "Error interno del servidor.")
        finally:
            request_id_var.reset(token)

    async def _read_body(self, scope, receive):
        """Lee el cuerpo sin pasar del límite; devuelve None si lo supera."""
        limit = get_settings().max_body_bytes
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                if not value.isdigit() or int(value) > limit:
                    return None
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            body.extend(message.get("body", b""))
            if len(body) > limit:
                return None
            if not message.get("more_body", False):
                break

        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        return replay
