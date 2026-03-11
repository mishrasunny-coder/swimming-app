variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "pool_id" {
  description = "Workload Identity Pool ID"
  type        = string
  default     = "github-pool"
}

variable "pool_display_name" {
  description = "Display name for the WIF pool"
  type        = string
  default     = "GitHub Actions Pool"
}

variable "provider_id" {
  description = "Workload Identity Pool Provider ID"
  type        = string
  default     = "github-provider"
}

variable "provider_display_name" {
  description = "Display name for the WIF provider"
  type        = string
  default     = "GitHub Actions Provider"
}

variable "github_repo" {
  description = "GitHub repository in owner/repo format"
  type        = string
}

variable "deploy_sa_id" {
  description = "Full resource ID of the deploy service account to bind WIF to"
  type        = string
}

variable "attribute_condition" {
  description = "CEL expression for provider attribute condition"
  type        = string
}
