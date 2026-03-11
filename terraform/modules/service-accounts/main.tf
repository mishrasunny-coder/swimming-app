resource "google_service_account" "runtime" {
  account_id   = "swimming-app-${var.environment}-sa"
  display_name = "Swimming App ${var.environment} runtime SA"
  project      = var.project_id
}

resource "google_service_account" "deploy" {
  account_id   = var.deploy_sa_account_id
  display_name = var.deploy_sa_display_name
  project      = var.project_id
}

resource "google_project_iam_member" "deploy_roles" {
  for_each = toset(var.deploy_sa_project_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_act_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_act_as_self" {
  count = var.grant_self_impersonation ? 1 : 0

  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
