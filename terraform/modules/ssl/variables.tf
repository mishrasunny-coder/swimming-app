variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "cert_name" {
  description = "Name of the managed SSL certificate"
  type        = string
}

variable "domain" {
  description = "Domain name for the managed SSL certificate"
  type        = string
}
