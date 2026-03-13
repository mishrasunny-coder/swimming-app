project_id  = "swim-prod-123185"
region      = "us-central1"
environment = "prod"

# Replace with your actual production domain
domain_name = "swim-prod.ssms.info"

github_repo = "mishrasunny-coder/swimming-app"

access_mode            = "iap"
iap_access_group_email = "swimming-app-prod-access@ssms.info"

lb_name_prefix = "swim-prod"

enable_http_redirect = true

# If you need to temporarily switch back to IP-restricted access, override:
#   access_mode       = "ip_restricted"
#   allowed_ip_ranges = ["x.x.x.x/32"]
#
# For IAP mode, set these as GitHub Environment secrets mapped to TF_VAR_*:
# - TF_VAR_iap_oauth_client_id
# - TF_VAR_iap_oauth_client_secret
