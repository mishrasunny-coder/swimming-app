variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "services" {
  description = "List of GCP API services to enable"
  type        = list(string)
  default = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "compute.googleapis.com",
    "certificatemanager.googleapis.com",
  ]
}
