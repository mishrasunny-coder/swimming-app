# GCP Deployment Runbook (Dev / Stage / Prod)

This runbook separates:
- `Build + Deploy` setup (typically `dev`)
- `Promotion Deploy` setup (typically `stage` and `prod`)

## 1) Organization and Projects

- Organization ID: `your_org_id`
- Projects:
  - Dev: `your-dev-project-id`
  - Stage: `your-stage-project-id`
  - Prod: `your-prod-project-id`
- Billing account ID: `your_billing_id`

## 2) Tag Policy Setup

Your org requires environment tags on projects.

- Tag key: `environment`
- Tag values:
  - `development`
  - `staging`
  - `production`

Create key and values (org-level):

```bash
export ORG_ID="your_org_id"

gcloud resource-manager tags keys create environment \
  --parent="organizations/${ORG_ID}" \
  --description="Environment classification"

TAG_KEY_ID="$(gcloud resource-manager tags keys list \
  --parent="organizations/${ORG_ID}" \
  --filter="shortName=environment" \
  --format='value(name)')"

gcloud resource-manager tags values create development --parent="$TAG_KEY_ID"
gcloud resource-manager tags values create staging --parent="$TAG_KEY_ID"
gcloud resource-manager tags values create production --parent="$TAG_KEY_ID"
```

Export values:

```bash
export DEV_TAG_VALUE="$(gcloud resource-manager tags values list --parent="$TAG_KEY_ID" --filter='shortName=development' --format='value(name)')"
export STAGE_TAG_VALUE="$(gcloud resource-manager tags values list --parent="$TAG_KEY_ID" --filter='shortName=staging' --format='value(name)')"
export PROD_TAG_VALUE="$(gcloud resource-manager tags values list --parent="$TAG_KEY_ID" --filter='shortName=production' --format='value(name)')"
```

Bind values to projects:

```bash
gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/your-dev-project-id \
  --tag-value="$DEV_TAG_VALUE"

gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/your-stage-project-id \
  --tag-value="$STAGE_TAG_VALUE"

gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/your-prod-project-id \
  --tag-value="$PROD_TAG_VALUE"
```

## 3) Required APIs (Per Project)

Run in each target project:

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  --project="$(gcloud config get-value project)"
```

## 4) Runtime Pattern

- Container image in Artifact Registry.
- Data stored privately in GCS (`swim_data.csv`), not committed to git.
- App reads CSV from:
  - `SWIM_DATA_PATH=/mnt/data/swim_data.csv`
- GCS bucket is mounted in Cloud Run at `/mnt/data`.

## 5) Common Baseline Setup (All Environments)

Set variables:

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"                # use us-central1, not us-central-1
export ENV="<dev|stage|prod>"
export SERVICE="swimming-app"
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export TAG="${ENV}-v1"
export BUCKET="${PROJECT_ID}-swim-data"
export SA_NAME="swimming-app-${ENV}-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
```

If you see ADC quota warning after switching project:

```bash
gcloud auth application-default set-quota-project "$PROJECT_ID"
```

If that fails with missing `serviceusage.services.use`, ask admin to grant your user:
- `roles/serviceusage.serviceUsageConsumer` on the target project.

Create runtime service account:

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Swimming App ${ENV} runtime SA" \
  --project="$PROJECT_ID"
```

Create bucket and upload data:

```bash
gcloud storage buckets create "gs://${BUCKET}" \
  --location="$REGION" \
  --project="$PROJECT_ID"

gcloud storage cp CSV/swim_data.csv "gs://${BUCKET}/swim_data.csv"
```

Grant runtime SA read access to bucket:

```bash
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectViewer"
```

## 6) Path A: Build + Deploy (Typically Dev)

Use this path only in environment(s) where images are built and pushed.

### 6.1 Create dedicated build service account

```bash
export ENV=dev or stage or prod
export BUILD_SA_NAME="swimming-app-${ENV}-build-sa"
export BUILD_SA_EMAIL="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$BUILD_SA_NAME" \
  --display-name="Swimming App ${ENV} build SA" \
  --project="$PROJECT_ID"
