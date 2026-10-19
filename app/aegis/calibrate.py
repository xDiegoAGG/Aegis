import argparse
import datetime
import json
import logging
import math
import signal
import time
from aegis.calibration import environment_fingerprint, pod_selector, write_calibration
from aegis.collector import PrometheusClient
from aegis.config import load_config
from aegis.kube import load_kubernetes_credentials
from kubernetes import client
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

ENTRYPOINT = 'entrypoint="web"'
QUERY_P95 = ('histogram_quantile(0.95, sum(rate(traefik_entrypoint_request_duration_seconds_bucket{'
             + ENTRYPOINT + '}[10s])) by (le))')
QUERY_RPS = 'sum(rate(traefik_entrypoint_requests_total{' + ENTRYPOINT + '}[10s]))'
QUERY_ERRORS = ('sum(rate(traefik_entrypoint_requests_total{' + ENTRYPOINT + ',code!~"2.."}[10s])) / '
                + QUERY_RPS)
SAMPLE_SECONDS = 5
METRIC_LAG_SECONDS = 5
WINDOW_SECONDS = 10
SHORTFALL_RATIO = 0.9
IDLE_RPS = 0.5
K6_SCRIPT = "\n".join([
    "import http from 'k6/http';",
    "export const options = OPTIONS;",
    "export default function () {",
    "  http.get('TARGET_URL');",
    "}",
    "",
])


