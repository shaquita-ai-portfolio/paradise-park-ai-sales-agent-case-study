"""Profit-aware deterministic curation for Paradise Park experiences.

The model may later explain this result, but package choice, entitlements,
prices and payment math are controlled here and in commercial_policy.py.
"""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any
from paradise_park_sales_agent.runtime_paths import DATA_DIR

from paradise_park_sales_agent.catalog import (
    ServiceCatalog,
    ServiceDefinition,
    load_catalog,
)
from paradise_park_sales_agent.commercial_policy import (
    AddonSelection,
    PaymentOption,
    PolicyRepository,
    quote_package,
    validate_experience_plan,
)
from paradise_park_sales_agent.recommendation_models import (
    AgendaItemRecommendation,
    AlternativePackageOption,
    CoreExperience,
    CommercialStatus,
    PackageRecommendation,
    PaymentChoice,
    PricingBreakdown,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationStrategy,
    SignalSource,
    WellnessInsight,
)


PATHWAYS = {
    "guided_reflection": "internal_work",
    "guided_breathwork": "internal_work",
    "transitions_clarity": "internal_work",
    "legacy_visualization": "internal_work",
    "faith_purpose_circle": "internal_work",
    "child_of_god": "internal_work",
    "tea_tasting": "internal_work",
    "garden_to_glass": "internal_work",
    "sound_therapy": "external_work",
    "advanced_aromatherapy": "external_work",
    "aromatherapy_treatment": "external_work",
    "stretch_swing": "external_work",
    "assisted_stretch": "external_work",
    "somatic_release": "external_work",
    "elevated_facial": "external_work",
    "herbal_foot_reflexology": "external_work",
    "womb_wellness": "external_work",
    "cycle_syncing_consult": "internal_work",
    "river_rest": "environment",
    "forest_bathing": "environment",
    "garden_tour": "environment",
    "garden_taste_tour": "environment",
    "team_building": "environment",
    "music_karaoke": "environment",
    "music_medicine": "environment",
    "vegan_dining": "internal_work",
}

EXPRESS_POOL = [
    "sound_therapy",
    "stretch_swing",
    "garden_taste_tour",
    "tea_tasting",
    "garden_to_glass",
]

INDIVIDUAL_LOW_POOL = [
    "guided_reflection",
    "sound_therapy",
    "river_rest",
    "guided_breathwork",
    "aromatherapy_treatment",
    "forest_bathing",
    "tea_tasting",
    "garden_tour",
]

GROUP_LOW_POOL = [
    "guided_reflection",
    "sound_therapy",
    "guided_breathwork",
    "team_building",
    "garden_tour",
    "advanced_aromatherapy",
    "music_karaoke",
]

PRIVATE_BY_SIGNAL = {
    "body_tension": "assisted_stretch",
    "gentle_body_support": "herbal_foot_reflexology",
    "intensive_mobility_support": "assisted_stretch",
    "emotional_load": "somatic_release",
    "womb_centered": "womb_wellness",
    "skin_ritual": "elevated_facial",
    "anxiety_support": "somatic_release",
    "trauma_aware_support": "somatic_release",
    "anti_aging": "elevated_facial",
    "natural_fertility": "womb_wellness",
    "high_stress": "somatic_release",
    "burnout_renewal": "somatic_release",
    "high_demand_lifestyle": "assisted_stretch",
}

DEFAULT_PRIVATE_POOL = ["assisted_stretch", "elevated_facial"]


def default_rules_path() -> Path:
    return DATA_DIR / "recommendation_rules.json"


@lru_cache(maxsize=2)
def load_recommendation_rules(path: str | Path | None = None) -> dict[str, Any]:
    rules_path = Path(path).resolve() if path else default_rules_path()
    if not rules_path.exists():
        raise FileNotFoundError(f"Recommendation rules were not found at {rules_path}")
    with rules_path.open(encoding="utf-8") as source:
        return json.load(source)


def normalize_goals(goals: list[str]) -> set[str]:
    return {goal.strip().lower().replace(" ", "_") for goal in goals}


def preferred_package_is_eligible(
    package_id: str,
    request: RecommendationRequest,
) -> bool:
    """Allow guest-selected alternatives only when their rules still hold."""

    if package_id == "express_reset":
        return request.group_size <= 5 and request.duration_days == 1
    if package_id == "rapid_reset":
        return request.group_size <= 5 and request.duration_days == 1
    if package_id == "executive_reset":
        return request.group_size <= 5 and request.duration_days <= 7
    if package_id == "peak_performance_pivot":
        return request.group_size <= 5 and request.duration_days >= 3
    if package_id == "group_wellness_reset":
        return request.group_size >= 10
    if package_id == "group_immersive_retreat":
        return request.group_size >= 15
    if package_id == "premium_small_group_retreat":
        return request.group_size >= 6
    return False


