# GCloud Setup Checklist (Per Environment)

This checklist covers terminal-only setup from authentication to billing verification.

## 0) Global Variables

```bash
export ORG_ID="YOUR_ORG_ID"
export BILLING_ID="YOUR_BILLING_ACCOUNT_ID"
export REGION="us-central1"

export DEV_PROJECT="YOUR_DEV_PROJECT_ID"
export STAGE_PROJECT="YOUR_STAGE_PROJECT_ID"
export PROD_PROJECT="YOUR_PROD_PROJECT_ID"
```

## 1) Install and Verify gcloud

```bash
gcloud version
```

## 2) Authenticate

```bash
gcloud auth login
gcloud auth list
```

Expected active account: `your-email@example.com`.

## 3) (Optional) Verify Organization Access

```bash
gcloud organizations list
gcloud projects list --filter="parent.type:organization parent.id=${ORG_ID}"
```

## 4) Per-Environment Setup (Run for each project)

Use one project at a time.

### 4.1 Set active project

```bash
# DEV
gcloud config set project "$DEV_PROJECT"
# STAGE
# gcloud config set project "$STAGE_PROJECT"
# PROD
# gcloud config set project "$PROD_PROJECT"

gcloud config get-value project
```

### 4.2 Verify project exists and you can access it

```bash
gcloud projects describe "$(gcloud config get-value project)"
```

### 4.3 Link billing to the project

```bash
gcloud billing projects link "$(gcloud config get-value project)" \
  --billing-account="$BILLING_ID"
```

### 4.4 Verify billing link

```bash
gcloud billing projects describe "$(gcloud config get-value project)"
```

Expected: `billingEnabled: true`.

### 4.5 Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  --project="$(gcloud config get-value project)"
```

## 5) Docker Auth for Artifact Registry (Once per machine)

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

## 6) Optional Quick Permission Check

```bash
gcloud run regions list
gcloud artifacts locations list
```

## 7) Notes

- If you get `PERMISSION_DENIED`, your IAM role is missing for that resource.
- If project creation/tag binding is blocked by org policy, org admin must grant required org roles.
- Deployment commands are in `agent-rules/deployment.md`.
