from decimal import Decimal

from paradise_park_sales_agent.models import (
    ProspectAssessment,
    ProspectGoal,
)
from paradise_park_sales_agent.pricing import (
    PricingType,
    RejectionReason,
    ServicePackage,
    evaluate_pricing,
)


def create_assessment(
    *,
    group_size: int = 40,
    budget: str = "3000.00",
) -> ProspectAssessment:
    """Create a reusable assessment for pricing tests."""

    return ProspectAssessment(
        contact_name="Summer",
        organization_name="Example Corporation",
        goals=[
            ProspectGoal.REST_AND_REJUVENATION,
            ProspectGoal.TEAM_CONNECTION,
        ],
        group_size=group_size,
        total_budget=Decimal(budget),
        event_length_hours=5,
    )


def create_staff_restoration_package() -> ServicePackage:
    """Create a development fixture for a group retreat."""

    return ServicePackage(
        package_id="staff-restoration",
        name="Staff Restoration Retreat",
        description=(
            "A five-hour group experience focused on "
            "restoration, connection and renewal."
        ),
        approved_goals=[
            ProspectGoal.REST_AND_REJUVENATION,
            ProspectGoal.TEAM_CONNECTION,
        ],
        min_group_size=20,
        max_group_size=40,
        min_event_hours=5,
        max_event_hours=5,
        pricing_type=PricingType.FLAT_RATE,
        flat_price=Decimal("3000.00"),
    )


def test_flat_rate_package_is_eligible() -> None:
    assessment = create_assessment()
    package = create_staff_restoration_package()

    result = evaluate_pricing(
        assessment=assessment,
        packages=[package],
    )

    assert len(result.valid_options) == 1
    assert result.valid_options[0].total_price == Decimal(
        "3000.00"
    )
    assert result.valid_options[0].price_per_guest == Decimal(
        "75.00"
    )
    assert result.valid_options[0].budget_remaining == Decimal(
        "0.00"
    )
    assert result.requires_human_review is False


def test_engine_does_not_invent_a_discount() -> None:
    assessment = create_assessment(budget="2999.00")
    package = create_staff_restoration_package()

    result = evaluate_pricing(
        assessment=assessment,
        packages=[package],
    )

    assert result.valid_options == []
    assert result.requires_human_review is True

    rejected = result.rejected_packages[0]

    assert RejectionReason.OVER_BUDGET in rejected.reasons


def test_group_above_capacity_is_rejected() -> None:
    assessment = create_assessment(
        group_size=50,
        budget="5000.00",
    )
    package = create_staff_restoration_package()

    result = evaluate_pricing(
        assessment=assessment,
        packages=[package],
    )

    assert result.valid_options == []

    rejected = result.rejected_packages[0]

    assert RejectionReason.GROUP_SIZE in rejected.reasons


def test_per_guest_pricing_is_calculated() -> None:
    assessment = create_assessment(
        group_size=20,
        budget="2000.00",
    )

    package = ServicePackage(
        package_id="per-guest-development-example",
        name="Per-Guest Development Example",
        description="Test fixture for per-guest pricing.",
        approved_goals=[
            ProspectGoal.REST_AND_REJUVENATION,
        ],
        min_group_size=10,
        max_group_size=40,
        min_event_hours=4,
        max_event_hours=6,
        pricing_type=PricingType.PER_GUEST,
        price_per_guest=Decimal("75.00"),
    )

    result = evaluate_pricing(
        assessment=assessment,
        packages=[package],
    )

    option = result.valid_options[0]

    assert option.total_price == Decimal("1500.00")
    assert option.price_per_guest == Decimal("75.00")
    assert option.budget_remaining == Decimal("500.00")

    