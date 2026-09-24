from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from paradise_park_sales_agent.runtime_paths import STATIC_DIR
from paradise_park_sales_agent.ai.router import (
    router as concierge_router,
)

from paradise_park_sales_agent.recommendation_models import (
    RecommendationRequest,
    RecommendationResponse,
)
from paradise_park_sales_agent.booking_rules import (
    validate_service_schedule,
)
from paradise_park_sales_agent.commercial_policy import PaymentOption
from paradise_park_sales_agent.square_checkout import (
    CheckoutLink,
    create_square_payment_link,
)
from paradise_park_sales_agent.workflow import (
    WorkflowStatus,
    run_sales_workflow,
)
from paradise_park_sales_agent.lead_repository import (
    get_lead_repository,
    lead_storage_enabled,
)
from paradise_park_sales_agent.lead_service import (
    notify_admin_and_record,
    persist_lead,
)
from paradise_park_sales_agent.telemetry_repository import (
    event_document_id,
    record_event_safely,
)


PRODUCT_SHOP_URL = "https://square.link/u/FGnBH1yz"
WELLNESS_AMBASSADOR_URL = "https://www.paradiseislife.biz/contact-8"


def booking_end_date(start_date: date, duration_days: int) -> date:
    return start_date + timedelta(days=duration_days - 1)


class UpgradeType(StrEnum):
    """Optional upgrades supported by the MVP."""

    PAMPER_COLLECTION = "pamper_collection"
    SOIL_TO_SOUL_PRODUCTS = "soil_to_soul_products"


class PublicSalesRequest(BaseModel):
    """Public request accepted from Wix or another frontend."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    assessment: RecommendationRequest
    requested_start_date: date
    duration_days: int = Field(default=1, ge=1, le=7)
    selected_upgrades: list[UpgradeType] = Field(
        default_factory=list
    )
    additional_text: str = Field(
        default="",
        max_length=2000,
    )
    lead_id: str = Field(min_length=8, max_length=80)

    @model_validator(mode="after")
    def validate_requested_schedule(
        self,
    ) -> "PublicSalesRequest":
        validate_service_schedule(
            self.requested_start_date,
            self.duration_days,
        )
        return self


class BookingSummary(BaseModel):
    """Guest-safe summary of the requested schedule."""

    model_config = ConfigDict(extra="forbid")

    requested_start_date: date
    requested_end_date: date
    duration_days: int
    group_size: int
    selected_upgrades: list[UpgradeType]
    pricing_basis: str = "per person, per service day"


class GuestActions(BaseModel):
    """Approved navigation choices displayed after the assessment."""

    model_config = ConfigDict(extra="forbid")

    express_calendar_url: str | None = None
    consultation_url: str | None = None
    product_shop_url: str
    questions_url: str


class LeadCaptureRequest(BaseModel):
    """Minimum contact record captured before the assessment is completed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    lead_id: str = Field(min_length=8, max_length=80)
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    )
    phone: str = Field(min_length=7, max_length=32)
    referral_source: str = Field(min_length=2, max_length=120)
    instagram_handle: str | None = Field(default=None, max_length=64)


class PublicSalesResponse(BaseModel):
    """Guest-safe response that hides internal guardrail details."""

    model_config = ConfigDict(extra="forbid")

    status: WorkflowStatus
    trace_id: str
    message: str
    booking: BookingSummary
    recommendation: RecommendationResponse | None = None
    actions: GuestActions


class PublicCheckoutRequest(PublicSalesRequest):
    """Recomputable checkout request; clients never submit an amount."""

    payment_option: PaymentOption
    non_refundable_policy_accepted: bool = False

    @model_validator(mode="after")
    def require_payment_policy_acceptance(self) -> "PublicCheckoutRequest":
        if not self.non_refundable_policy_accepted:
            raise ValueError(
                "You must accept the non-refundable payment policy before checkout."
            )
        return self