```

### 6.2 Grant build SA minimum required roles

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" \
  --role="roles/storage.objectAdmin"

gcloud iam service-accounts add-iam-policy-binding \
  "swimming-app-dev-build-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --member="user:mishrasunny123185@gmail.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" \
  --role="roles/logging.logWriter"

gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${BUILD_SA_EMAIL}" \
  --role="roles/artifactregistry.writer"
```

### 6.3 Build and push image

```bash
gcloud builds submit \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA_EMAIL}" \
  --gcs-log-dir="gs://${PROJECT_ID}_cloudbuild/logs" \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_IMAGE_NAME="$IMAGE_NAME",_TAG="$TAG" \
  .
```

### 6.4 Deploy Cloud Run

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}" \
  --service-account="$SA_EMAIL" \
  --port=8080 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/mnt/data \
  --set-env-vars SWIM_DATA_PATH=/mnt/data/swim_data.csv \
  --no-allow-unauthenticated
```

## 7) Path B: Promotion Deploy (Typically Stage / Prod)

Use this when image is already built in dev and promoted by tag/SHA.

### 7.1 Required access in promotion target env

- Runtime SA exists (`SA_EMAIL`) and has bucket read (`roles/storage.objectViewer`).
- Cloud Run deploy permissions available for your deployer identity.

### 7.2 Required image pull access (Cross-Project)

If target env deploys image from dev Artifact Registry project, you must grant reader access in the source image project to:

1. Target environment Cloud Run **service agent** (required)
2. Target runtime SA (recommended)

Reason:
- During deploy/runtime image resolution, Cloud Run uses the managed service agent in the target project:
  - `service-<TARGET_PROJECT_NUMBER>@serverless-robot-prod.iam.gserviceaccount.com`
- Without this permission, deploy fails with:
  - `artifactregistry.repositories.downloadArtifacts denied`

Set variables:

```bash
export SOURCE_IMAGE_PROJECT_ID="your-dev-project-id"
export TARGET_PROJECT_ID="$PROJECT_ID"            # stage or prod project
export REPO="swimming-app"
export REGION="us-central1"
```

Resolve target Cloud Run service agent:

```bash
TARGET_PROJECT_NUMBER="$(gcloud projects describe "$TARGET_PROJECT_ID" --format='value(projectNumber)')"
TARGET_RUN_AGENT="service-${TARGET_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com"
```

Grant Artifact Registry reader to target Cloud Run service agent (required):

```bash
gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$SOURCE_IMAGE_PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${TARGET_RUN_AGENT}" \
  --role="roles/artifactregistry.reader"
```

Grant Artifact Registry reader to target runtime SA (recommended):

```bash
gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$SOURCE_IMAGE_PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.reader"
```

Optional verification:

```bash
gcloud artifacts repositories get-iam-policy "$REPO" \
  --project="$SOURCE_IMAGE_PROJECT_ID" \
  --location="$REGION"
```

### 7.3 Deploy promoted image in target env

```bash
export SOURCE_IMAGE_PROJECT_ID="your-dev-project-id"
export SOURCE_TAG_OR_SHA="dev-v1"   # or commit SHA tag

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image "${REGION}-docker.pkg.dev/${SOURCE_IMAGE_PROJECT_ID}/${REPO}/${IMAGE_NAME}:${SOURCE_TAG_OR_SHA}" \
  --service-account="$SA_EMAIL" \
  --port=8080 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/mnt/data \
  --set-env-vars SWIM_DATA_PATH=/mnt/data/swim_data.csv \
  --no-allow-unauthenticated
```

Notes:
- `stage` and `prod` do not need `artifactregistry.writer` if they are deploy-only.
- If Cloud Run API was just enabled in target env, wait a few minutes before retrying deployment (service agent propagation delay).

## 8) Verify

```bash
gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='yaml(status.url,spec.template.spec.serviceAccountName,spec.template.spec.containers[0].env)'
```

## 9) Optional: Public Entry via Load Balancer

If you need browser access through custom domain + IP allowlist, use:
- `agent-rules/load_balancer.md`

That model uses:
- Cloud Run ingress: `internal-and-cloud-load-balancing`
- Cloud Armor allowlist (`allow your IP`, `deny all`)
- Cloud Run IAM `allUsers` invoker (LB path restricted by Armor)
