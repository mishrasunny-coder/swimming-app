output "cloud_run_service_url" {
  description = "Cloud Run service URL"
  value       = module.cloud_run.service_url
}

output "static_ip_address" {
  description = "Static IP address for DNS A record"
  value       = module.load_balancer.static_ip_address
}

output "wif_provider_name" {
  description = "WIF provider resource name (use as GitHub secret WIF_PROVIDER)"
  value       = module.wif.provider_name
}

output "runtime_sa_email" {
  description = "Runtime service account email"
  value       = module.service_accounts.runtime_sa_email
}

output "deploy_sa_email" {
  description = "Deploy/build service account email (use as GitHub secret WIF_SERVICE_ACCOUNT)"
  value       = module.service_accounts.deploy_sa_email
}

output "artifact_registry_url" {
  description = "Artifact Registry Docker URL"
  value       = module.artifact_registry.repository_url
}

output "bucket_name" {
  description = "GCS bucket name for swim data"
  value       = module.storage.bucket_name
}

output "backend_service_name" {
  description = "Backend service name (for GitHub variable BACKEND_SERVICE_NAME)"
  value       = module.load_balancer.backend_service_name
}

output "cloud_armor_policy_name" {
  description = "Cloud Armor policy name (for GitHub variable ARMOR_POLICY_NAME)"
  value       = module.cloud_armor.policy_name
}
