"""P2.10 Agenda con depósito: huecos, bloqueo, Stripe Checkout, webhook firmado, roles y Sofía."""

import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.api import webhooks
from app.core.config import get_settings
from app.core.db import get_connection
from app.core.ratelimit import limiter
from app.services import agent, booking, payments
from helpers import ORIGIN, PROD, login, make_tenant, make_user, reset_db

# Valores de prueba construidos por partes: no son llaves reales ni deben parecerlo a un escáner
STRIPE = {
    "STRIPE_SECRET_KEY": "sk_" + "test_" + "fake",
    "STRIPE_WEBHOOK_SECRET": "whsec_" + "pruebas",
    "PUBLIC_SITE_URL": "http://localhost:5173",
}
TZ = ZoneInfo("America/Toronto")
DAY = (datetime.now(TZ) + timedelta(days=2)).date()
SLOT = f"{DAY.isoformat()}T09:00"


@pytest.fixture
def biz(make_client, monkeypatch):
    limiter.reset()
    reset_db()
    sol = make_tenant("sol", "Clínica Sol")
    luna = make_tenant("luna", "Salón Luna")
    make_user(sol, "sol-admin", "admin")
    make_user(sol, "sol-staff", "staff")
    make_user(luna, "luna-admin", "admin")
    week = booking.WeeklyHours(ranges=[booking.HoursRange(weekday=d, open="09:00", close="12:00") for d in range(7)])
    for tenant in (sol, luna):
        booking.set_hours(tenant, week)
    cleaning = booking.create_service(sol, booking.ServiceIn(name="Limpieza", duration_minutes=60, deposit_cents=2500))
    free = booking.create_service(sol, booking.ServiceIn(name="Consulta", duration_minutes=30, deposit_cents=0))
    luna_service = booking.create_service(luna, booking.ServiceIn(name="Corte", duration_minutes=60, deposit_cents=1000))
    stripe = MagicMock(
        return_value=SimpleNamespace(
            status_code=200, json=lambda: {"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"}
        )
    )
    monkeypatch.setattr(payments.httpx, "post", stripe)
    calendar = MagicMock(return_value={"status": "disabled"})
    monkeypatch.setattr(webhooks, "create_appointment", calendar)
    client = make_client(**STRIPE)
    return SimpleNamespace(client=client, sol=sol, luna=luna, cleaning=cleaning, free=free, luna_service=luna_service,
                           stripe=stripe, calendar=calendar, make=make_client)


def book(c, service, start=SLOT, slug="sol", **extra):
    body = {"service_id": service, "start": start, "name": "Ana Sol", "email": "ana@sol.example", "consent": True, **extra}
    return c.post(f"/api/v1/public/{slug}/bookings", json=body)


def slots(c, service_id, slug="sol", day=DAY):
    return c.get(f"/api/v1/public/{slug}/slots", params={"service_id": service_id, "date": day.isoformat()}).json()["slots"]


def stripe_event(event_type="checkout.session.completed", appointment_id=1, tenant_id=1, amount=2500, currency="cad",
                 paid="paid", event_id="evt_1", session_id="cs_test_123"):
    return {"id": event_id, "type": event_type, "data": {"object": {
        "id": session_id, "payment_status": paid, "amount_total": amount, "currency": currency,
        "metadata": {"appointment_id": str(appointment_id), "tenant_id": str(tenant_id)},
    }}}


def send_webhook(c, event, secret=STRIPE["STRIPE_WEBHOOK_SECRET"], ts=None):
    raw = json.dumps(event).encode()
    t = ts or int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    return c.post("/api/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": f"t={t},v1={sig}"})


def status_of(appointment_id):
    with get_connection() as db:
        return db.execute("SELECT status FROM appointments WHERE id = ?", (appointment_id,)).fetchone()[0]


# --- Servicios y huecos -------------------------------------------------------------------------

