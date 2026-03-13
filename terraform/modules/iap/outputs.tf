output "access_group_member" {
  description = "IAM member string for the Google Group granted IAP access"
  value       = local.access_group_member
}

output "iap_service_agent_email" {
  description = "Email of the IAP service agent"
  value       = local.iap_service_agent_email
}

output "iap_service_agent_member" {
  description = "IAM member for the IAP service agent"
  value       = local.iap_service_agent_member
}
