"""Lead lifecycle persistence and observable admin notifications."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from paradise_park_sales_agent.lead_reporting import send_admin_report
from paradise_park_sales_agent.lead_repository import LeadRepository, utc_now


LOGGER = logging.getLogger(__name__)


def persist_lead(
    repository: LeadRepository,
    *,
    lead_id: str,
    stage: str,
    values: Mapping[str, Any],
) -> None:
    payload = dict(values)
    payload["stage"] = stage
    if stage == "assessment_started":
        payload.setdefault("created_at", utc_now())
    payload["notification_status"] = "pending"
    repository.upsert(lead_id, payload)


def notify_admin_and_record(
    repository: LeadRepository,
    *,
    lead_id: str,
    subject: str,
    fields: Mapping[str, object],
) -> None:
    sent = send_admin_report(subject=subject, fields=fields)
    status = "sent" if sent else "failed"
    repository.upsert(
        lead_id,
        {
            "notification_status": status,
            "notification_last_attempt_at": utc_now(),
        },
    )
    LOGGER.info("Admin notification status=%s lead_id=%s", status, lead_id)
