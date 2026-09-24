"""Guest-safe FastAPI routes for the Gemini concierge."""

from __future__ import annotations

import os
from enum import StrEnum
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from paradise_park_sales_agent.ai.gemini_client import (
    GeminiConfigurationError,
    GeminiGenerationError,
    generate_grounded_draft,
)
from paradise_park_sales_agent.ai.knowledge import (
    search_approved_knowledge,
)
from paradise_park_sales_agent.telemetry_repository import record_event_safely


class ConciergeStatus(StrEnum):
    """Public states returned by the concierge."""

    ANSWERED = "answered"
    AMBASSADOR = "ambassador"


class ConciergeRequest(BaseModel):
    """Validated guest question."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    question: str = Field(
        min_length=3,
        max_length=600,
    )
    trace_id: str | None = Field(
        default=None,
        max_length=100,
    )
    lead_id: str | None = Field(default=None, max_length=80)


class ConciergeResponse(BaseModel):
    """Guest-safe answer that excludes internal model details."""

    model_config = ConfigDict(extra="forbid")

    status: ConciergeStatus
    trace_id: str
    answer: str
    source_ids: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(
        default_factory=list
    )
    recommended_action: str
    requires_ambassador: bool
    wellness_disclaimer_required: bool


router = APIRouter(
    prefix="/v1/concierge",
    tags=["AI concierge"],
)


def concierge_enabled() -> bool:
    """Return whether guest-facing AI is enabled."""

    return os.getenv(
        "AI_CONCIERGE_ENABLED",
        "false",
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def ambassador_fallback(
    trace_id: str,
) -> ConciergeResponse:
    """Return a safe response without exposing internal errors."""

    return ConciergeResponse(
        status=ConciergeStatus.AMBASSADOR,
        trace_id=trace_id,
        answer=(
            "I’m unable to confirm that from the approved "
            "Paradise Park information available to me. "
            "A Paradise Park Wellness Ambassador can help "
            "you with this question."
        ),
        source_ids=[],
        suggested_questions=[
            "Would you like to view your recommendation?"
        ],
        recommended_action="contact_ambassador",
        requires_ambassador=True,
        wellness_disclaimer_required=False,
    )


def action_value(action: object) -> str:
    """Convert an enum or string action into a public string."""

    value = getattr(action, "value", action)
    return str(value)


@router.post(
    "/answer",
    response_model=ConciergeResponse,
)
def answer_concierge_question(
    payload: ConciergeRequest,
) -> ConciergeResponse:
    """Answer a guest question from approved knowledge."""

    trace_id = payload.trace_id or str(uuid4())
    interaction_id = str(uuid4())
    started = perf_counter()

    def finish(
        response: ConciergeResponse,
        outcome: str,
    ) -> ConciergeResponse:
        record_event_safely(
            collection_environment_name="FIRESTORE_CONCIERGE_COLLECTION",
            default_collection="ai_concierge_interactions",
            record_id=interaction_id,
            values={
                "interaction_id": interaction_id,
                "lead_id": payload.lead_id,
                "trace_id": trace_id,
                "question": payload.question,
                "outcome": outcome,
                "public_status": response.status.value,
                "answer": response.answer,
                "source_ids": response.source_ids,
                "recommended_action": response.recommended_action,
                "requires_ambassador": response.requires_ambassador,
                "latency_ms": round((perf_counter() - started) * 1000),
            },
        )
        return response

    if not concierge_enabled():
        return finish(ambassador_fallback(trace_id), "disabled_fallback")

    sources = search_approved_knowledge(
        payload.question
    )

    if not sources:
        return finish(ambassador_fallback(trace_id), "insufficient_knowledge")

    try:
        draft = generate_grounded_draft(
            payload.question,
            sources,
        )

    except (
        GeminiConfigurationError,
        GeminiGenerationError,
    ):
        return finish(ambassador_fallback(trace_id), "model_error")

    return finish(ConciergeResponse(
        status=ConciergeStatus.ANSWERED,
        trace_id=trace_id,
        answer=draft.answer,
        source_ids=draft.source_ids,
        suggested_questions=(
            draft.suggested_questions
        ),
        recommended_action=action_value(
            draft.recommended_action
        ),
        requires_ambassador=(
            draft.requires_ambassador
        ),
        wellness_disclaimer_required=(
            draft.wellness_disclaimer_required
        ),
    ), "answered")
