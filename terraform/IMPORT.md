# Terraform Import Guide

This document provides the `terraform import` commands needed to bring existing
GCP resources into Terraform state. Run these **after** `terraform init` and
**before** `terraform apply` in each environment.

## Prerequisites

1. Create the Terraform state bucket in each project (one-time, before `terraform init`):

```bash
# Dev
gcloud storage buckets create gs://swim-dev-123185-tf-state \
  --project=swim-dev-123185 --location=us-central1

# Staging
gcloud storage buckets create gs://swim-stage-123185-tf-state \
  --project=swim-stage-123185 --location=us-central1

# Production
gcloud storage buckets create gs://swim-prod-123185-tf-state \
  --project=swim-prod-123185 --location=us-central1
```

2. Authenticate:

```bash
gcloud auth application-default login
```

3. Initialize Terraform in the target environment:

```bash
cd terraform/environments/dev   # or staging / production
terraform init
```

---

## Dev Environment

Run from `terraform/environments/dev/`:

```bash
# APIs
terraform import 'module.apis.google_project_service.enabled["run.googleapis.com"]' swim-dev-123185/run.googleapis.com
terraform import 'module.apis.google_project_service.enabled["artifactregistry.googleapis.com"]' swim-dev-123185/artifactregistry.googleapis.com
terraform import 'module.apis.google_project_service.enabled["cloudbuild.googleapis.com"]' swim-dev-123185/cloudbuild.googleapis.com
terraform import 'module.apis.google_project_service.enabled["iam.googleapis.com"]' swim-dev-123185/iam.googleapis.com
terraform import 'module.apis.google_project_service.enabled["storage.googleapis.com"]' swim-dev-123185/storage.googleapis.com
terraform import 'module.apis.google_project_service.enabled["compute.googleapis.com"]' swim-dev-123185/compute.googleapis.com
terraform import 'module.apis.google_project_service.enabled["certificatemanager.googleapis.com"]' swim-dev-123185/certificatemanager.googleapis.com

# Service Accounts
terraform import module.service_accounts.google_service_account.runtime projects/swim-dev-123185/serviceAccounts/swimming-app-dev-sa@swim-dev-123185.iam.gserviceaccount.com
terraform import module.service_accounts.google_service_account.deploy projects/swim-dev-123185/serviceAccounts/swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com

# Service Account IAM (deploy SA -> runtime SA)
terraform import module.service_accounts.google_service_account_iam_member.deploy_act_as_runtime "projects/swim-dev-123185/serviceAccounts/swimming-app-dev-sa@swim-dev-123185.iam.gserviceaccount.com roles/iam.serviceAccountUser serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"

# Service Account IAM (deploy SA -> self)
terraform import 'module.service_accounts.google_service_account_iam_member.deploy_act_as_self[0]' "projects/swim-dev-123185/serviceAccounts/swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com roles/iam.serviceAccountUser serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"

# Project IAM (deploy SA roles)
terraform import 'module.service_accounts.google_project_iam_member.deploy_roles["roles/run.admin"]' "swim-dev-123185 roles/run.admin serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"
terraform import 'module.service_accounts.google_project_iam_member.deploy_roles["roles/cloudbuild.builds.builder"]' "swim-dev-123185 roles/cloudbuild.builds.builder serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"
terraform import 'module.service_accounts.google_project_iam_member.deploy_roles["roles/logging.logWriter"]' "swim-dev-123185 roles/logging.logWriter serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"

# Storage
terraform import module.storage.google_storage_bucket.data swim-dev-123185-swim-data
terraform import module.storage.google_storage_bucket_iam_member.runtime_viewer "b/swim-dev-123185-swim-data roles/storage.objectViewer serviceAccount:swimming-app-dev-sa@swim-dev-123185.iam.gserviceaccount.com"

# Artifact Registry
terraform import module.artifact_registry.google_artifact_registry_repository.repo projects/swim-dev-123185/locations/us-central1/repositories/swimming-app

# Artifact Registry IAM (writer - build SA)
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.writers["serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.writer serviceAccount:swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com"

# Artifact Registry IAM (readers - cross-project, one per member)
# Repeat for each member in ar_reader_members. Example for stage service agent:
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:service-219789203394@serverless-robot-prod.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:service-219789203394@serverless-robot-prod.iam.gserviceaccount.com"
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com"
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com"
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:service-1015197512963@serverless-robot-prod.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:service-1015197512963@serverless-robot-prod.iam.gserviceaccount.com"
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com"
terraform import 'module.artifact_registry.google_artifact_registry_repository_iam_member.readers["serviceAccount:swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com"]' "projects/swim-dev-123185/locations/us-central1/repositories/swimming-app roles/artifactregistry.reader serviceAccount:swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com"

# WIF Pool
terraform import module.wif.google_iam_workload_identity_pool.github projects/swim-dev-123185/locations/global/workloadIdentityPools/github-pool

# WIF Provider
terraform import module.wif.google_iam_workload_identity_pool_provider.github projects/swim-dev-123185/locations/global/workloadIdentityPools/github-pool/providers/github-provider

# WIF SA Binding
terraform import module.wif.google_service_account_iam_member.wif_binding "projects/swim-dev-123185/serviceAccounts/swimming-app-dev-build-sa@swim-dev-123185.iam.gserviceaccount.com roles/iam.workloadIdentityUser principalSet://iam.googleapis.com/projects/729427027630/locations/global/workloadIdentityPools/github-pool/attribute.repository/mishrasunny-coder/swimming-app"

# Cloud Run
terraform import module.cloud_run.google_cloud_run_v2_service.app projects/swim-dev-123185/locations/us-central1/services/swimming-app

# Cloud Run IAM (allUsers invoker)
terraform import 'module.cloud_run.google_cloud_run_v2_service_iam_member.public_invoker[0]' "projects/swim-dev-123185/locations/us-central1/services/swimming-app roles/run.invoker allUsers"

# Cloud Armor
# NOTE: Replace 'swim-dev-armor' with your actual policy name if different
terraform import module.cloud_armor.google_compute_security_policy.policy projects/swim-dev-123185/global/securityPolicies/swim-dev-armor

# SSL Certificate
# NOTE: Replace 'swim-dev-managed-cert' with your actual cert name if different
terraform import module.ssl.google_compute_managed_ssl_certificate.cert projects/swim-dev-123185/global/sslCertificates/swim-dev-managed-cert

# Load Balancer - Static IP
terraform import module.load_balancer.google_compute_global_address.static_ip projects/swim-dev-123185/global/addresses/swim-dev-ip

# Load Balancer - Serverless NEG
terraform import module.load_balancer.google_compute_region_network_endpoint_group.serverless projects/swim-dev-123185/regions/us-central1/networkEndpointGroups/swim-dev-neg

# Load Balancer - Backend Service
terraform import module.load_balancer.google_compute_backend_service.default projects/swim-dev-123185/global/backendServices/swim-dev-backend

# Load Balancer - URL Map
terraform import module.load_balancer.google_compute_url_map.default projects/swim-dev-123185/global/urlMaps/swim-dev-url-map

# Load Balancer - HTTPS Proxy
terraform import module.load_balancer.google_compute_target_https_proxy.default projects/swim-dev-123185/global/targetHttpsProxies/swim-dev-https-proxy

# Load Balancer - HTTPS Forwarding Rule
terraform import module.load_balancer.google_compute_global_forwarding_rule.https projects/swim-dev-123185/global/forwardingRules/swim-dev-fw

# Load Balancer - HTTP Redirect (if enabled)
terraform import 'module.load_balancer.google_compute_url_map.http_redirect[0]' projects/swim-dev-123185/global/urlMaps/swim-dev-http-redirect
terraform import 'module.load_balancer.google_compute_target_http_proxy.redirect[0]' projects/swim-dev-123185/global/targetHttpProxies/swim-dev-http-proxy
terraform import 'module.load_balancer.google_compute_global_forwarding_rule.http[0]' projects/swim-dev-123185/global/forwardingRules/swim-dev-http-fw
```