def test_public_services_and_slots(biz):
    body = biz.client.get("/api/v1/public/sol/services").json()
    assert {s["name"]: s["deposit_cents"] for s in body["services"]} == {"Consulta": 0, "Limpieza": 2500}
    assert body["timezone"] == "America/Toronto"
    assert slots(biz.client, biz.cleaning)[0] == SLOT and slots(biz.client, biz.cleaning)[-1].endswith("T11:00")
    assert len(slots(biz.client, biz.cleaning)) == 9


@pytest.mark.parametrize("days", [-1, 400])
def test_slots_outside_window_are_empty(biz, days):
    assert slots(biz.client, biz.cleaning, day=datetime.now(TZ).date() + timedelta(days=days)) == []


def test_other_tenants_service_is_not_found(biz):
    r = biz.client.get("/api/v1/public/sol/slots", params={"service_id": biz.luna_service, "date": DAY.isoformat()})
    assert r.status_code == 404


# --- Reservas -----------------------------------------------------------------------------------

def test_free_service_is_confirmed_immediately(biz):
    r = book(biz.client, biz.free)
    assert r.status_code == 201 and r.json()["status"] == "confirmed"
    biz.stripe.assert_not_called()
    assert SLOT not in slots(biz.client, biz.free)


def test_deposit_goes_to_stripe_with_server_amount(biz):
    r = book(biz.client, biz.cleaning)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending_payment" and body["checkout_url"].startswith("https://checkout.stripe.com/")
    call = biz.stripe.call_args
    form = call.kwargs["data"]
    assert form["line_items[0][price_data][unit_amount]"] == "2500" and form["line_items[0][price_data][currency]"] == "cad"
    assert form["success_url"].startswith("http://localhost:5173/#/book/sol?status=success&ref=")
    assert call.kwargs["headers"]["Idempotency-Key"].startswith("appointment-")
    assert call.kwargs["follow_redirects"] is False
    assert SLOT not in slots(biz.client, biz.cleaning)


@pytest.mark.parametrize("extra", [{"deposit_cents": 1}, {"amount": 1}, {"currency": "usd"}, {"success_url": "https://evil.example"}])
def test_client_cannot_set_amount_or_return_url(biz, extra):
    assert book(biz.client, biz.cleaning, **extra).status_code == 422
    biz.stripe.assert_not_called()


def test_held_slot_cannot_be_booked_twice(biz):
    assert book(biz.client, biz.cleaning).status_code == 201
    assert book(biz.client, biz.cleaning).status_code == 409
    assert book(biz.client, biz.free).status_code == 409  # solapa con la cita de 60 min


def test_expired_hold_frees_the_slot(biz):
    book(biz.client, biz.cleaning)
    with get_connection() as db:
        db.execute("UPDATE appointments SET hold_expires_at = 1")
    assert SLOT in slots(biz.client, biz.cleaning)
    assert booking.expire_holds() == 1


@pytest.mark.parametrize("start", [f"{DAY.isoformat()}T09:07", f"{DAY.isoformat()}T13:00", f"{DAY.isoformat()}T11:30", "2001-01-01T09:00"])
def test_only_listed_slots_can_be_booked(biz, start):
    assert book(biz.client, biz.cleaning, start=start).status_code == 409


@pytest.mark.parametrize(
    "change",
    [{"consent": False}, {"email": "no-es-correo"}, {"name": "A"}, {"start": "mañana"}, {"service_id": 0}, {"website": "spam"}],
)
def test_booking_validation(biz, change):
    assert book(biz.client, biz.cleaning, **change).status_code == 422


def test_deposit_without_stripe_is_refused_without_holding(biz):
    c = biz.make(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="", PUBLIC_SITE_URL="")  # Stripe apagado
    assert book(c, biz.cleaning).status_code == 503
    assert SLOT in slots(c, biz.cleaning)


