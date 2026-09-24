"""Export explicitly consented Firestore contacts for Wix CSV import."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from google.cloud import firestore

from paradise_park_sales_agent.lead_repository import consent_safe_contact


FIELDS = (
    "name",
    "email",
    "phone",
    "referral_source",
    "recommendation",
    "created_at",
    "marketing_consent",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export consented Paradise Park contacts for Wix."
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--database", default="(default)")
    parser.add_argument("--collection", default="sales_leads")
    args = parser.parse_args()

    client = firestore.Client(project=args.project, database=args.database)
    contacts_by_email: dict[str, dict[str, object]] = {}
    query = client.collection(args.collection).where(
        filter=firestore.FieldFilter("marketing_consent", "==", True)
    )
    for snapshot in query.stream():
        contact = consent_safe_contact(snapshot.to_dict())
        if contact and contact["email"]:
            contacts_by_email[str(contact["email"])] = contact

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(
            contacts_by_email[email]
            for email in sorted(contacts_by_email)
        )
    print(f"Exported {len(contacts_by_email)} consented contacts.")


if __name__ == "__main__":
    main()
