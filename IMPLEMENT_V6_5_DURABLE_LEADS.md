# Paradise Park v6.5 — Durable Lead Capture

## Outcome

Every assessment stage is saved in Firestore before an admin email is
attempted. Gmail or another provider can fail without losing the guest record.
Only contacts with explicit marketing consent can be exported for Wix.

## Data lifecycle

1. `/v1/leads/capture` creates or merges an `assessment_started` record.
2. `/v1/recommendations` adds the recommendation and consent selections.
3. `/v1/checkout` adds checkout-started details.
4. Admin email runs in the background and records `sent` or `failed`.
5. The private export script queries only `marketing_consent == true`.

Firestore collection: `sales_leads`.

## 1. Test locally

```bash
uv sync
uv run pytest -q
```

Expected baseline for this package: `175 passed` with one existing Starlette
deprecation warning.

Local development leaves durable storage off:

```text
LEAD_STORAGE_ENABLED=false
```

## 2. Create or confirm Firestore

List databases before creating anything:

```bash
gcloud firestore databases list --project="example-project-id"
```

If `(default)` already exists, do not create another database. If none exists,
create a Standard Firestore Native database in the Google Cloud console using
restrictive security rules and an approved United States location. Database
location is difficult to change later, so confirm it before creation.

## 3. Grant the Cloud Run identity least-privilege data access

```bash
export PP_PROJECT_ID="example-project-id"
export PP_REGION="us-east1"
export PP_SERVICE="paradise-park-sales-agent"
export PP_SERVICE_ACCOUNT="recruiter-app-runtime@example-project-id.iam.gserviceaccount.com"
```

```bash
gcloud projects add-iam-policy-binding "$PP_PROJECT_ID" \
  --member="serviceAccount:${PP_SERVICE_ACCOUNT}" \
  --role="roles/datastore.user"
```

This role permits the runtime to read and write lead documents. Do not grant
Owner or Editor to the runtime service account.

## 4. Add production environment variables

Add these non-secret settings to `deploy/cloudrun.production.env.yaml`:

```yaml
LEAD_STORAGE_ENABLED: "true"
FIRESTORE_DATABASE: "(default)"
FIRESTORE_LEADS_COLLECTION: "sales_leads"
```

Keep SMTP and Square credentials in Secret Manager. Never place them in YAML.

## 5. Deploy a no-traffic v6.5 revision

Use the same tested production deployment process and secret bindings, with a
new unique suffix. Do not reuse an old revision name.

```bash
export PP_V65_SUFFIX="v6-5-leads-$(date +%Y%m%d-%H%M%S)"
```

```bash
gcloud run deploy "$PP_SERVICE" \
  --project "$PP_PROJECT_ID" \
  --region "$PP_REGION" \
  --source . \
  --service-account "$PP_SERVICE_ACCOUNT" \
  --env-vars-file deploy/cloudrun.production.env.yaml \
  --set-secrets SQUARE_ACCESS_TOKEN=example-square-access-token-secret:latest,SMTP_PASSWORD=example-smtp-app-password-secret:3 \
  --revision-suffix "$PP_V65_SUFFIX" \
  --tag v6-5-test \
  --no-traffic
```

## 6. Acceptance test

Open the `v6-5-test` tagged URL. Submit a test contact and recommendation.
Confirm:

- `/health` reports `lead_storage: enabled`.
- A document appears in Firestore collection `sales_leads`.
- The document contains the same Lead ID across lifecycle stages.
- Marketing consent matches the guest's selection.
- Email status becomes `sent` or `failed`.
- If SMTP is deliberately unavailable, the lead remains stored.
- Square totals and checkout behavior are unchanged.

Do not enter real medical details during testing.

## 7. Export consented contacts for Wix

Authenticate your local CLI without downloading a service-account key:

```bash
gcloud auth application-default login
```

Run from the project root:

```bash
uv run python scripts/export_marketing_contacts.py \
  --project="example-project-id" \
  --output="$HOME/Downloads/paradise-park-wix-consented-contacts.csv"
```

The CSV includes only name, email, phone, referral source, recommendation,
created date and explicit consent. It excludes wellness priorities and the
personal recommendation narrative.

Review the CSV before importing it into Wix Contacts. In Wix, mark the imported
rows as subscribers only because this export already requires explicit consent.

## 8. Promote or roll back

After acceptance, point the existing Wix tag to the exact tested revision.
Record the previous revision first. If any problem appears, return the Wix tag
to that previous revision; Firestore records remain available independently.

## Scope boundary

This release makes lead capture durable and exportable. The following should be
the next release:

- Cloud Tasks or Pub/Sub for durable notification retries.
- Transactional email provider instead of personal Gmail SMTP.
- Square webhook for confirmed payment status.
- Direct, consent-aware Wix Contacts synchronization.
- Protected internal lead dashboard and audit logs.
