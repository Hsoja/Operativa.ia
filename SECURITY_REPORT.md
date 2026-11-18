# Reporte de seguridad de Operativa.ia

## Auditoría del 17 de noviembre de 2026 · rama `feat/lead-email-notify`

**Alcance:** nueva función de aviso por correo al negocio cuando llega un contacto nuevo (`notify_email`), pestaña de perfil en el panel (no existía ninguna), demo pública (GitHub Pages + Render) y su documentación. 3 commits.

### Veredicto: 🟢 Aprobado

Sin hallazgos altos ni secretos expuestos. El único rojo del CI (`npm audit` en el job `frontend`) es una alerta preexistente en `main` (ReDoS en `picomatch`, dependencia de desarrollo de Vite/Vitest), no introducida por esta rama; ya tiene un PR de Dependabot pendiente (#17, sube Vite) que la resuelve por separado.

### Resultados por herramienta

| Comprobación | Resultado |
|---|---|
| `gitleaks` en todo el historial (78 commits) | ✅ Sin fugas |
| CI `backend` (pytest, bandit, pip-audit) | ✅ Correcto |
| CI `semgrep` | ✅ Correcto |
| CI `secrets` | ✅ Correcto |
| CI `frontend` → `npm audit --audit-level=high` | 🟡 1 aviso (`picomatch`/ReDoS), preexistente en `main`, con fix pendiente en PR #17 de Dependabot |

### Revisión anti-puertas traseras

- **Ruta pública `/profile`:** confirmado que expone solo `{slug, name, business_type}`; `notify_email` solo es visible/editable por `/api/v1/admin/tenant` (roles owner/admin).
- **Inyección de cabeceras de correo:** el asunto del aviso siempre se reduce a una línea (`_one_line` limpia `\r`/`\n`) antes de usarse; se confirmó con una prueba que un nombre con salto de línea no agrega cabeceras extra.
- **Fail-closed:** sin `SMTP_HOST` configurado o sin `notify_email`, la función no hace nada; un fallo de SMTP nunca rompe la respuesta al visitante (tarea en segundo plano).
- **Secretos:** el correo real (`adminmilamoresgdl@gmail.com`) y la contraseña de aplicación de Gmail nunca se escriben en el repo; `render.yaml` los deja como variables `sync: false` para llenar solo en el panel de Render.
- **Dependencias:** ninguna nueva.

### No verificado

- **SMTP real:** no se probó el envío contra `smtp.gmail.com` con una cuenta real (sin credenciales en esta sesión). Las pruebas usan un sustituto que verifica qué se intenta enviar.
- **Render:** el servicio aún no existe; `render.yaml` no se ha desplegado de punta a punta.

---

## Auditoría del 16 de noviembre de 2026 · rama `feat/producto-completo`

**Alcance:** todo el diff contra `main` (`20a794d`): multi-tenant y roles, chat y contacto por negocio, sitio conectado a la API, panel, Caddy, WhatsApp, coberturas, agenda con depósito (Stripe), reactivación por correo (CASL) y plantillas. 70+ archivos, unas 6 800 líneas añadidas.

### Veredicto: 🟡 Aprobado con riesgos (aceptados por la dueña el 16 nov 2026)

No quedan hallazgos altos abiertos ni secretos expuestos, y todas las pruebas pasan. Quedan riesgos medios y bajos documentados abajo, que la dueña del proyecto debe aceptar antes del merge. **No apto para clientes reales** hasta cerrar los pendientes de "Antes de producción".

### Resultados por herramienta

| Comprobación | Resultado |
|---|---|
| `pytest` (backend) | ✅ 481 correctas (3 omitidas a propósito: límite documentado de R1) |
| `vitest` (frontend) | ✅ 82 correctas |
| `pip-audit -r requirements.lock` | ✅ Sin vulnerabilidades conocidas |
| `npm audit --audit-level=high` | ✅ 0 vulnerabilidades |
| `bandit` (severidad media o más) | ✅ Sin hallazgos |
| `semgrep` `p/python` (el del CI) | ✅ 0 hallazgos en 151 reglas |
| `semgrep` `p/owasp-top-ten`, `p/typescript`, `p/react`, `p/secrets`, `p/security-audit` | ⚠️ 3 hallazgos medios (Dependabot sin espera) → corregidos (H24) |
| `gitleaks` en todo el historial (59 commits) | ✅ Sin fugas |
| `scripts/scan_exposed_files.sh` | ✅ Sin archivos sensibles rastreados |
| Escaneo de llaves en `frontend/dist` | ✅ Limpio |
| `caddy validate` + `caddy run` local | ✅ CSP y HSTS presentes; `/.env`, `/.git/config` y `/docs` → 404 |
| Chrome headless con la CSP real | ✅ 10 páginas sin violaciones; formulario, chat, reserva y baja de punta a punta |
| Revisión manual del diff (anti-puertas traseras) | ✅ Ver abajo |

### Revisión anti-puertas traseras

- **Rutas:** 43 rutas (incluidas las 4 de documentación, que solo existen en desarrollo), todas en la lista esperada de `tests/test_tenancy.py`. Cualquier ruta nueva hace fallar la prueba. Todas las del panel exigen sesión (prueba que recorre la lista). Los webhooks exigen firma y dan 404 si su integración está apagada.
- **Código peligroso:** sin `eval`, `exec`, `pickle`, `shell=True` ni `yaml.load`. Las plantillas son JSON validado, nunca código.
- **Credenciales y bypass:** sin usuarios, tokens ni contraseñas fijos fuera de las pruebas; sin "modo admin" por variable, cabecera o parámetro. Negocios y owners solo por CLI en el servidor.
- **Red:** solo `api.stripe.com` y `graph.facebook.com` (documentados), con ids validados como dígitos y `follow_redirects=False`.
- **Dependencias:** la única nueva es `httpx==0.28.1`, ya presente en el lockfile como dependencia de `groq`. Sin cambios en npm.
- **CI:** nuevo job `frontend` con acciones fijadas por SHA (`setup-node` v7.1.0, publicada el 8 oct 2026), `permissions: contents: read` y `npm ci --ignore-scripts`. Sin `pull_request_target`.
- **Logs:** los eventos nuevos solo registran negocio, estado, conteos y hashes. Las pruebas confirman que nombres, correos, teléfonos y textos de mensajes no llegan al log.
- **Binarios:** ninguno nuevo.

### Pruebas de abuso cubiertas

Sin sesión, rol equivocado (matriz por rol), otro negocio (IDOR por id, por token y por slug), `tenant_id` enviado por el cliente, cuerpo enorme (413), demasiadas peticiones (429), SQLi, XSS guardado y mostrado como texto, CSRF sin token o con un token de otra sesión, inyección de prompt, herramientas no permitidas y argumentos maliciosos, firmas de webhook falsas, viejas o repetidas, montos manipulados, doble reserva concurrente (8 hilos), inyección de cabeceras de correo y bajas por GET.

### Hallazgos de este ciclo

| ID | Severidad | Hallazgo | Archivo | Corrección | Estado |
|---|---|---|---|---|---|
| H18 | Alta | Caddy enviaba todo lo que no era `/api` al panel Streamlit, que quedaba publicado en internet | `deploy/Caddyfile` | Caddy sirve solo el build de React; panel por túnel SSH (`9ae9c49`) | Corregido |
| H19 | Alta | El chat del panel creaba un evento en Calendar al escribir "cita", sin confirmación (agencia excesiva) | `frontend/app.py` | Formulario con confirmación explícita (`e47402a`) | Corregido |
| H20 | Alta | No existía aislamiento entre negocios: un solo rol `admin` y un prompt fijo | backend | Multi-tenant con `tenant_id` en todas las tablas y roles por negocio (`9e3cdab`…`088e024`) | Corregido |
| H21 | Media | Los leads (nombre, correo, mensaje) se guardaban en `localStorage` | `frontend/src/lib/leads.ts` | Envío a `/contact` con validación en el servidor (`c798d13`) | Corregido |
| H22 | Media | El sitio no tenía CSP | `deploy/Caddyfile`, `vite.config.ts` | CSP sin `unsafe-inline`, probada en Chrome (`327f5bc`) | Corregido |
| H23 | Media | En la demo por chat, "ok wait" contaba como consentimiento y enviaba los datos | `frontend/src/lib/sofia.ts` | Solo una respuesta afirmativa completa (`327f5bc`) | Corregido |
| H24 | Media | Dependabot proponía versiones recién publicadas (riesgo de cadena de suministro) | `.github/dependabot.yml` | `cooldown` de 7 días | Corregido |
| H25 | Baja | Un cliente de WhatsApp abría una conversación nueva con cada mensaje | `services/conversations.py` | Token del servidor reutilizado; el del navegador nunca se adopta (`b3cf828`) | Corregido |
| H26 | Baja | Una plantilla con horarios solapados tumbaba el CLI con un error sin capturar | `services/templates.py` | `TemplateError` controlado (`451a9a4`) | Corregido |
| H27 | Baja | Contraste del texto tenue de 4,05:1, por debajo de WCAG AA | `frontend/src/index.css` | 5:1 o más (`ec13d0f`) | Corregido |
| H28 | Media | Al verificar R1: la ruta `/coverage` afirmaba "acepta tu plan" en negocios sin reglas o sin lista de aseguradoras, y Sofía podía afirmar coberturas en texto libre sin usar la herramienta | `services/coverage.py`, `services/agent.py` | Solo se afirman las dimensiones configuradas; guardia de salida que reemplaza por la respuesta fija cualquier texto libre que hable de coberturas o nombre una aseguradora o ciudad configurada | Corregido |
| H16 | Media | `login_attempts` crecía sin límite | `services/auth.py` | Limpieza tras 24 h sin fallos (`604ecf6`) | Corregido |

### Riesgos residuales (medios y bajos, documentados)

| ID | Severidad | Riesgo | Mitigación actual | Estado |
|---|---|---|---|---|
| R1 | Baja (era Media) | Tras H28, solo queda un caso: en un negocio **sin reglas configuradas**, una frase que afirme cobertura sin palabras clave ni nombres conocidos (p. ej. "trabajamos con esa compañía") | Ruta `/coverage` y herramienta con texto fijo; guardia por palabras clave y por nombres configurados; regla 8 del prompt | Aceptado (16 nov 2026) |
| R2 | Media | Los límites de peticiones viven en memoria: con varios procesos cada uno cuenta por separado | Un solo proceso por ahora; `RATE_LIMIT_STORAGE=redis://` soportado, sin probar | Aceptado (16 nov 2026) |
| R3 | Media | Sin MFA para owner y admin | Argon2id, bloqueo progresivo, sesiones cortas | ⛔ **Bloqueante antes del primer cliente real.** Aceptado solo mientras no haya clientes. Revisión: 1 dic 2026 |
| R4 | Media | El aislamiento entre negocios es solo en la aplicación (SQLite no tiene RLS) | `tenant_id` en cada consulta, probado con dos negocios | Aceptado (16 nov 2026); RLS al migrar a PostgreSQL |
| R5 | Media | Términos y Política de Privacidad sin revisión legal (PIPEDA, CASL) | Marcados como borrador | ⛔ **Bloqueante antes del primer cliente real.** Aceptado solo mientras no haya clientes. Revisión: 1 dic 2026 |
| R6 | Baja | Las tareas en segundo plano (respuesta de WhatsApp, correos) se pierden si el proceso cae | Idempotencia evita duplicados al reintentar | Aceptado (16 nov 2026) |
| R7 | Baja | La referencia de la reserva y el token de baja viajan en URLs (historial, logs de acceso) | Solo permiten ver el estado sin datos personales o darse de baja; `Referrer-Policy: no-referrer` | Aceptado (16 nov 2026) |
| R8 | Baja | Los pagos que no cuadran quedan en "revisar reembolso" y se reembolsan a mano | Visibles en el panel; nunca se confirman | Aceptado (16 nov 2026) |
| R9 | Baja | El nombre del contacto se inserta en el cuerpo del correo | Texto plano, limpiado, 80 caracteres como máximo | Aceptado (16 nov 2026) |
| H17 | Baja | El tope de tokens puede superarse por una respuesta | Máximo 500 tokens de salida | Aceptado |

### No verificado

- **Servicios reales:** Groq, Stripe, WhatsApp Cloud API, SMTP y Google Calendar. No hay llaves; las pruebas usan sustitutos que verifican lo que enviamos y cómo reaccionamos a sus respuestas.
- **GitHub Actions:** el job nuevo `frontend` no se ha ejecutado en GitHub porque no se ha hecho push.
- **Redis**, **TLS real** y **DAST con OWASP ZAP:** no hay staging ni dominio.
- **Panel Streamlit en el navegador:** arranca y escucha solo en `127.0.0.1`; su render se probó con AppTest, no en un navegador.

### Antes de producción

- [ ] Ejecutar el CI en GitHub (PR) y agregar el check `frontend` al ruleset `protect-main`.
- [ ] Probar Stripe, WhatsApp y SMTP con llaves de prueba en un staging.
- [ ] OWASP ZAP sobre staging sin hallazgos altos.
- [ ] ⛔ R5: revisión legal de Términos y Privacidad (revisión 1 dic 2026).
- [ ] ⛔ R3: MFA para owner y admin (revisión 1 dic 2026).
- [ ] PostgreSQL con RLS si hay más de un servidor (R4).
- [ ] Pentest externo antes del primer cliente real.

---

## Histórico (auditorías del 2 al 5 de noviembre de 2026)

> Estado de entonces, sobre la rama `security-hardening`. Las filas H15, H16 y el punto 22 se actualizaron con su estado actual; lo demás describe el código de esa fecha.


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
| 22 | Revocar llaves | Cerrado (5 nov 2026) | No existían llaves de Google OAuth, Groq ni Gemini que rotar | Ninguno |
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
| H15 | Alta | Llaves compartidas antes, según el encargo | Externo | No había llaves que rotar (confirmado el 5 nov 2026) | Cerrado |
| H16 | Media | La tabla `login_attempts` crece con cada usuario distinto que se intente, frenada solo por el límite de peticiones | `services/auth.py` | Limpieza tras 24 h sin fallos (`604ecf6`) | Corregido |
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
