"""Deterministic commercial rules for Paradise Park retreat packages.

This module owns package entitlements, payment calculations and commercial
validation. Gemini may explain its results, but it must never change prices,
minimum guest counts, included session counts, discounts or payment terms.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from pathlib import Path
from typing import Iterable
from paradise_park_sales_agent.runtime_paths import DATA_DIR

MONEY = Decimal("0.01")
DEFAULT_POLICY_PATH = DATA_DIR / "package_policies.json"


def money(value: Decimal | str | int) -> Decimal:
    """Return a currency-safe Decimal rounded to cents."""

    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


class CommercialPolicyError(ValueError):
    """Raised when a proposed sale violates an approved commercial rule."""


class PaymentOption(StrEnum):
    PAY_IN_FULL = "pay_in_full"
    DEPOSIT = "deposit"


@dataclass(frozen=True)
class AddonSelection:
    """A separately priced enhancement selected by the guest."""

    addon_id: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise CommercialPolicyError("Add-on quantity must be at least one.")


@dataclass(frozen=True)
class PlanValidation:
    """Validated session entitlements for one proposed package agenda."""

    package_id: str
    duration_days: int
    included_low_overhead_sessions: int
    included_private_sessions: int
    paid_private_upgrades: int
    estimated_duration_minutes: int
    valid: bool = True


@dataclass(frozen=True)
class PaymentQuote:
    """Guest-safe, deterministic payment calculation."""

    package_id: str
    package_name: str
    group_size: int
    duration_days: int
    payment_option: PaymentOption
    package_subtotal: Decimal
    included_service_days: int
    additional_service_days: int
    additional_day_rate_per_person: Decimal
    extended_program_subtotal: Decimal
    addon_subtotal: Decimal
    rush_or_late_fees: Decimal
    discount: Decimal
    order_total: Decimal
    amount_due_now: Decimal
    remaining_balance: Decimal

    def model_dump(self) -> dict[str, object]:
        """Return a JSON-ready representation without internal policy data."""

        payload = asdict(self)
        for key, value in payload.items():
            if isinstance(value, Decimal):
                payload[key] = f"{value:.2f}"
            elif isinstance(value, StrEnum):
                payload[key] = value.value
        return payload


@dataclass(frozen=True)
class WelcomePackageWindow:
    earliest_delivery: datetime
    latest_delivery: datetime


class PolicyRepository:
    """Read-only access to the canonical package policy document."""

    def __init__(self, path: Path = DEFAULT_POLICY_PATH) -> None:
        with path.open(encoding="utf-8") as source:
            self._policy = json.load(source)

    @property
    def version(self) -> str:
        return str(self._policy["policy_version"])

    @property
    def payment_policy(self) -> dict[str, object]:
        return dict(self._policy["payment_policy"])

    def package(self, package_id: str) -> dict[str, object]:
        try:
            return dict(self._policy["packages"][package_id])
        except KeyError as exc:
            raise CommercialPolicyError(
                f"Unknown Paradise Park package: {package_id}."
            ) from exc

    def addon(self, addon_id: str) -> dict[str, object]:
        try:
            return dict(self._policy["addons"][addon_id])
        except KeyError as exc:
            raise CommercialPolicyError(
                f"Unknown Paradise Park add-on: {addon_id}."
            ) from exc

    def public_package_summaries(self) -> list[dict[str, object]]:
        """Return public package facts without internal cost or margin data."""

        summaries: list[dict[str, object]] = []
        for package_id, raw in self._policy["packages"].items():
            package = dict(raw)
            package["package_id"] = package_id
            summaries.append(package)
        return summaries


def _validate_group_size(package: dict[str, object], group_size: int) -> None:
    if group_size < 1:
        raise CommercialPolicyError("Group size must be at least one.")

    minimum = int(package.get("minimum_guests", 1))
    maximum = package.get("maximum_guests")

    if group_size < minimum:
        raise CommercialPolicyError(
            f"{package['name']} requires at least {minimum} guests."
        )
    if maximum is not None and group_size > int(maximum):
        raise CommercialPolicyError(
            f"{package['name']} supports no more than {maximum} guests."
        )


def _package_subtotal(
    package: dict[str, object],
    *,
    group_size: int,
    duration_days: int,
) -> Decimal:
    pricing_type = str(package["pricing_type"])

    if duration_days < 1:
        raise CommercialPolicyError("Duration must be at least one day.")

    pricing_scope = str(package.get("pricing_scope", "per_booking"))
    if pricing_scope not in {"per_booking", "per_person"}:
        raise CommercialPolicyError(
            f"Unsupported pricing scope: {pricing_scope}."
        )
    multiplier = group_size if pricing_scope == "per_person" else 1

    if pricing_type == "flat":
        fixed_days = package.get("base_duration_days")
        if fixed_days is not None and duration_days < int(fixed_days):
            raise CommercialPolicyError(
                f"{package['name']} requires at least {fixed_days} days."
            )
        if fixed_days is None and duration_days != 1:
            raise CommercialPolicyError(
                f"{package['name']} is sold as a single experience."
            )
        return money(money(package["base_price"]) * multiplier)

    if pricing_type == "duration_tier":
        try:
            base_days = min(duration_days, int(package.get("included_service_days", duration_days)))
            return money(package["duration_prices"][str(base_days)]) * multiplier
        except KeyError as exc:
            supported = ", ".join(package["duration_prices"].keys())
            raise CommercialPolicyError(
                f"{package['name']} supports these day counts: {supported}."
            ) from exc

    if pricing_type == "per_person_per_experience":
        if duration_days != 1:
            raise CommercialPolicyError(
                f"{package['name']} is a four-hour experience, not a daily rate."
            )
        return money(package["base_price"]) * group_size

    if pricing_type == "per_person_per_day":
        return money(package["base_price"]) * group_size * duration_days

    raise CommercialPolicyError(f"Unsupported pricing type: {pricing_type}.")


def _extended_program_subtotal(
    package: dict[str, object], *, group_size: int, duration_days: int
) -> tuple[int, int, Decimal, Decimal]:
    """Price immersive service days beyond the package's included days."""

    included_days = int(package.get("included_service_days", duration_days))
    additional_days = max(duration_days - included_days, 0)
    rate = money(package.get("additional_day_price_per_person", 0))
    subtotal = money(rate * group_size * additional_days)
    return included_days, additional_days, rate, subtotal


