import json
import subprocess
import sys
import time
import urllib.parse

# Checks that everything Aegis needs is up. It only uses kubectl (no port-forward):
# Prometheus is reached through the Kubernetes API server proxy.
# Usage: python3 scripts/check_env.py [--wait SECONDS]

PROMETHEUS_PROXY = "/api/v1/namespaces/monitoring/services/prometheus-kube-prometheus-prometheus:9090/proxy"
EXPECTED_BOOKS = 50
FETCH_BOOKS = (
    "fetch('http://localhost:3003/api/books')"
    ".then(async (r) => { const body = await r.json(); console.log(r.status, Array.isArray(body) ? body.length : -1); })"
    ".catch((e) => { console.log(0, -1); })"
)


def kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def prometheus_query(query):
    path = PROMETHEUS_PROXY + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
    code, out, err = kubectl(["get", "--raw", path])
    if code != 0:
        return None
    body = json.loads(out)
    if body.get("status") != "success":
        return None
    return body["data"]["result"]


def check_books():
    code, out, err = kubectl(["exec", "deploy/catalog-service", "--", "node", "-e", FETCH_BOOKS])
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


def check_prometheus_target():
    result = prometheus_query('up{namespace="default",service="catalog-service"}')
    if result is None:
        return False, "Prometheus did not answer"
    if not result:
        return False, "catalog-service is not a Prometheus target yet (ServiceMonitor)"
    for series in result:
        if series["value"][1] != "1":
            return False, "a catalog-service target is down: " + series["metric"].get("pod", "?")
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
    cpu = "?"
    for metric in spec.get("metrics", []):
        if metric.get("type") == "Resource" and metric["resource"]["name"] == "cpu":
            cpu = str(metric["resource"]["target"].get("averageUtilization", "?")) + "%"
    return True, "CPU " + cpu + ", minReplicas " + str(spec.get("minReplicas", 1)) + ", maxReplicas " + str(spec["maxReplicas"])


def check_metrics_server():
    code, out, err = kubectl(["top", "pod", "-l", "app=catalog-service", "--no-headers"])
    if code != 0 or not out:
        return False, "metrics-server has no CPU data yet (the HPA needs it)"
    return True, "CPU data available"


CHECKS = [
    ("catalog-service answers with books", check_books),
    ("Prometheus scrapes catalog-service", check_prometheus_target),
    ("kube-state-metrics reports replicas", check_replica_metric),
    ("HPA exists", check_hpa),
    ("metrics-server works", check_metrics_server),
]


def main():
    wait_seconds = 0
    if "--wait" in sys.argv:
        wait_seconds = int(sys.argv[sys.argv.index("--wait") + 1])

    # Some checks need a minute after a fresh start (first scrape, first CPU sample): retry them
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
