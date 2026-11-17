"""P2.11 Reactivación por correo con CASL: consentimiento explícito, baja de un clic, frecuencia y aislamiento."""

import json
import time
from types import SimpleNamespace

import pytest

from app.core.db import get_connection
from app.core.ratelimit import limiter
from app.services import reactivation, tenants
from helpers import ORIGIN, login, make_tenant, make_user, reset_db

SMTP = {"SMTP_HOST": "smtp.example.com", "SMTP_FROM": "hola@negocio.example", "PUBLIC_SITE_URL": "http://localhost:5173"}
LEAD = {"name": "Ana Sol", "email": "ana@sol.com", "topic": "Book a demo", "message": "Quiero información.", "consent": True}
OLD = int(time.time()) - 200 * 86400
CAMPAIGN = {"inactive_days": 90, "subject": "Te extrañamos", "body": "Hola {nombre}, hace tiempo que no te vemos.", "confirm": True}


class FakeSMTP:
    """Servidor SMTP simulado: guarda los mensajes y exige STARTTLS antes de enviar."""

    instances: list = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.tls, self.sent = host, port, False, []
        FakeSMTP.instances.append(self)

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        pass

    def send_message(self, message):
        assert self.tls, "nunca se envía sin TLS"
        self.sent.append(message)

    def quit(self):
        pass


@pytest.fixture
def biz(make_client, monkeypatch):
    limiter.reset()
    reset_db()
    FakeSMTP.instances = []
    monkeypatch.setattr(reactivation.smtplib, "SMTP", FakeSMTP)
    sol = make_tenant("sol", "Clínica Sol", location="123 King St, Waterloo, ON")
    luna = make_tenant("luna", "Salón Luna")
    for tenant, prefix in ((sol, "sol"), (luna, "luna")):
        make_user(tenant, f"{prefix}-admin", "admin")
        make_user(tenant, f"{prefix}-staff", "staff")
    client = make_client(**SMTP)
    return SimpleNamespace(client=client, sol=sol, luna=luna, make=make_client)


def contact(client, slug="sol", **change):
    return client.post(f"/api/v1/public/{slug}/contact", json={**LEAD, **change})


def age_contacts(when=OLD):
    with get_connection() as db:
        db.execute("UPDATE contacts SET last_activity_at = ?", (when,))


def logged(biz, username):
    c = biz.make(**SMTP)
    assert login(c, username).status_code == 200
    return c, {**ORIGIN, "X-CSRF-Token": c.cookies.get("csrf")}


def sent_messages():
    return [m for s in FakeSMTP.instances for m in s.sent]


# --- Consentimiento explícito ---------------------------------------------------------------------

def test_unchecked_box_never_gives_consent(biz):
    contact(biz.client)
    assert reactivation.contact_stats(biz.sol) == {"total": 1, "opted_in": 0, "unsubscribed": 0}


def test_checked_box_records_consent_with_date_and_source(biz):
    contact(biz.client, marketing_consent=True)
    with get_connection() as db:
        row = db.execute("SELECT marketing_consent, consent_at, consent_source FROM contacts").fetchone()
    assert row["marketing_consent"] == 1 and row["consent_at"] > 0 and row["consent_source"] == "contact-form"


def test_later_unchecked_visit_does_not_revoke_or_grant(biz):
    contact(biz.client, marketing_consent=True)
    contact(biz.client)
    assert reactivation.contact_stats(biz.sol)["opted_in"] == 1


@pytest.mark.parametrize("value", ["true", 1, "yes"])
def test_consent_must_be_a_real_boolean(biz, value):
    assert contact(biz.client, marketing_consent=value).status_code == 422


def test_contacts_are_per_business(biz):
    contact(biz.client, "sol", marketing_consent=True)
    assert reactivation.contact_stats(biz.luna)["total"] == 0


# --- Campañas -------------------------------------------------------------------------------------