class PublicCheckoutResponse(BaseModel):
    """Single-use Square link created from a server-calculated amount."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    package_id: str
    payment_option: PaymentOption
    amount_due_now: str
    order_total: str
    remaining_balance: str
    checkout_url: str


class CheckoutReadiness(StrEnum):
    READY = "ready_to_checkout"
    INTERESTED_NOT_READY = "interested_not_ready"
    NOT_RIGHT = "recommendation_not_right"


class DecisionBarrier(StrEnum):
    NEEDS_MORE_INFORMATION = "needs_more_information"
    NEEDS_AMBASSADOR = "needs_ambassador"
    TIMING = "timing_not_right"
    INVESTMENT = "investment_mismatch"
    SERVICES = "services_mismatch"
    COORDINATING = "coordinating_guests"
    COMPARING = "comparing_options"
    TECHNICAL = "technical_problem"
    OTHER = "other"


class RecommendationHelpfulness(StrEnum):
    VERY = "very_helpful"
    SOMEWHAT = "somewhat_helpful"
    NOT = "not_helpful"


class ConversionFeedbackRequest(BaseModel):
    """Conversion signal submitted without interrupting checkout."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    lead_id: str = Field(min_length=8, max_length=80)
    trace_id: str | None = Field(default=None, max_length=100)
    primary_package_id: str = Field(min_length=3, max_length=80)
    secondary_package_id: str | None = Field(default=None, max_length=80)
    investment_target: Decimal | None = Field(default=None, ge=0)
    quoted_total: Decimal | None = Field(default=None, ge=0)
    group_size: int = Field(default=1, ge=1, le=250)
    readiness: CheckoutReadiness
    barrier: DecisionBarrier | None = None
    helpfulness: RecommendationHelpfulness | None = None
    additional_comment: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def require_barrier_when_not_ready(self) -> "ConversionFeedbackRequest":
        if self.readiness != CheckoutReadiness.READY and self.barrier is None:
            raise ValueError("Please tell us what is keeping you from checkout.")
        return self


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("CORS_ORIGINS")

    if configured_origins:
        return [
            origin.strip()
            for origin in configured_origins.split(",")
            if origin.strip()
        ]

    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://paradiseislife.biz",
        "https://www.paradiseislife.biz",
    ]


def configured_https_url(environment_name: str) -> str | None:
    value = os.getenv(environment_name, "").strip()
    return value if value.startswith("https://") else None


def guest_actions() -> GuestActions:
    return GuestActions(
        express_calendar_url=configured_https_url(
            "EXPRESS_RESET_CALENDAR_URL"
        ),
        consultation_url=WELLNESS_AMBASSADOR_URL,
        product_shop_url=PRODUCT_SHOP_URL,
        questions_url=WELLNESS_AMBASSADOR_URL,
    )



app = FastAPI(
    title="Paradise Park Prescriptive Sales Agent",
    description=(
        "Deterministic assessment, package and agenda recommendation API."
    ),
    version="0.6.6",
)

app.include_router(concierge_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/", include_in_schema=False)
def assessment_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "paradise-park-sales-agent",
        "version": "0.6.6",
        "lead_storage": "enabled" if lead_storage_enabled() else "disabled",
    }


@app.post("/v1/feedback", status_code=202)
def capture_conversion_feedback(
    payload: ConversionFeedbackRequest,
) -> dict[str, str]:
    """Record why a guest is or is not ready to reserve."""

    record_event_safely(
        collection_environment_name="FIRESTORE_CONVERSION_COLLECTION",
        default_collection="conversion_feedback",
        record_id=event_document_id(payload.lead_id),
        values={
            "lead_id": payload.lead_id,
            "trace_id": payload.trace_id,
            "primary_package_id": payload.primary_package_id,
            "secondary_package_id": payload.secondary_package_id,
            "investment_target": str(payload.investment_target or ""),
            "quoted_total": str(payload.quoted_total or ""),
            "group_size": payload.group_size,
            "readiness": payload.readiness.value,
            "barrier": payload.barrier.value if payload.barrier else None,
            "helpfulness": (
                payload.helpfulness.value if payload.helpfulness else None
            ),
            "additional_comment": payload.additional_comment,
        },
    )
    return {"status": "accepted"}


