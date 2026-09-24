"""API tests for the guest-facing Gemini concierge."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from paradise_park_sales_agent.ai.schemas import ConciergeAction
from paradise_park_sales_agent.api import app


client = TestClient(app)


def test_disabled_concierge_uses_ambassador_fallback(
    monkeypatch,
) -> None:
    """The production-safe default does not call Gemini."""

    monkeypatch.setenv("AI_CONCIERGE_ENABLED", "false")

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "What is the difference between "
                "Express and Rapid Reset?"
            ),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ambassador"
    assert body["requires_ambassador"] is True
    assert body["recommended_action"] == "contact_ambassador"
    assert body["source_ids"] == []
    assert body["trace_id"]


def test_unknown_question_uses_ambassador_fallback(
    monkeypatch,
) -> None:
    """No approved source means Gemini must not improvise."""

    monkeypatch.setenv("AI_CONCIERGE_ENABLED", "true")

    monkeypatch.setattr(
        "paradise_park_sales_agent.ai.router."
        "search_approved_knowledge",
        lambda question: [],
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": "Can you guarantee a medical outcome?",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ambassador"
    assert body["requires_ambassador"] is True
    assert body["recommended_action"] == "contact_ambassador"


def test_grounded_concierge_returns_valid_answer(
    monkeypatch,
) -> None:
    """A grounded Gemini draft is returned through the public API."""

    monkeypatch.setenv("AI_CONCIERGE_ENABLED", "true")

    approved_source = SimpleNamespace(
        source_id="package-policies",
        title="Approved package policies",
        content="Express Reset is $147. Rapid Reset is $997.",
    )

    draft = SimpleNamespace(
        answer=(
            "Express Reset is a brief introduction to Paradise "
            "Park, while Rapid Reset provides a more personalized "
            "half-day experience."
        ),
        source_ids=["package-policies"],
        suggested_questions=[
            "What is included in Rapid Reset?",
        ],
        recommended_action=ConciergeAction.COMPARE_PACKAGES,
        requires_ambassador=False,
        wellness_disclaimer_required=False,
    )

    monkeypatch.setattr(
        "paradise_park_sales_agent.ai.router."
        "search_approved_knowledge",
        lambda question: [approved_source],
    )

    monkeypatch.setattr(
        "paradise_park_sales_agent.ai.router."
        "generate_grounded_draft",
        lambda question, sources: draft,
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "What is the difference between "
                "Express and Rapid Reset?"
            ),
            "trace_id": "sales-trace-001",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "answered"
    assert body["trace_id"] == "sales-trace-001"
    assert body["requires_ambassador"] is False
    assert body["recommended_action"] == "compare_packages"
    assert body["source_ids"] == ["package-policies"]
    assert "Express Reset" in body["answer"]


def test_concierge_rejects_short_question() -> None:
    """FastAPI rejects invalid input before calling the AI layer."""

    response = client.post(
        "/v1/concierge/answer",
        json={"question": "Hi"},
    )

    assert response.status_code == 422


def test_concierge_rejects_unexpected_fields() -> None:
    """Unapproved request fields cannot enter the AI workflow."""

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": "What does Rapid Reset include?",
            "override_price": "1.00",
        },
    )

    assert response.status_code == 422

    