output "enabled_services" {
  description = "Set of enabled API services"
  value       = { for k, v in google_project_service.enabled : k => v.service }
}
