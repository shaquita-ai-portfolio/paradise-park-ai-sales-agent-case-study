"""Tests for Paradise Park AI concierge contracts."""

import pytest
from pydantic import ValidationError

from paradise_park_sales_agent.ai.schemas import (
    ConciergeAction,
    ConciergeRequest,
    ConciergeResponse,
    GeminiAnswerDraft,
    SourceCitation,
)


def test_concierge_request_accepts_valid_question() -> None:
    request = ConciergeRequest(
        question=(
            "What is the difference between Express "
            "and Rapid Reset?"
        )
    )

    assert request.question.startswith("What is")
    assert request.conversation_id is None


def test_concierge_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ConciergeRequest(
            question="What is included?",
            requested_discount="50 percent",
        )


def test_gemini_draft_accepts_approved_action() -> None:
    draft = GeminiAnswerDraft(
        answer="Rapid Reset offers a personalized half-day reset.",
        source_ids=["package:rapid_reset"],
        suggested_questions=["What is included?"],
        recommended_action=ConciergeAction.VIEW_RECOMMENDATION,
    )

    assert (
        draft.recommended_action
        == ConciergeAction.VIEW_RECOMMENDATION
    )


def test_gemini_draft_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        GeminiAnswerDraft(
            answer="I changed the price for you.",
            source_ids=["package:rapid_reset"],
            recommended_action="apply_unapproved_discount",
        )


def test_gemini_draft_requires_unique_sources() -> None:
    with pytest.raises(ValidationError):
        GeminiAnswerDraft(
            answer="Rapid Reset may support your goals.",
            source_ids=[
                "package:rapid_reset",
                "package:rapid_reset",
            ],
        )


def test_gemini_draft_rejects_too_many_questions() -> None:
    with pytest.raises(ValidationError):
        GeminiAnswerDraft(
            answer="Here are several other questions.",
            source_ids=["package:rapid_reset"],
            suggested_questions=[
                "Question one?",
                "Question two?",
                "Question three?",
                "Question four?",
            ],
        )


def test_concierge_response_accepts_citation() -> None:
    response = ConciergeResponse(
        conversation_id="conversation-123",
        answer="Express Reset is a brief Paradise Park experience.",
        sources=[
            SourceCitation(
                source_id="package:express_reset",
                label="Express Reset",
            )
        ],
        recommended_action=(
            ConciergeAction.OPEN_EXPRESS_CALENDAR
        ),
    )

    assert response.used_fallback is False
    assert response.sources[0].label == "Express Reset"

    