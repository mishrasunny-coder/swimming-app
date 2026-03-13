resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = var.ingress

  template {
    service_account = var.runtime_sa_email

    containers {
      image = var.initial_image

      ports {
        container_port = var.port
      }

      env {
        name  = "SWIM_DATA_PATH"
        value = var.data_path
      }

      volume_mounts {
        name       = "data"
        mount_path = "/mnt/data"
      }
    }

    volumes {
      name = "data"
      gcs {
        bucket    = var.bucket_name
        read_only = true
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template,
      client,
      client_version,
    ]
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.access_mode != "iap" && var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