After all imports, verify with:

```bash
terraform plan
```

Expected: zero changes (or minor drift that can be reviewed and accepted).

---

## Staging Environment

Run from `terraform/environments/staging/`:

```bash
# APIs
terraform import 'module.apis.google_project_service.enabled["run.googleapis.com"]' swim-stage-123185/run.googleapis.com
terraform import 'module.apis.google_project_service.enabled["iam.googleapis.com"]' swim-stage-123185/iam.googleapis.com
terraform import 'module.apis.google_project_service.enabled["storage.googleapis.com"]' swim-stage-123185/storage.googleapis.com
terraform import 'module.apis.google_project_service.enabled["compute.googleapis.com"]' swim-stage-123185/compute.googleapis.com
terraform import 'module.apis.google_project_service.enabled["certificatemanager.googleapis.com"]' swim-stage-123185/certificatemanager.googleapis.com

# Service Accounts
terraform import module.service_accounts.google_service_account.runtime projects/swim-stage-123185/serviceAccounts/swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com
terraform import module.service_accounts.google_service_account.deploy projects/swim-stage-123185/serviceAccounts/swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com

# Service Account IAM (deploy SA -> runtime SA)
terraform import module.service_accounts.google_service_account_iam_member.deploy_act_as_runtime "projects/swim-stage-123185/serviceAccounts/swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com roles/iam.serviceAccountUser serviceAccount:swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com"

# Project IAM
terraform import 'module.service_accounts.google_project_iam_member.deploy_roles["roles/run.admin"]' "swim-stage-123185 roles/run.admin serviceAccount:swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com"

# Storage
terraform import module.storage.google_storage_bucket.data swim-stage-123185-swim-data
terraform import module.storage.google_storage_bucket_iam_member.runtime_viewer "b/swim-stage-123185-swim-data roles/storage.objectViewer serviceAccount:swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com"

# WIF Pool
terraform import module.wif.google_iam_workload_identity_pool.github projects/swim-stage-123185/locations/global/workloadIdentityPools/github-pool

# WIF Provider
terraform import module.wif.google_iam_workload_identity_pool_provider.github projects/swim-stage-123185/locations/global/workloadIdentityPools/github-pool/providers/github-provider

# WIF SA Binding
terraform import module.wif.google_service_account_iam_member.wif_binding "projects/swim-stage-123185/serviceAccounts/swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com roles/iam.workloadIdentityUser principalSet://iam.googleapis.com/projects/219789203394/locations/global/workloadIdentityPools/github-pool/attribute.repository/mishrasunny-coder/swimming-app"

# Cloud Run
terraform import module.cloud_run.google_cloud_run_v2_service.app projects/swim-stage-123185/locations/us-central1/services/swimming-app

# Cloud Run IAM
terraform import 'module.cloud_run.google_cloud_run_v2_service_iam_member.public_invoker[0]' "projects/swim-stage-123185/locations/us-central1/services/swimming-app roles/run.invoker allUsers"

# Cloud Armor
terraform import module.cloud_armor.google_compute_security_policy.policy projects/swim-stage-123185/global/securityPolicies/swim-stage-armor

# SSL Certificate
terraform import module.ssl.google_compute_managed_ssl_certificate.cert projects/swim-stage-123185/global/sslCertificates/swim-stage-managed-cert

# Load Balancer
terraform import module.load_balancer.google_compute_global_address.static_ip projects/swim-stage-123185/global/addresses/swim-stage-ip
terraform import module.load_balancer.google_compute_region_network_endpoint_group.serverless projects/swim-stage-123185/regions/us-central1/networkEndpointGroups/swim-stage-neg
terraform import module.load_balancer.google_compute_backend_service.default projects/swim-stage-123185/global/backendServices/swim-stage-backend
terraform import module.load_balancer.google_compute_url_map.default projects/swim-stage-123185/global/urlMaps/swim-stage-url-map
terraform import module.load_balancer.google_compute_target_https_proxy.default projects/swim-stage-123185/global/targetHttpsProxies/swim-stage-https-proxy
terraform import module.load_balancer.google_compute_global_forwarding_rule.https projects/swim-stage-123185/global/forwardingRules/swim-stage-fw

# HTTP Redirect (if enabled)
terraform import 'module.load_balancer.google_compute_url_map.http_redirect[0]' projects/swim-stage-123185/global/urlMaps/swim-stage-http-redirect
terraform import 'module.load_balancer.google_compute_target_http_proxy.redirect[0]' projects/swim-stage-123185/global/targetHttpProxies/swim-stage-http-proxy
terraform import 'module.load_balancer.google_compute_global_forwarding_rule.http[0]' projects/swim-stage-123185/global/forwardingRules/swim-stage-http-fw
```

