#!/usr/bin/env bash
# Brings up or repairs the whole environment and checks it. Safe to run many times.
# Usage: scripts/setup.sh [--hpa aegis|aegis-metric|baseline] [--build] [--aegis] [--pod-cpu VALUE]
#   --hpa aegis         Aegis writes minReplicas (default)
#   --hpa aegis-metric  the HPA reads aegis_target_replicas through prometheus-adapter (needs --aegis)
#   --hpa baseline      plain HPA on CPU 70%, without Aegis
#   --aegis             also run Aegis in the cluster (aegis-system)
#   --pod-cpu 60m       CPU per catalog-service pod (default: keep the current one, 200m on a new cluster);
#                       lower it on fast machines so one pod serves 20-30 req/s
set -euo pipefail
cd "$(dirname "$0")/.."

PROMETHEUS_CHART_VERSION="91.7.0"
PROMETHEUS_ADAPTER_CHART_VERSION="5.3.0"
TRAEFIK_CHART_VERSION="41.7.1"
IMAGE="catalog-service:local"
AEGIS_IMAGE="aegis:local"
HPA="aegis"
BUILD="no"
AEGIS="no"
POD_CPU=""

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
    --aegis)
      AEGIS="yes"
      shift
      ;;
    --pod-cpu)
      POD_CPU="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ "$HPA" != "aegis" ] && [ "$HPA" != "aegis-metric" ] && [ "$HPA" != "baseline" ]; then
  echo "--hpa must be aegis, aegis-metric or baseline"
  exit 1
fi
if [ "$HPA" = "aegis-metric" ] && [ "$AEGIS" != "yes" ]; then
  echo "--hpa aegis-metric needs --aegis: Prometheus can only scrape the Aegis that runs in the cluster"
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

# Create or start minikube (MINIKUBE_CPUS/MINIKUBE_MEMORY size a new one), metrics-server, images.
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
  if [ "$AEGIS" = "yes" ] && { [ "$BUILD" = "yes" ] || ! minikube image ls | grep -q "docker.io/library/$AEGIS_IMAGE"; }; then
    step "Building $AEGIS_IMAGE inside minikube"
    # -f is relative to the build context (app/).
    minikube image build -t "$AEGIS_IMAGE" -f Dockerfile app
    if ! minikube image ls | grep -q "docker.io/library/$AEGIS_IMAGE"; then
      echo "The $AEGIS_IMAGE image was not built"
      exit 1
    fi
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

step "Recording rules (aegis:catalog_p95_latency, aegis:catalog_rps, aegis:replica_count, ...)"
kubectl apply -f kubernetes/monitoring/recording-rules.yaml

step "prometheus-adapter $PROMETHEUS_ADAPTER_CHART_VERSION (Custom Metrics API for the Aegis metrics)"
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
  --version "$PROMETHEUS_ADAPTER_CHART_VERSION" --namespace monitoring \
  -f kubernetes/helm/prometheus-adapter-values.yaml --wait --timeout 5m

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
if [ -z "$POD_CPU" ]; then
  POD_CPU="$(kubectl get deploy catalog-service -o jsonpath='{.spec.template.spec.containers[0].resources.limits.cpu}' 2>/dev/null || true)"
fi
kubectl apply -f kubernetes/catalog-service/
if [ -n "$POD_CPU" ] && [ "$POD_CPU" != "200m" ]; then
  echo "Pod CPU: $POD_CPU (request = limit)"
  kubectl set resources deploy/catalog-service --requests=cpu="$POD_CPU" --limits=cpu="$POD_CPU"
fi
if [ "$BUILD" = "yes" ]; then
  kubectl rollout restart deploy/catalog-service
fi
kubectl rollout status deploy/catalog-service --timeout=600s

step "HPA ($HPA)"
kubectl apply -f "kubernetes/hpa/$HPA.yaml"

if [ "$AEGIS" = "yes" ]; then
  step "Aegis in the cluster (aegis-system)"
  MODE="min_replicas"
  if [ "$HPA" = "aegis-metric" ]; then
    MODE="metric"
  fi
  kubectl apply -f kubernetes/aegis/namespace.yaml
  kubectl create configmap aegis-config -n aegis-system --from-file=config.yaml=app/config.yaml \
    --dry-run=client -o yaml | kubectl apply -f -
  kubectl apply -f kubernetes/aegis/rbac.yaml -f kubernetes/aegis/deployment.yaml -f kubernetes/aegis/servicemonitor.yaml
  kubectl set env -n aegis-system deploy/aegis AEGIS_ACTUATOR_MODE="$MODE" >/dev/null
  if [ "$BUILD" = "yes" ]; then
    kubectl rollout restart -n aegis-system deploy/aegis
  fi
  if kubectl get configmap aegis-calibration >/dev/null 2>&1; then
    kubectl rollout status -n aegis-system deploy/aegis --timeout=180s
    echo "Dashboard: kubectl port-forward -n aegis-system svc/aegis 8080  ->  http://localhost:8080"
  else
    # Off until calibrated (it would crash-loop and disturb the calibration).
    kubectl scale -n aegis-system deploy/aegis --replicas=0
    echo "Aegis stays off until the calibration exists: run python3 -m aegis.calibrate from app/, then"
    echo "kubectl scale -n aegis-system deploy/aegis --replicas=1"
  fi
elif kubectl get deploy aegis -n aegis-system >/dev/null 2>&1; then
  step "Stopping the in-cluster Aegis (run without --aegis)"
  kubectl scale -n aegis-system deploy/aegis --replicas=0
fi

step "Removing finished load Jobs"
for job in load-linear load-fluctuating aegis-calibration-load; do
  kubectl delete job "$job" --ignore-not-found
done

step "Checking the environment"
python3 scripts/check_env.py --wait 300