def utc_text(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_steps(settings):
    steps = []
    rps = settings["start_rps"]
    while rps <= settings["max_rps"]:
        steps.append(rps)
        rps += settings["step_rps"]
    return steps


# k6 options: jump to each step in 1 s and hold it, one connection per request.
def build_k6_options(steps, step_seconds):
    stages = []
    for rps in steps:
        stages.append({"target": rps, "duration": "1s"})
        stages.append({"target": rps, "duration": str(step_seconds - 1) + "s"})
    return {
        "noConnectionReuse": True,
        "scenarios": {
            "calibration": {
                "executor": "ramping-arrival-rate",
                "startRate": steps[0],
                "timeUnit": "1s",
                "preAllocatedVUs": 50,
                "maxVUs": 300,
                "stages": stages,
            },
        },
    }


# Measures C (step load on 1 pod until it degrades) and T (time from asking for pods until Ready).
class Calibrator:
    def __init__(self, config):
        self.settings = config["calibration"]
        self.degradation = config["degradation"]
        kubernetes = config["kubernetes"]
        self.namespace = kubernetes["namespace"]
        self.hpa_name = kubernetes["hpa_name"]
        self.deployment_name = kubernetes["deployment_name"]
        self.query_ready = config["prometheus"]["query_replicas_ready"]
        self.prometheus = PrometheusClient.from_config(config)
        self.autoscaling = client.AutoscalingV2Api()
        self.apps = client.AppsV1Api()
        self.core = client.CoreV1Api()
        self.batch = client.BatchV1Api()
        self.original_limits = None

    def query(self, promql):
        return self.prometheus.query(promql, time.time())

    def read_hpa_limits(self):
        hpa = self.autoscaling.read_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace)
        min_replicas = hpa.spec.min_replicas
        if min_replicas is None:
            min_replicas = 1
        return min_replicas, hpa.spec.max_replicas

    def set_hpa_limits(self, min_replicas, max_replicas):
        body = {"spec": {"minReplicas": min_replicas, "maxReplicas": max_replicas}}
        self.autoscaling.patch_namespaced_horizontal_pod_autoscaler(self.hpa_name, self.namespace, body)
        logger.info("HPA %s: minReplicas=%s maxReplicas=%s", self.hpa_name, min_replicas, max_replicas)

    def restore_hpa(self):
        if self.original_limits is None:
            return
        try:
            self.set_hpa_limits(self.original_limits[0], self.original_limits[1])
        except Exception as error:
            logger.error("Could not restore the HPA to minReplicas=%s maxReplicas=%s: %s",
                         self.original_limits[0], self.original_limits[1], error)

    def selector(self):
        return pod_selector(self.apps.read_namespaced_deployment(self.deployment_name, self.namespace))

    def ready_pods(self, selector):
        ready = {}
        for pod in self.core.list_namespaced_pod(self.namespace, label_selector=selector).items:
            if pod.metadata.deletion_timestamp is not None:
                continue
            for condition in pod.status.conditions or []:
                if condition.type == "Ready" and condition.status == "True":
                    ready[pod.metadata.name] = pod
        return ready

    def wait_single_replica(self):
        logger.info("Waiting until the deployment runs exactly 1 Ready pod")
        selector = self.selector()
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            pods = self.core.list_namespaced_pod(self.namespace, label_selector=selector).items
            if len(pods) == 1 and len(self.ready_pods(selector)) == 1:
                return
            time.sleep(SAMPLE_SECONDS)
        raise RuntimeError("the deployment did not go down to 1 Ready pod in time")

    def wait_recovery(self):
        logger.info("Waiting for the service to recover")
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            rps = self.query(QUERY_RPS)
            ready = self.query(self.query_ready)
            if ready is not None and ready >= 1 and (rps is None or rps < IDLE_RPS):
                break
            time.sleep(SAMPLE_SECONDS)
        logger.info("Cooldown %s s", self.settings["cooldown_seconds"])
        time.sleep(self.settings["cooldown_seconds"])

    def check_idle(self):
        rps = self.query(QUERY_RPS)
        if rps is not None and rps >= IDLE_RPS:
            raise RuntimeError("the service already receives " + str(round(rps, 1)) + " req/s: stop other load first")

    def delete_load_job(self):
        name = self.settings["load_job_name"]
        try:
            self.batch.delete_namespaced_job(name, self.namespace, propagation_policy="Background")
        except ApiException as error:
            if error.status != 404:
                raise
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if not self.core.list_namespaced_pod(self.namespace, label_selector="job-name=" + name).items:
                return
            time.sleep(2)

    # Creates the k6 Job and returns the moment its container started.
    def start_load_job(self, steps):
        name = self.settings["load_job_name"]
        script = K6_SCRIPT.replace("OPTIONS", json.dumps(build_k6_options(steps, self.settings["step_seconds"])))
        script = script.replace("TARGET_URL", self.settings["target_url"])
        config_map = {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": name}, "data": {"test.js": script}}
        try:
            self.core.replace_namespaced_config_map(name, self.namespace, config_map)
        except ApiException as error:
            if error.status != 404:
                raise
            self.core.create_namespaced_config_map(self.namespace, config_map)
        container = {
            "name": "k6",
            "image": self.settings["k6_image"],
            "imagePullPolicy": "IfNotPresent",
            "args": ["run", "/scripts/test.js"],
            "volumeMounts": [{"name": "script", "mountPath": "/scripts"}],
        }
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": name, "labels": {"app.kubernetes.io/part-of": "aegis"}},
            "spec": {
                "backoffLimit": 0,
                "template": {"spec": {
                    "restartPolicy": "Never",
                    "containers": [container],
                    "volumes": [{"name": "script", "configMap": {"name": name}}],
                }},
            },
        }
        self.batch.create_namespaced_job(self.namespace, job)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            for pod in self.core.list_namespaced_pod(self.namespace, label_selector="job-name=" + name).items:
                for status in pod.status.container_statuses or []:
                    if status.state.running is not None:
                        return status.state.running.started_at.timestamp()
                    waiting = status.state.waiting
                    if waiting is not None and waiting.reason in ("ErrImagePull", "ImagePullBackOff"):
                        raise RuntimeError("the k6 pod cannot pull " + self.settings["k6_image"])
            time.sleep(1)
        raise RuntimeError("the k6 pod did not start in time")

    def load_job_finished(self):
        try:
            job = self.batch.read_namespaced_job(self.settings["load_job_name"], self.namespace)
        except ApiException:
            return True
        if job.status.succeeded or job.status.failed:
            return True
        return False

    # Degraded = P95 above L, errors, serving under 90% of the sent rate, or no Ready pod, for T_d.
    def degradation_reason(self, p95, rps, errors, ready, expected_rps):
        if ready is not None and ready < 1:
            return "no Ready pod"
        if expected_rps is not None and rps is not None and rps < SHORTFALL_RATIO * expected_rps:
            return "served under " + str(int(SHORTFALL_RATIO * 100)) + "% of the sent req/s"
        if p95 is not None and p95 > self.degradation["p95_threshold_seconds"]:
            return "P95 above " + str(self.degradation["p95_threshold_seconds"]) + " s"
        if errors is not None and errors > self.settings["max_error_ratio"]:
            return "error ratio above " + str(self.settings["max_error_ratio"])
        return ""

    # One step-load run; C is the last step before the pod degraded.
    def measure_capacity_once(self, steps):
        step_seconds = self.settings["step_seconds"]
        bad_needed = max(1, math.ceil(self.degradation["sustained_seconds"] / SAMPLE_SECONDS))
        stats = []
        for rps in steps:
            stats.append({"target_rps": rps, "measured_rps": [], "p95_max_s": None})
        self.delete_load_job()
        started_at = self.start_load_job(steps)
        logger.info("k6 started at %s: steps of %s s from %s to %s req/s", utc_text(started_at), step_seconds,
                    steps[0], steps[-1])
        bad = 0
        first_bad_time = None
        result = {"started_at": utc_text(started_at), "capacity_rps": None, "reason": ""}
        try:
            while True:
                time.sleep(SAMPLE_SECONDS)
                now = time.time()
                index = int((now - started_at) // step_seconds)
                if index >= len(steps) or self.load_job_finished():
                    result["reason"] = "no degradation up to " + str(steps[-1]) + " req/s: raise calibration.max_rps"
                    break
                p95 = self.query(QUERY_P95)
                rps = self.query(QUERY_RPS)
                errors = self.query(QUERY_ERRORS)
                ready = self.query(self.query_ready)
                lagged = now - METRIC_LAG_SECONDS - started_at
                lagged_index = int(lagged // step_seconds)
                inside = lagged % step_seconds >= WINDOW_SECONDS
                expected_rps = None
                if 0 <= lagged_index < len(steps):
                    if rps is not None and inside:
                        stats[lagged_index]["measured_rps"].append(rps)
                    if p95 is not None and (stats[lagged_index]["p95_max_s"] is None
                                            or p95 > stats[lagged_index]["p95_max_s"]):
                        stats[lagged_index]["p95_max_s"] = p95
                    if inside:
                        expected_rps = steps[lagged_index]
                    elif lagged_index > 0:
                        expected_rps = steps[lagged_index - 1]
                logger.info("step %s/%s target=%s req/s: served=%s p95=%s errors=%s ready=%s", index + 1, len(steps),
                            steps[index], short(rps, 2), short(p95, 3), short(errors, 3), short(ready, 0))
                reason = self.degradation_reason(p95, rps, errors, ready, expected_rps)
                if reason == "":
                    bad = 0
                    first_bad_time = None
                    continue
                if first_bad_time is None:
                    first_bad_time = now
                bad += 1
                if reason == "no Ready pod":
                    bad = bad_needed
                if bad < bad_needed:
                    continue
                broken = int((first_bad_time - METRIC_LAG_SECONDS - started_at) // step_seconds)
                broken = max(0, min(broken, len(steps) - 1))
                result["degraded_at"] = utc_text(first_bad_time)
                result["degraded_step_rps"] = steps[broken]
                if broken == 0:
                    result["reason"] = reason + " already in the first step: lower calibration.start_rps"
                else:
                    result["capacity_rps"] = steps[broken - 1]
                    result["reason"] = reason + " at " + str(steps[broken]) + " req/s"
                break
        finally:
            self.delete_load_job()
        result["ended_at"] = utc_text(time.time())
        result["steps"] = summarize_steps(stats)
        logger.info("Run result: C=%s (%s)", result["capacity_rps"], result["reason"])
        return result

    # Raises minReplicas and times each new pod from that request until it is Ready.
    def measure_startup(self, max_replicas):
        target = min(self.settings["startup_replicas"], max_replicas)
        if target < 2:
            raise RuntimeError("maxReplicas must be at least 2 to measure T")
        selector = self.selector()
        existing = set(self.ready_pods(selector).keys())
        self.set_hpa_limits(target, max_replicas)
        requested_at = time.time()
        new_ready = {}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline and len(new_ready) < target - len(existing):
            for name, pod in self.ready_pods(selector).items():
                if name in existing or name in new_ready:
                    continue
                new_ready[name] = {
                    "pod": name,
                    "request_to_ready_s": round(time.time() - requested_at, 1),
                    "created_to_ready_s": round(time.time() - pod.metadata.creation_timestamp.timestamp(), 1),
                }
                logger.info("Pod %s Ready %s s after the request", name, new_ready[name]["request_to_ready_s"])
            time.sleep(1)
        if len(new_ready) < target - len(existing):
            raise RuntimeError("the new pods were not Ready after 180 s")
        measurements = []
        for name in sorted(new_ready):
            measurements.append(new_ready[name])
        return measurements


def short(value, decimals):
    if value is None:
        return "-"
    return round(value, decimals)


def summarize_steps(stats):
    steps = []
    for step in stats:
        if not step["measured_rps"] and step["p95_max_s"] is None:
            continue
        mean_rps = None
        if step["measured_rps"]:
            mean_rps = round(sum(step["measured_rps"]) / len(step["measured_rps"]), 2)
        p95_max = None
        if step["p95_max_s"] is not None:
            p95_max = round(step["p95_max_s"], 3)
        steps.append({"target_rps": step["target_rps"], "measured_rps": mean_rps, "p95_max_s": p95_max})
    return steps


# Full calibration: capacity runs on 1 pod, then T; the HPA is always restored.
def run(config, repetitions):
    settings = config["calibration"]
    kubernetes = config["kubernetes"]
    calibrator = Calibrator(config)
    steps = build_steps(settings)
    calibrator.check_idle()
    calibrator.original_limits = calibrator.read_hpa_limits()
    started = time.time()
    capacity_runs = []
    try:
        calibrator.set_hpa_limits(1, 1)
        calibrator.wait_single_replica()
        for repetition in range(repetitions):
            logger.info("Capacity run %s of %s", repetition + 1, repetitions)
            if repetition > 0:
                calibrator.wait_recovery()
            capacity_runs.append(calibrator.measure_capacity_once(steps))
        calibrator.wait_recovery()
        calibrator.set_hpa_limits(1, calibrator.original_limits[1])
        startup = calibrator.measure_startup(calibrator.original_limits[1])
    finally:
        calibrator.restore_hpa()
    capacities = []
    for result in capacity_runs:
        if result["capacity_rps"] is None:
            raise RuntimeError("a capacity run failed (" + result["reason"] + "), nothing was saved")
        capacities.append(result["capacity_rps"])
    slowest = 0.0
    for measurement in startup:
        slowest = max(slowest, measurement["request_to_ready_s"])
    finished = time.time()
    calibration = {
        "capacity_rps": min(capacities),
        "startup_time_seconds": math.ceil(slowest),
        "measured_at": utc_text(finished),
        "measured_at_unix": finished,
        "started_at": utc_text(started),
        "environment": environment_fingerprint(kubernetes["deployment_name"], kubernetes["namespace"]),
        "degradation": config["degradation"],
        "load": {
            "start_rps": settings["start_rps"],
            "step_rps": settings["step_rps"],
            "step_seconds": settings["step_seconds"],
            "target_url": settings["target_url"],
        },
        "capacity_runs": capacity_runs,
        "startup_measurements": startup,
    }
    write_calibration(settings["configmap_name"], kubernetes["namespace"], calibration)
    logger.info("Saved in ConfigMap %s: C=%s req/s (runs: %s), T=%s s", settings["configmap_name"],
                calibration["capacity_rps"], capacities, calibration["startup_time_seconds"])


def stop(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description="Measure C (capacity of one pod) and T (startup time)")
    parser.add_argument("--repetitions", type=int, help="capacity runs; C is the lowest (default: config)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    signal.signal(signal.SIGTERM, stop)
    config = load_config()
    load_kubernetes_credentials()
    repetitions = args.repetitions
    if repetitions is None:
        repetitions = config["calibration"]["repetitions"]
    logger.info("Calibrating. Aegis must NOT be running: this pins the HPA to 1 replica for a while.")
    try:
        run(config, repetitions)
    except KeyboardInterrupt:
        logger.warning("Calibration interrupted: HPA restored and load stopped, nothing was saved")
    except RuntimeError as error:
        logger.error("Calibration failed: %s", error)


if __name__ == "__main__":
    main()
