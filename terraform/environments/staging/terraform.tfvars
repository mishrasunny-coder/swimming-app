project_id  = "swim-stage-123185"
region      = "us-central1"
environment = "stage"

# Replace with your actual staging domain
domain_name = "swim-stage.ssms.info"

github_repo = "mishrasunny-coder/swimming-app"

lb_name_prefix = "swim-stage"

enable_http_redirect = true

# IMPORTANT: Set allowed_ip_ranges in a local override file (terraform.tfvars.local)
# or via -var flag to avoid committing your IP address:
#   allowed_ip_ranges = ["x.x.x.x/32"]
