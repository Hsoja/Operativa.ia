# Reporte de seguridad de Operativa.ia

**Rama:** `security-hardening`, solo en local. **Alcance:** el código de este repositorio, es decir, API FastAPI con Sofía para una clínica dental y panel de Streamlit.

El repositorio no contiene la web React, `/contact`, los leads en SQLite, el modo FAQ, Gemini ni las herramientas de Sofía que describe el encargo. Lo que depende de esas partes aparece como "no aplica" (N/A). Para ese código, esta revisión no aporta ninguna garantía.

## Actualización del 2 de noviembre de 2026: sitio web nuevo

Se agregó un sitio React en `frontend/`, así que ya existe un paquete JS que revisar. Esta parte no cambia el backend. Los puntos 2, 5, 10 y 15 de la tabla siguen describiendo el estado anterior para el backend y el panel; esto es lo nuevo para el sitio:

| Punto | Estado en el sitio | Evidencia |
|---|---|---|
| 2. Llaves en el navegador | Sin secretos ni variables `VITE_` | `tests/test_static_checks.py` revisa `frontend/dist` después de compilar |
| 5. XSS | Sin `dangerouslySetInnerHTML`; el chat y los formularios se muestran como texto | Prueba en navegador con una carga XSS |
| 10. Dependencias | `package-lock.json` y Dependabot para npm | `npm audit` sin vulnerabilidades |
| 15. Cabeceras | **Pendiente:** `deploy/Caddyfile` aún no sirve este sitio ni le aplica una CSP | Se resuelve al desplegarlo |

**Riesgos nuevos:**
- **Datos en el navegador:** los formularios guardan nombre, correo y mensaje sin cifrar en `localStorage`. Es temporal y la Política de Privacidad lo explica, con un botón para borrarlos. Al conectar la API, hay que migrar a `POST /api/v1/contact` con la validación de servidor del punto 4.
- **Sofía no usa IA todavía:** responde con reglas locales. Los controles de LLM de esta auditoría se aplicarán cuando el chat use la API, y antes hay que cambiar el prompt de clínica dental del backend.
- **Textos legales:** los Términos y la Política son borradores sin revisión legal.

## Resultado

| Comprobación | Resultado |
|---|---|
| Pruebas (`pytest`) | 153 correctas |
| `pip-audit` sobre `requirements.lock` | Sin vulnerabilidades conocidas |
| `bandit` | Sin hallazgos |
| `semgrep` con `p/python` | Sin hallazgos |
| `gitleaks` en todo el historial | Sin fugas. Se ignoran 2 falsos positivos: contraseñas ficticias de pruebas |
| `caddy validate` | Configuración válida. No se probó TLS real |
| API real con `ENV=production` | Correcta: cabeceras, cookies, CSRF, login, logout, 413, 429, 404 en `/docs` |
| Panel en navegador real | Correcto: login, chat y carga XSS mostrada como texto |

**No verificado:**
- **GitHub Actions:** nunca se ejecutó porque el proyecto no se sube. Docker estaba apagado, así que tampoco se probaron las imágenes de `gitleaks` y `semgrep` del flujo.
- **Groq real:** las pruebas usan un sustituto porque no hay llave.
- **Google Calendar real:** no hay credenciales. Si reutilizas un token anterior, vuelve a autorizar la app.
- **Redis:** el almacenamiento compartido de límites no se probó y su paquete no está instalado.

## Los 28 puntos

