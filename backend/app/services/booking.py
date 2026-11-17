"""Agenda con depósito - Operativa.ia (P2.10)

- Servicios con duración y depósito fijo por servicio (el monto SIEMPRE sale de aquí, nunca del cliente).
- Horario semanal por negocio; los huecos se calculan en la zona horaria del negocio.
- Una reserva web crea una cita "pending_payment" que bloquea el hueco `BOOKING_HOLD_MINUTES`.
- La comprobación de solapes y el INSERT van en una transacción BEGIN IMMEDIATE: no hay doble reserva.
"""

import secrets
import time
from datetime import date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, Field, field_validator

from app.core.config import get_settings
from app.core.db import get_connection
from app.core.validation import CleanStr, StrictModel
from app.services.auth import hash_token
from app.services.leads import EMAIL

SLOT_STEP_MINUTES = 15
REF_PATTERN = r"^[A-Za-z0-9_-]{20,64}$"


class BookingError(ValueError):
    """La reserva no se puede hacer (servicio, hueco o datos inválidos)."""


class SlotTaken(BookingError):
    """El hueco ya no está libre."""


# --- Modelos ---------------------------------------------------------------------------------------

class ServiceIn(StrictModel):
    name: CleanStr(min_length=2, max_length=80)
    duration_minutes: Annotated[int, Field(ge=5, le=480)]
    deposit_cents: Annotated[int, Field(ge=0, le=100_000)]
    currency: Literal["cad", "usd", "mxn", "eur"] = "cad"
    active: bool = True


class HoursRange(StrictModel):
    weekday: Annotated[int, Field(ge=0, le=6)]  # 0 = lunes
    open: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
    close: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$|^24:00$")]

    def minutes(self) -> tuple[int, int]:
        to_min = lambda t: int(t[:2]) * 60 + int(t[3:])
        return to_min(self.open), to_min(self.close)


class WeeklyHours(StrictModel):
    ranges: Annotated[list[HoursRange], Field(max_length=28)]

    @field_validator("ranges")
    @classmethod
    def _valid_ranges(cls, ranges: list[HoursRange]) -> list[HoursRange]:
        by_day: dict[int, list[tuple[int, int]]] = {}
        for r in ranges:
            start, end = r.minutes()
            if start >= end:
                raise ValueError("La hora de cierre debe ser posterior a la de apertura.")
            by_day.setdefault(r.weekday, []).append((start, end))
        for spans in by_day.values():
            spans.sort()
            if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
                raise ValueError("Los horarios de un mismo día no pueden solaparse.")
        return ranges


def _valid_email(value: str) -> str:
    if not EMAIL.fullmatch(value):
        raise ValueError("Correo inválido.")
    return value.lower()


def _must_consent(value: bool) -> bool:
    if value is not True:
        raise ValueError("Se requiere consentimiento.")
    return value


class BookingIn(StrictModel):
    service_id: Annotated[int, Field(ge=1)]
    start: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")]  # hora local del negocio
    name: CleanStr(min_length=2, max_length=80)
    email: Annotated[CleanStr(min_length=6, max_length=254), AfterValidator(_valid_email)]
    consent: Annotated[bool, AfterValidator(_must_consent)]
    marketing_consent: bool = False  # CASL: casilla aparte, desmarcada por defecto
    website: Annotated[str, Field(max_length=0)] = ""  # trampa para bots


class PanelBookingIn(StrictModel):
    """Cita que agenda el equipo desde el panel: sin depósito, el correo es opcional."""

    service_id: Annotated[int, Field(ge=1)]
    start: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")]
    name: CleanStr(min_length=2, max_length=80)
    email: str = ""


# --- Servicios y horario ----------------------------------------------------------------------------

def list_services(tenant_id: int, only_active: bool = True) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT id, name, duration_minutes, deposit_cents, currency, active FROM services "
            "WHERE tenant_id = ? AND (active = 1 OR ? = 0) ORDER BY name",
            (tenant_id, 1 if only_active else 0),
        ).fetchall()
    return [dict(r) for r in rows]


def get_service(tenant_id: int, service_id: int, only_active: bool = True) -> dict | None:
    with get_connection() as db:
        row = db.execute(
            "SELECT id, name, duration_minutes, deposit_cents, currency, active FROM services "
            "WHERE id = ? AND tenant_id = ? AND (active = 1 OR ? = 0)",
            (service_id, tenant_id, 1 if only_active else 0),
        ).fetchone()
    return dict(row) if row else None


def create_service(tenant_id: int, service: ServiceIn) -> int:
    with get_connection() as db:
        return int(
            db.execute(
                "INSERT INTO services (tenant_id, name, duration_minutes, deposit_cents, currency, active) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, service.name, service.duration_minutes, service.deposit_cents, service.currency, int(service.active)),
            ).lastrowid
        )


def update_service(tenant_id: int, service_id: int, service: ServiceIn) -> bool:
    with get_connection() as db:
        return (
            db.execute(
                "UPDATE services SET name = ?, duration_minutes = ?, deposit_cents = ?, currency = ?, active = ? "
                "WHERE id = ? AND tenant_id = ?",
                (service.name, service.duration_minutes, service.deposit_cents, service.currency, int(service.active), service_id, tenant_id),
            ).rowcount
            == 1
        )


