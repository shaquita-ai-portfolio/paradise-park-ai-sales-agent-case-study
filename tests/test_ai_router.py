"""Tests for the guest-facing AI concierge router."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

from paradise_park_sales_agent.ai.gemini_client import (
    GeminiGenerationError,
)
from paradise_park_sales_agent.ai.knowledge import (
    KnowledgeSource,
)
from paradise_park_sales_agent.api import app


router_module = importlib.import_module(
    "paradise_park_sales_agent.ai.router"
)

client = TestClient(app)


def sample_source() -> KnowledgeSource:
    """Return approved knowledge for endpoint tests."""

    return KnowledgeSource(
        source_id="package:rapid_reset",
        title="Rapid Reset",
        source_type="package",
        content=(
            '{"name": "Rapid Reset", '
            '"price": {"amount": 997}}'
        ),
        relevance_score=10,
    )


def test_concierge_rejects_short_question(
    monkeypatch,
) -> None:
    """Questions must satisfy the public request schema."""

    monkeypatch.setenv(
        "AI_CONCIERGE_ENABLED",
        "true",
    )

    response = client.post(
        "/v1/concierge/answer",
        json={"question": "x"},
    )

    assert response.status_code == 422


def test_disabled_concierge_returns_safe_fallback(
    monkeypatch,
) -> None:
    """Disabled AI must not cause an application failure."""

    monkeypatch.setenv(
        "AI_CONCIERGE_ENABLED",
        "false",
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "What is included in Rapid Reset?"
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ambassador"
    assert body["requires_ambassador"] is True
    assert body["source_ids"] == []
    assert "internal" not in body["answer"].lower()


def test_concierge_returns_grounded_answer(
    monkeypatch,
) -> None:
    """A validated Gemini draft becomes a public answer."""

    monkeypatch.setenv(
        "AI_CONCIERGE_ENABLED",
        "true",
    )

    monkeypatch.setattr(
        router_module,
        "search_approved_knowledge",
        lambda question: [sample_source()],
    )

    monkeypatch.setattr(
        router_module,
        "generate_grounded_draft",
        lambda question, sources: SimpleNamespace(
            answer=(
                "Rapid Reset is an approved personalized "
                "Paradise Park experience."
            ),
            source_ids=["package:rapid_reset"],
            suggested_questions=[
                "What is included?"
            ],
            recommended_action=SimpleNamespace(
                value="view_recommendation"
            ),
            requires_ambassador=False,
            wellness_disclaimer_required=False,
        ),
    )
    captured = {}
    monkeypatch.setattr(
        router_module,
        "record_event_safely",
        lambda **kwargs: captured.update(kwargs) or True,
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "What is included in Rapid Reset?"
            ),
            "trace_id": "test-trace-001",
            "lead_id": "test-lead-1234",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "answered"
    assert body["trace_id"] == "test-trace-001"
    assert body["source_ids"] == [
        "package:rapid_reset"
    ]
    assert (
        body["recommended_action"]
        == "view_recommendation"
    )
    assert body["requires_ambassador"] is False
    assert captured["default_collection"] == "ai_concierge_interactions"
    assert captured["values"]["question"] == "What is included in Rapid Reset?"
    assert captured["values"]["lead_id"] == "test-lead-1234"
    assert captured["values"]["outcome"] == "answered"


def test_gemini_failure_returns_safe_fallback(
    monkeypatch,
) -> None:
    """A model failure must not expose internal errors."""

    monkeypatch.setenv(
        "AI_CONCIERGE_ENABLED",
        "true",
    )

    monkeypatch.setattr(
        router_module,
        "search_approved_knowledge",
        lambda question: [sample_source()],
    )

    def fail_generation(question, sources):
        raise GeminiGenerationError(
            "Sensitive internal model failure."
        )

    monkeypatch.setattr(
        router_module,
        "generate_grounded_draft",
        fail_generation,
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "What is included in Rapid Reset?"
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ambassador"
    assert body["requires_ambassador"] is True
    assert "sensitive" not in body["answer"].lower()
    assert "failure" not in body["answer"].lower()


def test_no_approved_sources_returns_fallback(
    monkeypatch,
) -> None:
    """Gemini must never answer without approved grounding."""

    monkeypatch.setenv(
        "AI_CONCIERGE_ENABLED",
        "true",
    )

    monkeypatch.setattr(
        router_module,
        "search_approved_knowledge",
        lambda question: [],
    )

    response = client.post(
        "/v1/concierge/answer",
        json={
            "question": (
                "Do you offer an invented treatment?"
            )
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "ambassador"
    assert body["source_ids"] == []
    assert body["requires_ambassador"] is True

    
