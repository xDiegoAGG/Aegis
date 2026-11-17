#!/usr/bin/env bash
# Deletes the EKS cluster and its load balancer, so nothing keeps spending credits.
set -euo pipefail

REGION="us-east-1"
if kubectl config current-context 2>/dev/null | grep -q "aegis"; then
  kubectl delete svc traefik -n traefik --ignore-not-found --wait=true || true
fi
eksctl delete cluster --name aegis --region "$REGION" --wait
