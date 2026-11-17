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
| Datos de cada PYME (leads, conversaciones, equipo) | Que un negocio vea o cambie datos de otro (IDOR, `tenant_id` enviado por el cliente) | `tenant_id` en cada tabla y consulta, tomado solo de la sesión o del slug; prueba de aislamiento entre dos negocios |
| Permisos dentro de un negocio | Escalada de privilegios (staff que actúa como owner) | `require_roles` en cada ruta, matriz de roles probada, owners solo por CLI |
| Formulario y chat públicos | Spam, abuso de costo, datos personales sin consentimiento | Límites por IP, topes de tokens por negocio, trampa anti-bots, consentimiento obligatorio, retención de conversaciones |
| Webhook de WhatsApp | Mensajes falsos, repetidos o viejos; respuesta desde otro negocio; SSRF por `phone_number_id` | Firma `X-Hub-Signature-256` en tiempo constante, idempotencia por id, antigüedad máxima, negocio por número registrado, ids solo numéricos, sin redirecciones, apagado sin llaves |
| Calificación de coberturas | Que el LLM afirme una cobertura que no existe; herramientas no permitidas; pedir datos de salud | Resultado determinista con texto fijo, una sola herramienta de solo lectura en lista blanca, argumentos validados, sin campos de póliza ni salud, consultas no guardadas |
| Historial del chat | Turnos de la asistente inventados por el cliente | El historial vive en el servidor; el navegador solo tiene un identificador aleatorio guardado como hash |

**Límites de confianza:** navegador → proxy → API o panel → Groq y Google. Entre negocios también hay un límite: el slug público identifica al negocio, pero nunca da acceso a sus datos. Todo lo que envía el navegador, responde el modelo o devuelve un proveedor se trata como no confiable.

## Controles y dónde están

- **Configuración y arranque seguro:** `backend/app/core/config.py`. La app no arranca con comodines en CORS ni con orígenes `http://` en producción.
- **Cabeceras, tamaño del cuerpo y errores genéricos:** `backend/app/core/middleware.py`.
- **Registro de seguridad:** `backend/app/core/logs.py`. Escribe JSON en `backend/logs/security.jsonl`, con rotación de 5 MB y 5 copias. Avisa con `security_alert` al llegar a `ALERT_THRESHOLD` eventos del mismo tipo en 5 minutos.
- **Límites de peticiones:** `backend/app/core/ratelimit.py`. `X-Forwarded-For` solo se usa si la conexión viene de `TRUSTED_PROXIES`.
- **Autenticación:** `backend/app/services/auth.py`, `backend/app/api/admin.py`, `backend/app/api/deps.py` y `backend/app/cli.py`.
- **Multi-tenant y roles:** `backend/app/services/tenants.py`, `backend/app/api/deps.py` (`require_roles`, `public_tenant`). Matriz: staff ve; admin además edita el perfil y borra leads; owner además crea personal. Negocios y owners se crean solo por CLI.
- **WhatsApp:** `backend/app/services/whatsapp.py`, `channels.py` y `backend/app/api/webhooks.py`. El número del cliente no se guarda: la conversación se identifica con un HMAC del número (clave: App Secret). Rotar el App Secret inicia conversaciones nuevas.
- **Coberturas:** `backend/app/services/coverage.py`. Sofía solo puede pedir `check_coverage`; cualquier otra herramienta o argumento inválido se rechaza y se registra. Riesgo residual: si el modelo responde sin llamar la herramienta, podría sugerir una cobertura; la regla 8 del prompt lo prohíbe y la ruta `/coverage` da la respuesta oficial.
- **Datos personales:** `backend/app/services/leads.py` y `conversations.py`. Retención con `python -m app.cli purge` (`CONVERSATION_RETENTION_DAYS`); se recomienda ejecutarlo a diario con cron.
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
- **Roadmap:** migración a PostgreSQL con Row Level Security como segunda barrera del multi-tenant, y contenedores.
