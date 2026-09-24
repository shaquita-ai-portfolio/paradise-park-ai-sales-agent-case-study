# Paradise Park Sales Agent v6.3

## Outcome

v6.3 strengthens the MVP conversion path while preserving deterministic pricing, server-side checkout recomputation and Gemini grounding.

## Implemented changes

- Checkout now appears before secondary packages and Wholistic Living Reflections.
- Two or more approved deep-support signals can elevate Executive Reset as the primary recommendation even when it exceeds the selected investment target.
- The API labels the recommendation strategy as `within_target` or `upsell`.
- Individual recommendations return one budget-aligned secondary path instead of a competing collection of offers.
- The repetitive priority list is replaced by a safe personalized narrative and no more than three fit signals.
- Executive Reset and Peak Performance Pivot explicitly include the Pre-Glow Program.
- Multi-day agendas render as separate Day 1, Day 2 and Day 3 itinerary sections.
- Overnight Stay is renamed Cabin Only Overnight Stay; Venue Rental is removed.
- Thanksgiving week, December 22–28 and December 29–January 7 are blocked.
- Checkout requires acknowledgment of the non-refundable payment policy.
- Square uses Order Checkout data with package, event-date, payment and reference context.
- Ambassador questions are grounded to the direct contact action.
- Express hospitality language now emphasizes intentional wellness micro-experiences.
- The results page uses an invitation-style ivory, olive and champagne-gold visual hierarchy.

## Architecture learning insights for Shaquita

1. Recommendation strategy is a governed domain decision. Python decides whether an offer is within target or an upsell; Gemini explains approved facts.
2. Conversion order is part of system architecture. The API contract and page composition must agree on primary and secondary offers.
3. Holiday availability belongs in deterministic validation, not prompt instructions.
4. Square receives an order identity while Paradise Park remains the source of truth for the detailed itinerary.
5. AI failure must not break a sale. The personalized recommendation contract has deterministic, wellness-safe copy that can later be enhanced by a non-blocking Gemini writer.
6. A deployed Cloud Run service is stable while each release is a reversible revision.

## Validation

- 168 automated tests passed.
- JavaScript syntax validation passed.
- JSON catalog and package-policy validation passed.
- One existing Starlette test-client deprecation warning remains non-blocking.
