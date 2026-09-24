from decimal import Decimal

from paradise_park_sales_agent.recommendation_engine import (
    build_recommendation,
)
from paradise_park_sales_agent.recommendation_models import (
    AssessmentMode,
    AssessmentSignal,
    RecommendationRequest,
    SignalSource,
)
from paradise_park_sales_agent.workflow import (
    WorkflowStatus,
    run_sales_workflow,
)


def create_request(
    guest_statement: str = "I want unhurried rest.",
) -> RecommendationRequest:
    return RecommendationRequest(
        assessment_mode=AssessmentMode.RETREAT_PLANNER,
        group_size=1,
        budget=Decimal("1200"),
        goals=["deep_rest"],
        signals=[
            AssessmentSignal(
                code="deep_rest",
                source=SignalSource.EXPLICIT,
                guest_statement=guest_statement,
            )
        ],
    )


def test_safe_request_completes_workflow() -> None:
    result = run_sales_workflow(create_request())

    assert result.status == WorkflowStatus.COMPLETED
    assert result.recommendation is not None
    assert result.recommendation.package.package_id == "rapid_reset"
    assert len(result.recommendation.agenda_items) >= 3


def test_pregnancy_request_routes_to_human_review() -> None:
    result = run_sales_workflow(
        create_request(
            "I am pregnant and want help selecting services."
        )
    )

    assert result.status == WorkflowStatus.HUMAN_REVIEW
    assert result.recommendation is None
    assert result.guardrail_decision.requires_human_review is True


def test_crisis_language_routes_to_human_review() -> None:
    result = run_sales_workflow(
        create_request(
            "I have been thinking about self-harm."
        )
    )

    assert result.status == WorkflowStatus.HUMAN_REVIEW
    assert result.recommendation is None


def test_unsafe_generated_output_is_not_returned() -> None:
    def unsafe_builder(request: RecommendationRequest):
        recommendation = build_recommendation(request)
        recommendation.agenda_items[0].why_helpful = (
            "This experience cures chronic stress."
        )
        return recommendation

    result = run_sales_workflow(
        create_request(),
        recommendation_builder=unsafe_builder,
    )

    assert result.status == WorkflowStatus.HUMAN_REVIEW
    assert result.recommendation is None
    assert "treatment_claim" in result.guardrail_decision.reasons


def test_trace_id_matches_recommendation() -> None:
    result = run_sales_workflow(create_request())

    assert result.recommendation is not None
    assert result.trace_id == result.recommendation.trace_id

    