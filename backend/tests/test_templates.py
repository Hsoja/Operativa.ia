"""P2.12 Plantillas por vertical: válidas, aplicables en un paso y sin pisar lo configurado."""

import json
from datetime import date, timedelta

import pytest

from app import cli
from app.services import agent, booking, coverage, templates, tenants
from helpers import reset_db

VERTICALS = ["dental", "fisio", "hogar", "salon"]


@pytest.fixture(autouse=True)
def clean(client):
    reset_db()


def test_the_four_verticals_exist_and_are_valid():
    assert templates.available() == VERTICALS
    for key in VERTICALS:
        template = templates.load(key)
        assert template.key == key and template.services and template.hours


@pytest.mark.parametrize("key", ["../etc/passwd", "dental.json", "DENTAL", "", "x", "general", None])
def test_unknown_or_malicious_keys_rejected(key):
    with pytest.raises(templates.TemplateError):
        templates.load(key)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(extra="x"),
        lambda d: d["services"][0].update(deposit_cents=-5),
        lambda d: d.update(hours=[{"weekday": 0, "open": "09:00", "close": "12:00"}, {"weekday": 0, "open": "11:00", "close": "13:00"}]),
        lambda d: d.update(key="otro"),
        lambda d: d["coverage"].update(insurers=["!!"]),
    ],
)
def test_malformed_template_files_rejected(tmp_path, mutate):
    data = json.loads((templates.TEMPLATES_DIR / "dental.json").read_text(encoding="utf-8"))
    mutate(data)
    (tmp_path / "dental.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(templates.TemplateError):
        templates.load("dental", directory=tmp_path)


def _next_weekday(target: int) -> date:
    day = date.today() + timedelta(days=2)
    while day.weekday() != target:
        day += timedelta(days=1)
    return day


@pytest.mark.parametrize("key", VERTICALS)
def test_business_from_template_is_ready_to_operate(key, monkeypatch):
    """De cero a operativo: horarios libres, cobertura y Sofía con sus herramientas."""
    assert cli.main(["create-tenant", "--slug", f"demo-{key}", "--name", "Negocio Demo", "--template", key, "--location", "Waterloo, ON"]) == 0
    tenant = tenants.get_by_slug(f"demo-{key}")
    template = templates.load(key)
    assert tenant["template"] == key and tenant["business_type"] == template.profile.business_type
    services = booking.list_services(tenant["id"])
    assert {s["name"] for s in services} == {s.name for s in template.services}
    workday = template.hours[0].weekday
    assert booking.list_slots(tenant, services[0], _next_weekday(workday))
    names = agent.enabled_tools(tenant["id"])
    assert "list_available_slots" in names
    assert ("check_coverage" in names) == any(template.coverage.model_dump().values())
    prompt = agent.build_system_prompt(tenant, "check_coverage" in names, "list_available_slots" in names)
    assert template.profile.services in prompt


def test_coverage_examples_per_vertical():
    for key, query, expected in [
        ("dental", {"insurer": "sun life"}, "covered"),
        ("hogar", {"postal_code": "N2L 3G1"}, "covered"),
        ("hogar", {"postal_code": "M5V 2T6"}, "not_covered"),
    ]:
        slug = f"cov-{key}"
        if not tenants.get_by_slug(slug):
            cli.main(["create-tenant", "--slug", slug, "--name", "Demo", "--template", key])
        result = coverage.check(tenants.get_by_slug(slug)["id"], coverage.CoverageQuery(**query))
        assert expected in (result["area"], result["insurance"])


def test_apply_never_overwrites_existing_configuration():
    cli.main(["create-tenant", "--slug", "propio", "--name", "Negocio Propio", "--business-type", "spa"])
    tenant = tenants.get_by_slug("propio")
    booking.create_service(tenant["id"], booking.ServiceIn(name="Limpieza dental", duration_minutes=30, deposit_cents=999))
    booking.set_hours(tenant["id"], booking.WeeklyHours(ranges=[booking.HoursRange(weekday=6, open="10:00", close="11:00")]))
    coverage.set_rules(tenant["id"], coverage.CoverageRules(cities=["Guelph"]))

    applied = templates.apply(tenant["id"], "dental")
    assert "business_type" not in applied["profile"] and applied["hours"] is False and applied["coverage"] is False
    assert "Limpieza dental" not in applied["services"]
    after = tenants.get(tenant["id"])
    assert after["business_type"] == "spa"
    limpieza = [s for s in booking.list_services(tenant["id"]) if s["name"] == "Limpieza dental"][0]
    assert limpieza["deposit_cents"] == 999
    assert booking.get_hours(tenant["id"]) == [{"weekday": 6, "open": "10:00", "close": "11:00"}]
    assert coverage.get_rules(tenant["id"])["cities"] == ["Guelph"]


def test_apply_twice_is_idempotent():
    cli.main(["create-tenant", "--slug", "doble", "--name", "Doble", "--template", "salon"])
    tenant = tenants.get_by_slug("doble")
    before = booking.list_services(tenant["id"])
    assert templates.apply(tenant["id"], "salon")["services"] == []
    assert booking.list_services(tenant["id"]) == before


def test_cli_template_errors_do_not_create_half_a_business():
    assert cli.main(["create-tenant", "--slug", "roto", "--name", "Roto", "--template", "no-existe"]) == 2
    assert tenants.get_by_slug("roto") is None
    assert cli.main(["apply-template", "--tenant", "nadie", "--template", "dental"]) == 1
    assert cli.main(["list-templates"]) == 0


def test_campaign_suggestion_comes_from_template():
    cli.main(["create-tenant", "--slug", "camp", "--name", "Camp", "--template", "dental"])
    assert "limpieza" in templates.campaign_suggestion(tenants.get_by_slug("camp")).subject.lower()
    cli.main(["create-tenant", "--slug", "sin", "--name", "Sin plantilla"])
    assert templates.campaign_suggestion(tenants.get_by_slug("sin")) is None
