variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "policy_name" {
  description = "Name of the Cloud Armor security policy"
  type        = string
}

variable "allowed_ip_ranges" {
  description = "List of IP CIDR ranges to allow (e.g. [\"x.x.x.x/32\"]). Override via terraform.tfvars.local or -var flag."
  type        = list(string)
  default     = []
}