@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("detalle-interno"),
        SimpleNamespace(status_code=402, json=lambda: {}),
        SimpleNamespace(status_code=200, json=lambda: {"id": "cs_test_1", "url": "https://evil.example/pay"}),
        SimpleNamespace(status_code=200, json=lambda: {"id": "nope", "url": "https://checkout.stripe.com/x"}),
    ],
)
def test_stripe_failures_release_the_slot(biz, security_log, failure):
    if isinstance(failure, Exception):
        biz.stripe.side_effect = failure
    else:
        biz.stripe.return_value = failure
    r = book(biz.client, biz.cleaning)
    assert r.status_code == 502 and "detalle-interno" not in r.text
    assert SLOT in slots(biz.client, biz.cleaning)
    assert "detalle-interno" not in json.dumps(security_log())


def test_booking_status_by_ref_has_no_personal_data(biz):
    ref = book(biz.client, biz.cleaning).json()["ref"]
    body = biz.client.get(f"/api/v1/public/sol/bookings/{ref}").json()
    assert body["status"] == "pending_payment" and body["service"] == "Limpieza"
    assert "ana" not in json.dumps(body).lower()
    assert biz.client.get(f"/api/v1/public/luna/bookings/{ref}").status_code == 404
    assert biz.client.get("/api/v1/public/sol/bookings/" + "x" * 32).status_code == 404
    assert biz.client.get("/api/v1/public/sol/bookings/corto").status_code == 422


def test_personal_data_never_logged(biz, security_log):
    book(biz.client, biz.cleaning)
    log = json.dumps(security_log())
    assert "ana@sol.example" not in log and "Ana Sol" not in log


# --- Webhook de Stripe ----------------------------------------------------------------------------

def _pending(biz):
    book(biz.client, biz.cleaning)
    with get_connection() as db:
        return db.execute("SELECT id FROM appointments").fetchone()[0]


def test_paid_checkout_confirms_and_syncs_calendar(biz):
    appointment = _pending(biz)
    assert send_webhook(biz.client, stripe_event(appointment_id=appointment, tenant_id=biz.sol)).status_code == 200
    assert status_of(appointment) == "confirmed"
    assert biz.calendar.call_args.kwargs["timezone"] == "America/Toronto"


@pytest.mark.parametrize("header", ["", "t=1,v1=abc", "v1=" + "0" * 64, "t=abc,v1=x"])
def test_bad_signatures_rejected(biz, header):
    appointment = _pending(biz)
    raw = json.dumps(stripe_event(appointment_id=appointment, tenant_id=biz.sol)).encode()
    assert biz.client.post("/api/v1/webhooks/stripe", content=raw, headers={"Stripe-Signature": header}).status_code == 401
    assert status_of(appointment) == "pending_payment"


def test_wrong_secret_and_old_timestamp_rejected(biz):
    appointment = _pending(biz)
    event = stripe_event(appointment_id=appointment, tenant_id=biz.sol)
    assert send_webhook(biz.client, event, secret="whsec_otro").status_code == 401
    assert send_webhook(biz.client, event, ts=int(time.time()) - 600).status_code == 401
    assert status_of(appointment) == "pending_payment"


def test_duplicate_events_processed_once(biz):
    appointment = _pending(biz)
    event = stripe_event(appointment_id=appointment, tenant_id=biz.sol)
    send_webhook(biz.client, event)
    assert send_webhook(biz.client, event).json()["status"] == "duplicate"
    assert biz.calendar.call_count == 1


@pytest.mark.parametrize("change, expected", [({"amount": 1}, "needs_refund"), ({"currency": "usd"}, "needs_refund"), ({"paid": "unpaid"}, "pending_payment")])
def test_amount_and_payment_status_are_checked(biz, change, expected):
    appointment = _pending(biz)
    send_webhook(biz.client, stripe_event(appointment_id=appointment, tenant_id=biz.sol, **change))
    assert status_of(appointment) == expected


def test_event_for_another_tenant_or_session_changes_nothing(biz):
    appointment = _pending(biz)
    send_webhook(biz.client, stripe_event(appointment_id=appointment, tenant_id=biz.luna, event_id="evt_a"))
    send_webhook(biz.client, stripe_event(appointment_id=appointment, tenant_id=biz.sol, session_id="cs_otra", event_id="evt_b"))
    assert status_of(appointment) == "pending_payment"


