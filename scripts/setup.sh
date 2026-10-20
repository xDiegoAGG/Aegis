#!/usr/bin/env bash
# Brings up or repairs the whole environment and checks it. Safe to run many times.
# Usage: scripts/setup.sh [--hpa aegis|baseline] [--build]
set -euo pipefail
cd "$(dirname "$0")/.."

PROMETHEUS_CHART_VERSION="91.7.0"
TRAEFIK_CHART_VERSION="41.7.1"
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

if [ "$HPA" != "aegis" ] && [ "$HPA" != "baseline" ]; then
  echo "--hpa must be aegis or baseline"
  exit 1
fi

step() {
  echo
  echo "==> $*"
}

for tool in kubectl helm python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing tool: $tool"
    exit 1
  fi
done

# minikube only: create or start it, enable metrics-server and build the image inside it.
# A stopped cluster is started with the size it already has; on a new machine it is created, and MINIKUBE_CPUS and MINIKUBE_MEMORY change its size.
ON_MINIKUBE="no"
CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
  ON_MINIKUBE="yes"
elif command -v minikube >/dev/null 2>&1 && { [ -z "$CONTEXT" ] || [ "$CONTEXT" = "minikube" ]; }; then
  step "Starting minikube"
  HOST_STATE="$(minikube status --format '{{.Host}}' 2>/dev/null || true)"
  if [ "$HOST_STATE" = "Stopped" ]; then
    minikube start
  else
    minikube start --driver=docker --kubernetes-version=v1.37.0 --cpus="${MINIKUBE_CPUS:-2}" --memory="${MINIKUBE_MEMORY:-4g}"
  fi
  ON_MINIKUBE="yes"
fi
if [ "$ON_MINIKUBE" = "yes" ]; then
  kubectl config use-context minikube >/dev/null
  step "metrics-server"
  minikube addons enable metrics-server >/dev/null
  if [ "$BUILD" = "yes" ] || ! minikube image ls | grep -q "docker.io/library/$IMAGE"; then
    step "Building $IMAGE inside minikube"
    minikube image build -t "$IMAGE" -f services/catalog-service/Dockerfile .
    BUILD="yes"
  fi
  if ! minikube image ls | grep -q "grafana/k6:2.3.0"; then
    step "Downloading the k6 image (so the first load does not wait for it)"
    minikube image pull grafana/k6:2.3.0 || true
  fi
fi

step "Prometheus (kube-prometheus-stack $PROMETHEUS_CHART_VERSION)"
if ! helm repo list 2>/dev/null | grep -q "^prometheus-community"; then
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
fi
if ! helm search repo prometheus-community/kube-prometheus-stack --version "$PROMETHEUS_CHART_VERSION" | grep -q kube-prometheus-stack; then
  helm repo update prometheus-community
fi
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  --version "$PROMETHEUS_CHART_VERSION" --namespace monitoring --create-namespace \
  -f kubernetes/helm/prometheus-values.yaml --wait --timeout 10m

step "Traefik (chart $TRAEFIK_CHART_VERSION)"
if ! helm repo list 2>/dev/null | grep -q "^traefik"; then
  helm repo add traefik https://traefik.github.io/charts
fi
if ! helm search repo traefik/traefik --version "$TRAEFIK_CHART_VERSION" | grep -q "traefik/traefik"; then
  helm repo update traefik
fi
helm upgrade --install traefik traefik/traefik \
  --version "$TRAEFIK_CHART_VERSION" --namespace traefik --create-namespace \
  -f kubernetes/helm/traefik-values.yaml --wait --timeout 5m

step "DynamoDB Local and the books table"
kubectl delete job seed-books --ignore-not-found >/dev/null
kubectl apply -f kubernetes/dynamodb/dynamodb-local.yaml
kubectl rollout status deploy/dynamodb-local --timeout=600s
kubectl apply -f kubernetes/dynamodb/seed-books-job.yaml
kubectl wait --for=condition=complete job/seed-books --timeout=300s
kubectl logs job/seed-books

step "catalog-service"
kubectl apply -f kubernetes/catalog-service/
if [ "$BUILD" = "yes" ]; then
  kubectl rollout restart deploy/catalog-service
fi
kubectl rollout status deploy/catalog-service --timeout=600s

step "HPA ($HPA)"
kubectl apply -f "kubernetes/hpa/$HPA.yaml"

step "Removing finished load Jobs"
for job in load-linear load-fluctuating aegis-calibration-load; do
  kubectl delete job "$job" --ignore-not-found
done

step "Checking the environment"
python3 scripts/check_env.py --wait 300