def set_hours(tenant_id: int, hours: WeeklyHours) -> None:
    with get_connection() as db:
        db.execute("DELETE FROM business_hours WHERE tenant_id = ?", (tenant_id,))
        for r in hours.ranges:
            start, end = r.minutes()
            db.execute(
                "INSERT INTO business_hours (tenant_id, weekday, open_minute, close_minute) VALUES (?, ?, ?, ?)",
                (tenant_id, r.weekday, start, end),
            )


def get_hours(tenant_id: int) -> list[dict]:
    fmt = lambda m: f"{m // 60:02d}:{m % 60:02d}"
    with get_connection() as db:
        rows = db.execute(
            "SELECT weekday, open_minute, close_minute FROM business_hours WHERE tenant_id = ? ORDER BY weekday, open_minute",
            (tenant_id,),
        ).fetchall()
    return [{"weekday": r["weekday"], "open": fmt(r["open_minute"]), "close": fmt(r["close_minute"])} for r in rows]


# --- Huecos -------------------------------------------------------------------------------------------

def _tz(tenant: dict) -> ZoneInfo:
    return ZoneInfo(tenant["timezone"])


def bookable_days(tenant: dict, now: int | None = None) -> tuple[date, date]:
    now = int(time.time()) if now is None else now
    today = datetime.fromtimestamp(now, _tz(tenant)).date()
    return today, today + timedelta(days=get_settings().booking_days_ahead)


def _busy(db, tenant_id: int, start: int, end: int, now: int) -> list[tuple[int, int]]:
    rows = db.execute(
        "SELECT starts_at, ends_at FROM appointments WHERE tenant_id = ? AND starts_at < ? AND ends_at > ? AND "
        "(status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > ?))",
        (tenant_id, end, start, now),
    ).fetchall()
    return [(r["starts_at"], r["ends_at"]) for r in rows]


def list_slots(tenant: dict, service: dict, day: date, now: int | None = None) -> list[str]:
    """Horas de inicio libres (hora local "YYYY-MM-DDTHH:MM") para un servicio en un día."""
    settings = get_settings()
    now = int(time.time()) if now is None else now
    first, last = bookable_days(tenant, now)
    if not first <= day <= last:
        return []
    tz = _tz(tenant)
    day_start = int(datetime.combine(day, datetime.min.time(), tz).timestamp())
    day_end = day_start + 2 * 86400  # holgura para cambios de horario
    with get_connection() as db:
        ranges = db.execute(
            "SELECT open_minute, close_minute FROM business_hours WHERE tenant_id = ? AND weekday = ? ORDER BY open_minute",
            (tenant["id"], day.weekday()),
        ).fetchall()
        busy = _busy(db, tenant["id"], day_start, day_end, now)
    duration = service["duration_minutes"]
    earliest = now + settings.booking_lead_minutes * 60
    slots = []
    for r in ranges:
        minute = r["open_minute"]
        while minute + duration <= r["close_minute"]:
            local = datetime.combine(day, datetime.min.time(), tz) + timedelta(minutes=minute)
            start = int(local.timestamp())
            end = start + duration * 60
            if start >= earliest and not any(s < end and e > start for s, e in busy):
                slots.append(local.strftime("%Y-%m-%dT%H:%M"))
            minute += SLOT_STEP_MINUTES
    return slots


# --- Reservas ------------------------------------------------------------------------------------------

def _new_ref() -> str:
    return secrets.token_urlsafe(24)


def create_booking(tenant: dict, booking: BookingIn | PanelBookingIn, source: str = "web", now: int | None = None) -> dict:
    """Crea la cita. Con depósito queda pendiente de pago; sin depósito queda confirmada."""
    settings = get_settings()
    now = int(time.time()) if now is None else now
    service = get_service(tenant["id"], booking.service_id)
    if service is None:
        raise BookingError("Servicio no disponible.")
    tz = _tz(tenant)
    try:
        local = datetime.strptime(booking.start, "%Y-%m-%dT%H:%M").replace(tzinfo=tz)
    except ValueError:
        raise BookingError("Fecha u hora inválida.") from None
    if booking.start not in list_slots(tenant, service, local.date(), now):
        raise SlotTaken("Ese horario no está disponible.")

    start = int(local.timestamp())
    end = start + service["duration_minutes"] * 60
    pending = service["deposit_cents"] > 0 and source == "web"
    ref = _new_ref()
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")  # bloquea escrituras concurrentes entre la comprobación y el INSERT
        if _busy(db, tenant["id"], start, end, now):
            raise SlotTaken("Ese horario no está disponible.")
        cursor = db.execute(
            "INSERT INTO appointments (tenant_id, service_id, starts_at, ends_at, status, source, customer_name, "
            "customer_email, deposit_cents, currency, ref_hash, hold_expires_at, created_at, confirmed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant["id"],
                service["id"],
                start,
                end,
                "pending_payment" if pending else "confirmed",
                source,
                booking.name,
                booking.email,
                service["deposit_cents"] if source == "web" else 0,
                service["currency"],
                hash_token(ref),
                now + settings.booking_hold_minutes * 60 if pending else None,
                now,
                None if pending else now,
            ),
        )
    return {
        "id": int(cursor.lastrowid),
        "ref": ref,
        "status": "pending_payment" if pending else "confirmed",
        "service": service,
        "start_local": booking.start,
        "starts_at": start,
    }


