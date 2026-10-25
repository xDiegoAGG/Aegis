import json
import subprocess
import sys
import time
import urllib.parse

PROMETHEUS_PROXY = "/api/v1/namespaces/monitoring/services/prometheus-kube-prometheus-prometheus:9090/proxy"
EXPECTED_BOOKS = 50
DIRECT_URL = "http://localhost:3003/api/books"
TRAEFIK_URL = "http://traefik.traefik.svc.cluster.local/api/books"
FETCH_BOOKS = (
    "fetch('URL')"
    ".then(async (r) => { const body = await r.json(); console.log(r.status, Array.isArray(body) ? body.length : -1); })"
    ".catch((e) => { console.log(0, -1); })"
)


def kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def prometheus_query(query):
    code, out, err = kubectl(["get", "--raw", PROMETHEUS_PROXY + "/api/v1/query?" + urllib.parse.urlencode({"query": query})])
    if code != 0:
        return None
    body = json.loads(out)
    if body.get("status") != "success":
        return None
    return body["data"]["result"]


# Asks for the books from inside the catalog-service pod, directly or through Traefik.
def fetch_books(url):
    code, out, err = kubectl(["exec", "deploy/catalog-service", "--", "node", "-e", FETCH_BOOKS.replace("URL", url)])
    if code != 0:
        return False, "could not run the request inside the pod: " + err
    parts = out.split()
    if len(parts) != 2:
        return False, "unexpected answer: " + out
    status, count = parts
    if status != "200":
        return False, "/api/books returned " + status + " (is the table seeded?)"
    if int(count) != EXPECTED_BOOKS:
        return False, "/api/books returned " + count + " books, expected " + str(EXPECTED_BOOKS)
    return True, str(EXPECTED_BOOKS) + " books"


def check_books():
    return fetch_books(DIRECT_URL)


def check_books_through_traefik():
    return fetch_books(TRAEFIK_URL)


def check_traefik_metrics():
    result = prometheus_query('traefik_entrypoint_requests_total{entrypoint="web"}')
    if result is None:
        return False, "Prometheus did not answer"
    if not result:
        return False, "no Traefik request metrics yet"
    return True, "Traefik counts the requests"


def check_prometheus_target():
    result = prometheus_query('up{namespace="default",service="catalog-service"}')
    if result is None:
        return False, "Prometheus did not answer"
    if not result:
        return False, "catalog-service is not a Prometheus target yet"
    for series in result:
        if series["value"][1] != "1":
            return False, "a catalog-service target is down"
    return True, str(len(result)) + " target(s) up"


def check_replica_metric():
    result = prometheus_query('kube_deployment_status_replicas_ready{deployment="catalog-service"}')
    if result is None:
        return False, "Prometheus did not answer"
    if not result:
        return False, "no kube-state-metrics data for catalog-service"
    return True, "replicas ready = " + result[0]["value"][1]


def check_hpa():
    code, out, err = kubectl(["get", "hpa", "catalog-service", "-o", "json"])
    if code != 0:
        return False, "HPA catalog-service not found"
    hpa = json.loads(out)
    spec = hpa["spec"]
    targets = []
    for metric in spec.get("metrics", []):
        if metric.get("type") == "Resource" and metric["resource"]["name"] == "cpu":
            targets.append("CPU " + str(metric["resource"]["target"].get("averageUtilization", "?")) + "%")
        if metric.get("type") == "Object":
            targets.append(metric["object"]["metric"]["name"])
    for condition in hpa.get("status", {}).get("conditions", []):
        if condition["type"] == "ScalingActive" and condition["status"] != "True":
            return False, "the HPA cannot read its metrics: " + condition.get("message", "")
    return True, ", ".join(targets) + ", minReplicas " + str(spec.get("minReplicas", 1)) + ", maxReplicas " + str(spec["maxReplicas"])


