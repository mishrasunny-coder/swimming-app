variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region where the serverless NEG targets Cloud Run"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for all LB resource names (e.g. 'swim-dev')"
  type        = string
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name for the serverless NEG"
  type        = string
}

variable "security_policy_self_link" {
  description = "Self-link of the Cloud Armor security policy to attach to the backend service"
  type        = string
}

variable "ssl_certificate_self_link" {
  description = "Self-link of the managed SSL certificate"
  type        = string
}

variable "enable_http_redirect" {
  description = "Whether to create HTTP-to-HTTPS redirect resources (port 80 → 443)"
  type        = bool
  default     = true
}

variable "enable_iap" {
  description = "Whether to enable IAP on the backend service"
  type        = bool
  default     = false
}

variable "iap_oauth_client_id" {
  description = "OAuth client ID used by IAP"
  type        = string
  default     = ""
}

variable "iap_oauth_client_secret" {
  description = "OAuth client secret used by IAP"
  type        = string
  default     = ""
  sensitive   = true
}