---

## Production Environment

Run from `terraform/environments/production/`:

```bash
# APIs
terraform import 'module.apis.google_project_service.enabled["run.googleapis.com"]' swim-prod-123185/run.googleapis.com
terraform import 'module.apis.google_project_service.enabled["iam.googleapis.com"]' swim-prod-123185/iam.googleapis.com
terraform import 'module.apis.google_project_service.enabled["storage.googleapis.com"]' swim-prod-123185/storage.googleapis.com
terraform import 'module.apis.google_project_service.enabled["compute.googleapis.com"]' swim-prod-123185/compute.googleapis.com
terraform import 'module.apis.google_project_service.enabled["certificatemanager.googleapis.com"]' swim-prod-123185/certificatemanager.googleapis.com

# Service Accounts
terraform import module.service_accounts.google_service_account.runtime projects/swim-prod-123185/serviceAccounts/swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com
terraform import module.service_accounts.google_service_account.deploy projects/swim-prod-123185/serviceAccounts/swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com

# Service Account IAM
terraform import module.service_accounts.google_service_account_iam_member.deploy_act_as_runtime "projects/swim-prod-123185/serviceAccounts/swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com roles/iam.serviceAccountUser serviceAccount:swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com"

# Project IAM
terraform import 'module.service_accounts.google_project_iam_member.deploy_roles["roles/run.admin"]' "swim-prod-123185 roles/run.admin serviceAccount:swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com"

# Storage
terraform import module.storage.google_storage_bucket.data swim-prod-123185-swim-data
terraform import module.storage.google_storage_bucket_iam_member.runtime_viewer "b/swim-prod-123185-swim-data roles/storage.objectViewer serviceAccount:swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com"

# WIF Pool
terraform import module.wif.google_iam_workload_identity_pool.github projects/swim-prod-123185/locations/global/workloadIdentityPools/github-pool

# WIF Provider
terraform import module.wif.google_iam_workload_identity_pool_provider.github projects/swim-prod-123185/locations/global/workloadIdentityPools/github-pool/providers/github-provider

# WIF SA Binding
terraform import module.wif.google_service_account_iam_member.wif_binding "projects/swim-prod-123185/serviceAccounts/swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com roles/iam.workloadIdentityUser principalSet://iam.googleapis.com/projects/1015197512963/locations/global/workloadIdentityPools/github-pool/attribute.repository/mishrasunny-coder/swimming-app"

# Cloud Run
terraform import module.cloud_run.google_cloud_run_v2_service.app projects/swim-prod-123185/locations/us-central1/services/swimming-app

# Cloud Run IAM
terraform import 'module.cloud_run.google_cloud_run_v2_service_iam_member.public_invoker[0]' "projects/swim-prod-123185/locations/us-central1/services/swimming-app roles/run.invoker allUsers"

# Cloud Armor
terraform import module.cloud_armor.google_compute_security_policy.policy projects/swim-prod-123185/global/securityPolicies/swim-prod-armor

# SSL Certificate
terraform import module.ssl.google_compute_managed_ssl_certificate.cert projects/swim-prod-123185/global/sslCertificates/swim-prod-managed-cert

# Load Balancer
terraform import module.load_balancer.google_compute_global_address.static_ip projects/swim-prod-123185/global/addresses/swim-prod-ip
terraform import module.load_balancer.google_compute_region_network_endpoint_group.serverless projects/swim-prod-123185/regions/us-central1/networkEndpointGroups/swim-prod-neg
terraform import module.load_balancer.google_compute_backend_service.default projects/swim-prod-123185/global/backendServices/swim-prod-backend
terraform import module.load_balancer.google_compute_url_map.default projects/swim-prod-123185/global/urlMaps/swim-prod-url-map
terraform import module.load_balancer.google_compute_target_https_proxy.default projects/swim-prod-123185/global/targetHttpsProxies/swim-prod-https-proxy
terraform import module.load_balancer.google_compute_global_forwarding_rule.https projects/swim-prod-123185/global/forwardingRules/swim-prod-fw

# HTTP Redirect (if enabled)
terraform import 'module.load_balancer.google_compute_url_map.http_redirect[0]' projects/swim-prod-123185/global/urlMaps/swim-prod-http-redirect
terraform import 'module.load_balancer.google_compute_target_http_proxy.redirect[0]' projects/swim-prod-123185/global/targetHttpProxies/swim-prod-http-proxy
terraform import 'module.load_balancer.google_compute_global_forwarding_rule.http[0]' projects/swim-prod-123185/global/forwardingRules/swim-prod-http-fw
```

