"""Tests for Paradise Park package entitlements and payment policy."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from paradise_park_sales_agent.commercial_policy import (
    AddonSelection,
    CommercialPolicyError,
    PaymentOption,
    PolicyRepository,
    balance_due_date,
    quote_package,
    validate_experience_plan,
    welcome_package_window,
)


def test_express_is_one_three_hour_core_service() -> None:
    result = validate_experience_plan(
        "express_reset",
        included_low_overhead_sessions=1,
    )

    assert result.estimated_duration_minutes == 180
    assert result.included_private_sessions == 0


def test_express_rejects_multiple_core_services() -> None:
    with pytest.raises(CommercialPolicyError, match="exactly one"):
        validate_experience_plan(
            "express_reset",
            included_low_overhead_sessions=3,
        )


def test_express_prices_one_private_enhancement() -> None:
    quote = quote_package(
        "express_reset",
        addons=[AddonSelection("womb_wellness")],
    )
    assert quote.addon_subtotal == Decimal("225.00")
    assert quote.order_total == Decimal("372.00")


def test_express_is_paid_in_full_without_discount() -> None:
    quote = quote_package("express_reset")

    assert quote.package_subtotal == Decimal("147.00")
    assert quote.discount == Decimal("0.00")
    assert quote.amount_due_now == Decimal("147.00")


def test_express_rejects_deposit() -> None:
    with pytest.raises(CommercialPolicyError, match="paid in full"):
        quote_package(
            "express_reset",
            payment_option=PaymentOption.DEPOSIT,
        )


def test_rapid_contains_four_low_overhead_sessions() -> None:
    result = validate_experience_plan(
        "rapid_reset",
        included_low_overhead_sessions=4,
    )

    assert result.estimated_duration_minutes == 240


def test_rapid_rejects_included_private_service() -> None:
    with pytest.raises(CommercialPolicyError, match="paid upgrades"):
        validate_experience_plan(
            "rapid_reset",
            included_low_overhead_sessions=4,
            included_private_sessions=1,
        )


def test_standard_rapid_allows_one_private_upgrade() -> None:
    quote = quote_package(
        "rapid_reset",
        payment_option=PaymentOption.DEPOSIT,
        addons=[AddonSelection("womb_wellness")],
    )

    assert quote.package_subtotal == Decimal("997.00")
    assert quote.addon_subtotal == Decimal("225.00")
    assert quote.order_total == Decimal("1222.00")
    assert quote.amount_due_now == Decimal("611.00")


def test_standard_rapid_rejects_two_private_upgrades() -> None:
    with pytest.raises(CommercialPolicyError, match="no more than 1"):
        quote_package(
            "rapid_reset",
            addons=[
                AddonSelection("womb_wellness"),
                AddonSelection("assisted_stretch"),
            ],
        )


def test_extended_rapid_allows_two_private_upgrades() -> None:
    quote = quote_package(
        "rapid_reset",
        payment_option=PaymentOption.DEPOSIT,
        extended_rapid=True,
        addons=[
            AddonSelection("womb_wellness"),
            AddonSelection("assisted_stretch"),
        ],
    )

    assert quote.addon_subtotal == Decimal("400.00")
    assert quote.order_total == Decimal("1397.00")


def test_rapid_never_exceeds_six_hours() -> None:
    repository = PolicyRepository()
    policy = repository.package("rapid_reset")

    assert policy["maximum_duration_minutes"] == 360


def test_rapid_pay_in_full_discount_applies_only_to_package_base() -> None:
    quote = quote_package(
        "rapid_reset",
        addons=[AddonSelection("womb_wellness")],
    )

    assert quote.discount == Decimal("99.70")
    assert quote.addon_subtotal == Decimal("225.00")
    assert quote.order_total == Decimal("1122.30")


def test_executive_duration_prices_are_deterministic() -> None:
    assert quote_package(
        "executive_reset", duration_days=1
    ).package_subtotal == Decimal("1800.00")
    assert quote_package(
        "executive_reset", duration_days=2
    ).package_subtotal == Decimal("3400.00")
    assert quote_package(
        "executive_reset", duration_days=3
    ).package_subtotal == Decimal("4800.00")


def test_two_day_executive_caps_private_sessions_at_four() -> None:
    result = validate_experience_plan(
        "executive_reset",
        duration_days=2,
        included_low_overhead_sessions=6,
        included_private_sessions=4,
    )

    assert result.included_private_sessions == 4

    with pytest.raises(CommercialPolicyError, match="no more than 4"):
        validate_experience_plan(
            "executive_reset",
            duration_days=2,
            included_low_overhead_sessions=6,
            included_private_sessions=5,
        )


def test_peak_entitlements_are_exact() -> None:
    result = validate_experience_plan(
        "peak_performance_pivot",
        duration_days=3,
        included_low_overhead_sessions=9,
        included_private_sessions=6,
    )

    assert result.duration_days == 3
    assert result.included_low_overhead_sessions == 9
    assert result.included_private_sessions == 6


def test_peak_pay_in_full_total_is_8988_30() -> None:
    quote = quote_package(
        "peak_performance_pivot",
        duration_days=3,
        payment_option=PaymentOption.PAY_IN_FULL,
    )

    assert quote.discount == Decimal("998.70")
    assert quote.order_total == Decimal("8988.30")
    assert quote.remaining_balance == Decimal("0.00")


def test_peak_deposit_is_4993_50() -> None:
    quote = quote_package(
        "peak_performance_pivot",
        duration_days=3,
        payment_option=PaymentOption.DEPOSIT,
    )

    assert quote.discount == Decimal("0.00")
    assert quote.order_total == Decimal("9987.00")
    assert quote.amount_due_now == Decimal("4993.50")
    assert quote.remaining_balance == Decimal("4993.50")


def test_group_wellness_reset_has_ten_guest_minimum() -> None:
    with pytest.raises(CommercialPolicyError, match="at least 10"):
        quote_package("group_wellness_reset", group_size=9)

    quote = quote_package(
        "group_wellness_reset",
        group_size=10,
        payment_option=PaymentOption.DEPOSIT,
    )
    assert quote.package_subtotal == Decimal("3750.00")


def test_group_immersive_has_fifteen_guest_minimum() -> None:
    with pytest.raises(CommercialPolicyError, match="at least 15"):
        quote_package("group_immersive_retreat", group_size=14)

    quote = quote_package(
        "group_immersive_retreat",
        group_size=15,
    )
    assert quote.package_subtotal == Decimal("13110.00")
    assert quote.discount == Decimal("1311.00")
    assert quote.order_total == Decimal("11799.00")


def test_premium_small_group_has_six_guest_minimum() -> None:
    quote = quote_package(
        "premium_small_group_retreat",
        group_size=6,
    )

    assert quote.package_subtotal == Decimal("6744.00")
    assert quote.discount == Decimal("674.40")
    assert quote.order_total == Decimal("6069.60")


def test_group_guided_experience_counts_are_enforced() -> None:
    immersive = validate_experience_plan(
        "group_immersive_retreat",
        included_low_overhead_sessions=3,
    )
    premium = validate_experience_plan(
        "premium_small_group_retreat",
        included_low_overhead_sessions=5,
    )

    assert immersive.included_low_overhead_sessions == 3
    assert premium.included_low_overhead_sessions == 5


def test_canonical_service_prices() -> None:
    repository = PolicyRepository()

    assert repository.addon("somatic_release")["price"] == "275.00"
    assert repository.addon("womb_wellness")["price"] == "225.00"
    assert repository.addon("cycle_syncing_support")["price"] == "275.00"
    assert repository.addon("cycle_syncing_support")[
        "included_product_value"
    ] == "57.00"
    assert repository.addon("farm_to_table_individual")["price"] == "295.00"


def test_four_somatic_sessions_total_1100() -> None:
    quote = quote_package(
        "executive_reset",
        duration_days=2,
        payment_option=PaymentOption.DEPOSIT,
        addons=[AddonSelection("somatic_release", quantity=4)],
    )

    assert quote.addon_subtotal == Decimal("1100.00")


def test_rush_fee_is_not_discounted() -> None:
    quote = quote_package(
        "rapid_reset",
        rush_or_late_fee=True,
    )

    assert quote.discount == Decimal("99.70")
    assert quote.rush_or_late_fees == Decimal("150.00")
    assert quote.order_total == Decimal("1047.30")


def test_balance_due_dates() -> None:
    event_start = date(2026, 10, 30)

    assert balance_due_date(
        event_start, is_group=False
    ) == date(2026, 10, 16)
    assert balance_due_date(
        event_start, is_group=True
    ) == date(2026, 9, 30)


def test_welcome_package_window_is_24_to_48_hours() -> None:
    checkout = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    window = welcome_package_window(checkout)

    assert window.earliest_delivery == datetime(
        2026, 8, 25, 12, 0, tzinfo=timezone.utc
    )
    assert window.latest_delivery == datetime(
        2026, 8, 26, 12, 0, tzinfo=timezone.utc
    )


def test_public_package_data_does_not_expose_internal_costs() -> None:
    repository = PolicyRepository()
    serialized = json.dumps(repository.public_package_summaries())

    assert "estimated_variable_cost" not in serialized
    assert "contribution_margin" not in serialized
    assert "internal_notes" not in serialized


def test_quote_is_json_ready_and_uses_strings_for_money() -> None:
    payload = quote_package("rapid_reset").model_dump()

    assert payload["payment_option"] == "pay_in_full"
    assert payload["package_subtotal"] == "997.00"
    assert payload["order_total"] == "897.30"