def attach_session(tenant_id: int, appointment_id: int, session_id: str) -> None:
    with get_connection() as db:
        db.execute(
            "UPDATE appointments SET stripe_session_id = ? WHERE id = ? AND tenant_id = ? AND status = 'pending_payment'",
            (session_id, appointment_id, tenant_id),
        )


def cancel(tenant_id: int, appointment_id: int) -> bool:
    with get_connection() as db:
        return (
            db.execute(
                "UPDATE appointments SET status = 'cancelled', hold_expires_at = NULL "
                "WHERE id = ? AND tenant_id = ? AND status IN ('pending_payment', 'confirmed')",
                (appointment_id, tenant_id),
            ).rowcount
            == 1
        )


def status_by_ref(tenant_id: int, ref: str) -> dict | None:
    """Estado público de una reserva: sin nombre ni correo del cliente."""
    with get_connection() as db:
        row = db.execute(
            "SELECT a.status, a.starts_at, s.name AS service FROM appointments a JOIN services s ON s.id = a.service_id "
            "WHERE a.ref_hash = ? AND a.tenant_id = ?",
            (hash_token(ref), tenant_id),
        ).fetchone()
    return dict(row) if row else None


def list_appointments(tenant_id: int, since: int, limit: int = 100) -> list[dict]:
    with get_connection() as db:
        rows = db.execute(
            "SELECT a.id, a.starts_at, a.ends_at, a.status, a.source, a.customer_name, a.customer_email, "
            "a.deposit_cents, a.currency, s.name AS service FROM appointments a JOIN services s ON s.id = a.service_id "
            "WHERE a.tenant_id = ? AND a.ends_at >= ? ORDER BY a.starts_at LIMIT ?",
            (tenant_id, since, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def expire_holds(now: int | None = None) -> int:
    """Marca como vencidas las citas cuyo pago no llegó a tiempo (el hueco ya estaba libre de todos modos)."""
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        return db.execute(
            "UPDATE appointments SET status = 'expired' WHERE status = 'pending_payment' AND hold_expires_at <= ?",
            (now,),
        ).rowcount


def confirm_payment(tenant_id: int, appointment_id: int, session_id: str, amount: int, currency: str, now: int | None = None) -> str:
    """Confirma una cita pagada. Devuelve el resultado; nunca confía en montos que no coincidan."""
    now = int(time.time()) if now is None else now
    with get_connection() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM appointments WHERE id = ? AND tenant_id = ? AND stripe_session_id = ?",
            (appointment_id, tenant_id, session_id),
        ).fetchone()
        if row is None:
            return "unknown"
        if row["status"] == "confirmed":
            return "already_confirmed"
        if amount != row["deposit_cents"] or currency.lower() != row["currency"]:
            db.execute("UPDATE appointments SET status = 'needs_refund' WHERE id = ?", (appointment_id,))
            return "amount_mismatch"
        if row["status"] not in ("pending_payment", "expired"):
            db.execute("UPDATE appointments SET status = 'needs_refund' WHERE id = ?", (appointment_id,))
            return "not_pending"
        # Si el hueco se liberó y alguien más lo tomó mientras tanto, se marca para reembolso manual
        others = db.execute(
            "SELECT 1 FROM appointments WHERE tenant_id = ? AND id != ? AND starts_at < ? AND ends_at > ? AND "
            "(status = 'confirmed' OR (status = 'pending_payment' AND hold_expires_at > ?))",
            (tenant_id, appointment_id, row["ends_at"], row["starts_at"], now),
        ).fetchone()
        if others:
            db.execute("UPDATE appointments SET status = 'needs_refund' WHERE id = ?", (appointment_id,))
            return "slot_conflict"
        db.execute(
            "UPDATE appointments SET status = 'confirmed', confirmed_at = ?, hold_expires_at = NULL WHERE id = ?",
            (now, appointment_id),
        )
        return "confirmed"


def expire_session(tenant_id: int, appointment_id: int, session_id: str) -> bool:
    with get_connection() as db:
        return (
            db.execute(
                "UPDATE appointments SET status = 'expired' WHERE id = ? AND tenant_id = ? AND stripe_session_id = ? "
                "AND status = 'pending_payment'",
                (appointment_id, tenant_id, session_id),
            ).rowcount
            == 1
        )


def get_appointment(tenant_id: int, appointment_id: int) -> dict | None:
    with get_connection() as db:
        row = db.execute(
            "SELECT a.*, s.name AS service, s.duration_minutes FROM appointments a JOIN services s ON s.id = a.service_id "
            "WHERE a.id = ? AND a.tenant_id = ?",
            (appointment_id, tenant_id),
        ).fetchone()
    return dict(row) if row else None