---

## Important Notes

1. **Resource names must match exactly.** If your existing resources use different
   names than the defaults in `terraform.tfvars` (e.g., `my-dev-lb` instead of
   `swim-dev-backend`), update `terraform.tfvars` to match before importing.

2. **Run `terraform plan` after each import batch** to catch drift early.

3. **The Cloud Run service template is ignored** by Terraform after initial import
   (`lifecycle { ignore_changes = [template] }`). GitHub Actions continues to
   deploy new revisions without Terraform interference.

4. **Cloud Armor allowed IPs** need to be set via `terraform.tfvars.local` or
   the `-var` flag before running `terraform plan`, otherwise the plan will show
   the allowed IPs being removed (replaced with an empty list).

5. **HTTP redirect resources** are optional. If you did not set up HTTP-to-HTTPS
   redirect for an environment, set `enable_http_redirect = false` in that
   environment's `terraform.tfvars` and skip the HTTP redirect import commands.

6. **Order matters for some resources.** Import APIs first, then SAs, then
   resources that depend on them. The order in this document follows the
   correct dependency chain.

7. **IAP OAuth is a manual bootstrap.** Create or verify the OAuth consent
   screen and OAuth client outside Terraform, then provide the values to
   Terraform via `TF_VAR_iap_oauth_client_id` and
   `TF_VAR_iap_oauth_client_secret` when `access_mode = "iap"`.

8. **IAP replaces Cloud Armor as the identity gate.** In `access_mode = "iap"`
   the Cloud Armor policy should allow public traffic so IAP can challenge
   users. Authorization is enforced by the environment-specific Google Group.

9. **The post-merge Terraform workflow expects OAuth secrets in GitHub.**
   Configure `IAP_OAUTH_CLIENT_ID` and `IAP_OAUTH_CLIENT_SECRET` in each GitHub
   Environment before merging Terraform changes to `main`.

## IAP Migration Resources

When migrating an existing environment to `access_mode = "iap"`, Terraform will
also manage these additional resources:

- `module.iap.google_iap_web_backend_service_iam_member.group_access[0]`
- `module.iap.google_cloud_run_v2_service_iam_member.iap_invoker[0]`

Use those Terraform addresses if the IAP access binding or Cloud Run invoker
binding already exists and needs importing before the first apply.
