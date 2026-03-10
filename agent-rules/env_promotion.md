# Environment Promotion Setup (Stage / Prod)

Use this when the image is already built in dev and you only want to deploy that exact image to stage or prod.

This model assumes:
- dev builds and pushes the image
- stage/prod only deploy an existing image from dev Artifact Registry
- no build happens in stage/prod

## 1) Current Known Runtime Resources

Already present:

```text
Stage project: swim-stage-123185
Stage project number: 219789203394
Stage runtime SA: swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com

Prod project: swim-prod-123185
Prod project number: 1015197512963
Prod runtime SA: swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com

Service name: swimming-app
Region: us-central1
Source image project: swim-dev-123185
Artifact Registry repo: swimming-app
Image name: swimming-app
```

Already verified:
- Cloud Run service exists in stage and prod
- runtime service accounts exist in stage and prod
- stage/prod runtime service accounts can read their GCS buckets
- stage/prod Cloud Run service agents can pull images from dev Artifact Registry

## 2) Variables

Set these once:

```bash
export REGION="us-central1"
export SERVICE="swimming-app"
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export SOURCE_IMAGE_PROJECT_ID="swim-dev-123185"
export GITHUB_REPO="mishrasunny-coder/swimming-app"

export STAGE_PROJECT_ID="swim-stage-123185"
export STAGE_PROJECT_NUMBER="219789203394"
export STAGE_RUNTIME_SA="swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com"
export STAGE_DEPLOYER_SA_NAME="swimming-app-stage-deployer"
export STAGE_DEPLOYER_SA="${STAGE_DEPLOYER_SA_NAME}@${STAGE_PROJECT_ID}.iam.gserviceaccount.com"

export PROD_PROJECT_ID="swim-prod-123185"
export PROD_PROJECT_NUMBER="1015197512963"
export PROD_RUNTIME_SA="swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com"
export PROD_DEPLOYER_SA_NAME="swimming-app-prod-deployer"
export PROD_DEPLOYER_SA="${PROD_DEPLOYER_SA_NAME}@${PROD_PROJECT_ID}.iam.gserviceaccount.com"

export POOL_ID="github-pool"
export PROVIDER_ID="github-provider"
```

Meaning:
- `SOURCE_IMAGE_PROJECT_ID`: the dev project where the image already exists
- `*_DEPLOYER_SA`: the service account GitHub Actions will impersonate for deploys
- `*_RUNTIME_SA`: the service account Cloud Run runs as in the target environment

## 3) Stage Setup

### 3.1 Create stage deployer SA

```bash
gcloud iam service-accounts create "$STAGE_DEPLOYER_SA_NAME" \
  --project="$STAGE_PROJECT_ID" \
  --display-name="Swimming App Stage Deployer"
```

Meaning:
- creates a dedicated GitHub deploy identity for stage

### 3.2 Grant stage deploy permissions

```bash
gcloud projects add-iam-policy-binding "$STAGE_PROJECT_ID" \
  --member="serviceAccount:${STAGE_DEPLOYER_SA}" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding "$STAGE_RUNTIME_SA" \
  --project="$STAGE_PROJECT_ID" \
  --member="serviceAccount:${STAGE_DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser"
```

Meaning:
- `roles/run.admin`: allows deploy/update of the stage Cloud Run service
- `roles/iam.serviceAccountUser`: allows deploying Cloud Run with the stage runtime SA

### 3.3 Create stage WIF pool

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$STAGE_PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

Meaning:
- creates the trust container for GitHub identities in stage

### 3.4 Create stage GitHub OIDC provider

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$STAGE_PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'"
```

Meaning:
- trusts GitHub's OIDC tokens
- restricts trust to this repository
- branch restriction can be handled in the workflow trigger and GitHub environment approvals

### 3.5 Allow GitHub to impersonate stage deployer SA

```bash
gcloud iam service-accounts add-iam-policy-binding "$STAGE_DEPLOYER_SA" \
  --project="$STAGE_PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${STAGE_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

Meaning:
- connects GitHub repo identity to the stage deployer service account

### 3.6 Get stage `WIF_PROVIDER` value

```bash
gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$STAGE_PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)'
```

Meaning:
- prints the exact provider resource name to use as GitHub secret `WIF_PROVIDER` for stage

## 4) Prod Setup

### 4.1 Create prod deployer SA

```bash
gcloud iam service-accounts create "$PROD_DEPLOYER_SA_NAME" \
  --project="$PROD_PROJECT_ID" \
  --display-name="Swimming App Prod Deployer"
```

Meaning:
- creates a dedicated GitHub deploy identity for prod

### 4.2 Grant prod deploy permissions

```bash
gcloud projects add-iam-policy-binding "$PROD_PROJECT_ID" \
  --member="serviceAccount:${PROD_DEPLOYER_SA}" \
  --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding "$PROD_RUNTIME_SA" \
  --project="$PROD_PROJECT_ID" \
  --member="serviceAccount:${PROD_DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser"
```

