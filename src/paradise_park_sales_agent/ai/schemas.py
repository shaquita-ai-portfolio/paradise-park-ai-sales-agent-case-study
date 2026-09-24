"""Strict data contracts for the Paradise Park AI concierge."""

from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class StrictAIModel(BaseModel):
    """Shared safety configuration for AI-facing models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ConciergeAction(StrEnum):
    """Guest actions the AI concierge may suggest."""

    NONE = "none"
    VIEW_RECOMMENDATION = "view_recommendation"
    COMPARE_PACKAGES = "compare_packages"
    OPEN_EXPRESS_CALENDAR = "open_express_calendar"
    CONTACT_AMBASSADOR = "contact_ambassador"
    VIEW_PRODUCTS = "view_products"


class ConciergeRequest(StrictAIModel):
    """Public question submitted by a Paradise Park guest."""

    question: str = Field(
        min_length=2,
        max_length=1000,
    )
    conversation_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=128,
    )


class SourceCitation(StrictAIModel):
    """Guest-safe reference supporting an AI answer."""

    source_id: str = Field(
        min_length=1,
        max_length=160,
    )
    label: str = Field(
        min_length=1,
        max_length=160,
    )


class GeminiAnswerDraft(StrictAIModel):
    """Structured draft Gemini must generate before safety validation."""

    answer: str = Field(
        min_length=1,
        max_length=3000,
    )
    source_ids: list[str] = Field(
        min_length=1,
        max_length=6,
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        max_length=3,
    )
    recommended_action: ConciergeAction = ConciergeAction.NONE
    requires_ambassador: bool = False
    wellness_disclaimer_required: bool = False

    @field_validator("source_ids")
    @classmethod
    def require_unique_source_ids(
        cls,
        source_ids: list[str],
    ) -> list[str]:
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source IDs must be unique")

        return source_ids

    @field_validator("suggested_questions")
    @classmethod
    def validate_suggested_questions(
        cls,
        questions: list[str],
    ) -> list[str]:
        cleaned_questions: list[str] = []

        for question in questions:
            cleaned = question.strip()

            if not cleaned:
                raise ValueError(
                    "Suggested questions cannot be empty"
                )

            if len(cleaned) > 200:
                raise ValueError(
                    "Suggested questions must be 200 characters or fewer"
                )

            cleaned_questions.append(cleaned)

        if len(cleaned_questions) != len(set(cleaned_questions)):
            raise ValueError(
                "Suggested questions must be unique"
            )

        return cleaned_questions


class ConciergeResponse(StrictAIModel):
    """Validated answer returned to the website."""

    conversation_id: str = Field(
        min_length=8,
        max_length=128,
    )
    answer: str = Field(
        min_length=1,
        max_length=3000,
    )
    sources: list[SourceCitation] = Field(
        default_factory=list,
        max_length=6,
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        max_length=3,
    )
    recommended_action: ConciergeAction = ConciergeAction.NONE
    requires_ambassador: bool = False
    wellness_disclaimer: str | None = Field(
        default=None,
        max_length=500,
    )
    used_fallback: bool = False

    