def select_package_id(request: RecommendationRequest) -> str:
    """Select an approved tier without allowing an LLM to change pricing."""

    budget = request.budget or Decimal("997")

    if (
        request.preferred_package_id
        and preferred_package_is_eligible(
            request.preferred_package_id,
            request,
        )
    ):
        return request.preferred_package_id

    if request.group_size >= 6:
        goals = normalize_goals(request.goals)
        wants_overnight = "overnight_stay" in goals
        if wants_overnight and request.group_size >= 15:
            return "group_immersive_retreat"
        if wants_overnight and request.group_size >= 6:
            return "premium_small_group_retreat"
        if request.group_size >= 15 and budget >= (
            Decimal("874") * request.group_size * request.duration_days
        ):
            return "group_immersive_retreat"
        if budget >= (
            Decimal("1124") * request.group_size * request.duration_days
        ):
            return "premium_small_group_retreat"
        if request.group_size < 10:
            return "premium_small_group_retreat"
        return "group_wellness_reset"

    # For personal retreats, the guest's stated investment is the hard
    # commercial boundary. Their priorities personalize the offer; they do
    # not silently promote a $499 guest into a multi-thousand-dollar package.
    if budget <= Decimal("500"):
        return "express_reset"
    if budget < Decimal("1800"):
        return "rapid_reset"
    if budget >= Decimal("9987") and request.duration_days >= 3:
        return "peak_performance_pivot"
    return "executive_reset"


def reflected_copy(
    request: RecommendationRequest,
    signal_maps: dict[str, dict[str, Any]],
) -> list[str]:
    statements: list[str] = []
    for signal in request.signals:
        rule = signal_maps.get(signal.code)
        if not rule:
            continue
        key = (
            "explicit_guest_copy"
            if signal.source == SignalSource.EXPLICIT
            else "inferred_guest_copy"
        )
        statements.append(rule[key])
    return statements or [
        "Based on your answers, you may enjoy a thoughtfully paced Paradise Park experience."
    ]


def personalized_narrative(
    request: RecommendationRequest,
    package_id: str,
) -> str:
    """Create a safe sales narrative without changing package decisions."""

    priorities = [goal.replace("_", " ") for goal in request.goals[:3]]
    priority_copy = ", ".join(priorities) or "rest and meaningful reflection"
    package_support = {
        "express_reset": (
            "Express Reset creates an intentional pause through one featured "
            "wellness activation, journal prompts, nature, solitude and time "
            "to explore Paradise Park."
        ),
        "rapid_reset": (
            "Rapid Reset creates a meaningful five-to-six-hour pause through "
            "fresh-pressed juice, guided wellness activations and restorative time."
        ),
        "executive_reset": (
            "Executive Reset creates protected time for a deeper exhale through "
            "Pre-Glow preparation, personalized guidance, private wellness care, "
            "restorative nature experiences and Farm-to-Table nourishment."
        ),
        "peak_performance_pivot": (
            "Peak Performance Pivot creates an immersive reset with Pre-Glow "
            "preparation, daily private care and structured integration support."
        ),
    }.get(
        package_id,
        "This experience creates intentional space for restoration, reflection and connection.",
    )
    return (
        "Modern life can leave very little room to slow down, gain clarity and "
        "reconnect with what matters most. You shared that "
        f"{priority_copy} are meaningful priorities. {package_support}"
    )


def recommendation_strategy(
    request: RecommendationRequest,
    package_subtotal: Decimal,
) -> RecommendationStrategy:
    budget = request.budget
    if budget is not None and package_subtotal > budget:
        return RecommendationStrategy.UPSELL
    return RecommendationStrategy.WITHIN_TARGET


def ranked_signal_services(
    request: RecommendationRequest,
    signal_maps: dict[str, dict[str, Any]],
) -> list[str]:
    ranked: list[str] = []
    for signal in request.signals:
        rule = signal_maps.get(signal.code)
        if rule:
            ranked.extend(rule["ranked_service_ids"])
    return list(dict.fromkeys(ranked))


def choose_from_pool(
    ranked: list[str],
    approved_pool: list[str],
    count: int,
) -> list[tuple[str, int]]:
    ordered = [item for item in ranked if item in approved_pool]
    ordered.extend(item for item in approved_pool if item not in ordered)
    chosen = ordered[: min(count, len(ordered))]
    if not chosen:
        raise RuntimeError("No approved services are available for this package.")

    quantities = [1] * len(chosen)
    remaining = count - len(chosen)
    cursor = 0
    while remaining > 0:
        quantities[cursor % len(quantities)] += 1
        cursor += 1
        remaining -= 1
    return list(zip(chosen, quantities, strict=True))