Meaning:
- gives the prod deployer SA permission to deploy Cloud Run and use the prod runtime SA

### 4.3 Create prod WIF pool

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --project="$PROD_PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

Meaning:
- creates the trust container for GitHub identities in prod

### 4.4 Create prod GitHub OIDC provider

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --project="$PROD_PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository == '${GITHUB_REPO}'"
```

Meaning:
- trusts GitHub OIDC for this repo in prod

### 4.5 Allow GitHub to impersonate prod deployer SA

```bash
gcloud iam service-accounts add-iam-policy-binding "$PROD_DEPLOYER_SA" \
  --project="$PROD_PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROD_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPO}"
```

Meaning:
- allows GitHub repo identity to impersonate the prod deployer SA

### 4.6 Get prod `WIF_PROVIDER` value

```bash
gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --project="$PROD_PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --format='value(name)'
```

Meaning:
- prints the exact provider resource name to use as GitHub secret `WIF_PROVIDER` for prod

## 5) What GitHub Needs for Promotion Workflows

Use distinct secrets and variables for each target environment.

Secrets:

```text
WIF_PROVIDER_STAGING=<stage provider resource name>
WIF_SERVICE_ACCOUNT_STAGING=swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com

WIF_PROVIDER_PRODUCTION=<prod provider resource name>
WIF_SERVICE_ACCOUNT_PRODUCTION=swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com
```

Variables:

```text
GCP_PROJECT_ID_STAGING=swim-stage-123185
RUNTIME_SA_EMAIL_STAGING=swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com
SWIM_DATA_BUCKET_STAGING=swim-stage-123185-swim-data

GCP_PROJECT_ID_PRODUCTION=swim-prod-123185
RUNTIME_SA_EMAIL_PRODUCTION=swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com
SWIM_DATA_BUCKET_PRODUCTION=swim-prod-123185-swim-data
```

Meaning:
- these values are target-environment specific
- common values are reused from the existing repo variables already used by dev CD:
  - `GCP_REGION`
  - `CLOUD_RUN_SERVICE`
  - `GCP_PROJECT_ID_DEV`
  - `ARTIFACT_REPO`
  - `IMAGE_NAME`

## 6) Promotion Deploy Command

Use this model in stage or prod promotion workflow:

```bash
export IMAGE_TAG="sha-<commit>"   # preferred

gcloud run deploy "$SERVICE" \
  --project="$GCP_PROJECT_ID" \
  --region="$GCP_REGION" \
  --image "${GCP_REGION}-docker.pkg.dev/${SOURCE_IMAGE_PROJECT_ID}/${ARTIFACT_REPO}/${IMAGE_NAME}:${IMAGE_TAG}" \
  --service-account="$RUNTIME_SA_EMAIL" \
  --port=8080 \
  --add-volume "name=data,type=cloud-storage,bucket=${GCP_PROJECT_ID}-swim-data" \
  --add-volume-mount "volume=data,mount-path=/mnt/data" \
  --set-env-vars SWIM_DATA_PATH=/mnt/data/swim_data.csv \
  --ingress=internal-and-cloud-load-balancing
```

Meaning:
- deploys an already-built image from dev into stage or prod
- no build happens in the target environment
- use `sha-*` tag for exact artifact promotion

## 7) Recommended Promotion Rule

Use:
- dev workflow: build + push + deploy
- stage workflow: deploy only
- prod workflow: deploy only

Use this promotion input:
- `sha-<commit>`

Avoid using:
- `dev-vx` for promotion decisions

Reason:
- `sha-*` is immutable and exact
- `dev-vx` is only an environment sequence tag

## 8) Troubleshooting

If the promotion workflow fails during `gcloud run deploy` with:

```text
PERMISSION_DENIED: Permission 'artifactregistry.repositories.downloadArtifacts' denied
```

Cause:
- the image is stored in the dev Artifact Registry project
- the target deployer service account can deploy Cloud Run in stage/prod
- but it cannot read the image from the dev Artifact Registry repo during deploy

Why this fix is required:
- Cloud Run service agent needs repo read access at runtime
- the deployer service account also needs repo read access because `gcloud run deploy` resolves and validates the image during deployment

Grant reader access to the stage deployer SA on the dev repo:

```bash
export DEV_PROJECT_ID="swim-dev-123185"
export REGION="us-central1"
export REPO="swimming-app"
export STAGE_DEPLOYER_SA="swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com"

gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$DEV_PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${STAGE_DEPLOYER_SA}" \
  --role="roles/artifactregistry.reader"
```

Grant reader access to the prod deployer SA on the dev repo:

```bash
export PROD_DEPLOYER_SA="swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com"

gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$DEV_PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${PROD_DEPLOYER_SA}" \
  --role="roles/artifactregistry.reader"
```

Optional verification:

```bash
gcloud artifacts repositories get-iam-policy "$REPO" \
  --project="$DEV_PROJECT_ID" \
  --location="$REGION"
```
