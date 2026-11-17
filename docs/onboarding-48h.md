# Guía de puesta en marcha en 48 horas

Cómo dejar operando a una PYME nueva en Operativa.ia, de cero a recibir clientes, en dos días hábiles.
Todos los comandos se ejecutan en el servidor, desde `backend/` y con el entorno virtual activo.

> Nada de esta guía requiere compartir contraseñas por chat o correo. Las llaves van solo en `.env`.

## Antes de empezar (pedirle al negocio)

- [ ] Nombre comercial y **dirección física** (CASL la exige en cada correo de reactivación).
- [ ] Vertical: clínica dental, salón de belleza, fisioterapia o servicios a domicilio/taller.
- [ ] Servicios reales, duración y depósito de cada uno.
- [ ] Horario semanal y zona horaria.
- [ ] Zona de servicio (códigos postales o ciudades) y aseguradoras aceptadas, si aplica.
- [ ] Correo de la persona dueña (será `owner`).
- [ ] Opcional: número de WhatsApp Business, cuenta de Stripe y servidor de correo (SMTP).

## Hora 0 a 2: negocio, plantilla y dueña

```bash
python -m app.cli list-templates
python -m app.cli create-tenant --slug clinica-sol --name "Clínica Sol" --template dental \
    --location "100 Example Rd, Waterloo, ON" --timezone America/Toronto
python -m app.cli create-user --tenant clinica-sol --username ana --role owner   # pide la contraseña (12+)
```

La plantilla carga perfil, servicios, horario, cobertura y un texto de campaña. **Los depósitos y las aseguradoras son de ejemplo.**

## Hora 2 a 8: ajustar con el negocio (panel)

Panel: `ssh -L 8501:127.0.0.1:8501 servidor` y abrir `http://localhost:8501`.

- [ ] **Perfil:** servicios, horario y ubicación tal como los diría el negocio (alimentan a Sofía).
- [ ] **Servicios y horario:** precios de depósito reales; desactivar lo que no ofrecen.
- [ ] **Cobertura:** códigos postales, ciudades y aseguradoras reales (lista vacía = no se revisa).
- [ ] **Equipo:** la dueña crea usuarios `admin` o `staff` desde la API del panel.
- [ ] **Probar a Sofía:** 5 preguntas reales del negocio (precio, horario, cobertura, cita, algo fuera de tema).

## Hora 8 a 24: canales y pagos (si el negocio los quiere)

Cada integración queda **apagada** hasta que sus variables estén completas en `.env`; a medio configurar, la app no arranca.

- [ ] **Stripe:** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PUBLIC_SITE_URL`. Webhook en Stripe → `https://DOMINIO/api/v1/webhooks/stripe` con los eventos `checkout.session.completed` y `checkout.session.expired`. En pruebas, solo llaves `sk_test_`.
- [ ] **WhatsApp:** `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN` (24+ caracteres), `WHATSAPP_ACCESS_TOKEN`. Webhook en Meta → `https://DOMINIO/api/v1/webhooks/whatsapp`. Después:
  `python -m app.cli link-whatsapp --tenant clinica-sol --phone-number-id <ID de Meta>`
- [ ] **Correo (reactivación):** `SMTP_HOST`, `SMTP_FROM` y credenciales; siempre con TLS.
- [ ] **Google Calendar (opcional):** `CALENDAR_ENABLED=true` y `secrets/credentials.json` (0600).

## Hora 24 a 40: prueba de punta a punta

- [ ] Reserva en `https://DOMINIO/#/book/clinica-sol` con un servicio sin depósito y otro con depósito (tarjeta de prueba de Stripe).
- [ ] La cita aparece en el panel como **Confirmada** y, si aplica, en Google Calendar.
- [ ] Un mensaje de WhatsApp recibe respuesta de Sofía con los datos del negocio.
- [ ] Formulario de contacto → el lead aparece en el panel.
- [ ] Consulta de cobertura dentro y fuera de zona.
- [ ] Campaña de prueba a un contacto propio con consentimiento → llega con dirección del negocio y enlace de baja; la baja funciona.

## Hora 40 a 48: salida a producción

- [ ] `ENV=production`, `ALLOWED_ORIGINS` y `PUBLIC_SITE_URL` con `https://`, `IP_HASH_SALT` de 32+ caracteres, `TRUSTED_PROXIES`.
- [ ] Llaves `live` de Stripe solo ahora (la app las rechaza fuera de producción).
- [ ] `npm run build` y Caddy con `SITE_ROOT` apuntando a `frontend/dist`.
- [ ] Verificar: `/.env`, `/.git/config` y `/docs` → 404; cabeceras CSP y HSTS presentes.
- [ ] Cron diario: `python -m app.cli purge` (retención de conversaciones, reservas vencidas, sesiones).
- [ ] Revisar `backend/logs/security.jsonl` la primera semana.

## Después

- Revisar con el negocio los primeros leads y conversaciones a los 7 días.
- Citas en **Revisar reembolso**: el reembolso se hace a mano desde el panel de Stripe.
- Ajustar el perfil cuando cambien servicios, horario o políticas.
