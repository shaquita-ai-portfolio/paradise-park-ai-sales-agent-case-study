# Cloud Run production update — v6.4

## 1. Create the email credential

Use the Google account that sends the notifications. Turn on two-step verification,
then create a Google app password for `Paradise Park Sales Agent`. Copy the generated
password without spaces.

If App Passwords is unavailable, the Google Workspace administrator must allow it or
the project should use an approved transactional email provider instead.

## 2. Store the password

```bash
printf '%s' 'PASTE_APP_PASSWORD_HERE' | gcloud secrets create \
  example-smtp-app-password-secret \
  --project "$PP_PROJECT_ID" \
  --replication-policy automatic \
  --data-file -
```

If the secret already exists, add a version:

```bash
printf '%s' 'PASTE_APP_PASSWORD_HERE' | gcloud secrets versions add \
  example-smtp-app-password-secret \
  --project "$PP_PROJECT_ID" \
  --data-file -
```

Grant the runtime service account read access:

```bash
gcloud secrets add-iam-policy-binding \
  example-smtp-app-password-secret \
  --project "$PP_PROJECT_ID" \
  --member="serviceAccount:${PP_SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. Add non-secret email settings

Add the five SMTP and admin variables documented in `RELEASE_6_4_NOTES.md` to
`deploy/cloudrun.production.env.yaml`.

## 4. Deploy without production traffic

```bash
gcloud run deploy "$PP_SERVICE" \
  --project "$PP_PROJECT_ID" \
  --region "$PP_REGION" \
  --source . \
  --service-account "$PP_SERVICE_ACCOUNT" \
  --env-vars-file deploy/cloudrun.production.env.yaml \
  --set-secrets SQUARE_ACCESS_TOKEN=example-square-access-token-secret:latest,SMTP_PASSWORD=example-smtp-app-password-secret:latest \
  --revision-suffix v6-4 \
  --no-traffic
```

## 5. Test the tagged revision

Create a revision tag, open its URL and verify:

- Contact-step email reaches `notifications@example.com`.
- Completed recommendation email has the same lead ID and a trace ID.
- Group Retreat automatically changes a smaller guest count to six.
- Enhancements are absent for Executive/Peak and group paths.
- Rapid has no automatic private-service charge.
- Adding Assisted Stretch to Rapid increases the quote by exactly $175.
- Checkout-started email matches the Square amount.

## 6. Promote

```bash
gcloud run services update-traffic "$PP_SERVICE" \
  --project "$PP_PROJECT_ID" \
  --region "$PP_REGION" \
  --to-latest
```

The Wix link does not change because the Cloud Run service URL remains stable.