def why_for_service(
    service_id: str,
    request: RecommendationRequest,
    signal_maps: dict[str, dict[str, Any]],
) -> str:
    for signal in request.signals:
        rule = signal_maps.get(signal.code)
        if rule and service_id in rule["ranked_service_ids"]:
            key = (
                "explicit_guest_copy"
                if signal.source == SignalSource.EXPLICIT
                else "inferred_guest_copy"
            )
            return rule[key]
    return (
        "You may enjoy this activation as part of a balanced experience "
        "designed around the priorities you shared."
    )


def service_price_statement(service: ServiceDefinition) -> str:
    price = service.client_price
    if price.status == "fixed" and price.amount is not None:
        basis = price.basis.replace("_", " ")
        return f"${price.amount:,.0f} per {basis}."
    return "Final price and availability are confirmed before checkout."


def agenda_item(
    *,
    order: int,
    service: ServiceDefinition,
    request: RecommendationRequest,
    signal_maps: dict[str, dict[str, Any]],
    status: CommercialStatus,
    quantity: int = 1,
    day: int = 1,
    service_class: str = "low_overhead",
) -> AgendaItemRecommendation:
    included = status == CommercialStatus.PROPOSED_INCLUDED
    return AgendaItemRecommendation(
        order=order,
        day=day,
        service_class=service_class,
        service_id=service.id,
        name=service.name,
        guest_description=service.agenda_copy,
        why_helpful=why_for_service(service.id, request, signal_maps),
        commercial_status=status,
        price_statement=(
            "Included in this package."
            if included
            else service_price_statement(service)
        ),
        pathway=PATHWAYS.get(service.id, "whole_person"),
        quantity=quantity,
        requires_human_confirmation=(
            service.requires_human_confirmation and not included
        ),
    )


def private_candidates(request: RecommendationRequest) -> list[str]:
    selected = [
        PRIVATE_BY_SIGNAL[signal.code]
        for signal in request.signals
        if signal.code in PRIVATE_BY_SIGNAL
    ]
    selected.extend(item for item in DEFAULT_PRIVATE_POOL if item not in selected)
    return list(dict.fromkeys(selected))


def package_entitlements(
    package_id: str,
    duration_days: int,
) -> tuple[int, int, int]:
    """Return included low-overhead, included private and paid-private limits."""

    if package_id == "express_reset":
        return 1, 0, 0
    if package_id == "rapid_reset":
        return 4, 0, 1
    if package_id == "executive_reset":
        return 3 * duration_days, 2 * duration_days, 0
    if package_id == "peak_performance_pivot":
        return 3 * duration_days, 2 * duration_days, 0
    if package_id == "group_wellness_reset":
        return 4 * duration_days, 0, 0
    if package_id == "group_immersive_retreat":
        return 3 * duration_days, 0, 0
    if package_id == "premium_small_group_retreat":
        return 5 * duration_days, 0, 0
    raise RuntimeError(f"Unsupported package: {package_id}")


def effective_duration(package_id: str, requested_days: int) -> int:
    if package_id in {"express_reset", "rapid_reset"}:
        return 1
    if package_id == "peak_performance_pivot":
        return max(3, min(requested_days, 7))
    return min(requested_days, 7)


def build_wellness_insights(request: RecommendationRequest) -> list[WellnessInsight]:
    signal_codes = {signal.code for signal in request.signals}
    internal_observation = (
        "You shared that clarity and emotional spaciousness matter right now."
        if signal_codes & {"clarity_transition", "emotional_load"}
        else "Your answers suggest that intentional pauses may support the reset you want."
    )
    external_observation = (
        "You noted body tension or a desire for more ease in your physical rhythm."
        if signal_codes & {"body_tension", "gentle_body_support", "intensive_mobility_support"}
        else "A gentle body-awareness practice can help make rest feel more embodied."
    )
    environment_observation = (
        "You specifically selected nature as part of a meaningful experience."
        if "nature_connection" in signal_codes
        else "A change of setting can create a clear boundary between pressure and restoration."
    )
    return [
        WellnessInsight(
            pathway="internal_work",
            title="Create an intentional pause",
            observation=internal_observation,
            practice_tip="Try three slow breaths before your next transition and name one priority for the next hour.",
        ),
        WellnessInsight(
            pathway="external_work",
            title="Listen to the body without judgment",
            observation=external_observation,
            practice_tip="Take a two-minute movement break and notice where you can soften your shoulders, jaw and hands.",
        ),
        WellnessInsight(
            pathway="environment",
            title="Let your surroundings support you",
            observation=environment_observation,
            practice_tip="Step outside or sit near a window for five quiet minutes without multitasking.",
        ),
    ]


