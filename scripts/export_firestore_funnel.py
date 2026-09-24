#!/usr/bin/env python3
"""Read-only Firestore funnel exporter for Paradise Park.

Exports the three production telemetry collections to CSV and creates one
lead-level joined CSV. This script never writes to Firestore.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from google.cloud import firestore


COLLECTIONS = (
    "sales_leads",
    "conversion_feedback",
    "ai_concierge_interactions",
)


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_value(v) for v in value]
    if hasattr(value, "path"):
        return str(value.path)
    if hasattr(value, "latitude") and hasattr(value, "longitude"):
        return {"latitude": value.latitude, "longitude": value.longitude}
    return str(value)


def flatten(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            result.update(flatten(item, name))
        elif isinstance(item, (list, tuple, set)):
            result[name] = json.dumps(json_value(item), ensure_ascii=False)
        else:
            result[name] = json_value(item)
    return result


def read_collection(client: firestore.Client, collection: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for snapshot in client.collection(collection).stream():
        data = snapshot.to_dict() or {}
        row = {
            "_collection": collection,
            "_document_id": snapshot.id,
            "_document_path": snapshot.reference.path,
            **flatten(data),
        }
        rows.append(row)
    return rows


def ordered_fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = ["_collection", "_document_id", "_document_path", "lead_id"]
    discovered = {key for row in rows for key in row}
    return [key for key in preferred if key in discovered] + sorted(discovered - set(preferred))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ordered_fields(rows)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(rows)


def first_present(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def lead_key(row: dict[str, Any]) -> str:
    return first_present(row, ("lead_id", "leadId", "lead.id", "_document_id"))


def timestamp_value(row: dict[str, Any]) -> str:
    return first_present(
        row,
        (
            "updated_at",
            "created_at",
            "timestamp",
            "occurred_at",
            "submitted_at",
            "received_at",
        ),
    )


def build_joined(
    leads: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    interactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lead_map: dict[str, dict[str, Any]] = {}
    feedback_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    interaction_map: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in leads:
        lead_map[lead_key(row)] = row
    for row in feedback:
        feedback_map[lead_key(row)].append(row)
    for row in interactions:
        interaction_map[lead_key(row)].append(row)

    all_keys = sorted(set(lead_map) | set(feedback_map) | set(interaction_map))
    joined: list[dict[str, Any]] = []

    for key in all_keys:
        base = dict(lead_map.get(key, {}))
        fb_rows = feedback_map.get(key, [])
        ix_rows = interaction_map.get(key, [])
        event_types = sorted(
            {
                first_present(row, ("event_type", "event", "interaction_type", "type", "action"))
                for row in ix_rows
            }
            - {""}
        )
        base.update(
            {
                "lead_id_joined": key,
                "feedback_count": len(fb_rows),
                "interaction_count": len(ix_rows),
                "interaction_event_types": " | ".join(event_types),
                "latest_feedback_at": max((timestamp_value(r) for r in fb_rows), default=""),
                "latest_interaction_at": max((timestamp_value(r) for r in ix_rows), default=""),
                "feedback_document_ids": " | ".join(r["_document_id"] for r in fb_rows),
                "interaction_document_ids": " | ".join(r["_document_id"] for r in ix_rows),
            }
        )
        joined.append(base)
    return joined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--database", default="(default)")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = firestore.Client(project=args.project, database=args.database)

    data = {name: read_collection(client, name) for name in COLLECTIONS}
    for name, rows in data.items():
        write_csv(args.output_dir / f"{name}.csv", rows)

    joined = build_joined(
        data["sales_leads"],
        data["conversion_feedback"],
        data["ai_concierge_interactions"],
    )
    write_csv(args.output_dir / "firestore_joined_funnel.csv", joined)

    manifest = {
        "exported_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "project": args.project,
        "database": args.database,
        "counts": {name: len(rows) for name, rows in data.items()},
        "joined_lead_count": len(joined),
        "files": [
            *(f"{name}.csv" for name in COLLECTIONS),
            "firestore_joined_funnel.csv",
        ],
    }
    (args.output_dir / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
