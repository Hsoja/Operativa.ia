# Seguridad de Operativa.ia

Proceso y controles del prototipo. El estado de cada punto de la lista está en [SECURITY_REPORT.md](../SECURITY_REPORT.md).

## Modelo de amenazas

| Activo | Amenaza | Control principal |
|---|---|---|
| Llave de Groq y presupuesto del LLM | Abuso de costos, robo de llave | Llave solo en el servidor, límites por IP, topes diarios de tokens |
| Cuenta de Google Calendar | Eventos falsos, lectura de citas | Permiso `calendar.events`, opción desactivada por defecto, panel con login |
| Cuenta de administrador | Fuerza bruta, robo de sesión, CSRF | Argon2id, bloqueo progresivo, cookies `HttpOnly`/`Secure`/`SameSite=Strict`, doble token CSRF |
| Instrucciones de Sofía | Inyección de prompt, filtración | Roles separados, registro de intentos, filtro de salida |
| Datos de citas en Google Calendar | Exposición en logs o pantalla | Logs sin datos personales, panel con texto plano |

**Límites de confianza:** navegador → proxy → API o panel → Groq y Google. Todo lo que envía el navegador, responde el modelo o devuelve un proveedor se trata como no confiable.

## Controles y dónde están

- **Configuración y arranque seguro:** `backend/app/core/config.py`. La app no arranca con comodines en CORS ni con orígenes `http://` en producción.
- **Cabeceras, tamaño del cuerpo y errores genéricos:** `backend/app/core/middleware.py`.
- **Registro de seguridad:** `backend/app/core/logs.py`. Escribe JSON en `backend/logs/security.jsonl`, con rotación de 5 MB y 5 copias. Avisa con `security_alert` al llegar a `ALERT_THRESHOLD` eventos del mismo tipo en 5 minutos.
- **Límites de peticiones:** `backend/app/core/ratelimit.py`. `X-Forwarded-For` solo se usa si la conexión viene de `TRUSTED_PROXIES`.
- **Autenticación:** `backend/app/services/auth.py`, `backend/app/api/admin.py`, `backend/app/api/deps.py` y `backend/app/cli.py`.
- **LLM:** `backend/app/services/llm_guard.py` y `backend/app/services/agent.py`.
- **Calendar:** `backend/app/services/calendar_service.py`.
- **Subidas futuras:** `backend/app/core/uploads.py`. Aún no hay ninguna ruta que lo use.
- **HTTPS:** `deploy/Caddyfile`.

## Cómo ejecutar las auditorías

Desde `backend/`, con el entorno activado e instalado con `requirements-dev.txt`:

```bash
python -m pytest -q
```

```bash
pip-audit -r requirements.lock
```

```bash
bandit -q -r app ../frontend/app.py --severity-level medium
```

```bash
bash ../scripts/scan_exposed_files.sh
```

Desde la raíz del proyecto:

```bash
gitleaks git . --log-opts=--all --redact=100 --no-banner
```

```bash
semgrep scan --config p/python --error --metrics=off backend/app frontend/app.py
```

`.github/workflows/security.yml` repite estos pasos, pero solo corre si el código se sube a GitHub.

## Rotación de llaves (acción manual)

Trata como comprometidos el cliente OAuth de Google y su token compartidos antes, y cualquier llave de Groq o Gemini pegada en un chat o captura. Limpiar Git no sustituye este paso.

1. **Google, permisos:** entra en <https://myaccount.google.com/permissions> y revoca el acceso de la app.
2. **Google, cliente OAuth:** en Google Cloud Console, en **APIs y servicios → Credenciales**, elimina el cliente OAuth y crea uno de tipo "Aplicación de escritorio".
3. **Google, archivos locales:** guarda el JSON nuevo como `secrets/credentials.json` y borra cualquier `token.json` anterior.
4. **Groq:** en la consola de Groq, elimina las llaves antiguas y crea una nueva. Guárdala en `.env` como `GROQ_API_KEY`.
5. **Gemini:** elimina las llaves antiguas en Google AI Studio. El código actual no usa Gemini, así que no hace falta crear otra.
6. **Comprobación:** revisa el uso reciente en cada proveedor para detectar consumos que no reconozcas.

## Respuesta a incidentes

1. **Contener:** detén los servicios o retira la ruta afectada del proxy.
2. **Cerrar accesos:** rota las llaves con la sección anterior. Para sacar a un administrador, usa `python -m app.cli reset-password --username USUARIO`, que invalida sus sesiones.
3. **Investigar:** busca en `backend/logs/security.jsonl` por `event` y `request_id`. Los usuarios y las IP aparecen seudonimizados, y `IP_HASH_SALT` permite correlacionarlos entre reinicios.
4. **Limpiar Git si hubo una fuga:** usa `git filter-repo` o BFG solo con una decisión explícita, porque reescribe el historial. Rota las llaves de todos modos.
5. **Cerrar:** añade una prueba que reproduzca el problema y anótalo en `SECURITY_REPORT.md`.

## Pendiente para versiones futuras

- **Recuperación de contraseña por web:** enlace de un solo uso, aleatorio, guardado como hash, con 15 minutos de validez, respuesta genérica y límite de peticiones. Requiere un sistema de correo.
- **Doble factor (MFA)** para administradores.
- **Roadmap del prompt:** migración a PostgreSQL, multi-tenant y contenedores.
