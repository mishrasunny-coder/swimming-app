output "repository_id" {
  description = "ID of the Artifact Registry repository"
  value       = google_artifact_registry_repository.repo.repository_id
}

output "repository_name" {
  description = "Full resource name of the repository"
  value       = google_artifact_registry_repository.repo.name
}

output "repository_url" {
  description = "Docker registry URL for this repository"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.repository_id}"
}
