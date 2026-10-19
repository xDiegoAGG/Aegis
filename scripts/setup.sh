#!/usr/bin/env bash
# Brings up (or repairs) the whole Aegis test environment. Safe to run many times:
# every step checks or applies the desired state, nothing is deleted except finished Jobs.
#
# Usage: scripts/setup.sh [--hpa aegis|baseline] [--build]
#   --hpa aegis      HPA used with Aegis (CPU 95%, no scale-down window). Default.
#   --hpa baseline   plain HPA (CPU 70%), to run tests without Aegis.
#   --build          rebuild the catalog-service image even if it exists (after code changes).
set -euo pipefail
cd "$(dirname "$0")/.."

PROMETHEUS_CHART_VERSION="91.7.0"
IMAGE="catalog-service:local"
HPA="aegis"
BUILD="no"

while [ $# -gt 0 ]; do
  case "$1" in
    --hpa)
      HPA="$2"
      shift 2
      ;;
    --build)
      BUILD="yes"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

case "$HPA" in
  aegis) HPA_FILE="kubernetes/catalog-service-hpa-aegis.yaml" ;;
  baseline) HPA_FILE="kubernetes/catalog-service-hpa.yaml" ;;
  *)
    echo "--hpa must be aegis or baseline"
    exit 1
    ;;
esac

step() {
  echo
  echo "==> $*"
}

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing tool: $1"
    exit 1
  fi
}

require kubectl
require helm
require python3

# --- Cluster ---------------------------------------------------------------
# minikube-only steps. On another cluster (EKS) they are skipped and the image
# must already be in a registry the cluster can pull from.
ON_MINIKUBE="no"
if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
  ON_MINIKUBE="yes"
elif command -v minikube >/dev/null 2>&1 && [ "$(kubectl config current-context 2>/dev/null || true)" = "minikube" ]; then
  step "Starting minikube"
  minikube start
  ON_MINIKUBE="yes"
fi

if [ "$ON_MINIKUBE" = "yes" ]; then
  kubectl config use-context minikube >/dev/null
  step "Enabling metrics-server (the HPA needs it to read CPU)"
  minikube addons enable metrics-server >/dev/null

  if [ "$BUILD" = "yes" ] || ! minikube image ls | grep -q "docker.io/library/$IMAGE"; then
    step "Building $IMAGE inside minikube"
    minikube image build -t "$IMAGE" -f services/catalog-service/Dockerfile .
    BUILD="yes"
  fi
else
  echo "Current context: $(kubectl config current-context). Not minikube: skipping minikube steps."
fi

# --- Prometheus ------------------------------------------------------------
step "Prometheus (kube-prometheus-stack $PROMETHEUS_CHART_VERSION)"
if ! helm repo list 2>/dev/null | grep -q "^prometheus-community"; then
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
fi
if ! helm search repo prometheus-community/kube-prometheus-stack --version "$PROMETHEUS_CHART_VERSION" | grep -q kube-prometheus-stack; then
  helm repo update prometheus-community
fi
INSTALLED_CHART="$(helm list -n monitoring -f '^prometheus$' -o json | python3 -c "
import json, sys
releases = json.load(sys.stdin)
if releases:
    print(releases[0]['chart'])
")"
if [ "$INSTALLED_CHART" = "kube-prometheus-stack-$PROMETHEUS_CHART_VERSION" ]; then
  echo "Already installed"
else
  helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    --version "$PROMETHEUS_CHART_VERSION" --namespace monitoring --create-namespace \
    --wait --timeout 10m
fi

# --- DynamoDB Local and table ----------------------------------------------
step "DynamoDB Local"
kubectl apply -f kubernetes/dynamodb-local.yaml
kubectl rollout status deploy/dynamodb-local --timeout=180s

step "Seeding tb_books"
kubectl delete job seed-books --ignore-not-found >/dev/null
kubectl apply -f kubernetes/seed-books-job.yaml
kubectl wait --for=condition=complete job/seed-books --timeout=180s
kubectl logs job/seed-books

# --- catalog-service -------------------------------------------------------
step "catalog-service"
kubectl apply -f kubernetes/catalog-service.yaml
kubectl apply -f kubernetes/catalog-service-servicemonitor.yaml
if [ "$BUILD" = "yes" ]; then
  # Same tag, new image: restart so the pods use it
  kubectl rollout restart deploy/catalog-service
fi
kubectl rollout status deploy/catalog-service --timeout=180s

step "HPA ($HPA)"
kubectl apply -f "$HPA_FILE"

# --- Leftovers from earlier runs -------------------------------------------
step "Deleting finished k6 Jobs (a finished Job blocks running the test again)"
for job in k6-ramp-demo k6-load-test; do
  ACTIVE="$(kubectl get job "$job" -o jsonpath='{.status.active}' 2>/dev/null || true)"
  if kubectl get job "$job" >/dev/null 2>&1 && [ -z "$ACTIVE" ]; then
    kubectl delete job "$job"
  fi
done

# --- Check -----------------------------------------------------------------
step "Checking the environment"
python3 scripts/check_env.py --wait 120

echo
echo "To run Aegis from this machine, open the Prometheus tunnel in another terminal:"
echo "  kubectl -n monitoring port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090"
