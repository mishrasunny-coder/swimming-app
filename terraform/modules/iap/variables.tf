variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "project_number" {
  description = "GCP project number"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run"
  type        = string
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name protected by IAP"
  type        = string
}

variable "backend_service_name" {
  description = "Backend service name protected by IAP"
  type        = string
}

variable "access_group_email" {
  description = "Google Group email granted access through IAP"
  type        = string
}

variable "enabled" {
  description = "Whether to enable IAP IAM resources"
  type        = bool
  default     = true
}