def _addon_subtotal(
    repository: PolicyRepository,
    addons: Iterable[AddonSelection],
) -> tuple[Decimal, int, int]:
    subtotal = money(0)
    private_count = 0
    duration_minutes = 0

    for selection in addons:
        addon = repository.addon(selection.addon_id)
        subtotal += money(addon["price"]) * selection.quantity
        duration_minutes += int(addon["duration_minutes"]) * selection.quantity
        if addon["delivery_type"] == "private":
            private_count += selection.quantity

    return money(subtotal), private_count, duration_minutes


def validate_experience_plan(
    package_id: str,
    *,
    duration_days: int = 1,
    included_low_overhead_sessions: int,
    included_private_sessions: int = 0,
    paid_private_upgrades: int = 0,
    extended_rapid: bool = False,
    repository: PolicyRepository | None = None,
) -> PlanValidation:
    """Validate that an agenda does not give away more than the package allows."""

    repo = repository or PolicyRepository()
    package = repo.package(package_id)

    if min(
        included_low_overhead_sessions,
        included_private_sessions,
        paid_private_upgrades,
    ) < 0:
        raise CommercialPolicyError("Session counts cannot be negative.")

    if package_id == "express_reset":
        expected_low = 1
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                "Express Reset includes exactly one core service."
            )
        if included_private_sessions:
            raise CommercialPolicyError(
                "Express Reset private services are paid enhancements, not inclusions."
            )
        if paid_private_upgrades > int(package["absolute_private_upgrade_limit"]):
            raise CommercialPolicyError("Express Reset allows one private enhancement.")
        estimated_minutes = int(package["base_duration_minutes"])

    elif package_id == "rapid_reset":
        expected_low = int(package["included_low_overhead_sessions"])
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                "Rapid Reset includes exactly four low-overhead/group activations."
            )
        if included_private_sessions:
            raise CommercialPolicyError(
                "Rapid Reset private services are paid upgrades, not inclusions."
            )
        allowed_upgrades = int(
            package[
                "absolute_private_upgrade_limit"
                if extended_rapid
                else "standard_private_upgrade_limit"
            ]
        )
        if paid_private_upgrades > allowed_upgrades:
            label = "Extended Rapid" if extended_rapid else "Rapid Reset"
            raise CommercialPolicyError(
                f"{label} allows no more than {allowed_upgrades} private upgrade(s)."
            )
        estimated_minutes = int(package["base_duration_minutes"]) + (
            paid_private_upgrades * 50
        )
        if estimated_minutes > int(package["maximum_duration_minutes"]):
            raise CommercialPolicyError("Rapid Reset cannot exceed six hours.")

    elif package_id == "executive_reset":
        if not 1 <= duration_days <= int(package.get("maximum_duration_days", 3)):
            raise CommercialPolicyError(
                "Executive Reset supports one through seven service days."
            )
        expected_low = (
            int(package["included_low_overhead_sessions_per_day"])
            * duration_days
        )
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                f"A {duration_days}-day Executive Reset includes exactly "
                f"{expected_low} low-overhead/group activations."
            )
        max_private = (
            int(package["maximum_private_sessions_per_day"])
            * duration_days
        )
        if included_private_sessions > max_private:
            raise CommercialPolicyError(
                f"A {duration_days}-day Executive Reset allows no more than "
                f"{max_private} private sessions."
            )
        estimated_minutes = (
            int(package["base_duration_minutes_per_day"]) * duration_days
        )

    elif package_id == "peak_performance_pivot":
        if not int(package["minimum_duration_days"]) <= duration_days <= int(package["maximum_duration_days"]):
            raise CommercialPolicyError(
                "Peak Performance Pivot requires three through seven service days."
            )
        expected_low = int(package["included_low_overhead_sessions_per_day"]) * duration_days
        expected_private = int(package["included_private_sessions_per_day"]) * duration_days
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                "Peak Performance Pivot includes three low-overhead sessions per day."
            )
        if included_private_sessions != expected_private:
            raise CommercialPolicyError(
                "Peak Performance Pivot includes two private sessions per day, "
                "for six total."
            )
        estimated_minutes = (
            int(package["base_duration_minutes_per_day"]) * duration_days
        )

    elif package_id == "group_wellness_reset":
        expected_low = (
            int(package["included_low_overhead_sessions"]) * duration_days
        )
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                "Group Wellness Reset includes exactly four guided group "
                "activations per service day."
            )
        if included_private_sessions:
            raise CommercialPolicyError(
                "Personal group-retreat services must remain paid upgrades."
            )
        estimated_minutes = (
            int(package["base_duration_minutes"]) * duration_days
        )

    elif package_id in {
        "group_immersive_retreat",
        "premium_small_group_retreat",
    }:
        per_day = int(package["included_low_overhead_sessions_per_day"])
        expected_low = per_day * duration_days
        if included_low_overhead_sessions != expected_low:
            raise CommercialPolicyError(
                f"{package['name']} includes exactly {per_day} guided group "
                "experiences per day."
            )
        if included_private_sessions:
            raise CommercialPolicyError(
                "Personal group-retreat services must remain paid upgrades."
            )
        estimated_minutes = (
            int(package["base_duration_minutes_per_day"]) * duration_days
        )

    else:
        raise CommercialPolicyError(
            f"Agenda validation is not configured for {package_id}."
        )

    return PlanValidation(
        package_id=package_id,
        duration_days=duration_days,
        included_low_overhead_sessions=included_low_overhead_sessions,
        included_private_sessions=included_private_sessions,
        paid_private_upgrades=paid_private_upgrades,
        estimated_duration_minutes=estimated_minutes,
    )


