from decimal import Decimal

from paradise_park_sales_agent.commercial_policy import (
    AddonSelection,
    PaymentOption,
    quote_package,
)
from paradise_park_sales_agent.guardrails import evaluate_generated_text
from paradise_park_sales_agent.recommendation_engine import build_recommendation
from paradise_park_sales_agent.recommendation_models import (
    AssessmentMode,
    AssessmentSignal,
    RecommendationRequest,
    SignalSource,
)


def request(*, package_id: str, days: int, guests: int = 1) -> RecommendationRequest:
    return RecommendationRequest(
        assessment_mode=AssessmentMode.INNER_WELLNESS,
        group_size=guests,
        duration_days=days,
        preferred_package_id=package_id,
        budget=Decimal("50000"),
        goals=["high_stress", "anxiety"],
        signals=[AssessmentSignal(code="emotional_load", source=SignalSource.EXPLICIT)],
    )


def test_executive_is_priced_per_person() -> None:
    quote = quote_package("executive_reset", group_size=4, duration_days=3)
    assert quote.package_subtotal == Decimal("19200.00")


def test_executive_fourth_day_is_separate_and_not_discounted() -> None:
    quote = quote_package(
        "executive_reset",
        group_size=4,
        duration_days=4,
        payment_option=PaymentOption.PAY_IN_FULL,
    )
    assert quote.extended_program_subtotal == Decimal("4800.00")
    assert quote.discount == Decimal("1920.00")
    assert quote.order_total == Decimal("22080.00")


def test_peak_is_priced_per_person_with_two_extension_days() -> None:
    quote = quote_package("peak_performance_pivot", group_size=2, duration_days=5)
    assert quote.package_subtotal == Decimal("19974.00")
    assert quote.extended_program_subtotal == Decimal("4800.00")


def test_rapid_farm_to_table_is_a_paid_enhancement() -> None:
    quote = quote_package(
        "rapid_reset",
        addons=[AddonSelection("farm_to_table_individual")],
    )
    assert quote.addon_subtotal == Decimal("295.00")


def test_every_premium_day_has_three_plus_two_and_rotates() -> None:
    response = build_recommendation(request(package_id="peak_performance_pivot", days=4))
    for day in range(1, 5):
        daily = [item for item in response.agenda_items if item.day == day]
        assert sum(item.service_class == "low_overhead" for item in daily) == 3
        assert sum(item.service_class == "one_on_one" for item in daily) == 2

    for day in range(2, 5):
        previous = {item.service_id for item in response.agenda_items if item.day == day - 1}
        current = {item.service_id for item in response.agenda_items if item.day == day}
        assert previous != current


def test_medical_outcome_claims_are_blocked() -> None:
    assert not evaluate_generated_text("This regulates your hormones.").allowed
    assert not evaluate_generated_text("We address infertility.").allowed

