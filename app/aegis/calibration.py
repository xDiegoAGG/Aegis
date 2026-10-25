import json
import logging
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

DATA_KEY = "calibration.json"
INSTANCE_TYPE_LABEL = "node.kubernetes.io/instance-type"


# Reads the saved calibration, or None if there is none yet.
def read_calibration(name, namespace):
    try:
        config_map = client.CoreV1Api().read_namespaced_config_map(name, namespace)
    except ApiException as error:
        if error.status == 404:
            return None
        raise
    data = config_map.data or {}
    if DATA_KEY not in data:
        return None
    return json.loads(data[DATA_KEY])


# Saves the calibration in a ConfigMap; C and T are also plain keys, readable with kubectl.
def write_calibration(name, namespace, calibration):
    core = client.CoreV1Api()
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
        core.replace_namespaced_config_map(name, namespace, body)
    except ApiException as error:
        if error.status != 404:
            raise
        core.create_namespaced_config_map(namespace, body)


def pod_selector(deployment):
    parts = []
    for key, value in deployment.spec.selector.match_labels.items():
        parts.append(key + "=" + value)
    return ",".join(parts)


# What the measured capacity depends on: image, pod limits and node.
def environment_fingerprint(deployment_name, namespace):
    deployment = client.AppsV1Api().read_namespaced_deployment(deployment_name, namespace)
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
    core = client.CoreV1Api()
    for pod in core.list_namespaced_pod(namespace, label_selector=pod_selector(deployment)).items:
        if pod.spec.node_name:
            node = core.read_node(pod.spec.node_name)
            fingerprint["node_instance_type"] = (node.metadata.labels or {}).get(INSTANCE_TYPE_LABEL, "")
            fingerprint["node_cpu"] = node.status.allocatable.get("cpu", "")
            break
    return fingerprint


# Puts C and T of the cluster calibration into the config; warns if the environment changed since then.
def load_cluster_calibration(config):
    kubernetes = config["kubernetes"]
    name = config["calibration"]["configmap_name"]
    calibration = read_calibration(name, kubernetes["namespace"])
    if calibration is None:
        logger.error("No calibration found (ConfigMap %s). Run first: python3 -m aegis.calibrate", name)
        return False
    fingerprint = environment_fingerprint(kubernetes["deployment_name"], kubernetes["namespace"])
    saved = calibration.get("environment", {})
    changes = []
    for key in fingerprint:
        if key in saved and saved[key] != fingerprint[key]:
            changes.append(key + ": " + str(saved[key]) + " -> " + str(fingerprint[key]))
    if changes:
        logger.warning("The environment changed since the calibration (%s): run python3 -m aegis.calibrate",
                       ", ".join(changes))
    config["capacity_rps"] = float(calibration["capacity_rps"])
    config["startup_time_seconds"] = float(calibration["startup_time_seconds"])
    config["calibrated_at"] = calibration["measured_at"]
    logger.info("Calibration from %s: C=%s req/s, T=%s s", calibration["measured_at"],
                calibration["capacity_rps"], calibration["startup_time_seconds"])
    return True
