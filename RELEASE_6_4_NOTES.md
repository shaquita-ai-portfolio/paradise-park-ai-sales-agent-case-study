# Paradise Park Sales Agent v6.4

## Guest experience updates

- Collects name, email, phone, referral source and optional Instagram handle.
- Removes Cabin Only and Venue Rental from the planner; only Personal Reset and Group Retreat remain.
- Sets the group-retreat minimum to six guests in both the browser and API contract.
- Displays the floating AI Concierge invitation above the fold on desktop and as a mobile action pill.
- Shows enhancement choices only for likely one-day Express/Rapid paths.
- Requires the guest to add selected enhancements to the cart before they enter the quote.
- Does not automatically add a paid private service to Rapid Reset.
- Prevents Express/Rapid-only cart selections from increasing an Executive or Peak quote.

## Lead recovery and reporting

The browser creates one lead ID for the assessment session. The API can send:

1. Assessment-started report after valid contact information is submitted.
2. Recommendation-completed report with the package, priorities, rationale and quote.
3. Checkout-started report with the payment option and server-calculated amount.

All reports default to `notifications@example.com`. Email delivery is non-blocking:
an SMTP failure does not prevent a guest from receiving a recommendation or checkout link.

## Important payment distinction

"Checkout started" means Square created a payment link. It does not prove payment was
completed. A future Square `payment.updated` webhook should produce the authoritative
paid/failed/cancelled status and connect it to the lead and trace identifiers.

## Required production configuration

Add these non-secret values to `deploy/cloudrun.production.env.yaml`:

```yaml
ADMIN_NOTIFICATION_EMAIL: "notifications@example.com"
SMTP_HOST: "smtp.gmail.com"
SMTP_PORT: "465"
SMTP_USERNAME: "notifications@example.com"
SMTP_FROM_EMAIL: "notifications@example.com"
```

Store the Google app password in Secret Manager as
`example-smtp-app-password-secret`; never place it in YAML, `.env.example`, Git or a ZIP.

## Verification

```bash
uv sync
uv run pytest -q
node --check static/app.js
```

Expected baseline: `170 passed` with the existing non-blocking Starlette warning.