def test_campaign_reaches_only_opted_in_inactive_contacts(biz):
    contact(biz.client, marketing_consent=True)
    contact(biz.client, email="sin@consent.com")
    contact(biz.client, email="reciente@sol.com", marketing_consent=True)
    age_contacts()
    with get_connection() as db:
        db.execute("UPDATE contacts SET last_activity_at = ? WHERE email = 'reciente@sol.com'", (int(time.time()),))
    admin, h = logged(biz, "sol-admin")
    assert admin.post("/api/v1/admin/campaigns/preview", json={"inactive_days": 90}, headers=h).json() == {"eligible": 1}
    r = admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    assert r.status_code == 202 and r.json()["recipients"] == 1
    [message] = sent_messages()
    assert message["To"] == "ana@sol.com" and message["Subject"] == "Te extrañamos"
    text = message.get_content()
    assert "Hola Ana Sol" in text and "123 King St, Waterloo, ON" in text and "#/unsubscribe/sol/" in text
    assert message["List-Unsubscribe"].startswith("<http://localhost:5173/api/v1/public/sol/unsubscribe/")
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "Clínica Sol" in message["From"]
    assert FakeSMTP.instances[0].tls


def test_unsubscribe_is_one_click_and_permanent(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    admin, h = logged(biz, "sol-admin")
    admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    token = sent_messages()[0]["List-Unsubscribe"].strip("<>").rsplit("/", 1)[1]
    assert biz.client.get(f"/api/v1/public/sol/unsubscribe/{token}").status_code == 405  # GET no da de baja
    assert biz.client.post(f"/api/v1/public/sol/unsubscribe/{token}").json() == {"status": "unsubscribed"}
    assert biz.client.post(f"/api/v1/public/sol/unsubscribe/{token}").status_code == 200  # idempotente
    assert reactivation.contact_stats(biz.sol) == {"total": 1, "opted_in": 0, "unsubscribed": 1}
    assert reactivation.preview(biz.sol, 90) == 0
    contact(biz.client)  # volver sin marcar la casilla no reactiva el consentimiento
    assert reactivation.contact_stats(biz.sol)["opted_in"] == 0


def test_unsubscribe_token_is_scoped_to_its_business(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    admin, h = logged(biz, "sol-admin")
    admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    token = sent_messages()[0]["List-Unsubscribe"].strip("<>").rsplit("/", 1)[1]
    assert biz.client.post(f"/api/v1/public/luna/unsubscribe/{token}").status_code == 404
    assert biz.client.post("/api/v1/public/sol/unsubscribe/" + "x" * 43).status_code == 404
    assert biz.client.post("/api/v1/public/sol/unsubscribe/corto").status_code == 422


def test_unsubscribe_during_delivery_is_respected(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    tenant = tenants.get(biz.sol)
    campaign = reactivation.CampaignIn(**CAMPAIGN)
    campaign_id, sends = reactivation.create_campaign(tenant, campaign)
    reactivation.unsubscribe(biz.sol, sends[0][3])
    assert reactivation.deliver(tenant, campaign_id, campaign, sends) == {"sent": 0, "failed": 1}
    assert sent_messages() == []


@pytest.mark.parametrize(
    "setup, reason",
    [
        (lambda biz: None, "No hay contactos"),
        (lambda biz: tenants.update_profile(biz.sol, tenants.TenantProfile(name="Clínica Sol")), "dirección física"),
    ],
)
def test_campaign_blocked_reasons(biz, setup, reason):
    setup(biz)
    admin, h = logged(biz, "sol-admin")
    r = admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    assert r.status_code == 409 and reason in r.json()["detail"]


def test_one_campaign_per_day_and_one_email_per_contact_per_month(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    admin, h = logged(biz, "sol-admin")
    assert admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h).status_code == 202
    second = admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    assert second.status_code == 409 and "24 horas" in second.json()["detail"]
    with get_connection() as db:
        db.execute("UPDATE campaigns SET created_at = 1")
    assert reactivation.preview(biz.sol, 90) == 0  # ya recibió un correo este mes


def test_campaign_without_smtp_is_refused(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    c = biz.make(SMTP_HOST="", SMTP_FROM="")
    login(c, "sol-admin")
    r = c.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers={**ORIGIN, "X-CSRF-Token": c.cookies.get("csrf")})
    assert r.status_code == 409 and "correo" in r.json()["detail"]


@pytest.mark.parametrize(
    "change",
    [
        {"confirm": False},
        {"confirm": "true"},
        {"subject": "Hola\r\nBcc: todos@example.com"},
        {"subject": "x" * 121},
        {"body": "corto"},
        {"inactive_days": 5},
        {"recipients": ["otro@example.com"]},
    ],
)
def test_campaign_validation(biz, change):
    admin, h = logged(biz, "sol-admin")
    assert admin.post("/api/v1/admin/campaigns", json={**CAMPAIGN, **change}, headers=h).status_code == 422


def test_roles_and_isolation(biz):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    staff, h = logged(biz, "sol-staff")
    assert staff.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h).status_code == 403
    assert staff.post("/api/v1/admin/campaigns/preview", json={"inactive_days": 90}, headers=h).status_code == 403
    assert staff.get("/api/v1/admin/campaigns").json()["contacts"]["opted_in"] == 1
    luna, h = logged(biz, "luna-admin")
    assert luna.get("/api/v1/admin/campaigns").json()["contacts"]["total"] == 0
    assert luna.post("/api/v1/admin/campaigns/preview", json={"inactive_days": 90}, headers=h).json() == {"eligible": 0}


def test_smtp_failures_are_counted_and_generic(biz, monkeypatch, security_log):
    contact(biz.client, marketing_consent=True)
    age_contacts()

    class Down(FakeSMTP):
        def starttls(self, context=None):
            raise OSError("detalle-interno")

    monkeypatch.setattr(reactivation.smtplib, "SMTP", Down)
    admin, h = logged(biz, "sol-admin")
    admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    assert reactivation.list_campaigns(biz.sol)[0]["failed"] == 1
    assert "detalle-interno" not in json.dumps(security_log())


def test_no_personal_data_in_logs(biz, security_log):
    contact(biz.client, marketing_consent=True)
    age_contacts()
    admin, h = logged(biz, "sol-admin")
    admin.post("/api/v1/admin/campaigns", json=CAMPAIGN, headers=h)
    log = json.dumps(security_log())
    assert "ana@sol.com" not in log and "Ana Sol" not in log and "Te extrañamos" not in log


def test_booking_can_record_marketing_consent(biz):
    from app.services import booking

    booking.set_hours(biz.sol, booking.WeeklyHours(ranges=[booking.HoursRange(weekday=d, open="09:00", close="12:00") for d in range(7)]))
    service = booking.create_service(biz.sol, booking.ServiceIn(name="Consulta", duration_minutes=30, deposit_cents=0))
    slot = booking.list_slots(tenants.get(biz.sol), booking.get_service(biz.sol, service), __import__("datetime").date.today() + __import__("datetime").timedelta(days=2))[0]
    body = {"service_id": service, "start": slot, "name": "Beto", "email": "beto@sol.com", "consent": True, "marketing_consent": True}
    assert biz.client.post("/api/v1/public/sol/bookings", json=body).status_code == 201
    with get_connection() as db:
        assert db.execute("SELECT consent_source FROM contacts WHERE email = 'beto@sol.com'").fetchone()[0] == "booking"


# --- Configuración fail-closed --------------------------------------------------------------------

@pytest.mark.parametrize(
    "env",
    [
        {"SMTP_HOST": "smtp.example.com"},
        {"SMTP_FROM": "hola@negocio.example"},
        {**SMTP, "SMTP_USERNAME": "usuario"},
        {**SMTP, "SMTP_FROM": "Hola <hola@negocio.example>\r\nBcc: x@y.z"},
        {**SMTP, "PUBLIC_SITE_URL": ""},
    ],
)
def test_smtp_misconfiguration_refuses_to_start(make_client, env):
    with pytest.raises(ValueError):
        make_client(**env)
