from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, model_validator

from paradise_park_sales_agent.guardrails import (
    GuardrailDecision,
    evaluate_guest_payload,
    evaluate_request_text,
)
from paradise_park_sales_agent.recommendation_engine import (
    build_recommendation,
)
from paradise_park_sales_agent.recommendation_models import (
    RecommendationRequest,
    RecommendationResponse,
)


class WorkflowStatus(StrEnum):
    COMPLETED = "completed"
    HUMAN_REVIEW = "human_review"


class SalesWorkflowResult(BaseModel):
    """Internal result from the deterministic sales workflow."""

    model_config = ConfigDict(extra="forbid")

    status: WorkflowStatus
    trace_id: str
    recommendation: RecommendationResponse | None = None
    guardrail_decision: GuardrailDecision
    message: str

    @model_validator(mode="after")
    def validate_workflow_result(self) -> "SalesWorkflowResult":
        if (
            self.status == WorkflowStatus.COMPLETED
            and self.recommendation is None
        ):
            raise ValueError(
                "A completed workflow requires a recommendation."
            )

        if (
            self.status == WorkflowStatus.HUMAN_REVIEW
            and self.recommendation is not None
        ):
            raise ValueError(
                "Unsafe or review-required recommendations "
                "must not be returned automatically."
            )

        return self


RecommendationBuilder = Callable[
    [RecommendationRequest],
    RecommendationResponse,
]


def collect_assessment_text(
    request: RecommendationRequest,
    additional_text: str,
) -> str:
    """Collect typed text for request-level safety checks."""

    statements = [
        signal.guest_statement
        for signal in request.signals
        if signal.guest_statement
    ]

    if additional_text.strip():
        statements.append(additional_text.strip())

    return "\n".join(statements)


def run_sales_workflow(
    request: RecommendationRequest,
    *,
    additional_text: str = "",
    recommendation_builder: RecommendationBuilder = build_recommendation,
) -> SalesWorkflowResult:
    """Run the deterministic Paradise Park MVP sales workflow."""

    request_text = collect_assessment_text(
        request,
        additional_text,
    )

    request_decision = evaluate_request_text(request_text)

    if not request_decision.allowed:
        return SalesWorkflowResult(
            status=WorkflowStatus.HUMAN_REVIEW,
            trace_id=str(uuid4()),
            recommendation=None,
            guardrail_decision=request_decision,
            message=(
                "Thank you for sharing this information. A Paradise "
                "Park team member will review your request personally "
                "before recommendations are provided."
            ),
        )

    recommendation = recommendation_builder(request)

    output_decision = evaluate_guest_payload(recommendation)

    if not output_decision.allowed:
        return SalesWorkflowResult(
            status=WorkflowStatus.HUMAN_REVIEW,
            trace_id=recommendation.trace_id,
            recommendation=None,
            guardrail_decision=output_decision,
            message=(
                "The proposed recommendation requires Paradise Park "
                "team review before it can be shared."
            ),
        )

    return SalesWorkflowResult(
        status=WorkflowStatus.COMPLETED,
        trace_id=recommendation.trace_id,
        recommendation=recommendation,
        guardrail_decision=output_decision,
        message=(
            "Your personalized Paradise Park recommendation is ready."
        ),
    )
