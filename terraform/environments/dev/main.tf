# SA emails are constructed statically so for_each and import work
# without needing resources to already exist in state.
locals {
  deploy_sa_account_id = "swimming-app-dev-build-sa"
  deploy_sa_email      = "${local.deploy_sa_account_id}@${var.project_id}.iam.gserviceaccount.com"
  runtime_sa_email     = "swimming-app-${var.environment}-sa@${var.project_id}.iam.gserviceaccount.com"
  bucket_name          = "${var.project_id}-swim-data"
}

data "google_project" "current" {
  project_id = var.project_id
}

# ── APIs ─────────────────────────────────────────────────────

module "apis" {
  source     = "../../modules/apis"
  project_id = var.project_id

  services = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "certificatemanager.googleapis.com",
  ]
}

# ── Service Accounts ─────────────────────────────────────────

module "service_accounts" {
  source      = "../../modules/service-accounts"
  project_id  = var.project_id
  environment = var.environment

  deploy_sa_account_id   = local.deploy_sa_account_id
  deploy_sa_display_name = "Swimming App dev build SA"

  deploy_sa_project_roles = [
    "roles/run.admin",
    "roles/cloudbuild.builds.builder",
    "roles/logging.logWriter",
    "roles/storage.objectAdmin",
    "roles/storage.admin",
    "roles/artifactregistry.admin",
    "roles/compute.admin",
    "roles/iap.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
  ]

  grant_self_impersonation = true

  depends_on = [module.apis]
}

# ── Storage ──────────────────────────────────────────────────

module "storage" {
  source     = "../../modules/storage"
  project_id = var.project_id
  region     = var.region

  bucket_name      = local.bucket_name
  runtime_sa_email = local.runtime_sa_email

  depends_on = [module.apis]
}

# ── Artifact Registry ────────────────────────────────────────

module "artifact_registry" {
  source        = "../../modules/artifact-registry"
  project_id    = var.project_id
  region        = var.region
  repository_id = "swimming-app"

  writer_members = [
    "serviceAccount:${local.deploy_sa_email}",
  ]

  reader_members = var.ar_reader_members

  depends_on = [module.apis]
}

# ── Workload Identity Federation ─────────────────────────────

module "wif" {
  source      = "../../modules/wif"
  project_id  = var.project_id
  github_repo = var.github_repo

  deploy_sa_id = "projects/${var.project_id}/serviceAccounts/${local.deploy_sa_email}"

  attribute_condition = "assertion.repository == '${var.github_repo}' && assertion.ref == 'refs/heads/main'"

  depends_on = [module.apis]
}

# ── Cloud Run ────────────────────────────────────────────────

module "cloud_run" {
  source     = "../../modules/cloud-run"
  project_id = var.project_id
  region     = var.region

  service_name          = "swimming-app"
  runtime_sa_email      = local.runtime_sa_email
  bucket_name           = local.bucket_name
  access_mode           = var.access_mode
  allow_unauthenticated = var.access_mode != "iap"

  depends_on = [module.apis]
}

# ── Cloud Armor ──────────────────────────────────────────────

module "cloud_armor" {
  source     = "../../modules/cloud-armor"
  project_id = var.project_id

  policy_name       = "swim-dev-armor"
  allowed_ip_ranges = var.allowed_ip_ranges
  policy_mode       = var.access_mode == "iap" ? "iap_fronted" : "ip_restricted"

  depends_on = [module.apis]
}

# ── SSL Certificate ──────────────────────────────────────────

module "ssl" {
  source     = "../../modules/ssl"
  project_id = var.project_id

  cert_name = "swim-dev-managed-cert"
  domain    = var.domain_name

  depends_on = [module.apis]
}

# ── Load Balancer ────────────────────────────────────────────

module "load_balancer" {
  source     = "../../modules/load-balancer"
  project_id = var.project_id
  region     = var.region

  name_prefix               = var.lb_name_prefix
  cloud_run_service_name    = module.cloud_run.service_name
  security_policy_self_link = module.cloud_armor.policy_self_link
  ssl_certificate_self_link = module.ssl.certificate_self_link
  enable_iap                = var.access_mode == "iap"
  iap_oauth_client_id       = var.iap_oauth_client_id
  iap_oauth_client_secret   = var.iap_oauth_client_secret
  enable_http_redirect      = var.enable_http_redirect
}

# ── IAP ──────────────────────────────────────────────────────

module "iap" {
  source = "../../modules/iap"

  enabled                = var.access_mode == "iap"
  project_id             = var.project_id
  project_number         = data.google_project.current.number
  region                 = var.region
  cloud_run_service_name = module.cloud_run.service_name
  backend_service_name   = module.load_balancer.backend_service_name
  access_group_email     = var.iap_access_group_email
}