| # | Punto | Estado | Evidencia | Riesgo residual |
|---|---|---|---|---|
| 1 | Autenticación | Hecho | `services/auth.py`, `api/admin.py`, `cli.py`, `tests/test_auth.py`, `tests/test_panel.py` | Sin MFA. Un atacante puede bloquear temporalmente al administrador si conoce su usuario |
| 2 | Llaves fuera del navegador | Hecho | `tests/test_static_checks.py`. No hay paquete JS: la llave solo se usa en el servidor | La revisión del paquete solo actuará si algún día existe `frontend/dist` |
| 3 | Argon2id | Hecho | `services/auth.py`, prueba de rehash en `tests/test_auth.py` | Ninguno destacable |
| 4 | Validación en servidor | Hecho, con N/A parcial | `core/validation.py`, `tests/test_chat_llm.py`, `tests/test_calendar_uploads.py`. Correo: N/A, ningún campo lo pide. Roles: el enum es una restricción `CHECK` en la base de datos, con un único rol | Ninguno destacable |
| 5 | XSS | Hecho | Panel con `st.text`, `is_safe_https_url`, prueba en navegador. `dangerouslySetInnerHTML`: N/A, no hay React | CSP limitada en el panel, ver punto 15 |
| 6 | Registro y monitoreo | Hecho | `core/logs.py`, `tests/test_hardening.py`, log revisado tras la prueba real | La alerta solo escribe en el log: nadie recibe un aviso |
| 7 | Consultas parametrizadas | Hecho | `core/db.py`, cargas SQLi en `tests/test_auth.py`, revisión AST en `tests/test_static_checks.py` | Ninguno destacable |
| 8 | CSRF | Hecho | `api/deps.py`, `tests/test_auth.py`. `/chat` no usa cookies. El panel usa la protección XSRF de Streamlit | Ninguno destacable |
| 9 | Precios y pagos | Hecho, con N/A parcial | `services/llm_guard.py`, `tests/test_chat_llm.py`. No hay fuente de planes ni pagos: N/A | El filtro usa expresiones regulares y puede fallar con formatos raros, como un precio escrito en palabras |
| 10 | Dependencias | Hecho, con N/A parcial | `requirements.txt`, `requirements.lock`, `.github/dependabot.yml`. `npm audit`: N/A, sin `package.json` | Dependabot solo actúa si el código está en GitHub |
| 11 | Secretos en el historial | Hecho | `gitleaks` sobre todas las ramas locales y remotas clonadas | No cubre el código ni las llaves que estén fuera de este repositorio |
| 12 | HTTPS | Configurado, sin desplegar | `deploy/Caddyfile`, `caddy validate` | TLS, redirección y certificado reales sin probar: no hay dominio |
| 13 | Límites de peticiones | Hecho | `core/ratelimit.py`, `tests/test_chat_llm.py`, `tests/test_auth.py`. `/chat` limita por IP porque no tiene sesión | En memoria, cada proceso cuenta por separado. Redis sin probar |
| 14 | CORS | Hecho | `main.py`, `core/config.py`, `tests/test_hardening.py` | Ninguno destacable |
| 15 | Cabeceras | Hecho en la API, parcial en el panel | `core/middleware.py`, `tests/test_hardening.py`, `deploy/Caddyfile` | El panel solo define `frame-ancestors` en el proxy: Streamlit controla sus propios scripts y no se probó una CSP estricta. La lista de fuentes es N/A sin la web React |
| 16 | Cookies de sesión | Hecho en la API | `api/admin.py`, `tests/test_auth.py`, prueba real | El panel usa la sesión de Streamlit más un tiempo de expiración propio, sin estas cookies |
| 17 | Recuperación de contraseña | CLI hecha | `cli.py reset-password`. El flujo web queda en `docs/SECURITY.md` | Sin recuperación por correo. No hay enlaces que puedan caducar |
| 18 | Subida de archivos | Hecho, sin rutas | `core/uploads.py`, `tests/test_calendar_uploads.py`, límite global en `core/middleware.py` | Sin análisis antivirus. La lista solo admite PDF, TXT y MD |
| 19 | Debug en producción | Hecho | `main.py`, `tests/test_hardening.py`, prueba real | `--reload` se controla por documentación, no por código |
| 20 | Archivos expuestos | Hecho | `scripts/scan_exposed_files.sh`, `.gitignore`, prueba real con 404 en `/.env` y `/.git/config`. `.env` ya no se rastrea | Ninguno destacable |
| 21 | Limpiar el historial | N/A | `gitleaks` limpio. El `.env` del commit `2db97e7` pesa 0 bytes, así que no se reescribió nada | Ninguno en este repositorio |
| 22 | Revocar llaves | Lista entregada, **acción tuya pendiente** | `docs/SECURITY.md`, sección de rotación | **Alto hasta que completes la rotación** |
| 23 | Auditoría | Hecho | Sección de mapeo más abajo | Revisión de código y pruebas, sin pentest externo |
| 24 | Reporte de vulnerabilidades | Hecho | Sección de hallazgos más abajo | Ninguno destacable |
| 25 | Pruebas de los arreglos | Hecho en local | `backend/tests/`, `.github/workflows/security.yml`. Pruebas de frontend: `tests/test_panel.py`, sin compilación porque no hay paquete JS | CI sin ejecutar |
| 26 | Documentar el proceso | Hecho | `docs/SECURITY.md` | Ninguno destacable |
| 27 | Reporte final | Hecho | Este archivo | Ninguno destacable |
| 28 | Sección en el README | Hecho | `README.md` | Ninguno destacable |

## Hallazgos

