"""Durable, privacy-aware storage for Paradise Park sales leads."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import os
from typing import Any, Mapping, Protocol


class LeadRepository(Protocol):
    """Storage boundary used by the public API and notification worker."""

    def upsert(self, lead_id: str, values: Mapping[str, Any]) -> None: ...


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def document_id(lead_id: str) -> str:
    """Create a safe, deterministic Firestore document identifier."""

    return hashlib.sha256(lead_id.encode("utf-8")).hexdigest()


class DisabledLeadRepository:
    """Local-only repository used unless durable storage is enabled."""

    def upsert(self, lead_id: str, values: Mapping[str, Any]) -> None:
        return None


class FirestoreLeadRepository:
    """Merge lead lifecycle events into one Firestore document."""

    def __init__(self) -> None:
        try:
            from google.cloud import firestore
        except ImportError as error:  # pragma: no cover - deployment guard
            raise RuntimeError(
                "LEAD_STORAGE_ENABLED requires google-cloud-firestore."
            ) from error

        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip() or None
        database = os.getenv("FIRESTORE_DATABASE", "(default)").strip()
        self._collection_name = os.getenv(
            "FIRESTORE_LEADS_COLLECTION", "sales_leads"
        ).strip()
        self._client = firestore.Client(project=project, database=database)

    def upsert(self, lead_id: str, values: Mapping[str, Any]) -> None:
        payload = dict(values)
        payload["lead_id"] = lead_id
        payload["updated_at"] = utc_now()
        reference = self._client.collection(self._collection_name).document(
            document_id(lead_id)
        )
        if "created_at" not in payload and not reference.get().exists:
            payload["created_at"] = utc_now()
        reference.set(payload, merge=True)


def lead_storage_enabled() -> bool:
    return os.getenv("LEAD_STORAGE_ENABLED", "false").strip().lower() == "true"


def get_lead_repository() -> LeadRepository:
    if lead_storage_enabled():
        return FirestoreLeadRepository()
    return DisabledLeadRepository()


def consent_safe_contact(values: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return only CRM-safe fields when marketing consent is explicit."""

    if values.get("marketing_consent") is not True:
        return None
    return {
        "name": values.get("name", ""),
        "email": str(values.get("email", "")).strip().lower(),
        "phone": values.get("phone", ""),
        "referral_source": values.get("referral_source", ""),
        "recommendation": values.get("recommendation", ""),
        "created_at": values.get("created_at", ""),
        "marketing_consent": True,
    }
