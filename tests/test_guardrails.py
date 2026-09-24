from decimal import Decimal

import pytest

from paradise_park_sales_agent.guardrails import (
    GuardrailViolation,
    assert_guest_safe,
    evaluate_generated_text,
    evaluate_guest_payload,
    evaluate_request_text,
)
from paradise_park_sales_agent.recommendation_engine import (
    build_recommendation,
)
from paradise_park_sales_agent.recommendation_models import (
    AssessmentMode,
    AssessmentSignal,
    RecommendationRequest,
    SignalSource,
)


def create_safe_recommendation():
    request = RecommendationRequest(
        assessment_mode=AssessmentMode.RETREAT_PLANNER,
        group_size=1,
        budget=Decimal("1200"),
        goals=["deep_rest"],
        signals=[
            AssessmentSignal(
                code="deep_rest",
                source=SignalSource.EXPLICIT,
                guest_statement="I want unhurried rest.",
            )
        ],
    )

    return build_recommendation(request)


def test_valid_recommendation_passes_guardrails() -> None:
    decision = evaluate_guest_payload(
        create_safe_recommendation()
    )

    assert decision.allowed is True
    assert decision.requires_human_review is False


def test_internal_cost_is_blocked() -> None:
    decision = evaluate_guest_payload(
        {
            "package": "Rapid Reset",
            "internal_cost": 500,
        }
    )

    assert decision.allowed is False
    assert "internal_field_exposure" in decision.reasons


def test_diagnosis_language_is_blocked() -> None:
    decision = evaluate_generated_text(
        "You have trauma and need this service."
    )

    assert decision.allowed is False
    assert "diagnosis_claim" in decision.reasons


def test_cure_claim_is_blocked() -> None:
    decision = evaluate_generated_text(
        "This experience cures chronic stress."
    )

    assert decision.allowed is False
    assert "treatment_claim" in decision.reasons


def test_pregnancy_routes_to_human_review() -> None:
    decision = evaluate_request_text(
        "I am pregnant and would like a wellness session."
    )

    assert decision.allowed is False
    assert decision.requires_human_review is True
    assert "pregnancy_or_postpartum" in decision.reasons


def test_crisis_language_routes_to_human_review() -> None:
    decision = evaluate_request_text(
        "I have been thinking about self-harm."
    )

    assert decision.allowed is False
    assert decision.requires_human_review is True
    assert "self_harm_language" in decision.reasons


def test_assert_guest_safe_raises_for_unsafe_payload() -> None:
    with pytest.raises(GuardrailViolation):
        assert_guest_safe(
            {
                "recommendation": (
                    "This service guarantees results."
                )
            }
        )