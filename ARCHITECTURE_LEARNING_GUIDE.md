# Paradise Park Sales Agent — Architecture Learning Guide

This release is designed as both a working sales system and an AI architecture
portfolio project for Shaquita Graham.

## 1. Establish the control baseline

The original 148 tests were run before changes. This creates a known-good
control, similar to establishing a baseline dataset before an AI evaluation.
An architect should be able to distinguish a new regression from an old defect.

## 2. Separate commercial authority from generative language

`commercial_policy.py` owns prices, per-person scope, discounts, add-ons and
extended-day charges. Gemini may explain a quote but cannot calculate or alter
it. This is the deterministic-core / probabilistic-edge design pattern.

## 3. Model price components instead of one opaque total

`PaymentQuote` preserves the package base, extended-program subtotal, add-ons,
fees and discount as separate values. This produces auditability and prevents
the 10% package discount from accidentally affecting $1,200 extension days.

## 4. Treat itinerary creation as constrained orchestration

Executive Reset and Peak Performance Pivot are built day by day. Each day has
three low-overhead services and two one-on-one services. The planner rotates
services while allowing clinically neutral, business-approved repeats. This is
a constraint-satisfaction problem, not a free-form text-generation problem.

## 5. Use the catalog as approved grounding

The service catalog provides guest descriptions, approved benefits, FAQ cues,
eligibility and blocked claims. The same source feeds the planner, API and
Gemini knowledge layer. This is a lightweight form of retrieval grounding and
prevents competing versions of business truth.

## 6. Layer safety controls

The Gemini instruction limits the model to retrieved sources. Deterministic
regex guardrails separately block medical-outcome claims such as treating
infertility, regulating hormones or treating trauma. Layered controls are more
reliable than relying on a prompt alone.

## 7. Recompute at the payment trust boundary

The browser submits selections, but the API rebuilds the recommendation and
quote before generating a Square payment link. Client-supplied totals are never
trusted. This is both an application-security control and an AI guardrail.

## 8. Design the response as a stable contract

The API returns typed core experiences, daily agenda items and a structured
pricing breakdown. The frontend renders the contract instead of parsing prose.
Typed contracts make Gemini, frontend and payment integrations independently
replaceable.

## 9. Make the AI layer gracefully degradable

The deterministic recommendation and checkout logic do not require Gemini to
be correct. If the model is unavailable, the system can still return a safe,
priced recommendation. Enterprise AI systems should fail soft around the model
and fail closed around money, permissions and unsafe claims.

## 10. Treat visual design as part of system trust

The invitation-style interface uses gold accents, restrained motion, visible
focus states, high-contrast controls and a subtle Paradise Park image. Elegant
presentation improves conversion, while accessibility and transparent pricing
preserve trust.

## Architecture summary

1. Assessment UI collects explicit guest intent.
2. FastAPI validates the typed request.
3. Policy code determines eligible pricing and payment choices.
4. The itinerary planner enforces daily entitlements and rotation.
5. Catalog retrieval supplies approved service knowledge.
6. Gemini explains grounded information in the Paradise Park voice.
7. Output guardrails inspect generated language.
8. The API returns a typed recommendation contract.
9. Square receives a server-recomputed checkout amount.
10. Trace IDs and tests make the full decision path auditable.

