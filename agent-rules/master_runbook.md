# Master Runbook (Dev / Stage / Prod)

Use this as the single orchestration file. It defines the strict sequence for setup and deployment in any environment.

## 1) Inputs Required Per Run

Set environment target first:

```bash
export TARGET_ENV="<dev|stage|prod>"
```

Then use placeholders (do not hardcode real values in docs):

```bash
export ORG_ID="<your-org-id>"
export BILLING_ID="<your-billing-id>"
export REGION="us-central1"

export DEV_PROJECT_ID="<your-dev-project-id>"
export STAGE_PROJECT_ID="<your-stage-project-id>"
export PROD_PROJECT_ID="<your-prod-project-id>"

export DEV_TAG_VALUE="<tagValues/.../development>"
export STAGE_TAG_VALUE="<tagValues/.../staging>"
export PROD_TAG_VALUE="<tagValues/.../production>"
```

Resolve env-specific values:

```bash
if [ "$TARGET_ENV" = "dev" ]; then
  export PROJECT_ID="$DEV_PROJECT_ID"
  export ENV="dev"
  export TAG_VALUE="$DEV_TAG_VALUE"
elif [ "$TARGET_ENV" = "stage" ]; then
  export PROJECT_ID="$STAGE_PROJECT_ID"
  export ENV="stage"
  export TAG_VALUE="$STAGE_TAG_VALUE"
elif [ "$TARGET_ENV" = "prod" ]; then
  export PROJECT_ID="$PROD_PROJECT_ID"
  export ENV="prod"
  export TAG_VALUE="$PROD_TAG_VALUE"
else
  echo "Invalid TARGET_ENV"; exit 1
fi
```

## 2) Mandatory File Execution Order

Follow these files in this exact order:

1. `agent-rules/data_security_rules.md`
2. `agent-rules/gcloud.md`
3. `agent-rules/deployment.md`
4. Optional internet entry path: `agent-rules/load_balancer.md`
5. For later updates: `agent-rules/redeployment.md`
6. Quality gate before push: `agent-rules/agent_pr_quality_rules.md`

Use data/parser files only when needed:
- `agent-rules/script_explanation.md`
- `agent-rules/csv_uniforming_rules.md`

## 3) Fresh Setup + Deploy (Any Env)

1. Security precheck:
   - Apply `agent-rules/data_security_rules.md`.
   - Confirm no private `CSV/`, `PDF/`, `codex/` data is staged in git.
2. gcloud auth/project/billing:
   - Run `agent-rules/gcloud.md` with `PROJECT_ID` matching `TARGET_ENV`.
3. Org tag setup/binding:
   - Run `agent-rules/deployment.md` section `## 2) Tag Policy Setup`.
   - Bind `TAG_VALUE` to `PROJECT_ID`.
4. Deploy app:
   - Run `agent-rules/deployment.md` section `## 5) Deploy One Environment`.
   - Use `PROJECT_ID="$PROJECT_ID"` and `ENV="$ENV"`.
5. Verify app:
   - Run `agent-rules/deployment.md` section `## 6) Verify`.
6. If custom domain/LB is required:
   - Run `agent-rules/load_balancer.md` using env-specific names.
7. Pre-push quality:
   - Run `make pre-push` per `agent-rules/agent_pr_quality_rules.md`.

## 4) Redeploy Flow (Any Env)

1. If data changed:
   - Parse/normalize using:
     - `agent-rules/script_explanation.md`
     - `agent-rules/csv_uniforming_rules.md`
2. Run `agent-rules/redeployment.md` with env-specific values.
3. Re-validate access model (if using LB + Armor):
   - Cloud Run ingress: `internal-and-cloud-load-balancing`
   - `roles/run.invoker` contains `allUsers`
   - Armor rules:
     - `1000 allow <your-ip>/32`
     - `2147483647 deny-403 *`

## 5) Standard Env Variables for Deploy/Redeploy

```bash
export SERVICE="swimming-app"
export REPO="swimming-app"
export IMAGE_NAME="swimming-app"
export TAG="${ENV}-v1"
export BUCKET="${PROJECT_ID}-swim-data"
export SA_NAME="swimming-app-${ENV}-sa"
export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
```

For load balancer path:

```bash
export DOMAIN_NAME="<${ENV}-domain>"
export ARMOR_POLICY_NAME="<${ENV}-armor-policy>"
export YOUR_PUBLIC_IP="$(curl -4 -s https://ifconfig.me)/32"
```

## 6) Stop Conditions (Ask User)

Stop and ask the user if any are missing:
- Project ID for target env
- Billing/account access for target env
- Org tag permissions
- Domain + DNS ownership (if LB path is requested)
- Which access model to enforce:
  - private Cloud Run only, or
  - LB + Cloud Armor IP allowlist

## 7) Done Criteria (Any Env)

- Deployed revision is active in target env.
- Data source path is correct and readable by app.
- Access behavior matches chosen model.
- `make pre-push` passes.
- No private dataset artifacts are staged for commit.
