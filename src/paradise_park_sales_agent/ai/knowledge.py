"""Guest-safe retrieval over approved Paradise Park knowledge."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from paradise_park_sales_agent.catalog import load_catalog
from paradise_park_sales_agent.runtime_paths import DATA_DIR


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "which",
    "with",
    "you",
}

QUERY_ALIASES = {
    "cost": {"price", "pricing", "investment"},
    "price": {"cost", "pricing", "investment"},
    "book": {"booking", "calendar", "reserve", "reservation"},
    "date": {"availability", "booking", "schedule"},
    "group": {"team", "corporate", "participants", "guests"},
    "relax": {"rest", "reset", "calm", "restoration"},
    "stress": {"rest", "reset", "calm", "tension"},
    "women": {"womb", "fertility", "cycle", "postpartum"},
    "product": {"herbal", "blend", "balm", "face", "soil"},
}


class KnowledgeSource(BaseModel):
    """One approved source that may be supplied to Gemini."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    relevance_score: int = Field(default=0, ge=0)


def load_json(filename: str) -> dict[str, Any]:
    """Load one approved business-data file."""

    path = DATA_DIR / filename

    with path.open(encoding="utf-8") as source:
        return json.load(source)


@lru_cache(maxsize=1)
def approved_documents() -> tuple[KnowledgeSource, ...]:
    """Build the guest-safe knowledge collection."""

    catalog = load_catalog()
    policies = load_json("package_policies.json")
    documents: list[KnowledgeSource] = []

    for package in catalog.packages:
        safe_content = {
            "package_id": package.id,
            "name": package.name,
            "price": package.price.model_dump(),
            "sales_promise": package.sales_promise,
            "guest_fit_copy": package.guest_fit_copy,
            "primary_cta": package.primary_cta,
        }

        policy = policies.get("packages", {}).get(package.id)
        if policy:
            safe_content["approved_package_policy"] = {
                key: policy.get(key)
                for key in (
                    "audience",
                    "base_price",
                    "minimum_guests",
                    "maximum_guests",
                    "base_duration_minutes",
                    "maximum_duration_minutes",
                    "full_meal_included",
                    "farm_to_table_included",
                    "lodging_included",
                    "deposit_allowed",
                    "pay_in_full_discount_allowed",
                    "direct_checkout_allowed",
                    "soft_extras",
                    "guest_promise",
                    "comparison_copy",
                )
                if key in policy
            }

        documents.append(
            KnowledgeSource(
                source_id=f"package:{package.id}",
                title=package.name,
                source_type="package",
                content=json.dumps(safe_content, sort_keys=True),
            )
        )

    for service in catalog.services:
        documents.append(
            KnowledgeSource(
                source_id=f"service:{service.id}",
                title=service.name,
                source_type="service",
                content=json.dumps(
                    service.guest_safe_dict(),
                    sort_keys=True,
                ),
            )
        )

    payment_policy = policies.get("payment_policy", {})
    documents.append(
        KnowledgeSource(
            source_id="policy:payments",
            title="Payment and reservation policy",
            source_type="policy",
            content=json.dumps(
                {
                    key: payment_policy.get(key)
                    for key in (
                        "deposit_percent",
                        "pay_in_full_discount_percent",
                        "discount_applies_to",
                        "individual_balance_due_days",
                        "group_balance_due_days",
                        "rush_window_hours",
                        "individual_rush_or_late_fee",
                        "group_rush_or_late_fee",
                    )
                    if key in payment_policy
                },
                sort_keys=True,
            ),
        )
    )

    documents.append(
        KnowledgeSource(
            source_id="policy:wellness-ambassador",
            title="Contact a Paradise Park Wellness Ambassador",
            source_type="policy",
            content=(
                "Guests can connect directly with a Paradise Park Wellness "
                "Ambassador using the Connect with a Wellness Ambassador "
                "button. The approved contact page is "
                "https://www.paradiseislife.biz/contact-8. Do not promise "
                "that the AI will send a message or make the connection itself."
            ),
        )
    )

    documents.append(
        KnowledgeSource(
            source_id="policy:availability",
            title="Paradise Park experience availability",
            source_type="policy",
            content=(
                "Paradise Park retreat experiences are offered during the "
                "second and fourth weeks of each month. Approved service "
                "days are Tuesday, Thursday, Friday, Saturday and Sunday. "
                "Requests remain subject to final availability confirmation "
                "by a Paradise Park Wellness Ambassador."
            ),
        )
    )

    return tuple(documents)


def query_terms(question: str) -> set[str]:
    """Convert a natural-language question into searchable terms."""

    tokens = {
        token
        for token in TOKEN_PATTERN.findall(question.lower())
        if token not in STOP_WORDS and len(token) > 1
    }

    expanded = set(tokens)

    for token in tokens:
        expanded.update(QUERY_ALIASES.get(token, set()))

    return expanded


def relevance_score(
    document: KnowledgeSource,
    terms: set[str],
) -> int:
    """Score a document using transparent lexical matching."""

    searchable = (
        f"{document.source_id} {document.title} {document.content}"
    ).lower()

    score = 0

    for term in terms:
        if term in document.title.lower():
            score += 5
        elif term in document.source_id.lower():
            score += 4
        elif term in searchable:
            score += 1

    return score


def search_approved_knowledge(
    question: str,
    *,
    limit: int = 6,
) -> list[KnowledgeSource]:
    """Return the most relevant approved sources for a question."""

    clean_question = question.strip()

    if not clean_question:
        return []

    if limit < 1 or limit > 10:
        raise ValueError("Knowledge-search limit must be between 1 and 10")

    terms = query_terms(clean_question)

    ranked = [
        document.model_copy(
            update={
                "relevance_score": relevance_score(document, terms),
            }
        )
        for document in approved_documents()
    ]

    matches = [
        document
        for document in ranked
        if document.relevance_score > 0
    ]

    matches.sort(
        key=lambda document: (
            -document.relevance_score,
            document.source_id,
        )
    )

    return matches[:limit]


def clear_knowledge_cache() -> None:
    """Clear cached documents during tests or controlled reloads."""

    approved_documents.cache_clear()

    
