output "runtime_sa_email" {
  description = "Email of the runtime service account"
  value       = google_service_account.runtime.email
}

output "runtime_sa_name" {
  description = "Fully qualified name of the runtime service account"
  value       = google_service_account.runtime.name
}

output "runtime_sa_id" {
  description = "ID of the runtime service account"
  value       = google_service_account.runtime.id
}

output "deploy_sa_email" {
  description = "Email of the deploy/build service account"
  value       = google_service_account.deploy.email
}

output "deploy_sa_name" {
  description = "Fully qualified name of the deploy/build service account"
  value       = google_service_account.deploy.name
}

output "deploy_sa_id" {
  description = "ID of the deploy/build service account"
  value       = google_service_account.deploy.id
}
