from decimal import Decimal

import pytest
from pydantic import ValidationError

from paradise_park_sales_agent.recommendation_models import (
    AgendaItemRecommendation,
    AssessmentMode,
    AssessmentSignal,
    CommercialStatus,
    ConsentPreferences,
    PackageRecommendation,
    RecommendationRequest,
    RecommendationResponse,
    SignalSource,
)


def create_package(package_id: str = "rapid_reset") -> PackageRecommendation:
    return PackageRecommendation(
        package_id=package_id,
        name="Rapid Reset",
        price_statement="$997.00",
        why_it_fits="This package may address the priorities you shared.",
    )


def create_item(order: int = 1) -> AgendaItemRecommendation:
    return AgendaItemRecommendation(
        order=order,
        service_id=f"service_{order}",
        name="Guided Wellness Activation",
        guest_description="A calming guided experience.",
        why_helpful="You stated that you want time to slow down.",
        commercial_status=CommercialStatus.PROPOSED_INCLUDED,
        price_statement="Included in this package.",
    )


def test_request_preserves_explicit_and_inferred_signals() -> None:
    request = RecommendationRequest(
        assessment_mode=AssessmentMode.INNER_WELLNESS,
        group_size=1,
        budget=Decimal("1000.00"),
        duration_days=2,
        goals=["rest", "reduce tension"],
        signals=[
            AssessmentSignal(
                code="physical_tension",
                source=SignalSource.EXPLICIT,
                guest_statement="I feel physically tense.",
            ),
            AssessmentSignal(
                code="prefers_gentle_movement",
                source=SignalSource.INFERRED,
            ),
        ],
    )

    assert request.signals[0].source == SignalSource.EXPLICIT
    assert request.signals[1].source == SignalSource.INFERRED
    assert request.duration_days == 2


def test_report_and_marketing_consent_are_independent() -> None:
    consent = ConsentPreferences(deliver_report=True, marketing=False)
    assert consent.deliver_report is True
    assert consent.marketing is False


def test_express_response_accepts_one_core_activation() -> None:
    response = RecommendationResponse(
        assessment_mode=AssessmentMode.RETREAT_PLANNER,
        reflected_statements=["You stated that rest is a priority."],
        personalized_narrative="Modern life can make rest difficult.",
        fit_signals=["Rest is a meaningful priority."],
        recommendation_strategy="within_target",
        package=create_package("express_reset"),
        agenda_items=[create_item()],
        price_summary="$147.00 paid in full.",
        call_to_action="Choose an Express Reset calendar date.",
        wellness_disclaimer="This is a wellness recommendation.",
    )

    assert len(response.agenda_items) == 1


def test_response_rejects_nonsequential_agenda_order() -> None:
    with pytest.raises(ValidationError, match="sequential"):
        RecommendationResponse(
            assessment_mode=AssessmentMode.RETREAT_PLANNER,
            reflected_statements=["You stated that rest is a priority."],
            personalized_narrative="Modern life can make rest difficult.",
            fit_signals=["Rest is a meaningful priority."],
            recommendation_strategy="within_target",
            package=create_package(),
            agenda_items=[create_item(order=2)],
            price_summary="$997.00",
            call_to_action="Reserve your Rapid Reset.",
            wellness_disclaimer="This is a wellness recommendation.",
        )


def test_internal_cost_cannot_enter_guest_package() -> None:
    with pytest.raises(ValidationError):
        PackageRecommendation(
            package_id="rapid_reset",
            name="Rapid Reset",
            price_statement="$997",
            why_it_fits="This package may support the priorities shared.",
            internal_cost="500.00",
        )
