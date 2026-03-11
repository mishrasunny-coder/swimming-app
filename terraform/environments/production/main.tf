locals {
  deploy_sa_account_id = "swimming-app-prod-deployer"
  deploy_sa_email      = "${local.deploy_sa_account_id}@${var.project_id}.iam.gserviceaccount.com"
  runtime_sa_email     = "swimming-app-${var.environment}-sa@${var.project_id}.iam.gserviceaccount.com"
  bucket_name          = "${var.project_id}-swim-data"
}

# ── APIs ─────────────────────────────────────────────────────

module "apis" {
  source     = "../../modules/apis"
  project_id = var.project_id

  services = [
    "run.googleapis.com",
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
  deploy_sa_display_name = "Swimming App Prod Deployer"

  deploy_sa_project_roles = [
    "roles/run.admin",
  ]

  grant_self_impersonation = false

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

# ── Workload Identity Federation ─────────────────────────────

module "wif" {
  source      = "../../modules/wif"
  project_id  = var.project_id
  github_repo = var.github_repo

  deploy_sa_id = "projects/${var.project_id}/serviceAccounts/${local.deploy_sa_email}"

  attribute_condition = "assertion.repository == '${var.github_repo}'"

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
  allow_unauthenticated = true

  depends_on = [module.apis]
}

# ── Cloud Armor ──────────────────────────────────────────────

module "cloud_armor" {
  source     = "../../modules/cloud-armor"
  project_id = var.project_id

  policy_name       = "swim-prod-armor"
  allowed_ip_ranges = var.allowed_ip_ranges

  depends_on = [module.apis]
}

# ── SSL Certificate ──────────────────────────────────────────

module "ssl" {
  source     = "../../modules/ssl"
  project_id = var.project_id

  cert_name = "swim-prod-managed-cert"
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
  enable_http_redirect      = var.enable_http_redirect
}
