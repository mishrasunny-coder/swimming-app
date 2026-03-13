project_id  = "swim-stage-123185"
region      = "us-central1"
environment = "stage"

# Replace with your actual staging domain
domain_name = "swim-stage.ssms.info"

github_repo = "mishrasunny-coder/swimming-app"

access_mode = "ip_restricted"

lb_name_prefix = "swim-stage"

enable_http_redirect = true

# Set allowed_ip_ranges in a local override file (terraform.tfvars.local)
# or via -var to permit your current IP:
#   allowed_ip_ranges = ["x.x.x.x/32"]
#
# If you later switch staging back to IAP, also set:
#   access_mode            = "iap"
#   iap_access_group_email = "group@your-managed-domain"
