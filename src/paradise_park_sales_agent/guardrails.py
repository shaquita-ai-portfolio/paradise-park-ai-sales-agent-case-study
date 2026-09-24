from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


FORBIDDEN_GUEST_FIELDS = {
    "internal_cost",
    "internal_name",
    "overhead_tier",
}

UNSAFE_OUTPUT_PATTERNS = {
    "diagnosis_claim": re.compile(
        r"\byou (?:have|suffer from|are suffering from)\b",
        re.IGNORECASE,
    ),
    "treatment_claim": re.compile(
        r"\b(?:cures?|treats?|heals?)\b",
        re.IGNORECASE,
    ),
    "guaranteed_result": re.compile(
        r"\b(?:guaranteed results?|guarantees? results?)\b",
        re.IGNORECASE,
    ),
    "toxin_claim": re.compile(
        r"\b(?:removes?|flushes?) toxins?\b|"
        r"\byour body is toxic\b",
        re.IGNORECASE,
    ),
    "blood_pressure_claim": re.compile(
        r"\b(?:lowers?|reduces?|regulates?) "
        r"(?:your )?blood pressure\b",
        re.IGNORECASE,
    ),
    "trauma_treatment_claim": re.compile(
        r"\b(?:heals?|treats?|releases?) trauma\b",
        re.IGNORECASE,
    ),
    "fertility_treatment_claim": re.compile(
        r"\b(?:treats?|address(?:es)?|cures?) (?:in)?fertility\b|"
        r"\b(?:improves?|restores?|guarantees?) fertility\b",
        re.IGNORECASE,
    ),
    "hormone_regulation_claim": re.compile(
        r"\b(?:balances?|regulates?|fixes?) (?:your )?hormones?\b",
        re.IGNORECASE,
    ),
}

CRISIS_PATTERNS = {
    "self_harm_language": re.compile(
        r"\bself[- ]?harm\b|\bharm myself\b",
        re.IGNORECASE,
    ),
    "suicide_language": re.compile(
        r"\bsuicid(?:e|al)\b|\bkill myself\b",
        re.IGNORECASE,
    ),
}

HUMAN_REVIEW_PATTERNS = {
    "pregnancy_or_postpartum": re.compile(
        r"\bpregnan(?:t|cy)\b|\bpostpartum\b.{0,30}\b"
        r"(?:complication|bleeding|pain|depression|injury|medical)\b",
        re.IGNORECASE,
    ),
    "fertility_treatment": re.compile(
        r"\bfertility treatment\b|\bivf\b",
        re.IGNORECASE,
    ),
    "injury_or_contraindication": re.compile(
        r"\binjur(?:y|ed)\b|\bcontraindication\b",
        re.IGNORECASE,
    ),
    "diagnosis_request": re.compile(
        r"\bdiagnos(?:e|is|ed)\b",
        re.IGNORECASE,
    ),
    "treatment_request": re.compile(
        r"\b(?:cure|treat) my\b",
        re.IGNORECASE,
    ),
}


class GuardrailDecision(BaseModel):
    """Result returned by a deterministic guardrail check."""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    requires_human_review: bool = False
    reasons: list[str] = Field(default_factory=list)
    matched_text: list[str] = Field(default_factory=list)


class GuardrailViolation(ValueError):
    """Raised when content cannot continue automatically."""


def find_pattern_matches(
    text: str,
    patterns: Mapping[str, re.Pattern[str]],
) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    matched_text: list[str] = []

    for reason, pattern in patterns.items():
        match = pattern.search(text)

        if match:
            reasons.append(reason)
            matched_text.append(match.group(0))

    return reasons, matched_text


def iter_field_names(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            yield str(key)
            yield from iter_field_names(nested_value)

    elif isinstance(value, list | tuple):
        for item in value:
            yield from iter_field_names(item)


def iter_text_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value

    elif isinstance(value, Mapping):
        for nested_value in value.values():
            yield from iter_text_values(nested_value)

    elif isinstance(value, list | tuple):
        for item in value:
            yield from iter_text_values(item)


def evaluate_request_text(text: str) -> GuardrailDecision:
    """Determine whether assessment text can continue automatically."""

    crisis_reasons, crisis_matches = find_pattern_matches(
        text,
        CRISIS_PATTERNS,
    )

    review_reasons, review_matches = find_pattern_matches(
        text,
        HUMAN_REVIEW_PATTERNS,
    )

    reasons = crisis_reasons + review_reasons
    matches = crisis_matches + review_matches

    return GuardrailDecision(
        allowed=not reasons,
        requires_human_review=bool(reasons),
        reasons=reasons,
        matched_text=matches,
    )


def evaluate_generated_text(text: str) -> GuardrailDecision:
    """Check Gemini or template-generated guest language."""

    reasons, matches = find_pattern_matches(
        text,
        UNSAFE_OUTPUT_PATTERNS,
    )

    return GuardrailDecision(
        allowed=not reasons,
        requires_human_review=bool(reasons),
        reasons=reasons,
        matched_text=matches,
    )


def evaluate_guest_payload(
    payload: BaseModel | Mapping[str, Any],
) -> GuardrailDecision:
    """Check a complete recommendation before returning it to a guest."""

    if isinstance(payload, BaseModel):
        data = payload.model_dump()
    else:
        data = dict(payload)

    field_names = set(iter_field_names(data))
    exposed_fields = sorted(
        field_names.intersection(FORBIDDEN_GUEST_FIELDS)
    )

    reasons: list[str] = []
    matches: list[str] = []

    if exposed_fields:
        reasons.append("internal_field_exposure")
        matches.extend(exposed_fields)

    combined_text = "\n".join(iter_text_values(data))

    text_reasons, text_matches = find_pattern_matches(
        combined_text,
        UNSAFE_OUTPUT_PATTERNS,
    )

    reasons.extend(text_reasons)
    matches.extend(text_matches)

    return GuardrailDecision(
        allowed=not reasons,
        requires_human_review=bool(reasons),
        reasons=reasons,
        matched_text=matches,
    )


def assert_guest_safe(
    payload: BaseModel | Mapping[str, Any],
) -> None:
    """Raise an exception if a payload fails guest-safety checks."""

    decision = evaluate_guest_payload(payload)

    if not decision.allowed:
        joined_reasons = ", ".join(decision.reasons)

        raise GuardrailViolation(
            f"Guest payload failed guardrails: {joined_reasons}"
        )

    
