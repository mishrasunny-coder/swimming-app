output "certificate_self_link" {
  description = "Self-link of the managed SSL certificate"
  value       = google_compute_managed_ssl_certificate.cert.self_link
}

output "certificate_id" {
  description = "ID of the managed SSL certificate"
  value       = google_compute_managed_ssl_certificate.cert.id
}

output "certificate_name" {
  description = "Name of the managed SSL certificate"
  value       = google_compute_managed_ssl_certificate.cert.name
}
