# Paradise Park Sales Agent — MVP v3

## What this release guarantees

- Package eligibility, minimum group sizes, service caps, multi-day quantities,
  discounts and Square amounts are calculated in Python—not by the browser or
  an LLM.
- A 12-person, two-day `$375/person/day` group retreat totals `$9,000`.
- The `$874/person/day` immersive group offer is identified as conditional when
  the group has fewer than 15 guests.
- An overnight request cannot be reduced to Express Reset.
- Express Reset uses the external Express wellness-session calendar.
- Pamper Collection and Soil to Soul interest never blocks retreat checkout.
  Products open in a separate tab for this MVP and are not silently included in
  the Square retreat total.
- The Paradise Park questions/chat site opens in a new tab from both the page
  header and recommendation report.
- Pay-in-full saves 10% on the package base; a deposit preserves the undiscounted
  order total.

## Required environment values

Copy `.env.example` to `.env` and replace placeholders with actual HTTPS URLs
and Square sandbox credentials:

```text
EXPRESS_RESET_CALENDAR_URL=https://...
WELLNESS_CONSULT_URL=https://...
PRODUCT_SHOP_URL=https://paradiseislife.biz/...
QUESTIONS_URL=https://paradiseislife.biz
```

Never commit `.env`.

## Local validation

```bash
uv sync
uv run pytest -q
uv run uvicorn paradise_park_sales_agent.api:app --reload
```

Open `http://127.0.0.1:8000/?version=8`.

## Acceptance scenarios

1. **Express:** one guest, one day, budget below `$500`. Confirm one core
   activation and the external wellness-session calendar.
2. **Rapid:** one guest, budget `$501–$1,800`. Confirm four included group/low-
   overhead activations and one separately priced private upsell.
3. **Overnight protection:** one guest selects overnight with a low budget.
   Confirm the primary recommendation is Executive Reset, not Express.
4. **Group multi-day:** 12 guests and two days. Confirm base subtotal `$9,000`,
   pay-in-full `$8,100`, deposit `$4,500`, and `$4,500` remaining.
5. **Conditional immersive tier:** 12 guests. Confirm the `$874/person/day`
   option explains that 15 guests are required.
6. **Product interest:** choose Pamper Collection or Soil to Soul. Confirm
   retreat checkout still works and the product link opens separately.
7. **Questions:** confirm the Wellness Ambassador link opens Paradise Park in a
   new tab without losing the assessment.

## AI boundary for the next release

Gemini should receive only server-approved Good/Better/Best candidates plus
grounded Savauna-authored knowledge. It may summarize guest needs, rank valid
offers and write warm explanations. It must not invent packages, change prices,
ignore minimums, add free services or submit a Square amount. The server must
revalidate the selected offer before checkout.

## Remaining production gates

- Replace every placeholder URL and verify Square sandbox end to end.
- Add Square webhook signature verification and idempotent order fulfillment.
- Persist assessment, quote, order, payment and trace status in a database.
- Add authentication for staff-only views, Secret Manager and production CORS.
- Add observability, alerting, rate limits, abuse controls and privacy/retention
  policy.
- Add real product variants and prices to Square before combining products with
  retreat checkout. Until then, the separate product-shop link is intentional.
- Deploy to Cloud Run staging, run acceptance tests, then promote to production.