def payment_choices(
    package_id: str,
    *,
    group_size: int,
    duration_days: int,
    addon_ids: list[str] | None = None,
) -> list[PaymentChoice]:
    addons = [AddonSelection(addon_id) for addon_id in (addon_ids or [])]
    choices: list[PaymentChoice] = []
    full = quote_package(
        package_id,
        group_size=group_size,
        duration_days=duration_days,
        payment_option=PaymentOption.PAY_IN_FULL,
        addons=addons,
    )
    choices.append(
        PaymentChoice(
            payment_option=PaymentOption.PAY_IN_FULL.value,
            label=("Pay in full" if full.discount == 0 else "Pay in full and save 10%"),
            amount_due_now=full.amount_due_now,
            order_total=full.order_total,
            remaining_balance=full.remaining_balance,
            savings=full.discount,
            description=(
                "Complete your purchase in one payment."
                if full.discount == 0
                else "Save 10% on the package base; separately priced enhancements are not discounted."
            ),
        )
    )

    policy = PolicyRepository().package(package_id)
    if bool(policy["deposit_allowed"]):
        balance_due_days = int(
            PolicyRepository().payment_policy[
                "individual_balance_due_days"
            ]
        )
        deposit = quote_package(
            package_id,
            group_size=group_size,
            duration_days=duration_days,
            payment_option=PaymentOption.DEPOSIT,
            addons=addons,
        )
        choices.append(
            PaymentChoice(
                payment_option=PaymentOption.DEPOSIT.value,
                label="Reserve with a 50% deposit",
                amount_due_now=deposit.amount_due_now,
                order_total=deposit.order_total,
                remaining_balance=deposit.remaining_balance,
                description=(
                    "Reserve now and pay the remaining balance "
                    f"{balance_due_days} days before the event date."
                ),
            )
        )
    return choices


def alternative_packages(
    request: RecommendationRequest,
    primary_package_id: str,
    duration_days: int,
) -> list[AlternativePackageOption]:
    """Offer profitable Good/Better/Best paths without relaxing eligibility."""

    alternatives: list[AlternativePackageOption] = []

    def add(
        package_id: str,
        price_statement: str,
        why: str,
        *,
        qualification: str | None = None,
        action: str = "Select this level and refresh your recommendation.",
    ) -> None:
        if package_id == primary_package_id:
            return
        policy = PolicyRepository().package(package_id)
        alternatives.append(
            AlternativePackageOption(
                package_id=package_id,
                name=str(policy["name"]),
                price_statement=price_statement,
                why_consider=why,
                qualification_note=qualification,
                action=action,
            )
        )

    if request.group_size >= 6:
        days = max(1, min(duration_days, 3))
        if request.group_size >= 10:
            total = Decimal("375") * request.group_size * days
            add(
                "group_wellness_reset",
                f"${total:,.2f} estimated for {request.group_size} guests and {days} day(s)",
                "A profitable four-hour restoration format each service day with four guided group activations.",
            )
        if request.group_size >= 15:
            total = Decimal("874") * request.group_size * days
            add(
                "group_immersive_retreat",
                f"${total:,.2f} estimated at $874 per person per day",
                "Adds full-day immersion, Farm-to-Table culinary exploration and Lakeside Villas lodging.",
            )
        else:
            add(
                "group_immersive_retreat",
                "$874 per person per day",
                "Adds full-day immersion, Farm-to-Table culinary exploration and Lakeside Villas lodging.",
                qualification="Available when the group reaches the 15-guest minimum.",
                action="Invite additional guests or ask a Wellness Ambassador about the premium small-group path.",
            )
        premium_total = Decimal("1124") * request.group_size * days
        add(
            "premium_small_group_retreat",
            f"${premium_total:,.2f} estimated at $1,124 per person per day",
            "A high-touch option with five guided experiences per day, culinary exploration and Lakeside Villas lodging.",
        )
        return alternatives[:3]

    budget = request.budget or Decimal("997")

    if primary_package_id == "express_reset":
        add(
            "rapid_reset",
            "$997 before optional private enhancements",
            "When you are ready for more personalization, Rapid Reset expands your experience to four guided activations and allows you to add focused private care.",
        )
        return alternatives[:1]

    if primary_package_id == "rapid_reset":
        add(
            "executive_reset",
            "From $1,800 per person",
            "If your priorities call for deeper private support, Executive Reset adds Pre-Glow preparation, culinary exploration, lodging and focused one-to-one care.",
        )
        return alternatives[:1]

    if primary_package_id in {"executive_reset", "peak_performance_pivot"}:
        if budget <= Decimal("500"):
            add(
                "express_reset",
                "$147 paid through the wellness-session calendar",
                "Based on the investment target you selected, Express Reset is an intentional single-session introduction with journal prompts, nature, solitude and time to explore the property. It does not provide the customized multi-session depth of your primary recommendation.",
                action="Choose an Express wellness session from the calendar.",
            )
        elif budget < Decimal("1800"):
            add(
                "rapid_reset",
                "$997 before optional private enhancements",
                "Based on the investment target you selected, Rapid Reset offers a meaningful five-to-six-hour refresh. Your primary recommendation provides stronger support for the deeper priorities you shared.",
            )
        elif primary_package_id == "peak_performance_pivot":
            executive_days = max(1, min(request.duration_days, 3))
            executive_price = {1: 1800, 2: 3400, 3: 4800}[executive_days]
            add(
                "executive_reset",
                f"From ${executive_price:,.2f} per person",
                "Based on your investment target, Executive Reset preserves personalized immersion at a lower investment than Peak Performance Pivot.",
            )
        else:
            add(
                "rapid_reset",
                "$997 before optional private enhancements",
                "A shorter secondary path when you prefer a smaller commitment than the primary Executive Reset recommendation.",
            )
        return alternatives[:1]

    add(
        "express_reset",
        "$147 paid through the wellness-session calendar",
        "Based on the investment target you selected, this is an intentional introduction to Paradise Park through one featured activation, journal prompts, nature, solitude and time to explore the property.",
        action="Choose an Express wellness session from the calendar.",
    )
    add(
        "rapid_reset",
        "$997 before optional private enhancements",
        "Based on the investment target you selected, this meaningful half-day refresh offers four guided activations with the option to add focused private care.",
    )
    executive_days = max(1, min(request.duration_days, 3))
    executive_price = {1: 1800, 2: 3400, 3: 4800}[executive_days]
    add(
        "executive_reset",
        f"From ${executive_price:,.2f} for {executive_days} day(s)",
        "A deeper private reset with culinary exploration, lodging and focused one-to-one care.",
    )
    return alternatives[:1]