def test_expired_checkout_releases_slot(biz):
    appointment = _pending(biz)
    send_webhook(biz.client, stripe_event("checkout.session.expired", appointment_id=appointment, tenant_id=biz.sol))
    assert status_of(appointment) == "expired" and SLOT in slots(biz.client, biz.cleaning)


def test_late_payment_for_a_retaken_slot_needs_refund(biz):
    appointment = _pending(biz)
    with get_connection() as db:
        db.execute("UPDATE appointments SET status = 'expired', hold_expires_at = 1")
    assert book(biz.client, biz.free).status_code == 201
    send_webhook(biz.client, stripe_event(appointment_id=appointment, tenant_id=biz.sol))
    assert status_of(appointment) == "needs_refund"


def test_stripe_webhook_404_when_disabled(client):
    assert client.post("/api/v1/webhooks/stripe", content=b"{}").status_code == 404


def test_unknown_event_types_are_ignored(biz):
    assert send_webhook(biz.client, stripe_event("invoice.paid")).json()["status"] == "ignored"


# --- Panel: servicios, horario y citas ------------------------------------------------------------

def logged(biz, username):
    c = biz.make(**STRIPE)
    assert login(c, username).status_code == 200
    return c, {**ORIGIN, "X-CSRF-Token": c.cookies.get("csrf")}


def test_roles_for_services_hours_and_cancel(biz):
    staff, h = logged(biz, "sol-staff")
    new = {"name": "Blanqueamiento", "duration_minutes": 90, "deposit_cents": 5000}
    assert staff.post("/api/v1/admin/services", json=new, headers=h).status_code == 403
    assert staff.post("/api/v1/admin/hours", json={"ranges": []}, headers=h).status_code == 403
    assert staff.get("/api/v1/admin/appointments").status_code == 200

    admin, h = logged(biz, "sol-admin")
    assert admin.post("/api/v1/admin/services", json=new, headers=h).status_code == 201
    assert admin.post("/api/v1/admin/services", json=new, headers=h).status_code == 409
    appointment = _pending(biz)
    assert staff.post(f"/api/v1/admin/appointments/{appointment}/cancel", headers=logged(biz, "sol-staff")[1]).status_code in (403,)
    assert admin.post(f"/api/v1/admin/appointments/{appointment}/cancel", headers=h).status_code == 200
    assert SLOT in slots(biz.client, biz.cleaning)


def test_appointments_and_services_are_isolated(biz):
    _pending(biz)
    luna, h = logged(biz, "luna-admin")
    assert luna.get("/api/v1/admin/appointments").json()["appointments"] == []
    assert luna.post(f"/api/v1/admin/services/{biz.cleaning}", json={"name": "X Y", "duration_minutes": 10, "deposit_cents": 0}, headers=h).status_code == 404
    assert luna.post("/api/v1/admin/appointments/1/cancel", headers=h).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"ranges": [{"weekday": 0, "open": "12:00", "close": "09:00"}]},
        {"ranges": [{"weekday": 0, "open": "09:00", "close": "12:00"}, {"weekday": 0, "open": "11:00", "close": "13:00"}]},
        {"ranges": [{"weekday": 7, "open": "09:00", "close": "12:00"}]},
        {"ranges": [{"weekday": 0, "open": "9", "close": "12:00"}]},
        {"ranges": [{"weekday": 0, "open": "09:00", "close": "12:00"}] * 29},
    ],
)
def test_hours_validation(biz, body):
    admin, h = logged(biz, "sol-admin")
    assert admin.post("/api/v1/admin/hours", json=body, headers=h).status_code == 422


@pytest.mark.parametrize("change", [{"deposit_cents": -1}, {"deposit_cents": 100001}, {"duration_minutes": 0}, {"currency": "btc"}])
def test_service_validation(biz, change):
    admin, h = logged(biz, "sol-admin")
    body = {"name": "Nuevo", "duration_minutes": 30, "deposit_cents": 0, **change}
    assert admin.post("/api/v1/admin/services", json=body, headers=h).status_code == 422


