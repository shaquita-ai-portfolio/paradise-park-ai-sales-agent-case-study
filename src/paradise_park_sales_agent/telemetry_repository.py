"""Fail-open Firestore storage for sales and concierge telemetry."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import logging
import os
from typing import Any, Mapping


LOGGER = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def telemetry_storage_enabled() -> bool:
    """Use the lead-storage switch unless telemetry is explicitly configured."""

    configured = os.getenv("TELEMETRY_STORAGE_ENABLED")
    if configured is None:
        configured = os.getenv("LEAD_STORAGE_ENABLED", "false")
    return configured.strip().lower() == "true"


def event_document_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_event_safely(
    *,
    collection_environment_name: str,
    default_collection: str,
    record_id: str,
    values: Mapping[str, Any],
) -> bool:
    """Merge an event into Firestore without disrupting the guest journey."""

    if not telemetry_storage_enabled():
        return False

    try:
        from google.cloud import firestore

        project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip() or None
        database = os.getenv("FIRESTORE_DATABASE", "(default)").strip()
        collection = os.getenv(
            collection_environment_name,
            default_collection,
        ).strip()
        client = firestore.Client(project=project, database=database)
        payload = dict(values)
        payload["updated_at"] = utc_now()
        reference = client.collection(collection).document(record_id)
        if "created_at" not in payload and not reference.get().exists:
            payload["created_at"] = utc_now()
        reference.set(payload, merge=True)
        return True
    except Exception:  # pragma: no cover - production fail-open boundary
        LOGGER.exception("Telemetry persistence failed for %s", default_collection)
        return False
