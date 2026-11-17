#!/usr/bin/env bash
# Builds catalog-service and Aegis for x86 nodes and pushes them to ECR; prints the --registry for setup.sh.
set -euo pipefail
cd "$(dirname "$0")/.."

REGION="us-east-1"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
HOST="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
REGISTRY="$HOST/aegis"

for repository in catalog-service aegis; do
  if ! aws ecr describe-repositories --region "$REGION" --repository-names "aegis/$repository" >/dev/null 2>&1; then
    aws ecr create-repository --region "$REGION" --repository-name "aegis/$repository" >/dev/null
  fi
done
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$HOST"

docker build --platform linux/amd64 -t "$REGISTRY/catalog-service:latest" -f services/catalog-service/Dockerfile .
docker push "$REGISTRY/catalog-service:latest"
docker build --platform linux/amd64 -t "$REGISTRY/aegis:latest" -f app/Dockerfile app
docker push "$REGISTRY/aegis:latest"

echo
echo "Pushed. Next: scripts/setup.sh --aegis --registry $REGISTRY"
