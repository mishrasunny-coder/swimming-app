output "policy_self_link" {
  description = "Self-link of the Cloud Armor security policy"
  value       = google_compute_security_policy.policy.self_link
}

output "policy_name" {
  description = "Name of the Cloud Armor security policy"
  value       = google_compute_security_policy.policy.name
}

output "policy_id" {
  description = "ID of the Cloud Armor security policy"
  value       = google_compute_security_policy.policy.id
}
