# Redeployment Runbook (Cloud Run + LB + IP Allowlist)

Use this after parsing new data or shipping code changes. This only requires pushing code to staging and prod

## 1) Set Variables

```bash
export PROJECT_ID="your-dev-project-id"   # change for stage/prod
export REGION="us-central1"
export SERVICE="swimming-app"
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export TAG="dev-v5"                   # set a new tag each deploy
export BUCKET="${PROJECT_ID}-swim-data"
export ARMOR_POLICY_NAME="your-dev-armor"
export YOUR_PUBLIC_IP="$(curl -4 -s https://ifconfig.me)/32"
export SOURCE_IMAGE_PROJECT_ID="your dev project id"
```


If Bucket does not exist then create

```bash
gcloud config set project "$PROJECT_ID"
gcloud storage buckets create "gs://${BUCKET}" \
  --project="$PROJECT_ID" \
  --location="$REGION"
```

Then to validate whether bucket was created succcessfully run
```bash
gcloud storage buckets describe "gs://${BUCKET}"
```

Then create SA for each environment (dev/stage/prod) wherever you are deploying your code to bind SA with IAM permissions for the bucket

```bash
gcloud iam service-accounts create "swimming-app-prod-sa" \
  --project="$PROJECT_ID" \
  --display-name="Swimming App prod runtime SA"
```

Verify SA exists
```bash
gcloud iam service-accounts list --project="$PROJECT_ID" \
  --filter="email:swimming-app-prod-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --format="value(email)"
```

No add Bucket Read Permissions for this service account

```bash
export SA_EMAIL="swimming-app-prod-sa@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.objectViewer"
```

## 2) Upload Latest CSV to GCS

```bash
gcloud storage cp CSV/swim_data.csv "gs://${BUCKET}/swim_data.csv"
```

Add Cross Project Permission (in dev project)

First step is to enable google api
```bash
gcloud services enable run.googleapis.com --project="$PROJECT_ID"
```

Then run the following

```bash
TARGET_PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
TARGET_RUN_AGENT="service-${TARGET_PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com"

gcloud artifacts repositories add-iam-policy-binding "$REPO" \
  --project="$SOURCE_IMAGE_PROJECT_ID" \
  --location="$REGION" \
  --member="serviceAccount:${TARGET_RUN_AGENT}" \
  --role="roles/artifactregistry.reader"
```

## 3) Deploy Cloud Run (LB-Compatible Ingress + Mounted Data)

ONLY for dev you need to first build and then deploy
```bash
export ENV=dev or stage or prod
export BUILD_SA_NAME="swimming-app-${ENV}-build-sa"
# export SA_NAME="swimming-app-${ENV}-sa"
export BUILD_SA_EMAIL="${BUILD_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
# export BUILD_SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud builds submit \
  --project="$PROJECT_ID" \
  --service-account="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA_EMAIL}" \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_IMAGE_NAME="$IMAGE_NAME",_TAG="$TAG" \
  .
```

```bash
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}:${TAG}" \
  --ingress=internal-and-cloud-load-balancing \
  --add-volume name=data,type=cloud-storage,bucket="$BUCKET" \
  --add-volume-mount volume=data,mount-path=/mnt/data \
  --set-env-vars SWIM_DATA_PATH=/mnt/data/swim_data.csv
```

## 4) Re-Add Public Invoker (Required After Some Deploys)

```bash
gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"
```

## 6) Lock Cloud Armor to Your IP Only

You may have to create policy once in each env
```bash
gcloud compute security-policies create "$ARMOR_POLICY_NAME"
```

```bash
gcloud compute security-policies rules update 1000 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="$YOUR_PUBLIC_IP" \
  --action=allow

gcloud compute security-policies rules update 2147483647 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="*" \
  --action=deny-403
```

## 7) Verify

```bash
gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='yaml(spec.ingress,status.latestReadyRevisionName,status.url)'

gcloud run services get-iam-policy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --format='yaml(bindings)'

gcloud compute security-policies describe "$ARMOR_POLICY_NAME" \
  --format='yaml(rules)'
```

Expected:
- `spec.ingress: internal-and-cloud-load-balancing`
- `allUsers` present in `roles/run.invoker`
- Armor rule `1000` allows only your `/32`
- Armor rule `2147483647` is `deny-403` for `*`

Open only your LB domain URL (for example: `https://app-dev.example.com`).
