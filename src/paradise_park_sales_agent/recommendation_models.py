"""Guest-safe data contracts for Paradise Park recommendations."""

from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Reject unexpected fields so internal business data cannot leak."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AssessmentMode(StrEnum):
    RETREAT_PLANNER = "retreat_planner"
    INNER_WELLNESS = "inner_wellness"


class BookingMode(StrEnum):
    PERSONAL_RESET = "personal_reset"
    PRIVATE_GROUP = "private_group"
    LARGE_GROUP = "large_group"
    TEAM_RETREAT = "team_retreat"


class SignalSource(StrEnum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


class CommercialStatus(StrEnum):
    PROPOSED_INCLUDED = "proposed_included"
    PAID_UPGRADE = "paid_upgrade"
    CUSTOM_QUOTE = "custom_quote"
    HUMAN_REVIEW = "human_review"


class RecommendationStrategy(StrEnum):
    WITHIN_TARGET = "within_target"
    UPSELL = "upsell"


class AssessmentSignal(StrictModel):
    code: str = Field(min_length=1)
    source: SignalSource
    guest_statement: str | None = None


class ConsentPreferences(StrictModel):
    deliver_report: bool = False
    marketing: bool = False


class RecommendationRequest(StrictModel):
    """Normalized guest input consumed by the deterministic engine."""

    assessment_mode: AssessmentMode
    booking_mode: BookingMode = BookingMode.PERSONAL_RESET
    contact_name: str = Field(default="Guest", min_length=2, max_length=120)
    contact_email: str = Field(
        default="guest@example.com",
        min_length=5,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    contact_phone: str = Field(default="0000000", min_length=7, max_length=32)
    referral_source: str = Field(default="Not provided", min_length=2, max_length=120)
    instagram_handle: str | None = Field(default=None, max_length=64)
    organization_name: str | None = None
    group_size: int = Field(default=1, ge=1)
    budget: Decimal | None = Field(default=None, gt=0)
    duration_days: int = Field(default=1, ge=1, le=7)
    preferred_package_id: str | None = Field(default=None, min_length=1)
    goals: list[str] = Field(min_length=1)
    selected_addon_ids: list[str] = Field(default_factory=list)
    signals: list[AssessmentSignal] = Field(min_length=1)
    consent: ConsentPreferences = Field(default_factory=ConsentPreferences)

    @model_validator(mode="after")
    def reject_duplicate_signals(self) -> "RecommendationRequest":
        signal_codes = [signal.code for signal in self.signals]
        if len(signal_codes) != len(set(signal_codes)):
            raise ValueError("Signal codes must be unique.")
        if (
            self.booking_mode
            in {
                BookingMode.PRIVATE_GROUP,
                BookingMode.LARGE_GROUP,
                BookingMode.TEAM_RETREAT,
            }
            and self.group_size < 6
        ):
            raise ValueError(
                "Paradise Park group retreats require a minimum of 6 guests."
            )
        return self


class PackageRecommendation(StrictModel):
    package_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price_statement: str = Field(min_length=1)
    why_it_fits: str = Field(min_length=1)
    care_level: str = Field(default="Personalized wellness support", min_length=1)
    duration_statement: str = Field(default="Schedule confirmed after purchase", min_length=1)
    included_summary: str = Field(default="See the proposed experience below.", min_length=1)
    hospitality_summary: str = Field(default="Hospitality varies by package.", min_length=1)
    checkout_mode: str = Field(default="square_checkout", min_length=1)
    requires_human_approval: bool = False


class AgendaItemRecommendation(StrictModel):
    """One included activation or separately priced enhancement."""

    order: int = Field(ge=1)
    day: int = Field(default=1, ge=1)
    service_class: str = Field(default="low_overhead", min_length=1)
    service_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    guest_description: str = Field(min_length=1)
    why_helpful: str = Field(min_length=1)
    commercial_status: CommercialStatus
    price_statement: str = Field(min_length=1)
    pathway: str = Field(default="whole_person", min_length=1)
    quantity: int = Field(default=1, ge=1)
    requires_human_confirmation: bool = False


class CoreExperience(StrictModel):
    service_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class PricingBreakdown(StrictModel):
    currency: str = "USD"
    pricing_basis: str = Field(min_length=1)
    guest_count: int = Field(ge=1)
    duration_days: int = Field(ge=1)
    package_base_subtotal: Decimal = Field(ge=0)
    included_service_days: int = Field(ge=1)
    additional_service_days: int = Field(ge=0)
    additional_day_rate_per_person: Decimal = Field(ge=0)
    extended_program_subtotal: Decimal = Field(ge=0)
    addon_subtotal: Decimal = Field(ge=0)
    discount: Decimal = Field(ge=0)
    order_total: Decimal = Field(ge=0)


class EnhancementAction(StrictModel):
    enhancement_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    selected: bool = True
    included_in_retreat_total: bool
    purchase_mode: str = Field(min_length=1)
    purchase_url: str = Field(min_length=1)
    button_label: str = Field(min_length=1)


class WellnessInsight(StrictModel):
    """Helpful education that makes the report valuable without diagnosis."""

    pathway: str = Field(min_length=1)
    title: str = Field(min_length=1)
    observation: str = Field(min_length=1)
    practice_tip: str = Field(min_length=1)


class PaymentChoice(StrictModel):
    """A deterministic payment choice ready for a Square payment link."""

    payment_option: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount_due_now: Decimal = Field(ge=0)
    order_total: Decimal = Field(ge=0)
    remaining_balance: Decimal = Field(ge=0)
    savings: Decimal = Field(default=Decimal("0.00"), ge=0)
    description: str = Field(min_length=1)


class AlternativePackageOption(StrictModel):
    """A valid next-best offer; never a fabricated or underpriced package."""

    package_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price_statement: str = Field(min_length=1)
    why_consider: str = Field(min_length=1)
    qualification_note: str | None = None
    action: str = Field(min_length=1)


class RecommendationResponse(StrictModel):
    """Controlled result returned to the UI and, later, Gemini."""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    assessment_mode: AssessmentMode
    reflected_statements: list[str] = Field(min_length=1)
    personalized_narrative: str = Field(min_length=1)
    fit_signals: list[str] = Field(min_length=1, max_length=3)
    recommendation_strategy: RecommendationStrategy
    package: PackageRecommendation
    agenda_items: list[AgendaItemRecommendation] = Field(min_length=1)
    core_experiences: list[CoreExperience] = Field(default_factory=list)
    pricing_breakdown: PricingBreakdown | None = None
    enhancement_actions: list[EnhancementAction] = Field(default_factory=list)
    wellness_insights: list[WellnessInsight] = Field(default_factory=list)
    payment_choices: list[PaymentChoice] = Field(default_factory=list)
    alternatives: list[AlternativePackageOption] = Field(default_factory=list)
    price_summary: str = Field(min_length=1)
    call_to_action: str = Field(min_length=1)
    consultation_available: bool = True
    wellness_disclaimer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_agenda(self) -> "RecommendationResponse":
        orders = [item.order for item in self.agenda_items]
        expected_orders = list(range(1, len(self.agenda_items) + 1))
        if orders != expected_orders:
            raise ValueError("Agenda item order must be sequential starting at 1.")
        return self
