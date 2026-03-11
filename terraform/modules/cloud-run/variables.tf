variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run"
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "swimming-app"
}

variable "runtime_sa_email" {
  description = "Email of the runtime service account"
  type        = string
}

variable "bucket_name" {
  description = "GCS bucket name to mount as volume"
  type        = string
}

variable "initial_image" {
  description = "Initial container image (only used on first creation; GitHub Actions manages image updates after)"
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello:latest"
}

variable "port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "data_path" {
  description = "Value for SWIM_DATA_PATH environment variable"
  type        = string
  default     = "/mnt/data/swim_data.csv"
}

variable "ingress" {
  description = "Ingress traffic setting"
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

variable "allow_unauthenticated" {
  description = "Grant allUsers roles/run.invoker (required for LB access model)"
  type        = bool
  default     = true
}
