project_id  = "swim-prod-123185"
region      = "us-central1"
environment = "prod"

# Replace with your actual production domain
domain_name = "swim-prod.ssms.info"

github_repo = "mishrasunny-coder/swimming-app"

lb_name_prefix = "swim-prod"

enable_http_redirect = true

# IMPORTANT: Set allowed_ip_ranges in a local override file (terraform.tfvars.local)
# or via -var flag to avoid committing your IP address:
#   allowed_ip_ranges = ["x.x.x.x/32"]