@app.post("/v1/leads/capture", status_code=202)
def capture_lead(
    payload: LeadCaptureRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """Preserve a recoverable lead when the guest advances beyond contact."""

    repository = get_lead_repository()
    lead_values = {
        "name": payload.name,
        "email": payload.email.lower(),
        "phone": payload.phone,
        "instagram_handle": payload.instagram_handle,
        "referral_source": payload.referral_source,
        "marketing_consent": False,
    }
    persist_lead(
        repository,
        lead_id=payload.lead_id,
        stage="assessment_started",
        values=lead_values,
    )
    background_tasks.add_task(
        notify_admin_and_record,
        repository,
        lead_id=payload.lead_id,
        subject=f"Paradise Park assessment started — {payload.name}",
        fields={
            "Lead ID": payload.lead_id,
            "Name": payload.name,
            "Email": payload.email,
            "Phone": payload.phone,
            "Instagram": payload.instagram_handle or "Not provided",
            "How they heard about us": payload.referral_source,
            "Status": "Assessment started; recommendation not yet completed",
        },
    )
    return {"status": "accepted", "lead_id": payload.lead_id}


@app.post(
    "/v1/recommendations",
    response_model=PublicSalesResponse,
)
def create_recommendation(
    payload: PublicSalesRequest,
    background_tasks: BackgroundTasks,
) -> PublicSalesResponse:
    dates = validate_service_schedule(
        payload.requested_start_date,
        payload.duration_days,
    )

    assessment = payload.assessment.model_copy(
        update={"duration_days": payload.duration_days}
    )

    result = run_sales_workflow(
        assessment,
        additional_text=payload.additional_text,
    )

    response = PublicSalesResponse(
        status=result.status,
        trace_id=result.trace_id,
        message=result.message,
        booking=BookingSummary(
            requested_start_date=dates[0],
            requested_end_date=dates[-1],
            duration_days=payload.duration_days,
            group_size=assessment.group_size,
            selected_upgrades=payload.selected_upgrades,
        ),
        recommendation=result.recommendation,
        actions=guest_actions(),
    )
    recommendation = result.recommendation
    repository = get_lead_repository()
    persist_lead(
        repository,
        lead_id=payload.lead_id,
        stage="recommendation_completed",
        values={
            "trace_id": result.trace_id,
            "name": assessment.contact_name,
            "email": assessment.contact_email.lower(),
            "phone": assessment.contact_phone,
            "instagram_handle": assessment.instagram_handle,
            "referral_source": assessment.referral_source,
            "marketing_consent": assessment.consent.marketing,
            "report_consent": assessment.consent.deliver_report,
            "group_size": assessment.group_size,
            "booking_mode": assessment.booking_mode.value,
            "requested_start_date": dates[0].isoformat(),
            "requested_end_date": dates[-1].isoformat(),
            "investment_target": str(assessment.budget or ""),
            "priority_codes": [signal.code for signal in assessment.signals],
            "selected_addon_ids": assessment.selected_addon_ids,
            "product_interests": [
                item.value for item in payload.selected_upgrades
            ],
            "recommendation": (
                recommendation.package.name
                if recommendation
                else "Ambassador review"
            ),
            "recommendation_reason": (
                recommendation.personalized_narrative
                if recommendation
                else result.message
            ),
            "quoted_total": (
                str(recommendation.pricing_breakdown.order_total)
                if recommendation and recommendation.pricing_breakdown
                else None
            ),
        },
    )
    background_tasks.add_task(
        notify_admin_and_record,
        repository,
        lead_id=payload.lead_id,
        subject=f"Paradise Park recommendation completed — {assessment.contact_name}",
        fields={
            "Lead ID": payload.lead_id,
            "Trace ID": result.trace_id,
            "Name": assessment.contact_name,
            "Email": assessment.contact_email,
            "Phone": assessment.contact_phone,
            "Instagram": assessment.instagram_handle or "Not provided",
            "How they heard about us": assessment.referral_source,
            "Guests": assessment.group_size,
            "Booking mode": assessment.booking_mode.value,
            "Requested dates": f"{dates[0]} through {dates[-1]}",
            "Investment target": assessment.budget,
            "Priorities": ", ".join(signal.code for signal in assessment.signals),
            "Cart enhancements": ", ".join(assessment.selected_addon_ids) or "None",
            "Product interests": ", ".join(item.value for item in payload.selected_upgrades) or "None",
            "Recommendation": recommendation.package.name if recommendation else "Ambassador review",
            "Why selected": recommendation.personalized_narrative if recommendation else result.message,
            "Quoted total": (
                recommendation.pricing_breakdown.order_total
                if recommendation and recommendation.pricing_breakdown
                else "Not available"
            ),
        },
    )
    return response


@app.post(
    "/v1/checkout",
    response_model=PublicCheckoutResponse,
)
def create_checkout(
    payload: PublicCheckoutRequest,
    background_tasks: BackgroundTasks,
) -> PublicCheckoutResponse:
    """Rebuild the offer and create a Square link for the approved amount."""

    assessment = payload.assessment.model_copy(
        update={"duration_days": payload.duration_days}
    )
    result = run_sales_workflow(
        assessment,
        additional_text=payload.additional_text,
    )

    if result.status != WorkflowStatus.COMPLETED or not result.recommendation:
        raise HTTPException(
            status_code=409,
            detail=(
                "A Paradise Park Wellness Ambassador must review this "
                "request before checkout."
            ),
        )

    recommendation = result.recommendation
    choice = next(
        (
            item
            for item in recommendation.payment_choices
            if item.payment_option == payload.payment_option.value
        ),
        None,
    )
    if choice is None:
        raise HTTPException(
            status_code=422,
            detail="That payment option is not available for this package.",
        )

    try:
        link: CheckoutLink = create_square_payment_link(
            name=(
                f"{recommendation.package.name} — {choice.label}"
            ),
            amount=choice.amount_due_now,
            trace_id=result.trace_id,
            event_dates=(
                f"{payload.requested_start_date.isoformat()} through "
                f"{booking_end_date(payload.requested_start_date, payload.duration_days).isoformat()}"
            ),
            purchase_details=(
                f"{recommendation.package.name}; {payload.duration_days} service day(s); "
                f"{assessment.group_size} guest(s); {choice.label}; "
                f"remaining balance ${choice.remaining_balance:.2f} due 14 days before the event"
            ),
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    repository = get_lead_repository()
    persist_lead(
        repository,
        lead_id=payload.lead_id,
        stage="checkout_started",
        values={
            "trace_id": result.trace_id,
            "name": assessment.contact_name,
            "email": assessment.contact_email.lower(),
            "phone": assessment.contact_phone,
            "marketing_consent": assessment.consent.marketing,
            "package": recommendation.package.name,
            "payment_option": payload.payment_option.value,
            "amount_due_now": str(choice.amount_due_now),
            "order_total": str(choice.order_total),
            "requested_start_date": payload.requested_start_date.isoformat(),
            "requested_end_date": booking_end_date(
                payload.requested_start_date, payload.duration_days
            ).isoformat(),
        },
    )
    background_tasks.add_task(
        notify_admin_and_record,
        repository,
        lead_id=payload.lead_id,
        subject=f"Paradise Park checkout started — {assessment.contact_name}",
        fields={
            "Lead ID": payload.lead_id,
            "Trace ID": result.trace_id,
            "Guest": assessment.contact_name,
            "Email": assessment.contact_email,
            "Phone": assessment.contact_phone,
            "Package": recommendation.package.name,
            "Payment option": payload.payment_option.value,
            "Amount due now": f"${choice.amount_due_now:.2f}",
            "Order total": f"${choice.order_total:.2f}",
            "Requested dates": f"{payload.requested_start_date} through {booking_end_date(payload.requested_start_date, payload.duration_days)}",
            "Note": "Checkout link created. Completed payment requires Square webhook confirmation.",
        },
    )

    return PublicCheckoutResponse(
        trace_id=result.trace_id,
        package_id=recommendation.package.package_id,
        payment_option=payload.payment_option,
        amount_due_now=f"{choice.amount_due_now:.2f}",
        order_total=f"{choice.order_total:.2f}",
        remaining_balance=f"{choice.remaining_balance:.2f}",
        checkout_url=link.url,
    )
