"""Tests for the controlled Google Gemini adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from paradise_park_sales_agent.ai.gemini_client import (
    GeminiConfigurationError,
    GeminiGenerationError,
    GeminiSettings,
    build_grounded_prompt,
    generate_grounded_draft,
)
from paradise_park_sales_agent.ai.knowledge import KnowledgeSource
from paradise_park_sales_agent.ai.schemas import (
    ConciergeAction,
)


def sample_source() -> KnowledgeSource:
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


class FakeModels:
    def __init__(self, response: object) -> None:
        self.response = response
        self.last_request: dict | None = None

    def generate_content(self, **kwargs):
        self.last_request = kwargs
        return self.response


class FakeClient:
    def __init__(self, response: object) -> None:
        self.models = FakeModels(response)


def test_settings_require_project(monkeypatch) -> None:
    monkeypatch.delenv(
        "GOOGLE_CLOUD_PROJECT",
        raising=False,
    )

    with pytest.raises(GeminiConfigurationError):
        GeminiSettings.from_environment()


def test_grounded_prompt_contains_question_and_source() -> None:
    prompt = build_grounded_prompt(
        "What is Rapid Reset?",
        [sample_source()],
    )

    assert "What is Rapid Reset?" in prompt
    assert "package:rapid_reset" in prompt
    assert "997" in prompt


def test_generate_grounded_draft_accepts_valid_response() -> None:
    response = SimpleNamespace(
        parsed={
            "answer": (
                "Rapid Reset is an approved personalized "
                "Paradise Park experience."
            ),
            "source_ids": ["package:rapid_reset"],
            "suggested_questions": [
                "What is included?"
            ],
            "recommended_action": (
                "view_recommendation"
            ),
            "requires_ambassador": False,
            "wellness_disclaimer_required": False,
        },
        text=None,
    )
    client = FakeClient(response)
    settings = GeminiSettings(
        project="test-project",
        location="global",
        model="test-model",
    )

    draft = generate_grounded_draft(
        "What is Rapid Reset?",
        [sample_source()],
        client=client,
        settings=settings,
    )

    assert draft.source_ids == [
        "package:rapid_reset"
    ]
    assert (
        draft.recommended_action
        == ConciergeAction.VIEW_RECOMMENDATION
    )
    assert client.models.last_request is not None
    assert (
        client.models.last_request["model"]
        == "test-model"
    )


def test_generate_rejects_unknown_citation() -> None:
    response = SimpleNamespace(
        parsed={
            "answer": "A special discount is available.",
            "source_ids": [
                "policy:invented_discount"
            ],
            "suggested_questions": [],
            "recommended_action": "none",
            "requires_ambassador": False,
            "wellness_disclaimer_required": False,
        },
        text=None,
    )

    with pytest.raises(
        GeminiGenerationError,
        match="unknown sources",
    ):
        generate_grounded_draft(
            "Can I receive a special discount?",
            [sample_source()],
            client=FakeClient(response),
            settings=GeminiSettings(
                project="test-project",
                location="global",
                model="test-model",
            ),
        )


def test_generate_requires_approved_sources() -> None:
    with pytest.raises(
        GeminiGenerationError,
        match="without approved sources",
    ):
        generate_grounded_draft(
            "Tell me anything.",
            [],
            client=FakeClient(
                SimpleNamespace(parsed=None, text=None)
            ),
            settings=GeminiSettings(
                project="test-project",
                location="global",
                model="test-model",
            ),
        )


def test_invalid_model_output_is_rejected() -> None:
    response = SimpleNamespace(
        parsed=None,
        text='{"unexpected": "value"}',
    )

    with pytest.raises(
        GeminiGenerationError,
        match="invalid response structure",
    ):
        generate_grounded_draft(
            "What is Rapid Reset?",
            [sample_source()],
            client=FakeClient(response),
            settings=GeminiSettings(
                project="test-project",
                location="global",
                model="test-model",
            ),
        )

        