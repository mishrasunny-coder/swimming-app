project_id  = "swim-dev-123185"
region      = "us-central1"
environment = "dev"

# Replace with your actual dev domain
domain_name = "swim-dev.ssms.info"

github_repo = "mishrasunny-coder/swimming-app"

access_mode = "ip_restricted"

lb_name_prefix = "swim-dev"

enable_http_redirect = true

# Cross-project Artifact Registry readers:
# Stage and prod Cloud Run service agents + deployer SAs + runtime SAs
# These allow stage/prod to pull images from the dev Artifact Registry.
ar_reader_members = [
  "serviceAccount:service-219789203394@serverless-robot-prod.iam.gserviceaccount.com",
  "serviceAccount:swimming-app-stage-deployer@swim-stage-123185.iam.gserviceaccount.com",
  "serviceAccount:swimming-app-stage-sa@swim-stage-123185.iam.gserviceaccount.com",
  "serviceAccount:service-1015197512963@serverless-robot-prod.iam.gserviceaccount.com",
  "serviceAccount:swimming-app-prod-deployer@swim-prod-123185.iam.gserviceaccount.com",
  "serviceAccount:swimming-app-prod-sa@swim-prod-123185.iam.gserviceaccount.com",
]

# Set allowed_ip_ranges in a local auto-loaded override file
# (terraform.tfvars.local.auto.tfvars) or via -var to permit your current IP:
#   allowed_ip_ranges = ["x.x.x.x/32"]
#
# If you later switch dev back to IAP, also set:
#   access_mode            = "iap"
#   iap_access_group_email = "group@your-managed-domain"
