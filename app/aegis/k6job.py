import json
import time
from kubernetes import client
from kubernetes.client.rest import ApiException

K6_SCRIPT = "\n".join([
    "import http from 'k6/http';",
    "export const options = OPTIONS;",
    "export default function () {",
    "  http.get('TARGET_URL');",
    "}",
    "",
])


# k6 options for an arrival-rate load: the given stages, one connection per request.
def arrival_rate_options(start_rate, stages, pre_allocated_vus, max_vus):
    return {
        "noConnectionReuse": True,
        "scenarios": {
            "load": {
                "executor": "ramping-arrival-rate",
                "startRate": start_rate,
                "timeUnit": "1s",
                "preAllocatedVUs": pre_allocated_vus,
                "maxVUs": max_vus,
                "stages": stages,
            },
        },
    }


def build_script(options, target_url):
    return K6_SCRIPT.replace("OPTIONS", json.dumps(options)).replace("TARGET_URL", target_url)


# One k6 Job and its script ConfigMap, both with the same name, created through the Kubernetes API.
class K6Job:
    def __init__(self, name, namespace, image, target_url, labels=None, deadline_seconds=None):
        self.name = name
        self.namespace = namespace
        self.image = image
        self.target_url = target_url
        self.labels = dict(labels or {})
        if "app.kubernetes.io/part-of" not in self.labels:
            self.labels["app.kubernetes.io/part-of"] = "aegis"
        self.deadline_seconds = deadline_seconds
        self.core = client.CoreV1Api()
        self.batch = client.BatchV1Api()

    def pods(self):
        return self.core.list_namespaced_pod(self.namespace, label_selector="job-name=" + self.name).items

    # Deletes the Job (and its pods); waits up to wait_seconds for the pods to go.
    def delete(self, wait_seconds=120):
        try:
            self.batch.delete_namespaced_job(self.name, self.namespace, propagation_policy="Background")
        except ApiException as error:
            if error.status != 404:
                raise
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if not self.pods():
                return
            time.sleep(2)

    def write_script(self, options):
        config_map = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": self.name, "labels": self.labels},
            "data": {"test.js": build_script(options, self.target_url)},
        }
        try:
            self.core.replace_namespaced_config_map(self.name, self.namespace, config_map)
        except ApiException as error:
            if error.status != 404:
                raise
            self.core.create_namespaced_config_map(self.namespace, config_map)

    def create(self, options):
        self.write_script(options)
        container = {
            "name": "k6",
            "image": self.image,
            "imagePullPolicy": "IfNotPresent",
            "args": ["run", "--quiet", "/scripts/test.js"],
            "volumeMounts": [{"name": "script", "mountPath": "/scripts"}],
        }
        spec = {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {"labels": self.labels},
                "spec": {
                    "restartPolicy": "Never",
                    "containers": [container],
                    "volumes": [{"name": "script", "configMap": {"name": self.name}}],
                },
            },
        }
        if self.deadline_seconds is not None:
            spec["activeDeadlineSeconds"] = int(self.deadline_seconds)
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"name": self.name, "labels": self.labels},
            "spec": spec,
        }
        self.batch.create_namespaced_job(self.namespace, job)

    # Waits until the k6 container runs and returns that moment (unix time).
    def wait_started(self, timeout_seconds=180):
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            for pod in self.pods():
                for status in pod.status.container_statuses or []:
                    if status.state.running is not None:
                        return status.state.running.started_at.timestamp()
                    waiting = status.state.waiting
                    if waiting is not None and waiting.reason in ("ErrImagePull", "ImagePullBackOff"):
                        raise RuntimeError("the k6 pod cannot pull " + self.image)
            time.sleep(1)
        raise RuntimeError("the k6 pod did not start in time")

    # True when the Job ended or does not exist.
    def finished(self):
        try:
            job = self.batch.read_namespaced_job(self.name, self.namespace)
        except ApiException:
            return True
        if job.status.succeeded or job.status.failed:
            return True
        return False
