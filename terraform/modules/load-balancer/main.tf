locals {
  neg_name             = "${var.name_prefix}-neg"
  backend_name         = "${var.name_prefix}-backend"
  url_map_name         = "${var.name_prefix}-url-map"
  https_proxy_name     = "${var.name_prefix}-https-proxy"
  forwarding_rule_name = "${var.name_prefix}-fw"
  static_ip_name       = "${var.name_prefix}-ip"
  http_redirect_name   = "${var.name_prefix}-http-redirect"
  http_proxy_name      = "${var.name_prefix}-http-proxy"
  http_fw_rule_name    = "${var.name_prefix}-http-fw"
}

# ── Static IP ────────────────────────────────────────────────

resource "google_compute_global_address" "static_ip" {
  name    = local.static_ip_name
  project = var.project_id
}

# ── Serverless NEG ───────────────────────────────────────────

resource "google_compute_region_network_endpoint_group" "serverless" {
  name                  = local.neg_name
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  project               = var.project_id

  cloud_run {
    service = var.cloud_run_service_name
  }
}

# ── Backend Service ──────────────────────────────────────────

resource "google_compute_backend_service" "default" {
  name                  = local.backend_name
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  security_policy       = var.security_policy_self_link

  backend {
    group = google_compute_region_network_endpoint_group.serverless.id
  }
}

# ── URL Map ──────────────────────────────────────────────────

resource "google_compute_url_map" "default" {
  name            = local.url_map_name
  project         = var.project_id
  default_service = google_compute_backend_service.default.id
}

# ── HTTPS Proxy ──────────────────────────────────────────────

resource "google_compute_target_https_proxy" "default" {
  name             = local.https_proxy_name
  project          = var.project_id
  ssl_certificates = [var.ssl_certificate_self_link]
  url_map          = google_compute_url_map.default.id
}

# ── HTTPS Forwarding Rule (port 443) ────────────────────────

resource "google_compute_global_forwarding_rule" "https" {
  name                  = local.forwarding_rule_name
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.static_ip.id
  target                = google_compute_target_https_proxy.default.id
  port_range            = "443"
}

# ── HTTP → HTTPS Redirect (optional) ────────────────────────

resource "google_compute_url_map" "http_redirect" {
  count   = var.enable_http_redirect ? 1 : 0
  name    = local.http_redirect_name
  project = var.project_id

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "redirect" {
  count   = var.enable_http_redirect ? 1 : 0
  name    = local.http_proxy_name
  project = var.project_id
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http" {
  count                 = var.enable_http_redirect ? 1 : 0
  name                  = local.http_fw_rule_name
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_address            = google_compute_global_address.static_ip.id
  target                = google_compute_target_http_proxy.redirect[0].id
  port_range            = "80"
}
