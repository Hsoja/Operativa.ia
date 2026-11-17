"""Métricas del panel - Operativa.ia

Conteos reales por negocio (siempre filtrados por tenant_id). Sin datos personales.
"""

import time

from app.core.db import get_connection

DAY = 86400


def tenant_summary(tenant_id: int, now: int | None = None) -> dict:
    now = int(time.time()) if now is None else now
    week = now - 7 * DAY
    with get_connection() as db:
        leads_total = db.execute("SELECT COUNT(*) FROM leads WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
        leads_week = db.execute(
            "SELECT COUNT(*) FROM leads WHERE tenant_id = ? AND created_at >= ?", (tenant_id, week)
        ).fetchone()[0]
        conversations_week = db.execute(
            "SELECT COUNT(*) FROM conversations WHERE tenant_id = ? AND last_at >= ?", (tenant_id, week)
        ).fetchone()[0]
        messages_week = db.execute(
            "SELECT COUNT(*) FROM messages WHERE tenant_id = ? AND role = 'user' AND created_at >= ?", (tenant_id, week)
        ).fetchone()[0]
    return {
        "leads_total": leads_total,
        "leads_week": leads_week,
        "conversations_week": conversations_week,
        "messages_week": messages_week,
    }