def package_copy(
    package_id: str,
    request: RecommendationRequest,
    *,
    duration_days: int,
) -> dict[str, str]:
    goals = ", ".join(goal.replace("_", " ") for goal in request.goals[:3])
    shared = f"You shared that {goals} matter to you. " if goals else ""
    copies = {
        "express_reset": {
            "care_level": "A taste of Paradise Park and a quick refresh",
            "duration": "Approximately 3 hours on an approved Paradise Park service date",
            "included": "One featured core activation plus tea, a property tour, journal prompts and simple refreshments.",
            "hospitality": "Although this is not a customized multi-session retreat, intentional wellness micro-experiences are included, such as journal prompts and time to explore the property, nature and solitude.",
            "why": shared + "Express Reset offers one nurturing scheduled activation so you can step away from pressure and leave feeling refreshed without overcommitting.",
            "cta": "Choose an approved date and any available enhancements through the Express wellness-session calendar.",
            "checkout_mode": "express_calendar",
        },
        "rapid_reset": {
            "care_level": "A personalized, immersive half-day unplug",
            "duration": "Approximately 4 hours; up to 6 hours with approved private upgrades",
            "included": "Four scalable guided activations across internal work, external work and environment; private care is priced separately.",
            "hospitality": "Fresh-pressed juice and light raw or vegan refreshments support an intermittently fasted experience; no full meal is included.",
            "why": shared + "Rapid Reset creates a more personalized rhythm than Express, with four complementary activations and the option to add focused one-to-one care.",
            "cta": "Choose a payment option and any private enhancement, or schedule a Wellness Ambassador consultation.",
            "checkout_mode": "square_checkout",
        },
        "executive_reset": {
            "care_level": "A private, deeply personalized reset for restoration and clarity",
            "duration": f"{duration_days} immersive day(s)",
            "included": "The Pre-Glow Program—an Inner Wellness Assessment, Personality Assessment and Ultimate Wellness Pathways Intuitive Guidance Consult—plus three guided activations and up to two private services per day. These insights allow us to curate a deeply personalized and transformative experience.",
            "hospitality": "Farm-to-Table culinary exploration and Grand Cabin lodging are included; Lakeside Villas are an optional upgrade.",
            "why": shared + "Executive Reset provides the time and private attention needed to examine patterns, interrupt stress habits and establish a clearer restorative rhythm.",
            "cta": "Choose pay-in-full or deposit checkout, or speak with a Wellness Ambassador before purchasing.",
            "checkout_mode": "square_checkout",
        },
        "peak_performance_pivot": {
            "care_level": "An intensive transformation with structured aftercare",
            "duration": "3 days and 2 nights, followed by 60 days of integration support",
            "included": "The Pre-Glow Program—an Inner Wellness Assessment, Personality Assessment and Ultimate Wellness Pathways Intuitive Guidance Consult—plus daily guided and private experiences and a mind-body-spirit-emotions Wellness Blueprint Workbook.",
            "hospitality": "Farm-to-Table culinary exploration and Grand Cabin lodging are included; Lakeside Villas are an optional upgrade.",
            "why": shared + "Peak Performance Pivot is designed for guests ready for an in-depth reset with daily private care and a structured path to carry insights forward.",
            "cta": "Secure the transformation in full for 10% savings or reserve it with a 50% deposit.",
            "checkout_mode": "square_checkout",
        },
        "group_wellness_reset": {
            "care_level": "A restorative four-hour group experience",
            "duration": f"Approximately 4 hours per service day for {duration_days} day(s); minimum 10 guests",
            "included": "Four scalable guided group activations per day, beginning with a signature welcome and intention setting.",
            "hospitality": "Fresh juice and light refreshments are included; meals and lodging are not included.",
            "why": shared + "Your restoration begins with a signature welcome and intention setting, followed by a curated rhythm of guided reflection, Nirvana Sound Therapy, movement and nature. This tier creates a meaningful shared reset while keeping private, staffing-intensive services as paid enhancements.",
            "cta": "Select a payment option to reserve the group experience or schedule a Wellness Ambassador consultation.",
            "checkout_mode": "square_checkout",
        },
        "group_immersive_retreat": {
            "care_level": "A full-day immersive group retreat",
            "duration": f"{duration_days} full retreat day(s); minimum 15 guests",
            "included": "Three rotating guided group experiences per day.",
            "hospitality": "Farm-to-Table culinary exploration and premium Lakeside Villas accommodations are included.",
            "why": shared + "This immersive tier balances restoration, shared connection, culinary care and overnight comfort for a larger group.",
            "cta": "Choose a payment option to reserve the retreat or request Wellness Ambassador guidance.",
            "checkout_mode": "square_checkout",
        },
        "premium_small_group_retreat": {
            "care_level": "A premium high-touch small-group retreat",
            "duration": f"{duration_days} full retreat day(s); minimum 6 guests",
            "included": "Five guided group experiences per day.",
            "hospitality": "Farm-to-Table culinary exploration and premium Lakeside Villas accommodations are included.",
            "why": shared + "This tier offers a denser, more personalized daily agenda for a smaller group while retaining the efficiencies of guided group delivery.",
            "cta": "Choose a payment option to reserve the retreat or request Wellness Ambassador guidance.",
            "checkout_mode": "square_checkout",
        },
    }
    return copies[package_id]


