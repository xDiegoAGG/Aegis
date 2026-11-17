#!/usr/bin/env bash
# Builds the monitor against the Aegis API of the EKS load balancer, publishes it as an S3 website (HTTP)
# and lets that site call the API (CORS).
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="us-east-1"
BUCKET="${MONITOR_BUCKET:-aegis-monitor}"
SITE="http://$BUCKET.s3-website-$REGION.amazonaws.com"
API_HOST="$(kubectl get svc traefik -n traefik -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')"
if [ -z "$API_HOST" ]; then
  echo "Traefik has no load balancer yet: run scripts/setup.sh --registry ... on EKS first"
  exit 1
fi
API="http://$API_HOST:8090"

if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=false,RestrictPublicBuckets=false
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Sid\":\"ReadSite\",\"Effect\":\"Allow\",\"Principal\":\"*\",\"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]}"
aws s3 website "s3://$BUCKET" --index-document index.html --error-document index.html

(cd monitor && npm ci --no-fund --no-audit && VITE_AEGIS_API_URL="$API" npm run build)
aws s3 sync monitor/dist "s3://$BUCKET" --delete

kubectl create configmap aegis-monitor -n aegis-system --from-literal=allowed_origin="$SITE,http://localhost:5173" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart -n aegis-system deploy/aegis >/dev/null
kubectl rollout status -n aegis-system deploy/aegis --timeout=180s

echo
echo "Monitor: $SITE"
echo "API:     $API/api/state"
