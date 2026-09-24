from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProspectGoal(StrEnum):
    """Approved high-level goals a prospect can select."""

    REST_AND_REJUVENATION = "rest_and_rejuvenation"
    TEAM_CONNECTION = "team_connection"
    STRATEGIC_PLANNING = "strategic_planning"
    WELLNESS_EDUCATION = "wellness_education"
    CELEBRATION = "celebration"
    PRIVATE_RETREAT = "private_retreat"


class ProspectAssessment(BaseModel):
    """Validated customer information used by the sales agent."""

    model_config = ConfigDict(str_strip_whitespace=True)

    contact_name: str = Field(min_length=1, max_length=100)
    organization_name: str | None = Field(default=None, max_length=150)

    goals: list[ProspectGoal] = Field(min_length=1)

    group_size: int = Field(
        ge=1,
        le=250,
        description="Expected number of guests.",
    )

    total_budget: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Total event budget in USD.",
    )

    preferred_date: date | None = None

    event_length_hours: int = Field(
        default=5,
        ge=2,
        le=12,
    )

    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("goals")
    @classmethod
    def remove_duplicate_goals(
        cls,
        goals: list[ProspectGoal],
    ) -> list[ProspectGoal]:
        """Keep goals unique while preserving their original order."""

        return list(dict.fromkeys(goals))

    def budget_per_guest(self) -> Decimal:
        """Calculate the maximum available budget per guest."""

        return (
            self.total_budget / Decimal(self.group_size)
        ).quantize(Decimal("0.01"))