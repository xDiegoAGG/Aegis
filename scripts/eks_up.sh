#!/usr/bin/env bash
# Creates the EKS cluster of infra/eks/cluster.yaml (~15-20 min, ~0.20 USD/h) and points kubectl to it.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${EKS_ROLE:-}" ]; then
  echo "Set EKS_ROLE to the existing IAM role for the cluster and the nodes, e.g. EKS_ROLE=my-eks-role $0"
  exit 1
fi
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ROLE_ARN="arn:aws:iam::$ACCOUNT_ID:role/$EKS_ROLE"
REGION="us-east-1"
CONFIG="$(mktemp)"
trap 'rm -f "$CONFIG"' EXIT
sed "s#ROLE_ARN#$ROLE_ARN#g" infra/eks/cluster.yaml > "$CONFIG"

if eksctl get cluster --name aegis --region "$REGION" >/dev/null 2>&1; then
  echo "Cluster aegis already exists"
else
  eksctl create cluster -f "$CONFIG"
fi
aws eks update-kubeconfig --name aegis --region "$REGION"
kubectl get nodes
