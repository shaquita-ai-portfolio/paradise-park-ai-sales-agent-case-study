# Paradise Park Cloud Run staging deployment

This deployment intentionally uses Square Sandbox. Do not switch to production credentials until every acceptance scenario has passed and Savauna has approved the displayed prices, inclusions and policies.

## 1. Confirm the project and region

Run these commands from the repository root:

```bash
gcloud config get-value project
gcloud config set run/region us-east1
gcloud auth list
```

`us-east1` is the selected development region for the Atlanta-based project.

## 2. Enable the required Google Cloud services

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

## 3. Prepare the non-secret staging configuration

```bash
cp deploy/cloudrun.staging.env.yaml.example deploy/cloudrun.staging.env.yaml
```

Open `deploy/cloudrun.staging.env.yaml` in VS Code. Replace the Square Sandbox location ID and replace the temporary Paradise Park links when the exact calendar, consultation and shop URLs are available.

The real staging file is ignored by Git. Never place the Square access token in this file.

## 4. Store the Square Sandbox access token securely

Create a dedicated runtime service account:

```bash
PROJECT_ID="$(gcloud config get-value project)"
SERVICE_ACCOUNT_NAME="recruiter-app-runtime"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts describe "$SERVICE_ACCOUNT" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Paradise Park sales agent runtime"
```

Enter the Sandbox token without displaying it on screen or storing it in shell history:

```bash
read -s "SQUARE_TOKEN?Square Sandbox access token: "
echo

if gcloud secrets describe ppk-square-sandbox-access-token >/dev/null 2>&1; then
  printf %s "$SQUARE_TOKEN" | \
    gcloud secrets versions add ppk-square-sandbox-access-token --data-file=-
else
  printf %s "$SQUARE_TOKEN" | \
    gcloud secrets create ppk-square-sandbox-access-token \
      --replication-policy=automatic \
      --data-file=-
fi

unset SQUARE_TOKEN
```

Allow only the runtime service account to read this secret:

```bash
gcloud secrets add-iam-policy-binding ppk-square-sandbox-access-token \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## 5. Run the release checks

```bash
uv sync
uv run pytest -q
```

Do not deploy unless the complete suite passes.

## 6. Deploy the public staging service

```bash
gcloud run deploy paradise-park-sales-agent-staging \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --service-account "$SERVICE_ACCOUNT" \
  --env-vars-file deploy/cloudrun.staging.env.yaml \
  --set-secrets SQUARE_ACCESS_TOKEN=ppk-square-sandbox-access-token:latest \
  --min-instances 0 \
  --max-instances 3 \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 20 \
  --timeout 60
```

Cloud Run prints a public HTTPS service URL when the deployment completes.

## 7. Verify the deployed application

```bash
SERVICE_URL="$(gcloud run services describe paradise-park-sales-agent-staging \
  --region us-east1 \
  --format='value(status.url)')"

echo "$SERVICE_URL"
curl -fsS "${SERVICE_URL}/health"
```

Open the printed URL in a private browser window and complete these journeys:

1. Express Reset routes to the wellness-session calendar and does not create a Square payment link.
2. Rapid Reset produces correct pay-in-full and deposit totals plus an optional private-service upsell.
3. A two-day group quote multiplies the per-person, per-day amount by both guest count and duration.
4. An overnight request displays the Grand Cabin link in a new window.
5. A product option does not block the retreat checkout.
6. Square opens in Sandbox and charges the exact server-calculated amount.

## 8. Review logs and roll back safely

View recent application logs:

```bash
gcloud run services logs read paradise-park-sales-agent-staging \
  --region us-east1 \
  --limit 100
```

List revisions:

```bash
gcloud run revisions list \
  --service paradise-park-sales-agent-staging \
  --region us-east1
```

If a new revision fails acceptance testing, route all traffic back to the last approved revision:

```bash
gcloud run services update-traffic paradise-park-sales-agent-staging \
  --region us-east1 \
  --to-revisions APPROVED_REVISION_NAME=100
```

## Production gate

Do not use a live Square token yet. Production activation requires a final pricing review, refund/cancellation language, privacy notice, webhook validation, a successful low-dollar live transaction and explicit approval from the Paradise Park business owner.
