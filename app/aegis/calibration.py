import json
import logging
import time

from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

DATA_KEY = "calibration.json"
INSTANCE_TYPE_LABEL = "node.kubernetes.io/instance-type"


# Reads the calibration saved by `python3 -m aegis.calibrate`, or None if there is none yet.
def read_calibration(name, namespace, core_api=None):
    if core_api is None:
        core_api = client.CoreV1Api()
    try:
        config_map = core_api.read_namespaced_config_map(name, namespace)
    except ApiException as error:
        if error.status == 404:
            return None
        raise
    data = config_map.data or {}
    if DATA_KEY not in data:
        return None
    return json.loads(data[DATA_KEY])


# Saves the calibration in a ConfigMap. The main values are also plain keys, readable with kubectl.
def write_calibration(name, namespace, calibration, core_api=None):
    if core_api is None:
        core_api = client.CoreV1Api()
    body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": name, "labels": {"app.kubernetes.io/part-of": "aegis"}},
        "data": {
            "capacity_rps": str(calibration["capacity_rps"]),
            "startup_time_seconds": str(calibration["startup_time_seconds"]),
            "measured_at": calibration["measured_at"],
            DATA_KEY: json.dumps(calibration, indent=2),
        },
    }
    try:
        core_api.replace_namespaced_config_map(name, namespace, body)
    except ApiException as error:
        if error.status != 404:
            raise
        core_api.create_namespaced_config_map(namespace, body)


# What the measured capacity depends on. If any of these change, the calibration may be wrong.
def environment_fingerprint(deployment_name, namespace, apps_api=None, core_api=None):
    if apps_api is None:
        apps_api = client.AppsV1Api()
    if core_api is None:
        core_api = client.CoreV1Api()

    deployment = apps_api.read_namespaced_deployment(deployment_name, namespace)
    container = deployment.spec.template.spec.containers[0]
    limits = {}
    if container.resources is not None and container.resources.limits is not None:
        limits = container.resources.limits

    fingerprint = {
        "image": container.image,
        "cpu_limit": limits.get("cpu", ""),
        "memory_limit": limits.get("memory", ""),
        "node_instance_type": "",
        "node_cpu": "",
    }

    # Node of one running pod of the deployment
    selector_parts = []
    for key, value in deployment.spec.selector.match_labels.items():
        selector_parts.append(key + "=" + value)
    pods = core_api.list_namespaced_pod(namespace, label_selector=",".join(selector_parts)).items
    for pod in pods:
        if pod.spec.node_name:
            node = core_api.read_node(pod.spec.node_name)
            labels = node.metadata.labels or {}
            fingerprint["node_instance_type"] = labels.get(INSTANCE_TYPE_LABEL, "")
            fingerprint["node_cpu"] = node.status.allocatable.get("cpu", "")
            break
    return fingerprint


# Returns the fields that changed since the calibration was measured (empty list = still valid).
def changed_fields(calibration, fingerprint):
    saved = calibration.get("environment", {})
    changes = []
    for key in fingerprint:
        if key in saved and saved[key] != fingerprint[key]:
            changes.append(key + ": " + str(saved[key]) + " -> " + str(fingerprint[key]))
    return changes


# Puts C and T from the cluster calibration into the config, so RiskCalculator.from_config works as before.
def apply_calibration(config, calibration):
    config["capacity_rps"] = float(calibration["capacity_rps"])
    config["startup_time_seconds"] = float(calibration["startup_time_seconds"])


# For the Aegis entry points: reads the calibration, warns if it looks stale and applies it.
# Returns False (and logs why) if there is no calibration, so the caller can stop.
def load_cluster_calibration(config):
    kubernetes = config["kubernetes"]
    name = config["calibration"]["configmap_name"]
    calibration = read_calibration(name, kubernetes["namespace"])
    if calibration is None:
        logger.error("No calibration found (ConfigMap %s/%s). Run first: python3 -m aegis.calibrate",
                     kubernetes["namespace"], name)
        return False

    fingerprint = environment_fingerprint(kubernetes["deployment_name"], kubernetes["namespace"])
    changes = changed_fields(calibration, fingerprint)
    if changes:
        logger.warning("The environment changed since the calibration (%s). Run python3 -m aegis.calibrate again",
                       ", ".join(changes))

    apply_calibration(config, calibration)
    age_hours = (time.time() - calibration["measured_at_unix"]) / 3600
    logger.info("Calibration from %s (%.1f h ago): C=%s req/s, T=%s s",
                calibration["measured_at"], age_hours, calibration["capacity_rps"],
                calibration["startup_time_seconds"])
    return True
