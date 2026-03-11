variable "project_id" {
  description = "GCP project ID for dev"
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
  default     = "dev"
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
  description = "IP CIDR ranges to allow through Cloud Armor. Set in terraform.tfvars.local (gitignored) or via -var flag."
  type        = list(string)
  default     = []
}

variable "lb_name_prefix" {
  description = "Prefix for all load balancer resource names"
  type        = string
  default     = "swim-dev"
}

variable "ar_reader_members" {
  description = "IAM members to grant Artifact Registry reader (cross-project stage/prod SAs and service agents)"
  type        = list(string)
  default     = []
}

variable "enable_http_redirect" {
  description = "Whether to create HTTP-to-HTTPS redirect"
  type        = bool
  default     = true
}
