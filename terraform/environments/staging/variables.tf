variable "project_id" {
  description = "GCP project ID for staging"
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
  default     = "stage"
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
  description = "IP CIDR ranges to allow through Cloud Armor. Set in terraform.tfvars.local or via -var flag."
  type        = list(string)
  default     = []
}

variable "lb_name_prefix" {
  description = "Prefix for all load balancer resource names"
  type        = string
  default     = "swim-stage"
}

variable "enable_http_redirect" {
  description = "Whether to create HTTP-to-HTTPS redirect"
  type        = bool
  default     = true
}
