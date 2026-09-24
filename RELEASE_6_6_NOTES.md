# Paradise Park Sales Agent v6.6

## Outcome

This release makes the sales path investment-first, preserves the existing
durable lead and email-notification behavior, and adds conversion telemetry.
The permanent Cloud Run service URL remains:

`https://paradise-park-sales-agent-https://example-ai-sales-agent.run.app-ue.a.run.app/`

Do not replace this URL in Wix when deploying a new revision. Cloud Run moves
the service URL to whichever verified revision receives production traffic.

## Customer-facing changes

- Personal investment targets of $500 or less recommend Express Reset.
- Personal targets above $500 and below $1,800 recommend Rapid Reset.
- Personal targets from $1,800 recommend Executive Reset unless the guest
  qualifies for the $9,987 three-day Peak Performance Pivot.
- Six or more guests are always evaluated against approved group tiers.
- Express Reset links directly to the configured Express calendar. It does not
  use the in-app enhancement cart or custom Square checkout.
- Rapid Reset remains the only package with the in-app paid-enhancement cart.
- The secondary option appears directly below the primary recommendation.
- Guests can report checkout readiness, their main barrier, helpfulness and an
  optional comment without interrupting checkout.

## New Firestore collections

When `TELEMETRY_STORAGE_ENABLED` is true, the application creates these
collections automatically after the first matching event:

- `conversion_feedback`: one merged feedback record per lead.
- `ai_concierge_interactions`: one document for each question, including the
  outcome, answer, grounding source IDs and latency.

The guest journey is fail-open: a Firestore telemetry problem is logged but
does not block recommendations, concierge answers or checkout.

Add these non-secret values to `deploy/cloudrun.production.env.yaml`:

```yaml
LEAD_STORAGE_ENABLED: "true"
FIRESTORE_DATABASE: "default"
FIRESTORE_LEADS_COLLECTION: "sales_leads"
TELEMETRY_STORAGE_ENABLED: "true"
FIRESTORE_CONCIERGE_COLLECTION: "ai_concierge_interactions"
FIRESTORE_CONVERSION_COLLECTION: "conversion_feedback"
```

## Safe production deployment

Run these commands from the v6.6 project folder. They create a no-traffic
revision first and keep the existing production revision live.

```bash
export PP_PROJECT_ID="example-project-id"
export PP_REGION="us-east1"
export PP_SERVICE="paradise-park-sales-agent"
export PP_SERVICE_ACCOUNT="recruiter-app-runtime@example-project-id.iam.gserviceaccount.com"
export PP_REVISION_SUFFIX="v66-$(date +%m%d-%H%M%S)"

uv sync
uv run pytest -q

gcloud run deploy "$PP_SERVICE" \
  --project="$PP_PROJECT_ID" \
  --region="$PP_REGION" \
  --source=. \
  --service-account="$PP_SERVICE_ACCOUNT" \
  --env-vars-file=deploy/cloudrun.production.env.yaml \
  --set-secrets=SQUARE_ACCESS_TOKEN=example-square-access-token-secret:latest,SMTP_PASSWORD=example-smtp-app-password-secret:latest \
  --revision-suffix="$PP_REVISION_SUFFIX" \
  --no-traffic
```

Find the new revision and give it a test tag:

```bash
export PP_V66_REVISION="$(
  gcloud run revisions list \
    --service="$PP_SERVICE" \
    --project="$PP_PROJECT_ID" \
    --region="$PP_REGION" \
    --sort-by='~metadata.creationTimestamp' \
    --limit=1 \
    --format='value(metadata.name)'
)"

gcloud run services update-traffic "$PP_SERVICE" \
  --project="$PP_PROJECT_ID" \
  --region="$PP_REGION" \
  --update-tags="v6-6-test=$PP_V66_REVISION"

export PP_V66_TEST_URL="$(
  gcloud run services describe "$PP_SERVICE" \
    --project="$PP_PROJECT_ID" \
    --region="$PP_REGION" \
    --format=json | uv run python -c '
import json, sys
service = json.load(sys.stdin)
print(next(item["url"] for item in service["status"]["traffic"] if item.get("tag") == "v6-6-test"))
'
)"

printf 'Test URL: %s\n' "$PP_V66_TEST_URL"
curl -s "$PP_V66_TEST_URL/health"
```

In the test URL, verify all of the following before moving traffic:

1. One guest at $499 receives Express Reset and a working calendar link.
2. One guest at $1,200 receives Rapid Reset and can add an enhancement.
3. One guest at $1,800 receives Executive Reset and Square checkout opens.
4. Six guests receive a group package, never an individual package.
5. A readiness response creates a `conversion_feedback` document.
6. A concierge question creates an `ai_concierge_interactions` document.
7. A normal assessment still creates or updates `sales_leads` and sends the
   admin email.

Then move only 10% of the stable service URL to v6.6:

```bash
export PP_CURRENT_REVISION="$(
  gcloud run services describe "$PP_SERVICE" \
    --project="$PP_PROJECT_ID" \
    --region="$PP_REGION" \
    --format=json | uv run python -c '
import json, sys
service = json.load(sys.stdin)
print(next(item["revisionName"] for item in service["status"]["traffic"] if item.get("percent") == 100))
'
)"

gcloud run services update-traffic "$PP_SERVICE" \
  --project="$PP_PROJECT_ID" \
  --region="$PP_REGION" \
  --to-revisions="$PP_V66_REVISION=10,$PP_CURRENT_REVISION=90"
```

After a live assessment, checkout-link test, Firestore check and log review,
move 100% to v6.6:

```bash
gcloud run services update-traffic "$PP_SERVICE" \
  --project="$PP_PROJECT_ID" \
  --region="$PP_REGION" \
  --to-revisions="$PP_V66_REVISION=100"

gcloud run services describe "$PP_SERVICE" \
  --project="$PP_PROJECT_ID" \
  --region="$PP_REGION" \
  --format="yaml(status.url,status.latestReadyRevisionName,status.traffic)"
```

The displayed `status.url` should remain the permanent address already used by
Wix. If production verification fails, route 100% back to the saved
`$PP_CURRENT_REVISION`.
