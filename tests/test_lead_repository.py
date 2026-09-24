from __future__ import annotations

from typing import Any, Mapping

from paradise_park_sales_agent.lead_repository import (
    consent_safe_contact,
    document_id,
)
from paradise_park_sales_agent.lead_service import (
    notify_admin_and_record,
    persist_lead,
)


class MemoryRepository:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def upsert(self, lead_id: str, values: Mapping[str, Any]) -> None:
        self.records.setdefault(lead_id, {}).update(values)


def test_document_id_is_stable_and_firestore_safe() -> None:
    assert document_id("lead/with/slashes") == document_id("lead/with/slashes")
    assert "/" not in document_id("lead/with/slashes")


def test_lead_is_preserved_before_notification() -> None:
    repository = MemoryRepository()
    persist_lead(
        repository,
        lead_id="lead-12345678",
        stage="assessment_started",
        values={"email": "guest@example.com"},
    )
    assert repository.records["lead-12345678"]["email"] == "guest@example.com"
    assert repository.records["lead-12345678"]["notification_status"] == "pending"


def test_email_failure_is_recorded_without_deleting_lead(monkeypatch) -> None:
    repository = MemoryRepository()
    persist_lead(
        repository,
        lead_id="lead-12345678",
        stage="assessment_started",
        values={"email": "guest@example.com"},
    )
    monkeypatch.setattr(
        "paradise_park_sales_agent.lead_service.send_admin_report",
        lambda **_: False,
    )
    notify_admin_and_record(
        repository,
        lead_id="lead-12345678",
        subject="Test",
        fields={},
    )
    record = repository.records["lead-12345678"]
    assert record["email"] == "guest@example.com"
    assert record["notification_status"] == "failed"


def test_marketing_export_requires_explicit_consent() -> None:
    private_record = {
        "name": "Guest",
        "email": "Guest@Example.com",
        "priority_codes": ["grief_support"],
        "marketing_consent": False,
    }
    assert consent_safe_contact(private_record) is None


def test_marketing_export_excludes_sensitive_assessment_fields() -> None:
    record = {
        "name": "Guest",
        "email": "Guest@Example.com",
        "phone": "4045550100",
        "referral_source": "Instagram",
        "recommendation": "Executive Reset",
        "created_at": "2026-08-31T00:00:00+00:00",
        "priority_codes": ["grief_support", "fertility_support"],
        "recommendation_reason": "Private narrative",
        "marketing_consent": True,
    }
    contact = consent_safe_contact(record)
    assert contact is not None
    assert contact["email"] == "guest@example.com"
    assert "priority_codes" not in contact
    assert "recommendation_reason" not in contact
