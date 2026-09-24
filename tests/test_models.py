from decimal import Decimal

import pytest
from pydantic import ValidationError

from paradise_park_sales_agent.models import (
    ProspectAssessment,
    ProspectGoal,
)


def test_valid_prospect_assessment() -> None:
    assessment = ProspectAssessment(
        contact_name="Summer",
        organization_name="Example Corporation",
        goals=[
            ProspectGoal.REST_AND_REJUVENATION,
            ProspectGoal.TEAM_CONNECTION,
        ],
        group_size=40,
        total_budget=Decimal("3000.00"),
        event_length_hours=5,
    )

    assert assessment.group_size == 40
    assert assessment.budget_per_guest() == Decimal("75.00")


def test_invalid_group_size_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProspectAssessment(
            contact_name="Test Prospect",
            goals=[ProspectGoal.TEAM_CONNECTION],
            group_size=0,
            total_budget=Decimal("3000.00"),
        )


def test_duplicate_goals_are_removed() -> None:
    assessment = ProspectAssessment(
        contact_name="Test Prospect",
        goals=[
            ProspectGoal.TEAM_CONNECTION,
            ProspectGoal.TEAM_CONNECTION,
        ],
        group_size=20,
        total_budget=Decimal("5000.00"),
    )

    assert assessment.goals == [ProspectGoal.TEAM_CONNECTION]
    