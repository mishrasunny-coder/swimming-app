variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCS bucket location"
  type        = string
}

variable "bucket_name" {
  description = "Name of the GCS bucket for swim data"
  type        = string
}

variable "runtime_sa_email" {
  description = "Email of the runtime service account to grant objectViewer"
  type        = string
}
