# GitHub CD + WIF Setup (Dev)

This guide sets up GitHub Actions so a merge to `main` can build and deploy `swimming-app` to dev Cloud Run.

It covers:
- creating or verifying the GitHub Workload Identity Pool
- creating or verifying the GitHub OIDC provider
- binding GitHub to your existing build service account
- setting the exact GitHub secrets and variables used by the workflow

## 1) Values Used in This Repo

Use these values for the current dev setup:

```bash
export PROJECT_ID="swim-dev-123185"
export PROJECT_NUMBER="729427027630"
export REGION="us-central1"
export GITHUB_REPO="mishrasunny-coder/swimming-app"

export BUILD_SA="swimming-app-dev-build-sa@${PROJECT_ID}.iam.gserviceaccount.com"
export RUNTIME_SA="swimming-app-dev-sa@${PROJECT_ID}.iam.gserviceaccount.com"

export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"
```

What these mean:
- `BUILD_SA`: the existing service account GitHub Actions will impersonate
- `RUNTIME_SA`: the existing service account Cloud Run uses at runtime
- `POOL_ID`: the logical container for external identities from GitHub
- `PROVIDER_ID`: the GitHub OIDC trust configuration inside that pool

## 2) Check Whether the Pool Already Exists

```bash
gcloud iam workload-identity-pools list \
  --project="$PROJECT_ID" \
  --location="global"
```

If `github-pool` is already listed, keep it.
If not, create it:

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

## 3) Check Whether the Provider Already Exists

```bash
gcloud iam workload-identity-pools providers list \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID"
```

If `github-provider` is already listed, keep it.
If not, create it:

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}' && assertion.ref == 'refs/heads/main'"
```

What this does:
- trusts GitHub's OIDC issuer
- maps GitHub token claims into Google attributes
- allows only this repo on `main` to use the provider

## 4) Allow GitHub to Use the Existing Build Service Account

Bind the GitHub repo identity to the existing build SA:

```bash
gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

This is the most important WIF binding.
Without it, GitHub can authenticate to the provider but cannot impersonate the build service account.

## 5) Ensure the Build Service Account Can Deploy

The workflow uses `BUILD_SA` both to run Cloud Build and to deploy Cloud Run.

Grant:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"
```

What this does:
- `roles/run.admin`: allows deploy/update of the Cloud Run service
- `roles/iam.serviceAccountUser`: allows the deployer to deploy Cloud Run using the runtime SA

## 6) Get the Exact GitHub Secret Value for `WIF_PROVIDER`

Run:

```bash
gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)'
```

Expected format:

```text
projects/729427027630/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

That full string is the value for GitHub secret `WIF_PROVIDER`.

## 7) Create GitHub Secrets

In GitHub:
- open the repository
- go to `Settings`
- go to `Secrets and variables`
- open `Actions`
- open `Secrets`

Create these secrets:

```text
WIF_PROVIDER=projects/729427027630/locations/global/workloadIdentityPools/github-pool/providers/github-provider
WIF_SERVICE_ACCOUNT=swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com
```

What they mean:
- `WIF_PROVIDER`: which Google identity provider GitHub should use
- `WIF_SERVICE_ACCOUNT`: which Google service account GitHub should impersonate after authentication

## 8) Create GitHub Variables

In GitHub:
- open the repository
- go to `Settings`
- go to `Secrets and variables`
- open `Actions`
- open `Variables`

Create these variables:

```text
GCP_PROJECT_ID_DEV=swim-dev-123185
GCP_REGION=us-central1
ARTIFACT_REPO=swimming-app
IMAGE_NAME=swimming-app
CLOUD_RUN_SERVICE=swimming-app
RUNTIME_SA_EMAIL=swimming-app-dev-sa@swim-dev-123185.iam.gserviceaccount.com
BUILD_SERVICE_ACCOUNT_EMAIL=swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com
SWIM_DATA_BUCKET=swim-dev-123185-swim-data
```

These map directly to `.github/workflows/cd-dev.yml`.

## 9) Variables You Can Leave Unset

If you do not want the workflow to touch backend service or Cloud Armor, leave these unset:
- `BACKEND_SERVICE_NAME`
- `ARMOR_POLICY_NAME`

The workflow only runs that step if both are present.

## 10) Final Check

Before merging to `main`, verify:
- `WIF_PROVIDER` secret exists
- `WIF_SERVICE_ACCOUNT` secret exists
- all required variables exist
- the build SA has `roles/run.admin`
- the build SA has `roles/iam.serviceAccountUser` on the runtime SA

After that, merging a PR to `main` should trigger the dev CD workflow automatically.

## 11) Troubleshooting

If the workflow fails in the Cloud Build step with an error like:

```text
INVALID_ARGUMENT: if 'build.service_account' is specified, the build must either ...
```

Cause:
- the workflow is using a custom build service account
- Cloud Build requires an explicit logging mode when a custom build service account is set

Fix:
- make sure `cloudbuild.yaml` includes:

```yaml
options:
  logging: CLOUD_LOGGING_ONLY
```

This keeps build logs in Cloud Logging and avoids extra logs bucket setup.

If the workflow fails in the Cloud Build step with an error like:

```text
PERMISSION_DENIED: caller does not have permission to act as service account ...
```

Cause:
- GitHub successfully impersonated the build service account through WIF
- the workflow then asked Cloud Build to run using that same service account
- the build service account does not have `roles/iam.serviceAccountUser` on itself

Check current bindings:

```bash
gcloud iam service-accounts get-iam-policy "$BUILD_SA" \
  --project="$PROJECT_ID" \
  --flatten="bindings[].members" \
  --format='table(bindings.role,bindings.members)'
```

Fix:

```bash
gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/iam.serviceAccountUser"
```

This allows the build service account to act as itself when `gcloud builds submit --service-account=...` is used.
