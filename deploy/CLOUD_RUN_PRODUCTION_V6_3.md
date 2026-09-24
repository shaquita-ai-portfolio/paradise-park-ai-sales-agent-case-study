# Deploy v6.3 beside the approved v6.2 revision

## 1. Restore local production configuration

The release ZIP excludes secrets and `deploy/cloudrun.production.env.yaml`. Copy the working production YAML and `.env` from v6.2 into the unzipped v6.3 folder. Never commit or upload either file.

## 2. Validate

```bash
cd "$HOME/Downloads/paradise-park-sales-agent-v6.3"
uv sync
uv run pytest -q
node --check static/app.js
```

Expected: 168 tests pass.

## 3. Restore deployment variables

```bash
PP_PROJECT_ID="example-project-id"
PP_SERVICE_ACCOUNT_NAME="recruiter-app-runtime"
PP_SERVICE_ACCOUNT="${PP_SERVICE_ACCOUNT_NAME}@${PP_PROJECT_ID}.iam.gserviceaccount.com"
```

## 4. Deploy a new revision to the same service

```bash
gcloud run deploy paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --service-account "$PP_SERVICE_ACCOUNT" \
  --env-vars-file deploy/cloudrun.production.env.yaml \
  --set-secrets SQUARE_ACCESS_TOKEN=example-square-access-token-secret:latest \
  --revision-suffix v6-3 \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 20 \
  --timeout 60 \
  --no-traffic
```

`--no-traffic` protects the working production experience while v6.3 is inspected.

## 5. Identify the tagged revision URL

```bash
gcloud run revisions list \
  --service paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --region us-east1
```

Tag the new revision for acceptance testing:

```bash
V63_REVISION="$(gcloud run revisions list \
  --service paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --region us-east1 \
  --filter='metadata.name~v6-3' \
  --sort-by='~metadata.creationTimestamp' \
  --limit=1 \
  --format='value(metadata.name)')"

gcloud run services update-traffic paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --region us-east1 \
  --update-tags "v6-3=${V63_REVISION}"
```

Retrieve the tag URL from Cloud Run and test it without changing the Wix link.

## 6. Acceptance test

- Confirm v6.2 still serves production traffic.
- Confirm the v6.3 tag returns `/health` as healthy.
- Test a low-budget guest with two deep-support signals: Executive should be primary and Express or Rapid secondary after checkout.
- Test a two-day Executive agenda: Day 1 and Day 2 must render separately.
- Confirm the non-refundable checkbox blocks checkout until accepted.
- Open Square and confirm package, date and payment type are recognizable before paying.
- Confirm Venue Rental never appears and Cabin Only opens the approved cabin URL.
- Confirm holiday dates are rejected.
- Test Gemini and the Wellness Ambassador action.

## 7. Promote only after approval

```bash
gcloud run services update-traffic paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --region us-east1 \
  --to-latest
```

The stable Cloud Run URL and Wix link do not change.

## 8. Roll back if necessary

Find the approved v6.2 revision name and run:

```bash
gcloud run services update-traffic paradise-park-sales-agent \
  --project "$PP_PROJECT_ID" \
  --region us-east1 \
  --to-revisions APPROVED_V6_2_REVISION=100
```
