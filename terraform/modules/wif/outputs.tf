output "pool_name" {
  description = "Full resource name of the Workload Identity Pool"
  value       = google_iam_workload_identity_pool.github.name
}

output "pool_id" {
  description = "Workload Identity Pool ID"
  value       = google_iam_workload_identity_pool.github.workload_identity_pool_id
}

output "provider_name" {
  description = "Full resource name of the WIF provider (use as WIF_PROVIDER GitHub secret)"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "project_number" {
  description = "GCP project number (used for WIF bindings)"
  value       = data.google_project.current.number
}
