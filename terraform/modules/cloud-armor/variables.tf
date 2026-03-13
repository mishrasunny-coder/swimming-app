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

variable "policy_mode" {
  description = "Cloud Armor behavior mode: ip_restricted or iap_fronted"
  type        = string
  default     = "ip_restricted"

  validation {
    condition     = contains(["ip_restricted", "iap_fronted"], var.policy_mode)
    error_message = "policy_mode must be one of: ip_restricted, iap_fronted."
  }
}
