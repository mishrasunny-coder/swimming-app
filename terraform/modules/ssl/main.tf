resource "google_compute_managed_ssl_certificate" "cert" {
  name    = var.cert_name
  project = var.project_id

  managed {
    domains = [var.domain]
  }
}
