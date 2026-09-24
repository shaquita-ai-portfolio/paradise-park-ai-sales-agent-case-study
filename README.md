# Paradise Park Prescriptive Sales Agent

A deterministic, profit-aware wellness experience planner for Paradise Park Atlanta. The MVP collects a short guest assessment, selects an approved package, curates a guest-safe agenda across Paradise Park's three pathways, prepares a holistic living reflection, and offers a server-calculated Square checkout choice.

## What is controlled by code

- Package eligibility, minimum group sizes and service entitlements
- Included versus separately priced services
- Second- and fourth-week scheduling rules
- Package totals, deposits and pay-in-full discounts
- Express calendar routing and Square checkout amounts
- Wellness safety language and ambassador review routing

The future Gemini layer may explain approved results warmly, but it must not invent prices, entitlements, availability or wellness claims.

## Local setup

```bash
uv sync
cp .env.example .env
uv run pytest -q
uv run uvicorn paradise_park_sales_agent.api:app --reload
```

Open `http://127.0.0.1:8000`.

## Environment configuration

Populate `.env` with Square sandbox credentials and the real HTTPS links for the Express Reset calendar and Wellness Ambassador consultation. Never commit `.env`.

## Staging deployment

The repository includes a non-root Cloud Run container, secret-safe ignore rules and a detailed staging runbook. Follow `deploy/CLOUD_RUN_STAGING.md` to deploy with Square Sandbox before connecting the Wix site.

## Production sequence

1. Deploy the current release to Cloud Run staging with Square Sandbox.
2. Complete and document every acceptance journey and payment calculation.
3. Add trace persistence, audit logging and evaluation datasets.
4. Add the bounded Gemini explanation layer and approved-content retrieval.
5. Connect Wix to the approved Cloud Run revision.
6. Complete the production-payment gate before enabling live Square credentials.
