variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, stage, prod)"
  type        = string
}

variable "deploy_sa_account_id" {
  description = "Account ID for the deploy/build service account"
  type        = string
}

variable "deploy_sa_display_name" {
  description = "Display name for the deploy/build service account"
  type        = string
}

variable "deploy_sa_project_roles" {
  description = "Project-level IAM roles to grant to the deploy SA"
  type        = list(string)
  default     = ["roles/run.admin"]
}

variable "grant_self_impersonation" {
  description = "Whether the deploy SA needs roles/iam.serviceAccountUser on itself (required for Cloud Build --service-account in dev)"
  type        = bool
  default     = false
}