# --- Configuración fail-closed --------------------------------------------------------------------

@pytest.mark.parametrize(
    "env",
    [
        {"STRIPE_SECRET_KEY": STRIPE["STRIPE_SECRET_KEY"]},
        {"STRIPE_WEBHOOK_SECRET": STRIPE["STRIPE_WEBHOOK_SECRET"]},
        {**STRIPE, "STRIPE_SECRET_KEY": "pk_" + "test_" + "fake"},
        {**STRIPE, "STRIPE_SECRET_KEY": "sk_" + "live_" + "fake"},
        {**STRIPE, "STRIPE_WEBHOOK_SECRET": "otro"},
        {**STRIPE, "PUBLIC_SITE_URL": ""},
        {**STRIPE, **PROD, "PUBLIC_SITE_URL": "http://sitio.example"},
    ],
)
def test_stripe_misconfiguration_refuses_to_start(make_client, env):
    with pytest.raises(ValueError):
        make_client(**env)


# --- Sofía: horarios de solo lectura --------------------------------------------------------------

@pytest.fixture
def groq(monkeypatch):
    fake = MagicMock()

    def tool(arguments):
        call = SimpleNamespace(id="c1", type="function", function=SimpleNamespace(name="list_available_slots", arguments=arguments))
        fake.return_value.chat.completions.create.return_value = SimpleNamespace(
            usage=SimpleNamespace(total_tokens=10), choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[call]))]
        )

    fake.tool = tool
    monkeypatch.setattr(agent, "Groq", fake)
    yield fake


def test_sofia_lists_slots_and_shares_link_without_booking(biz, groq):
    c = biz.make(GROQ_API_KEY="k", **STRIPE)
    groq.tool(json.dumps({"service": "limpieza", "date": DAY.isoformat()}))
    reply = c.post("/api/v1/public/sol/chat", json={"message": "¿Tienen horario?"}).json()["agent_response"]
    assert "09:00" in reply and "http://localhost:5173/#/book/sol" in reply
    kwargs = groq.return_value.chat.completions.create.call_args.kwargs
    assert {t["function"]["name"] for t in kwargs["tools"]} == {"list_available_slots"}
    with get_connection() as db:
        assert db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] == 0


@pytest.mark.parametrize("arguments", ['{"service": "limpieza"}', '{"service": "limpieza", "date": "mañana"}', '{"service": "x", "date": "2026-13-45"}', "nope"])
def test_sofia_slot_tool_rejects_bad_arguments(biz, groq, arguments):
    c = biz.make(GROQ_API_KEY="k", **STRIPE)
    groq.tool(arguments)
    assert c.post("/api/v1/public/sol/chat", json={"message": "hola"}).json()["agent_response"] == agent.SLOTS_ERROR_REPLY


def test_sofia_asks_which_service_when_ambiguous(biz, groq):
    c = biz.make(GROQ_API_KEY="k", **STRIPE)
    groq.tool(json.dumps({"service": "masaje", "date": DAY.isoformat()}))
    assert "Opciones" in c.post("/api/v1/public/sol/chat", json={"message": "hola"}).json()["agent_response"]


def test_concurrent_bookings_cannot_double_book(biz):
    """Ocho hilos piden el mismo hueco a la vez: BEGIN IMMEDIATE deja pasar solo a uno."""
    from concurrent.futures import ThreadPoolExecutor

    from app.services import tenants

    tenant = tenants.get(biz.sol)
    payload = booking.BookingIn(service_id=biz.free, start=SLOT, name="Ana Sol", email="ana@sol.example", consent=True)

    def attempt(_):
        try:
            booking.create_booking(tenant, payload)
            return "ok"
        except booking.SlotTaken:
            return "taken"

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert results.count("ok") == 1 and results.count("taken") == 7
