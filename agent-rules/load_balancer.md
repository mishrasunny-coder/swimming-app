# Load Balancer Setup (Cloud Run + IP-Restricted Public Entry)

This file covers only internet entry via External HTTPS Load Balancer for an already deployed Cloud Run service.

For project creation, build/push, and Cloud Run deployment, use:
- `agent-rules/deployment.md`

## Goal

Expose app using:
- External HTTPS Load Balancer
- Static external IP
- Custom domain + managed SSL
- Cloud Armor: allow only your IP, deny all others

Working access model used here:
- Cloud Run ingress: `internal-and-cloud-load-balancing`
- Cloud Run IAM: `allUsers` has `roles/run.invoker`
- Security boundary is enforced at Cloud Armor (IP allowlist)

## 1) Set Variables

```bash
export PROJECT_ID="your-dev-project-id"      # change per env
export REGION="us-central1"
export SERVICE="swimming-app"
export LB_NAME="your-dev-lb"
export NEG_NAME="your-dev-neg"
export BACKEND_NAME="your-dev-backend"
export URL_MAP_NAME="your-dev-url-map"
export PROXY_NAME="your-dev-https-proxy"
export FORWARDING_RULE_NAME="your-dev-fw"
export STATIC_IP_NAME="your-dev-ip"
export SSL_CERT_NAME="your-dev-managed-cert"
export DOMAIN_NAME="app-dev.example.com"     # required for managed SSL cert
export ARMOR_POLICY_NAME="your-dev-armor"
export YOUR_PUBLIC_IP="x.x.x.x/32"       # your current public IP CIDR

gcloud config set project "$PROJECT_ID"
```

## 2) Create/Verify Managed SSL Certificate

```bash
gcloud compute ssl-certificates describe "$SSL_CERT_NAME" --global >/dev/null 2>&1 || \
gcloud compute ssl-certificates create "$SSL_CERT_NAME" \
  --domains="$DOMAIN_NAME" \
  --global
```

Check status (wait until `ACTIVE`):
```bash
gcloud compute ssl-certificates describe "$SSL_CERT_NAME" --global --format='value(managed.status,managed.domainStatus)'
```

## 3) Reserve Static IP

```bash
gcloud compute addresses describe "$STATIC_IP_NAME" --global >/dev/null 2>&1 || \
gcloud compute addresses create "$STATIC_IP_NAME" --global
gcloud compute addresses describe "$STATIC_IP_NAME" --global --format='value(address)'
```

Use the returned IP in your DNS `A` record for `$DOMAIN_NAME`.

## 4) Enable Required APIs

```bash
gcloud services enable compute.googleapis.com certificatemanager.googleapis.com --project="$PROJECT_ID"
```

## 5) Cloud Run Access Configuration (Required)

Restrict network ingress to LB path, then allow invocation at IAM layer:
```bash
gcloud run services update "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --ingress=internal-and-cloud-load-balancing

gcloud run services add-iam-policy-binding "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --member="allUsers" \
  --role="roles/run.invoker"
```

Notes:
- This does not make open internet access possible by itself because ingress is LB-only.
- Cloud Armor rules on LB control who can reach the app.

## 6) Create Serverless NEG

```bash
gcloud compute network-endpoint-groups create "$NEG_NAME" \
  --region="$REGION" \
  --network-endpoint-type=serverless \
  --cloud-run-service="$SERVICE"
```

## 7) Configure Cloud Armor (Allow Only Your IP)

```bash
gcloud compute security-policies describe "$ARMOR_POLICY_NAME" >/dev/null 2>&1 || \
gcloud compute security-policies create "$ARMOR_POLICY_NAME"
```

Allow your IP at priority `1000`:
```bash
gcloud compute security-policies rules update 1000 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="$YOUR_PUBLIC_IP" \
  --action=allow || \
gcloud compute security-policies rules create 1000 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="$YOUR_PUBLIC_IP" \
  --action=allow
```

Default deny-all at priority `2147483647`:
```bash
gcloud compute security-policies rules update 2147483647 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="*" \
  --action=deny-403 || \
gcloud compute security-policies rules create 2147483647 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="*" \
  --action=deny-403
```

## 8) Create Backend Service + Attach NEG + Armor

```bash
gcloud compute backend-services create "$BACKEND_NAME" \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --protocol=HTTP
  ```

Attaches your serverless NEG (which points to Cloud Run service) to that backend service.
This is the actual wiring from LB backend to Cloud Run.
```bash
gcloud compute backend-services add-backend "$BACKEND_NAME" \
  --global \
  --network-endpoint-group="$NEG_NAME" \
  --network-endpoint-group-region="$REGION"
```

Attaches Cloud Armor policy to backend service.
All requests through LB are evaluated by that policy (allow your IP, deny others).
```bash
gcloud compute backend-services update "$BACKEND_NAME" \
  --global \
  --security-policy="$ARMOR_POLICY_NAME"
```

## 9) URL Map + HTTPS Certificate + HTTPS Proxy + Forwarding Rule

```bash
gcloud compute url-maps create "$URL_MAP_NAME" \
  --default-service="$BACKEND_NAME"
```

```bash
gcloud compute target-https-proxies create "$PROXY_NAME" \
  --ssl-certificates="$SSL_CERT_NAME" \
  --url-map="$URL_MAP_NAME"
```

```bash
gcloud compute forwarding-rules create "$FORWARDING_RULE_NAME" \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --address="$STATIC_IP_NAME" \
  --target-https-proxy="$PROXY_NAME" \
  --ports=443
```

## 10) DNS

Point DNS `A` record (`$DOMAIN_NAME`) to the static IP from step 3.

Managed cert becomes `ACTIVE` only after DNS is correct and propagated.

## 11) Verify

```bash
gcloud compute ssl-certificates describe "$SSL_CERT_NAME" --global --format='value(managed.status,managed.domainStatus)'
gcloud compute backend-services describe "$BACKEND_NAME" --global --format='value(securityPolicy)'
gcloud compute security-policies describe "$ARMOR_POLICY_NAME" --format='yaml(rules)'
gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='yaml(spec.ingress,status.url)'
gcloud run services get-iam-policy "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='yaml(bindings)'
```

Then open:
- `https://$DOMAIN_NAME`

Expected:
- Access from your allowed IP works
- Other IPs receive 403

## 12) Rotate Allowed IP

If your IP changes:
```bash
export YOUR_PUBLIC_IP="$(curl -4 -s https://ifconfig.me)/32"
gcloud compute security-policies rules update 1000 \
  --security-policy="$ARMOR_POLICY_NAME" \
  --src-ip-ranges="$YOUR_PUBLIC_IP" \
  --action=allow
```

## 13) Optional: HTTP to HTTPS Redirect

```bash
export HTTP_PROXY_NAME="swim-dev-http-proxy"
export HTTP_FW_RULE_NAME="swim-dev-http-fw"

gcloud compute url-maps create "${URL_MAP_NAME}-http-redirect" \
  --default-url-redirect-https-redirect \
  --default-url-redirect-strip-query=false

gcloud compute target-http-proxies create "$HTTP_PROXY_NAME" \
  --url-map="${URL_MAP_NAME}-http-redirect"

gcloud compute forwarding-rules create "$HTTP_FW_RULE_NAME" \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --address="$STATIC_IP_NAME" \
  --target-http-proxy="$HTTP_PROXY_NAME" \
  --ports=80
```

## 14) Repeat for Stage/Prod

Repeat with environment-specific names and IPs:
- `swim-stage-*`
- `swim-prod-*`
