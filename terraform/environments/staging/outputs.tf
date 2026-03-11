output "cloud_run_service_url" {
  description = "Cloud Run service URL"
  value       = module.cloud_run.service_url
}

output "static_ip_address" {
  description = "Static IP address for DNS A record"
  value       = module.load_balancer.static_ip_address
}

output "wif_provider_name" {
  description = "WIF provider resource name (use as GitHub secret WIF_PROVIDER_STAGING)"
  value       = module.wif.provider_name
}

output "runtime_sa_email" {
  description = "Runtime service account email"
  value       = module.service_accounts.runtime_sa_email
}

output "deploy_sa_email" {
  description = "Deployer service account email (use as GitHub secret WIF_SERVICE_ACCOUNT_STAGING)"
  value       = module.service_accounts.deploy_sa_email
}

output "bucket_name" {
  description = "GCS bucket name for swim data"
  value       = module.storage.bucket_name
}

output "cloud_armor_policy_name" {
  description = "Cloud Armor policy name"
  value       = module.cloud_armor.policy_name
}
