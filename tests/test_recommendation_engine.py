from decimal import Decimal

import pytest

from paradise_park_sales_agent.recommendation_engine import build_recommendation
from paradise_park_sales_agent.recommendation_models import (
    AssessmentMode,
    AssessmentSignal,
    CommercialStatus,
    RecommendationRequest,
    SignalSource,
)


def make_request(
    *,
    budget: str = "1200",
    group_size: int = 1,
    duration_days: int = 1,
    goals: list[str] | None = None,
    signals: list[str] | None = None,
    preferred_package_id: str | None = None,
) -> RecommendationRequest:
    signal_codes = signals or ["deep_rest"]
    return RecommendationRequest(
        assessment_mode=AssessmentMode.RETREAT_PLANNER,
        group_size=group_size,
        budget=Decimal(budget),
        duration_days=duration_days,
        preferred_package_id=preferred_package_id,
        goals=goals or ["deep_rest"],
        signals=[
            AssessmentSignal(
                code=code,
                source=SignalSource.EXPLICIT,
                guest_statement=f"I selected {code}.",
            )
            for code in signal_codes
        ],
    )


@pytest.mark.parametrize(
    ("budget", "group_size", "duration", "goals", "expected"),
    [
        ("500", 1, 1, ["deep_rest"], "express_reset"),
        ("1200", 1, 1, ["deep_rest"], "rapid_reset"),
        ("2500", 1, 2, ["deep_rest"], "executive_reset"),
        ("9987", 1, 3, ["deep_rest"], "peak_performance_pivot"),
        ("5000", 12, 1, ["team_connection"], "group_wellness_reset"),
        ("15000", 15, 2, ["overnight_stay"], "group_immersive_retreat"),
        ("7000", 6, 1, ["team_connection"], "premium_small_group_retreat"),
    ],
)
def test_selects_approved_package_tier(
    budget: str,
    group_size: int,
    duration: int,
    goals: list[str],
    expected: str,
) -> None:
    response = build_recommendation(
        make_request(
            budget=budget,
            group_size=group_size,
            duration_days=duration,
            goals=goals,
        )
    )
    assert response.package.package_id == expected


def test_express_has_one_core_service_and_no_private_upgrade() -> None:
    response = build_recommendation(make_request(budget="500"))

    assert len(response.agenda_items) == 1
    assert response.package.checkout_mode == "express_calendar"
    assert response.agenda_items[0].commercial_status == (
        CommercialStatus.PROPOSED_INCLUDED
    )
    assert response.payment_choices[0].amount_due_now == Decimal("147.00")


def test_two_day_personal_reset_honors_the_guests_investment_target() -> None:
    response = build_recommendation(
        make_request(budget="1200", duration_days=2, goals=["deep_rest"])
    )

    assert response.package.package_id == "rapid_reset"
    assert response.pricing_breakdown.duration_days == 1


def test_rapid_does_not_automatically_add_a_paid_upsell() -> None:
    response = build_recommendation(
        make_request(signals=["deep_rest", "womb_centered"])
    )
    included_quantity = sum(
        item.quantity
        for item in response.agenda_items
        if item.commercial_status == CommercialStatus.PROPOSED_INCLUDED
    )
    paid = [
        item
        for item in response.agenda_items
        if item.commercial_status == CommercialStatus.PAID_UPGRADE
    ]

    assert included_quantity == 4
    assert paid == []


def test_executive_does_not_charge_rapid_only_cart_enhancements() -> None:
    request = make_request(
        budget="2500",
        duration_days=2,
        goals=["deep_rest"],
    ).model_copy(update={"selected_addon_ids": ["assisted_stretch"]})

    response = build_recommendation(request)

    assert response.package.package_id == "executive_reset"
    assert response.pricing_breakdown is not None
    assert response.pricing_breakdown.addon_subtotal == Decimal("0.00")
    assert all(
        item.commercial_status != CommercialStatus.PAID_UPGRADE
        for item in response.agenda_items
    )


def test_two_day_executive_obeys_daily_caps() -> None:
    response = build_recommendation(
        make_request(
            budget="3400",
            duration_days=2,
            signals=["emotional_load", "womb_centered"],
        )
    )
    low_quantity = sum(
        item.quantity
        for item in response.agenda_items
        if item.service_class == "low_overhead"
    )
    private_quantity = sum(
        item.quantity
        for item in response.agenda_items
        if item.service_class == "one_on_one"
    )

    assert low_quantity == 6
    assert private_quantity == 4
    assert any(item.service_id == "vegan_dining" for item in response.core_experiences)


