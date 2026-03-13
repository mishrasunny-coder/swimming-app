locals {
  access_group_member      = "group:${var.access_group_email}"
  iap_service_agent_email  = "service-${var.project_number}@gcp-sa-iap.iam.gserviceaccount.com"
  iap_service_agent_member = "serviceAccount:${local.iap_service_agent_email}"
}

resource "google_project_service_identity" "iap" {
  count    = var.enabled ? 1 : 0
  provider = google-beta

  project = var.project_id
  service = "iap.googleapis.com"
}

resource "google_iap_web_backend_service_iam_member" "group_access" {
  count = var.enabled ? 1 : 0

  project             = var.project_id
  web_backend_service = var.backend_service_name
  role                = "roles/iap.httpsResourceAccessor"
  member              = local.access_group_member

  lifecycle {
    precondition {
      condition     = trimspace(var.access_group_email) != ""
      error_message = "IAP requires a non-empty access_group_email."
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  count = var.enabled ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = var.cloud_run_service_name
  role     = "roles/run.invoker"
  member   = local.iap_service_agent_member

  depends_on = [google_project_service_identity.iap]
}