def build_recommendation(
    request: RecommendationRequest,
    *,
    catalog: ServiceCatalog | None = None,
    rules: dict[str, Any] | None = None,
) -> RecommendationResponse:
    """Curate an approved package, agenda, report and payment choices."""

    active_catalog = catalog or load_catalog()
    active_rules = rules if rules is not None else load_recommendation_rules()
    signal_maps = {item["signal"]: item for item in active_rules["signal_maps"]}
    ranked = ranked_signal_services(request, signal_maps)
    package_id = select_package_id(request)
    priced_addon_ids = (
        request.selected_addon_ids
        if package_id == "rapid_reset"
        else []
    )
    duration_days = effective_duration(package_id, request.duration_days)
    low_count, private_included_limit, paid_private_limit = package_entitlements(
        package_id, duration_days
    )

    if package_id == "express_reset":
        low_pool = EXPRESS_POOL
    elif package_id.startswith("group_") or package_id == "premium_small_group_retreat":
        low_pool = GROUP_LOW_POOL
    else:
        low_pool = INDIVIDUAL_LOW_POOL

    premium_daily_itinerary = package_id in {
        "executive_reset", "peak_performance_pivot"
    }
    if premium_daily_itinerary:
        ordered_low = [item for item in ranked if item in low_pool]
        ordered_low.extend(item for item in low_pool if item not in ordered_low)
        low_selections = []
    elif duration_days > 1 and package_id in {
        "group_immersive_retreat", "premium_small_group_retreat"
    }:
        per_day = low_count // duration_days
        low_selections = [
            (service_id, duration_days)
            for service_id, _ in choose_from_pool(ranked, low_pool, per_day)
        ]
    else:
        low_selections = choose_from_pool(ranked, low_pool, low_count)

    items: list[AgendaItemRecommendation] = []
    if premium_daily_itinerary:
        for day in range(1, duration_days + 1):
            start = ((day - 1) * 2) % len(ordered_low)
            daily_low = [
                ordered_low[(start + offset) % len(ordered_low)]
                for offset in range(3)
            ]
            for service_id in daily_low:
                items.append(
                    agenda_item(
                        order=len(items) + 1,
                        day=day,
                        service_class="low_overhead",
                        service=active_catalog.require_service(service_id),
                        request=request,
                        signal_maps=signal_maps,
                        status=CommercialStatus.PROPOSED_INCLUDED,
                    )
                )
    else:
        for service_id, quantity in low_selections:
            items.append(
                agenda_item(
                    order=len(items) + 1,
                    service=active_catalog.require_service(service_id),
                    request=request,
                    signal_maps=signal_maps,
                    status=CommercialStatus.PROPOSED_INCLUDED,
                    quantity=quantity,
                )
            )

    included_private_count = 0
    paid_private_count = 0
    candidate_private = private_candidates(request)
    if private_included_limit:
        if premium_daily_itinerary:
            rotation_pool = list(dict.fromkeys(
                candidate_private
                + ["somatic_release", "womb_wellness", "elevated_facial"]
            ))
            private_selections = []
            for day in range(1, duration_days + 1):
                start = day - 1
                daily_private = [
                    rotation_pool[start % len(rotation_pool)],
                    rotation_pool[(start + 1) % len(rotation_pool)],
                ]
                for service_id in daily_private:
                    items.append(
                        agenda_item(
                            order=len(items) + 1,
                            day=day,
                            service_class="one_on_one",
                            service=active_catalog.require_service(service_id),
                            request=request,
                            signal_maps=signal_maps,
                            status=CommercialStatus.PROPOSED_INCLUDED,
                        )
                    )
                    included_private_count += 1
            private_selections = []
        else:
            per_day_types = min(2, len(candidate_private))
            private_selections = [
                (service_id, duration_days)
                for service_id in candidate_private[:per_day_types]
            ]
        for service_id, quantity in private_selections:
            items.append(
                agenda_item(
                    order=len(items) + 1,
                    service=active_catalog.require_service(service_id),
                    request=request,
                    signal_maps=signal_maps,
                    status=CommercialStatus.PROPOSED_INCLUDED,
                    quantity=quantity,
                    service_class="one_on_one",
                )
            )
            included_private_count += quantity
    elif paid_private_limit and priced_addon_ids:
        selected_private_ids = [
            addon_id
            for addon_id in priced_addon_ids
            if addon_id != "farm_to_table_individual"
        ]
        for service_id in selected_private_ids:
            items.append(
                agenda_item(
                    order=len(items) + 1,
                    service=active_catalog.require_service(service_id),
                    request=request,
                    signal_maps=signal_maps,
                    status=CommercialStatus.PAID_UPGRADE,
                )
            )
        paid_private_count = len(selected_private_ids)

        if "farm_to_table_individual" in priced_addon_ids:
            items.append(
                agenda_item(
                    order=len(items) + 1,
                    service=active_catalog.require_service("vegan_dining"),
                    request=request,
                    signal_maps=signal_maps,
                    status=CommercialStatus.PAID_UPGRADE,
                )
            )

    if package_id in {
        "group_immersive_retreat", "premium_small_group_retreat",
    }:
        dining = active_catalog.require_service("vegan_dining")
        items.append(
            agenda_item(
                order=len(items) + 1,
                service=dining,
                request=request,
                signal_maps=signal_maps,
                status=CommercialStatus.PROPOSED_INCLUDED,
                quantity=duration_days,
            )
        )

    validate_experience_plan(
        package_id,
        duration_days=duration_days,
        included_low_overhead_sessions=low_count,
        included_private_sessions=included_private_count,
        paid_private_upgrades=paid_private_count,
    )

    repo = PolicyRepository()
    policy = repo.package(package_id)
    copy = package_copy(
        package_id,
        request,
        duration_days=duration_days,
    )
    choices = payment_choices(
        package_id,
        group_size=request.group_size,
        duration_days=duration_days,
        addon_ids=priced_addon_ids,
    )
    base_quote = quote_package(
        package_id,
        group_size=request.group_size,
        duration_days=duration_days,
        payment_option=PaymentOption.DEPOSIT if policy["deposit_allowed"] else PaymentOption.PAY_IN_FULL,
        addons=[AddonSelection(addon_id) for addon_id in priced_addon_ids],
    )
    package_subtotal = base_quote.package_subtotal
    is_per_person_day = policy["pricing_type"] == "per_person_per_day"
    is_per_person_experience = (
        policy["pricing_type"] == "per_person_per_experience"
    )
    is_per_person = policy.get("pricing_scope") == "per_person"
    display_price = (
        Decimal(str(policy["base_price"]))
        if is_per_person_day or is_per_person_experience
        else Decimal(str(policy["duration_prices"][str(min(duration_days, 3))]))
        if is_per_person and policy["pricing_type"] == "duration_tier"
        else Decimal(str(policy["base_price"]))
        if is_per_person
        else package_subtotal
    )
    basis = (
        " per person per day"
        if is_per_person_day
        else " per person"
        if is_per_person_experience
        else " per person"
        if is_per_person
        else ""
    )
    separate = any(item.commercial_status == CommercialStatus.PAID_UPGRADE for item in items)
    price_summary = f"Package base: ${display_price:,.2f}{basis}."
    if is_per_person_day or is_per_person_experience:
        price_summary += (
            f" Estimated package subtotal for {request.group_size} guest(s): "
            f"${package_subtotal:,.2f}."
        )
    if separate:
        price_summary += " Optional private enhancements are priced separately."
    if bool(policy["deposit_allowed"]):
        price_summary += (
            " Pay in full for 10% package-base savings, "
            "or reserve with a 50% deposit."
        )
    else:
        price_summary += " This experience is paid in full through its booking calendar."

    return RecommendationResponse(
        assessment_mode=request.assessment_mode,
        reflected_statements=reflected_copy(request, signal_maps),
        personalized_narrative=personalized_narrative(request, package_id),
        fit_signals=reflected_copy(request, signal_maps)[:3],
        recommendation_strategy=recommendation_strategy(
            request,
            base_quote.package_subtotal + base_quote.extended_program_subtotal,
        ),
        package=PackageRecommendation(
            package_id=package_id,
            name=str(policy["name"]),
            price_statement=f"${display_price:,.2f}{basis}",
            why_it_fits=copy["why"],
            care_level=copy["care_level"],
            duration_statement=copy["duration"],
            included_summary=copy["included"],
            hospitality_summary=copy["hospitality"],
            checkout_mode=copy["checkout_mode"],
        ),
        agenda_items=items,
        core_experiences=(
            [
                CoreExperience(service_id="fresh_pressed_juice", name="Fresh-Pressed Juices", description="Fresh, plant-forward refreshment prepared as part of your immersive wellness rhythm."),
                CoreExperience(service_id="vegan_dining", name="Farm-to-Table Vegan Culinary Experience", description="A thoughtfully presented plant-forward culinary experience."),
                CoreExperience(service_id="sauna", name="Infrared Sauna", description="A warm, quiet relaxation ritual."),
                CoreExperience(service_id="red_light", name="Red Light Wellness Session", description="A quiet light-based ritual that complements rest and recovery routines."),
                CoreExperience(service_id="intuitive_guidance", name="Savauna's Holistic Intuitive Guidance & Support", description="Personalized reflection and guidance throughout the experience."),
                CoreExperience(service_id="wellness_blueprint", name="Personalized Wellness Blueprint", description="A practical, personalized guide for continuing the experience after your visit."),
            ]
            if package_id in {"executive_reset", "peak_performance_pivot"}
            else []
        ),
        pricing_breakdown=PricingBreakdown(
            pricing_basis=("per_person" if policy.get("pricing_scope") == "per_person" else str(policy["pricing_type"])),
            guest_count=request.group_size,
            duration_days=duration_days,
            package_base_subtotal=base_quote.package_subtotal,
            included_service_days=base_quote.included_service_days,
            additional_service_days=base_quote.additional_service_days,
            additional_day_rate_per_person=base_quote.additional_day_rate_per_person,
            extended_program_subtotal=base_quote.extended_program_subtotal,
            addon_subtotal=base_quote.addon_subtotal,
            discount=base_quote.discount,
            order_total=base_quote.order_total,
        ),
        wellness_insights=build_wellness_insights(request),
        payment_choices=choices,
        alternatives=alternative_packages(request, package_id, request.duration_days),
        price_summary=price_summary,
        call_to_action=copy["cta"],
        consultation_available=True,
        wellness_disclaimer=(
            "These recommendations support general wellbeing and enjoyment. "
            "They are not medical advice, diagnosis or treatment."
        ),
    )
