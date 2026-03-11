variable "project_id" {
  description = "GCP project ID where the Artifact Registry repo lives"
  type        = string
}

variable "region" {
  description = "Region for the Artifact Registry repository"
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry repository ID"
  type        = string
}

variable "writer_members" {
  description = "IAM members to grant artifactregistry.writer (e.g. build SA)"
  type        = list(string)
  default     = []
}

variable "reader_members" {
  description = "IAM members to grant artifactregistry.reader (e.g. cross-project deployer/service-agent SAs)"
  type        = list(string)
  default     = []
}