def check_metrics_server():
    code, out, err = kubectl(["top", "pod", "-l", "app=catalog-service", "--no-headers"])
    if code != 0 or not out:
        return False, "metrics-server has no CPU data yet"
    return True, "CPU data available"


def check_recording_rules():
    result = prometheus_query("aegis:replica_count")
    if result is None:
        return False, "Prometheus did not answer"
    if not result:
        return False, "aegis:replica_count has no data yet (kubernetes/monitoring/recording-rules.yaml)"
    return True, "aegis:replica_count = " + result[0]["value"][1]


def check_custom_metrics_api():
    code, out, err = kubectl(["get", "--raw", "/apis/custom.metrics.k8s.io/v1beta1"])
    if code != 0:
        return False, "custom.metrics.k8s.io not available (prometheus-adapter): " + err
    resources = json.loads(out).get("resources", [])
    names = sorted({resource["name"].split("/")[-1] for resource in resources})
    if not names:
        return True, "API up, no Aegis metric yet (they appear when Aegis runs in the cluster)"
    return True, ", ".join(names)


# Only when Aegis runs in the cluster (scripts/setup.sh --aegis); otherwise informative.
def check_aegis_in_cluster():
    code, out, err = kubectl(["get", "deploy", "aegis", "-n", "aegis-system", "-o", "json"])
    if code != 0:
        return True, "not deployed (Aegis runs on this machine)"
    deployment = json.loads(out)
    if deployment["spec"].get("replicas", 1) == 0:
        return True, "scaled to 0 (Aegis runs on this machine)"
    if deployment["status"].get("readyReplicas", 0) < 1:
        return False, "the aegis pod is not Ready (calibrated? kubectl logs -n aegis-system deploy/aegis)"
    result = prometheus_query("aegis_risk")
    if not result:
        return False, "Prometheus has no aegis_risk yet (ServiceMonitor aegis)"
    return True, "running, risk = " + str(round(float(result[0]["value"][1]) * 100, 1)) + "%"


def check_calibration():
    code, out, err = kubectl(["get", "configmap", "aegis-calibration", "-o", "jsonpath={.data.capacity_rps} {.data.startup_time_seconds}"])
    if code != 0:
        return True, "not calibrated yet: run python3 -m aegis.calibrate from app/"
    parts = out.split()
    return True, "C = " + parts[0] + " req/s, T = " + parts[1] + " s"


CHECKS = [
    ("catalog-service answers with books", check_books),
    ("Traefik routes to catalog-service", check_books_through_traefik),
    ("Prometheus scrapes Traefik", check_traefik_metrics),
    ("Prometheus scrapes catalog-service", check_prometheus_target),
    ("kube-state-metrics reports replicas", check_replica_metric),
    ("Recording rules evaluate", check_recording_rules),
    ("Custom Metrics API (prometheus-adapter)", check_custom_metrics_api),
    ("HPA exists", check_hpa),
    ("metrics-server works", check_metrics_server),
    ("Aegis calibration", check_calibration),
    ("Aegis in the cluster", check_aegis_in_cluster),
]


# Runs every check, retrying the failed ones for up to --wait seconds (some need a minute after a start).
def main():
    wait_seconds = 0
    if "--wait" in sys.argv:
        wait_seconds = int(sys.argv[sys.argv.index("--wait") + 1])
    deadline = time.monotonic() + wait_seconds
    results = {}
    while True:
        pending = False
        for name, check in CHECKS:
            if name in results and results[name][0]:
                continue
            results[name] = check()
            if not results[name][0]:
                pending = True
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(5)
    failed = 0
    for name, check in CHECKS:
        ok, detail = results[name]
        mark = "OK  "
        if not ok:
            mark = "FAIL"
            failed += 1
        print(mark, name, "-", detail)
    if failed:
        print(failed, "check(s) failed")
        sys.exit(1)
    print("Environment ready")


if __name__ == "__main__":
    main()
