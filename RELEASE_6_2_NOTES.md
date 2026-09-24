# Paradise Park Sales Agent v6.2

## Customer-facing corrections

- Deposit checkout now states that the remaining balance is due 14 days before the event date.
- Square payment choices use distinct gold borders, spacing and shadow so each option reads as a separate selection.
- “Explore natural products” opens the approved Pamper Collection Square link.
- Every Wellness Ambassador action opens the approved Paradise Park contact page.
- Gemini retrieval now contains an approved Rapid Reset versus Executive Reset comparison.

## Architecture learning insights for Shaquita

1. **Generate copy from policy.** The 14-day sentence is built from the same policy value used by the commercial rules. This prevents the interface and checkout logic from communicating different obligations.
2. **Ground the agent; do not loosen it.** Gemini previously declined the comparison because the approved knowledge did not contain enough detail. Adding the comparison to governed package data preserves the safety boundary while making the answer useful.
3. **Version approved destinations.** Product and Ambassador links are application constants because they are public commercial destinations, not secrets. This prevents an old local `.env` file from silently routing a guest to an outdated page.
4. **Use visual boundaries to clarify decisions.** The gold border and spacing make each payment choice independently scannable. Elegant design is also interaction architecture: it reduces selection errors while supporting the invitation aesthetic.
5. **Test promises at their source.** Contract tests now verify the balance language, public destinations, Gemini knowledge and payment-card styling. An AI architect treats language, links and presentation as testable system behavior.

## Validation

- Full automated test suite: 160 passed.
- Square remains configured for Sandbox validation before production deployment.
