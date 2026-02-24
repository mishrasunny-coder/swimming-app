# GCP Deployment Runbook (Dev / Stage / Prod)

This runbook captures the exact setup path used for this repo.

## 1) Organization and Projects

- Organization ID: `your_org_id`
- Projects:
  - Dev: `swim-dev-123185`
  - Stage: `swim-stage-123185`
  - Prod: `swim-prod-123185`
- Billing account ID: `your_billing_id`

> Note: We previously created and deleted `swimming-app-prod`.

## 2) Tag Policy Setup

Your org requires environment tags on projects.

- Tag key: `environment`
- Tag values are already created and exported:
  - `DEV_TAG_VALUE`
  - `STAGE_TAG_VALUE`
  - `PROD_TAG_VALUE`

Bind tags (already done, command for reference):

```bash
gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/swim-dev-123185 \
  --tag-value=$DEV_TAG_VALUE

gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/swim-stage-123185 \
  --tag-value=$STAGE_TAG_VALUE

gcloud resource-manager tags bindings create \
  --parent=//cloudresourcemanager.googleapis.com/projects/swim-prod-123185 \
  --tag-value=$PROD_TAG_VALUE
```

## 3) Required APIs (per project)

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
- Data kept private in GCS bucket (`swim_data.csv`), not in git.
- Cloud Run deployed with `--no-allow-unauthenticated`.
- App reads CSV via env var:
  - `SWIM_DATA_PATH=/mnt/data/swim_data.csv`
- GCS bucket mounted into Cloud Run at `/mnt/data`.

## 5) Deploy One Environment (repeat for dev/stage/prod)

Set variables:

```bash
export PROJECT_ID="swim-dev-123185"     # change per env
export REGION="us-central1"
export ENV="dev"                         # dev | stage | prod
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export TAG="${ENV}-v1"
export SERVICE="swimming-app"
export BUCKET="${PROJECT_ID}-swim-data"
export SA_NAME="swimming-app-${ENV}-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

Create service account:

```bash
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="Swimming App ${ENV} runtime SA" \
  --project="$PROJECT_ID"
```

Verify APIs enabled:

```bash
gcloud services list --enabled --project="$(gcloud config get-value project)" \
  --filter="name:(run.googleapis.com OR artifactregistry.googleapis.com OR cloudbuild.googleapis.com OR iam.googleapis.com OR storage.googleapis.com)"
```

Create Artifact Registry repo:

```bash
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="Swimming app images" \
  --project="$PROJECT_ID"
```

Create bucket and upload data:

```bash
gcloud storage buckets create "gs://${BUCKET}" --location="$REGION" --project="$PROJECT_ID"
gcloud storage cp CSV/swim_data.csv "gs://${BUCKET}/swim_data.csv"
```

Grant bucket read access to runtime service account:

```bash
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectViewer"
```

Cloud Build permissions (required before build):

```bash
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
LEGACY_COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Cloud Build source/artifact access
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/storage.admin"

# Some projects use legacy compute SA during build source fetch
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${LEGACY_COMPUTE_SA}" \
  --role="roles/storage.objectAdmin"
```

# Write access to cloud build SA and legacy compute SA on the repo
```bash
gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/artifactregistry.writer"

gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${LEGACY_COMPUTE_SA}" \
  --role="roles/artifactregistry.writer"
```

# Give Logs Writer Access to Cloud Build SA and developer service account
```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${LEGACY_COMPUTE_SA}" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/logging.logWriter"
```

Verify Cloud Build-related IAM bindings:

```bash
gcloud projects get-iam-policy "$PROJECT_ID" \
  --flatten="bindings[].members" \
  --filter="cloudbuild.gserviceaccount.com OR developer.gserviceaccount.com" \
  --format="table(bindings.role,bindings.members)"
```

Expected: at least `roles/cloudbuild.builds.builder` and storage roles for build access.

Build and push image:

```bash
# run from repo root (must contain cloudbuild.yaml and Dockerfile.swimming)
gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_IMAGE_NAME="$IMAGE_NAME",_TAG="$TAG" \
  .
```

If build fails with `storage.objects.get` permission errors, re-run the Cloud Build permissions block above and retry.

Deploy Cloud Run:

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}" \
  --service-account="$SA_EMAIL" \
  --no-allow-unauthenticated \
  --port=8080 \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/mnt/data \
  --set-env-vars SWIM_DATA_PATH=/mnt/data/swim_data.csv
```

The container is configured to listen on `${PORT}` (Cloud Run runtime env), with `8080` as default.

Allow only your user to invoke:

```bash
gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --member="user:your-email" \
  --role="roles/run.invoker"
```

## 6) Verify

```bash
gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='value(status.url)'
```

Open URL while signed in as `your-email`.

## 7) Notes / Uncertainties

- Static dedicated external IP per environment was discussed, but not fully implemented yet.
  - Current Cloud Run deployment is private by IAM (`--no-allow-unauthenticated`).
  - If fixed per-env IPs are required, add External HTTPS LB + static IP + Cloud Armor allowlist per environment.


## 8) Optional: Public Entry via Load Balancer

If you need browser-friendly access with controlled entry (instead of direct private `run.app`), add:
- External HTTPS Load Balancer
- Static IP per environment
- Cloud Armor IP allowlist (only your IP)
- Keep Cloud Run service private (`--no-allow-unauthenticated`)