def test_peak_has_daily_three_plus_two_entitlements() -> None:
    response = build_recommendation(
        make_request(budget="9987", duration_days=3)
    )
    low = sum(
        item.quantity
        for item in response.agenda_items
        if item.service_id in {
            "guided_reflection", "sound_therapy", "river_rest",
            "guided_breathwork", "aromatherapy_treatment",
            "forest_bathing", "tea_tasting", "garden_tour",
        }
    )
    private = sum(
        item.quantity
        for item in response.agenda_items
        if item.service_id in {"assisted_stretch", "elevated_facial"}
    )

    assert low == 9
    assert sum(item.quantity for item in response.agenda_items if item.service_class == "one_on_one") == 6
    assert "60 days" in response.package.duration_statement


def test_report_contains_three_wholistic_pathway_insights() -> None:
    response = build_recommendation(make_request())
    assert {item.pathway for item in response.wellness_insights} == {
        "internal_work", "external_work", "environment"
    }


def test_pay_in_full_and_deposit_choices_are_present() -> None:
    response = build_recommendation(make_request())
    choices = {choice.payment_option: choice for choice in response.payment_choices}

    assert choices["pay_in_full"].savings == Decimal("99.70")
    assert choices["pay_in_full"].amount_due_now == Decimal("897.30")
    assert choices["deposit"].amount_due_now == Decimal("498.50")
    assert choices["deposit"].description == (
        "Reserve now and pay the remaining balance 14 days before "
        "the event date."
    )


def test_two_day_group_wellness_prices_every_guest_every_day() -> None:
    response = build_recommendation(
        make_request(
            budget="5000",
            group_size=12,
            duration_days=2,
            goals=["team_connection"],
        )
    )
    choices = {choice.payment_option: choice for choice in response.payment_choices}

    assert response.package.package_id == "group_wellness_reset"
    assert choices["deposit"].order_total == Decimal("9000.00")
    assert choices["deposit"].amount_due_now == Decimal("4500.00")
    assert "per person per day" in response.price_summary


def test_overnight_interest_does_not_override_a_499_investment_target() -> None:
    response = build_recommendation(
        make_request(
            budget="499",
            duration_days=2,
            goals=["overnight_stay", "deep_rest"],
        )
    )

    assert response.package.package_id == "express_reset"


def test_multiple_deep_support_signals_do_not_override_budget() -> None:
    response = build_recommendation(
        make_request(
            budget="499",
            signals=["high_stress", "clarity_transition"],
        )
    )

    assert response.package.package_id == "express_reset"
    assert response.recommendation_strategy == "within_target"
    assert len(response.alternatives) == 1
    assert response.alternatives[0].package_id == "rapid_reset"


def test_six_guests_always_receive_an_eligible_group_tier() -> None:
    response = build_recommendation(
        make_request(
            budget="499",
            group_size=6,
            signals=["high_stress", "clarity_transition"],
        )
    )

    assert response.package.package_id == "premium_small_group_retreat"
    assert "minimum 6 guests" in response.package.duration_statement


def test_twelve_guest_group_sees_immersive_tier_as_conditional() -> None:
    response = build_recommendation(
        make_request(
            budget="5000",
            group_size=12,
            duration_days=2,
            goals=["team_connection"],
        )
    )
    immersive = next(
        option
        for option in response.alternatives
        if option.package_id == "group_immersive_retreat"
    )

    assert immersive.qualification_note is not None
    assert "15-guest minimum" in immersive.qualification_note


def test_guest_can_choose_an_eligible_alternative() -> None:
    response = build_recommendation(
        make_request(
            budget="40000",
            group_size=15,
            duration_days=2,
            goals=["team_connection"],
            preferred_package_id="group_immersive_retreat",
        )
    )

    assert response.package.package_id == "group_immersive_retreat"


def test_ineligible_alternative_cannot_bypass_minimum_group_size() -> None:
    response = build_recommendation(
        make_request(
            budget="5000",
            group_size=12,
            duration_days=2,
            goals=["team_connection"],
            preferred_package_id="group_immersive_retreat",
        )
    )

    assert response.package.package_id == "group_wellness_reset"


def test_guest_response_never_exposes_internal_cost() -> None:
    serialized = build_recommendation(make_request()).model_dump_json()
    assert "internal_cost" not in serialized
    assert "overhead_tier" not in serialized
    assert "internal_name" not in serialized


def test_business_result_is_deterministic() -> None:
    request = make_request()
    first = build_recommendation(request).model_dump(exclude={"trace_id"})
    second = build_recommendation(request).model_dump(exclude={"trace_id"})
    assert first == second
