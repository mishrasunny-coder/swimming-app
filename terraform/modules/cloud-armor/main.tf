resource "google_compute_security_policy" "policy" {
  name    = var.policy_name
  project = var.project_id

  dynamic "rule" {
    for_each = var.policy_mode == "ip_restricted" && length(var.allowed_ip_ranges) > 0 ? [1] : []
    content {
      action   = "allow"
      priority = 1000

      match {
        versioned_expr = "SRC_IPS_V1"
        config {
          src_ip_ranges = var.allowed_ip_ranges
        }
      }

      description = "Allow traffic from specified IP ranges"
    }
  }

  rule {
    action   = var.policy_mode == "iap_fronted" ? "allow" : "deny(403)"
    priority = 2147483647

    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }

    description = var.policy_mode == "iap_fronted" ? "Default allow so IAP can enforce identity" : "Default deny all"
  }
}