def quote_package(
    package_id: str,
    *,
    group_size: int = 1,
    duration_days: int = 1,
    payment_option: PaymentOption = PaymentOption.PAY_IN_FULL,
    addons: Iterable[AddonSelection] = (),
    extended_rapid: bool = False,
    rush_or_late_fee: bool = False,
    repository: PolicyRepository | None = None,
) -> PaymentQuote:
    """Calculate a deterministic package quote and amount due at checkout."""

    repo = repository or PolicyRepository()
    package = repo.package(package_id)
    _validate_group_size(package, group_size)

    package_subtotal = _package_subtotal(
        package,
        group_size=group_size,
        duration_days=duration_days,
    )
    (
        included_service_days,
        additional_service_days,
        additional_day_rate,
        extended_program_subtotal,
    ) = _extended_program_subtotal(
        package, group_size=group_size, duration_days=duration_days
    )
    selections = tuple(addons)
    addon_subtotal, private_count, addon_minutes = _addon_subtotal(
        repo,
        selections,
    )

    if package_id == "express_reset" and private_count > int(package["absolute_private_upgrade_limit"]):
        raise CommercialPolicyError("Express Reset allows one private enhancement.")

    if package_id == "rapid_reset":
        allowed = int(
            package[
                "absolute_private_upgrade_limit"
                if extended_rapid
                else "standard_private_upgrade_limit"
            ]
        )
        if private_count > allowed:
            raise CommercialPolicyError(
                f"Rapid Reset allows no more than {allowed} private upgrade(s) "
                "for this checkout path."
            )
        total_minutes = int(package["base_duration_minutes"]) + addon_minutes
        if total_minutes > int(package["maximum_duration_minutes"]):
            raise CommercialPolicyError("Rapid Reset cannot exceed six hours.")

    payment_policy = repo.payment_policy
    fee = money(0)
    if rush_or_late_fee:
        fee_key = (
            "group_rush_or_late_fee"
            if package["audience"] == "group"
            else "individual_rush_or_late_fee"
        )
        fee = money(payment_policy[fee_key])

    discount = money(0)
    if payment_option == PaymentOption.PAY_IN_FULL:
        if bool(package["pay_in_full_discount_allowed"]):
            percent = money(
                payment_policy["pay_in_full_discount_percent"]
            ) / Decimal("100")
            discount = money(package_subtotal * percent)
    elif payment_option == PaymentOption.DEPOSIT:
        if not bool(package["deposit_allowed"]):
            raise CommercialPolicyError(
                f"{package['name']} must be paid in full."
            )
    else:
        raise CommercialPolicyError(
            f"Unsupported payment option: {payment_option}."
        )

    order_total = money(
        package_subtotal + extended_program_subtotal + addon_subtotal + fee - discount
    )

    if payment_option == PaymentOption.PAY_IN_FULL:
        amount_due_now = order_total
        remaining_balance = money(0)
    else:
        deposit_percent = money(
            payment_policy["deposit_percent"]
        ) / Decimal("100")
        amount_due_now = money(order_total * deposit_percent)
        remaining_balance = money(order_total - amount_due_now)

    return PaymentQuote(
        package_id=package_id,
        package_name=str(package["name"]),
        group_size=group_size,
        duration_days=duration_days,
        payment_option=payment_option,
        package_subtotal=money(package_subtotal),
        included_service_days=included_service_days,
        additional_service_days=additional_service_days,
        additional_day_rate_per_person=additional_day_rate,
        extended_program_subtotal=extended_program_subtotal,
        addon_subtotal=money(addon_subtotal),
        rush_or_late_fees=fee,
        discount=discount,
        order_total=order_total,
        amount_due_now=amount_due_now,
        remaining_balance=remaining_balance,
    )


def balance_due_date(
    event_start: date,
    *,
    is_group: bool,
    repository: PolicyRepository | None = None,
) -> date:
    """Return the contractual final-balance due date."""

    repo = repository or PolicyRepository()
    policy = repo.payment_policy
    days = int(
        policy[
            "group_balance_due_days"
            if is_group
            else "individual_balance_due_days"
        ]
    )
    return event_start - timedelta(days=days)


def welcome_package_window(
    checkout_completed_at: datetime,
    *,
    repository: PolicyRepository | None = None,
) -> WelcomePackageWindow:
    """Return the promised 24-48 hour digital welcome-package window."""

    repo = repository or PolicyRepository()
    policy = repo.payment_policy
    return WelcomePackageWindow(
        earliest_delivery=checkout_completed_at
        + timedelta(hours=int(policy["welcome_package_min_hours"])),
        latest_delivery=checkout_completed_at
        + timedelta(hours=int(policy["welcome_package_max_hours"])),
    )
