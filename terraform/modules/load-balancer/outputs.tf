output "static_ip_address" {
  description = "Reserved static IP address (point your DNS A record here)"
  value       = google_compute_global_address.static_ip.address
}

output "static_ip_name" {
  description = "Name of the static IP resource"
  value       = google_compute_global_address.static_ip.name
}

output "backend_service_name" {
  description = "Name of the backend service"
  value       = google_compute_backend_service.default.name
}

output "backend_service_self_link" {
  description = "Self-link of the backend service"
  value       = google_compute_backend_service.default.self_link
}

output "neg_name" {
  description = "Name of the serverless NEG"
  value       = google_compute_region_network_endpoint_group.serverless.name
}

output "url_map_name" {
  description = "Name of the URL map"
  value       = google_compute_url_map.default.name
}
