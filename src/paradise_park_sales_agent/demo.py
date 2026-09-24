from decimal import Decimal

from paradise_park_sales_agent.recommendation_models import (
    AssessmentMode,
    AssessmentSignal,
    RecommendationRequest,
    SignalSource,
)
from paradise_park_sales_agent.workflow import run_sales_workflow


def main() -> None:
    request = RecommendationRequest(
        assessment_mode=AssessmentMode.RETREAT_PLANNER,
        contact_name="Sample Guest",
        organization_name="Example Organization",
        group_size=1,
        budget=Decimal("1200"),
        goals=["deep_rest", "body_tension"],
        signals=[
            AssessmentSignal(
                code="deep_rest",
                source=SignalSource.EXPLICIT,
                guest_statement=(
                    "I want unhurried rest and time to reset."
                ),
            ),
            AssessmentSignal(
                code="body_tension",
                source=SignalSource.EXPLICIT,
                guest_statement=(
                    "I often notice physical tension."
                ),
            ),
        ],
    )

    result = run_sales_workflow(request)

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

    