| ID | Severidad | Hallazgo | Archivo | Corrección | Estado |
|---|---|---|---|---|---|
| H1 | Alta | El panel mostraba citas y creaba eventos sin login | `frontend/app.py` | Login obligatorio y escucha solo en `localhost` | Corregido |
| H2 | Alta | `credentials.json` y `token.json` se leían de `backend/`, una ruta que `.gitignore` no cubría | `calendar_service.py`, `.gitignore` | Movidos a `secrets/`, con reglas de exclusión y permisos `0600` | Corregido |
| H3 | Alta | CORS con `*` y credenciales | `main.py` | Lista explícita, y la app no arranca con comodines | Corregido |
| H4 | Alta | Sin límites de peticiones ni de costo en `/chat` | `endpoints.py`, `agent.py` | `slowapi` y topes diarios de tokens | Corregido |
| H5 | Media | Las excepciones llegaban al cliente | `agent.py`, `calendar_service.py`, `frontend/app.py` | Mensajes genéricos y solo el tipo de error en el log | Corregido |
| H6 | Media | `/agent/prompt` exponía el prompt del sistema sin autenticación | `endpoints.py` | Requiere sesión de administrador | Corregido |
| H7 | Media | Permiso de Google demasiado amplio | `calendar_service.py` | `calendar.events` y opción desactivada por defecto | Corregido |
| H8 | Media | Texto dinámico del panel interpretado como Markdown | `frontend/app.py` | `st.text` y prueba AST | Corregido |
| H9 | Media | Sin validación estricta de entradas ni de los argumentos de Calendar | `endpoints.py`, `calendar_service.py` | Modelos estrictos | Corregido |
| H10 | Media | `.env` versionado por error, aunque vacío | raíz | `git rm --cached` | Corregido |
| H11 | Media | `requirements.txt` con `&gt;=`: la instalación no funcionaba | `requirements.txt` | Reparado, fijado y con lockfile | Corregido |
| H12 | Baja | `/health` afirmaba "connected" sin comprobar nada | `main.py` | Consulta real a la base de datos | Corregido |
| H13 | Baja | Documentación de la API siempre activa | `main.py` | Solo en desarrollo | Corregido |
| H14 | Baja | Sin cabeceras de seguridad | `main.py` | `SecurityMiddleware` | Corregido |
| H15 | Alta | Llaves compartidas antes, según el encargo | Externo | Lista de rotación | **Abierto: acción tuya** |
| H16 | Media | La tabla `login_attempts` crece con cada usuario distinto que se intente, frenada solo por el límite de peticiones | `services/auth.py` | Añadir una limpieza periódica | Abierto |
| H17 | Baja | El tope de tokens se comprueba antes de cada llamada, así que puede superarse por una respuesta | `llm_guard.py` | Aceptado: como máximo 500 tokens de salida más el mensaje | Aceptado |

## Mapeo con OWASP

**OWASP Top 10 (2021)**

| Riesgo | Cobertura |
|---|---|
| A01 Control de acceso | `require_admin`, login en el panel, CSRF |
| A02 Fallos criptográficos | Argon2id, tokens aleatorios guardados como hash, HSTS |
| A03 Inyección | Consultas parametrizadas, texto plano, validación estricta |
| A04 Diseño inseguro | Modelo de amenazas, topes del LLM, Calendar opcional |
| A05 Configuración | Cabeceras, debug apagado, arranque que rechaza valores inseguros |
| A06 Componentes vulnerables | Versiones fijadas, `pip-audit`, Dependabot |
| A07 Autenticación | Bloqueo, no enumeración, rotación e invalidación de sesiones. Falta MFA |
| A08 Integridad | Lockfile, revisiones en CI. Sin firmas ni hashes de paquetes |
| A09 Registro | Log JSON con ID de petición y umbral de alerta. Sin aviso externo |
| A10 SSRF | No hay URLs controladas por el usuario |

**OWASP ASVS nivel 1**

Cubre autenticación (V2), sesiones (V3), control de acceso (V4), validación (V5), errores y logs (V7), archivos (V12) y configuración (V14). Quedan abiertos el MFA, la recuperación por correo y las pruebas de TLS real (V9). Esta es una correspondencia por áreas: no se verificaron los requisitos del estándar uno por uno, así que no es una certificación.

**OWASP Top 10 para aplicaciones LLM**

| Riesgo | Cobertura |
|---|---|
| Inyección de prompt | Roles separados, reglas en el prompt, registro de intentos. Reduce el riesgo, no lo elimina |
| Manejo inseguro de salida | Filtros de secretos, prompt y precios. La salida es JSON |
| Agencia excesiva | El LLM no tiene herramientas. El panel agenda por palabra clave, sin el LLM |
| Abuso de costos | Límites por IP y topes de tokens por cliente y globales |
| Filtración de información | Sin secretos en el prompt, `/agent/prompt` protegido |

## Roadmap A–F

| Bloque | Estado |
|---|---|
| A. Área de administración | Parcial: login y panel listos. No hay leads que ver o exportar |
| B. SQLAlchemy, PostgreSQL y Alembic | Pendiente. Se usa SQLite con `sqlite3` |
| C. Multi-tenant | Pendiente |
| D. Empaquetado | Parcial: `/health`, logs estructurados y CI. Faltan Docker y `/ready` |
| E. Integraciones | Hecho: permiso mínimo y opción de activación para Calendar. Gmail no existe |
| F. Seguridad del LLM | Hecho para el chat actual. No hay herramientas que limitar |

## Sobre los commits

El encargo pedía un commit por punto. Los puntos dependen entre sí, así que se agruparon en commits por hito, con los números indicados en cada mensaje. El commit `45c063a` también incluye el login, las sesiones, CSRF y la CLI, aunque su mensaje no lo diga; el commit siguiente lo aclara.
