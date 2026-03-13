variable "project_id" {
  description = "GCP project ID for production"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "domain_name" {
  description = "Domain name for the managed SSL certificate"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format"
  type        = string
}

variable "allowed_ip_ranges" {
  description = "IP CIDR ranges to allow through Cloud Armor when access_mode is ip_restricted. Set in terraform.tfvars.local or via -var flag."
  type        = list(string)
  default     = []
}

variable "access_mode" {
  description = "Application access mode: ip_restricted or iap"
  type        = string
  default     = "iap"

  validation {
    condition     = contains(["ip_restricted", "iap"], var.access_mode)
    error_message = "access_mode must be one of: ip_restricted, iap."
  }
}

variable "iap_access_group_email" {
  description = "Google Group email granted access through IAP"
  type        = string
}

variable "iap_oauth_client_id" {
  description = "OAuth client ID used by IAP"
  type        = string
  default     = ""
  sensitive   = true
}

variable "iap_oauth_client_secret" {
  description = "OAuth client secret used by IAP"
  type        = string
  default     = ""
  sensitive   = true
}

variable "lb_name_prefix" {
  description = "Prefix for all load balancer resource names"
  type        = string
  default     = "swim-prod"
}

variable "enable_http_redirect" {
  description = "Whether to create HTTP-to-HTTPS redirect"
  type        = bool
  default     = true
}
