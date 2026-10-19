import datetime
import json
import math
import re
import subprocess
import time
import urllib.parse
from settings import CONFIG, HPA_FILES, PROFILES, STEP

PROMETHEUS = "/api/v1/namespaces/monitoring/services/prometheus-kube-prometheus-prometheus:9090/proxy/api/v1/"
QUERY_IDLE = 'sum(rate(traefik_entrypoint_requests_total{entrypoint="web"}[30s]))'
QUERY_POD_CREATED = 'kube_pod_created{namespace="default",pod=~"catalog-service-.*"}'
QUERY_POD_READY = 'kube_pod_status_ready_time{namespace="default",pod=~"catalog-service-.*"}'


def say(*parts):
    print(datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S"), *parts, flush=True)


def kubectl(args, check=True):
    result = subprocess.run(["kubectl"] + args, capture_output=True)
    if check and result.returncode != 0:
        raise RuntimeError("kubectl " + " ".join(args) + ": " + result.stderr.decode().strip())
    return result.stdout


# Calls the Prometheus API through the Kubernetes API server and returns the result list.
def prometheus(endpoint, params):
    out = kubectl(["get", "--raw", PROMETHEUS + endpoint + "?" + urllib.parse.urlencode(params)], False)
    try:
        body = json.loads(out)
    except ValueError:
        return []
    if body.get("status") != "success":
        return []
    return body["data"]["result"]


def number(text):
    value = float(text)
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def instant(promql):
    result = prometheus("query", {"query": promql})
    if not result:
        return None
    return number(result[0]["value"][1])


# Values of the first series of a range query as {timestamp: value}, one every STEP seconds.
def range_values(promql, start, end):
    values = {}
    result = prometheus("query_range", {"query": promql, "start": start, "end": end, "step": STEP})
    if result:
        for timestamp, text in result[0]["values"]:
            value = number(text)
            if value is not None:
                values[int(float(timestamp))] = value
    return values


def read_calibration():
    out = kubectl(["get", "configmap", CONFIG["calibration"]["configmap_name"], "-o", "json"])
    return json.loads(json.loads(out)["data"]["calibration.json"])


def pod_count():
    return len(json.loads(kubectl(["get", "pods", "-l", "app=catalog-service", "-o", "json"]))["items"])


# Stops any load and leaves exactly 1 Ready pod with the HPA of the mode, and no traffic.
def reset(mode):
    for name in PROFILES:
        kubectl(["delete", "job", "load-" + name, "--ignore-not-found", "--wait=true"])
    kubectl(["apply", "-f", str(HPA_FILES[mode])])
    kubectl(["patch", "hpa", "catalog-service", "--type", "merge", "-p", '{"spec":{"minReplicas":1,"maxReplicas":1}}'])
    deadline = time.monotonic() + 600
    while True:
        deployment = json.loads(kubectl(["get", "deploy", "catalog-service", "-o", "json"]))
        ready = deployment["status"].get("readyReplicas", 0)
        if deployment["spec"]["replicas"] == 1 and ready == 1 and pod_count() == 1:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("the service did not go back to 1 pod")
        time.sleep(5)
    max_replicas = str(CONFIG["kubernetes"]["max_replicas"])
    kubectl(["patch", "hpa", "catalog-service", "--type", "merge", "-p", '{"spec":{"maxReplicas":' + max_replicas + '}}'])
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        rps = instant(QUERY_IDLE)
        if rps is not None and rps < 0.5:
            break
        time.sleep(5)
    say("reset done:", mode, "HPA, 1 pod, no traffic")


# Replica changes the HPA made since a moment, from its SuccessfulRescale events.
def hpa_scale_changes(since):
    events = json.loads(kubectl(["get", "events", "--field-selector", "reason=SuccessfulRescale", "-o", "json"]))
    found = []
    for event in events["items"]:
        stamp = event.get("lastTimestamp") or event.get("eventTime")
        size = re.search(r"New size: (\d+)", event.get("message", ""))
        if not stamp or size is None:
            continue
        moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        if moment >= since:
            found.append((moment, int(size.group(1))))
    found.sort()
    changes = []
    previous = 1
    for moment, size in found:
        changes.append({"time": moment, "from": previous, "to": size})
        previous = size
    return changes


# Creation and first Ready time of every catalog-service pod seen in the window.
def pod_times(start, end):
    params = {"start": start, "end": end, "step": STEP, "query": QUERY_POD_CREATED}
    pods = {}
    for series in prometheus("query_range", params):
        pods[series["metric"]["pod"]] = {"created": float(series["values"][0][1]), "ready": None}
    params["query"] = QUERY_POD_READY
    for series in prometheus("query_range", params):
        name = series["metric"]["pod"]
        if name not in pods:
            continue
        for timestamp, text in series["values"]:
            value = float(text)
            if pods[name]["ready"] is None or value < pods[name]["ready"]:
                pods[name]["ready"] = value
    return pods
