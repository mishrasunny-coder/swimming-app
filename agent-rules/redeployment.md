# Redeployment Runbook (Cloud Run + LB + IP Allowlist)

Use this after parsing new data or shipping code changes.

## 1) Set Variables

```bash
export PROJECT_ID="your-dev-project-id"   # change for stage/prod
export REGION="us-central1"
export SERVICE="swimming-app"
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export TAG="dev-v2"                   # set a new tag each deploy
export BUCKET="${PROJECT_ID}-swim-data"
export ARMOR_POLICY_NAME="your-dev-armor"
export YOUR_PUBLIC_IP="$(curl -4 -s https://ifconfig.me)/32"
```

## 2) Upload Latest CSV to GCS

```bash
gcloud storage cp CSV/swim_data.csv "gs://${BUCKET}/swim_data.csv"
```

## 3) Build and Push New Image Tag

```bash
gcloud builds submit \
  --project="$PROJECT_ID" \
  --config=cloudbuild.yaml \
  --substitutions=_REGION="$REGION",_REPO="$REPO",_IMAGE_NAME="$IMAGE_NAME",_TAG="$TAG" \
  .
```

## 4) Deploy Cloud Run (LB-Compatible Ingress + Mounted Data)

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

## 5) Re-Add Public Invoker (Required After Some Deploys)

```bash
gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"
```

## 6) Lock Cloud Armor to Your IP Only

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
