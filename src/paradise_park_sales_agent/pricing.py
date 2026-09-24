from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, Field, model_validator

from paradise_park_sales_agent.models import (
    ProspectAssessment,
    ProspectGoal,
)


MONEY = Decimal("0.01")


def round_money(value: Decimal) -> Decimal:
    """Round a monetary value to two decimal places."""

    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


class PricingType(StrEnum):
    """Supported deterministic pricing methods."""

    FLAT_RATE = "flat_rate"
    PER_GUEST = "per_guest"


class ServicePackage(BaseModel):
    """An approved Paradise Park service package."""

    package_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9_-]+$",
    )

    name: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=1000)

    approved_goals: list[ProspectGoal] = Field(min_length=1)

    min_group_size: int = Field(ge=1, le=250)
    max_group_size: int = Field(ge=1, le=250)

    min_event_hours: int = Field(ge=1, le=24)
    max_event_hours: int = Field(ge=1, le=24)

    pricing_type: PricingType

    flat_price: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
    )

    price_per_guest: Decimal | None = Field(
        default=None,
        gt=0,
        decimal_places=2,
    )

    active: bool = True

    @model_validator(mode="after")
    def validate_package_rules(self) -> "ServicePackage":
        """Verify that the package contains consistent business rules."""

        if self.min_group_size > self.max_group_size:
            raise ValueError(
                "min_group_size cannot exceed max_group_size"
            )

        if self.min_event_hours > self.max_event_hours:
            raise ValueError(
                "min_event_hours cannot exceed max_event_hours"
            )

        if self.pricing_type == PricingType.FLAT_RATE:
            if self.flat_price is None:
                raise ValueError(
                    "A flat-rate package requires flat_price"
                )

            if self.price_per_guest is not None:
                raise ValueError(
                    "A flat-rate package cannot use price_per_guest"
                )

        if self.pricing_type == PricingType.PER_GUEST:
            if self.price_per_guest is None:
                raise ValueError(
                    "A per-guest package requires price_per_guest"
                )

            if self.flat_price is not None:
                raise ValueError(
                    "A per-guest package cannot use flat_price"
                )

        return self

    def calculate_total(self, group_size: int) -> Decimal:
        """Calculate the package total without using an AI model."""

        if self.pricing_type == PricingType.FLAT_RATE:
            if self.flat_price is None:
                raise ValueError("flat_price is missing")

            return round_money(self.flat_price)

        if self.price_per_guest is None:
            raise ValueError("price_per_guest is missing")

        return round_money(
            self.price_per_guest * Decimal(group_size)
        )


class RejectionReason(StrEnum):
    """Reasons a service package cannot be recommended."""

    INACTIVE = "package_is_inactive"
    GROUP_SIZE = "group_size_not_supported"
    EVENT_LENGTH = "event_length_not_supported"
    GOAL_MISMATCH = "no_matching_prospect_goal"
    OVER_BUDGET = "package_exceeds_budget"


class PricingOption(BaseModel):
    """A service package that passed every pricing rule."""

    package_id: str
    package_name: str

    total_price: Decimal
    price_per_guest: Decimal
    budget_remaining: Decimal

    matched_goals: list[ProspectGoal]


class RejectedPackage(BaseModel):
    """A package that failed one or more business rules."""

    package_id: str
    package_name: str
    calculated_price: Decimal
    reasons: list[RejectionReason]


class PricingDecision(BaseModel):
    """Complete and traceable result from the pricing engine."""

    valid_options: list[PricingOption]
    rejected_packages: list[RejectedPackage]

    requires_human_review: bool
    review_reason: str | None = None


def evaluate_pricing(
    assessment: ProspectAssessment,
    packages: Iterable[ServicePackage],
) -> PricingDecision:
    """Return only packages that satisfy every business rule."""

    valid_options: list[PricingOption] = []
    rejected_packages: list[RejectedPackage] = []

    for package in packages:
        reasons: list[RejectionReason] = []

        total_price = package.calculate_total(
            assessment.group_size
        )

        if not package.active:
            reasons.append(RejectionReason.INACTIVE)

        if not (
            package.min_group_size
            <= assessment.group_size
            <= package.max_group_size
        ):
            reasons.append(RejectionReason.GROUP_SIZE)

        if not (
            package.min_event_hours
            <= assessment.event_length_hours
            <= package.max_event_hours
        ):
            reasons.append(RejectionReason.EVENT_LENGTH)

        matched_goals = [
            goal
            for goal in assessment.goals
            if goal in package.approved_goals
        ]

        if not matched_goals:
            reasons.append(RejectionReason.GOAL_MISMATCH)

        if total_price > assessment.total_budget:
            reasons.append(RejectionReason.OVER_BUDGET)

        if reasons:
            rejected_packages.append(
                RejectedPackage(
                    package_id=package.package_id,
                    package_name=package.name,
                    calculated_price=total_price,
                    reasons=reasons,
                )
            )
            continue

        price_per_guest = round_money(
            total_price / Decimal(assessment.group_size)
        )

        budget_remaining = round_money(
            assessment.total_budget - total_price
        )

        valid_options.append(
            PricingOption(
                package_id=package.package_id,
                package_name=package.name,
                total_price=total_price,
                price_per_guest=price_per_guest,
                budget_remaining=budget_remaining,
                matched_goals=matched_goals,
            )
        )

    valid_options.sort(
        key=lambda option: (
            option.total_price,
            option.package_id,
        )
    )

    requires_human_review = len(valid_options) == 0

    review_reason = None

    if requires_human_review:
        review_reason = (
            "No approved package satisfies all assessment "
            "and pricing rules."
        )

    return PricingDecision(
        valid_options=valid_options,
        rejected_packages=rejected_packages,
        requires_human_review=requires_human_review,
        review_reason=review_reason,
    )

