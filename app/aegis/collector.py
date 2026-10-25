import json
import logging
import math
import time
import urllib.parse
import urllib.request
from kubernetes import client

logger = logging.getLogger(__name__)


def clean(value):
    if math.isnan(value) or math.isinf(value):
        return None
    return value


# One reading of the service. A value is None when Prometheus could not give it.
class Sample:
    def __init__(self, timestamp, rps, p95_s, replicas_ready):
        self.timestamp = timestamp
        self.rps = rps
        self.p95_s = p95_s
        self.replicas_ready = replicas_ready


# Queries Prometheus through the API server, or directly at url in the cluster.
class PrometheusClient:
    def __init__(self, namespace, service, timeout_seconds, url=""):
        self.path = "/api/v1/namespaces/" + namespace + "/services/" + service + "/proxy/api/v1/"
        self.url = url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api = None
        if not self.url:
            self.api = client.ApiClient()

    @classmethod
    def from_config(cls, config):
        prometheus = config["prometheus"]
        return cls(prometheus["namespace"], prometheus["service"], prometheus["timeout_seconds"],
                   prometheus.get("url") or "")

    def fetch(self, endpoint, params):
        if self.url:
            address = self.url + "/api/v1/" + endpoint + "?" + urllib.parse.urlencode(params)
            with urllib.request.urlopen(address, timeout=self.timeout_seconds) as response:
                return response.read()
        response = self.api.call_api(
            self.path + endpoint,
            "GET",
            query_params=params,
            header_params={"Accept": "application/json"},
            auth_settings=["BearerToken"],
            _preload_content=False,
            _return_http_data_only=True,
            _request_timeout=self.timeout_seconds,
        )
        return response.data

    # Returns the result list of one API call, or None on any error: a failed query never stops Aegis.
    def get(self, endpoint, params):
        try:
            body = json.loads(self.fetch(endpoint, params))
        except Exception as error:
            logger.warning("Prometheus did not answer: %s", error)
            return None
        if body.get("status") != "success":
            logger.warning("Prometheus rejected the query: %s", body.get("error"))
            return None
        return body["data"]["result"]

    # Single value of an instant query, or None when there is no data.
    def query(self, promql, timestamp):
        result = self.get("query", [("query", promql), ("time", str(timestamp))])
        if not result:
            return None
        return clean(float(result[0]["value"][1]))


# Reads demand, latency and Ready replicas once per cycle.
class Collector:
    def __init__(self, prometheus, query_rps, query_p95, query_replicas_ready):
        self.prometheus = prometheus
        self.query_rps = query_rps
        self.query_p95 = query_p95
        self.query_replicas_ready = query_replicas_ready

    @classmethod
    def from_config(cls, config):
        prometheus = config["prometheus"]
        return cls(
            PrometheusClient.from_config(config),
            prometheus["query_rps"],
            prometheus["query_p95"],
            prometheus["query_replicas_ready"],
        )

    def collect(self):
        now = time.time()
        rps = self.prometheus.query(self.query_rps, now)
        p95_s = self.prometheus.query(self.query_p95, now)
        replicas = self.prometheus.query(self.query_replicas_ready, now)
        replicas_ready = None
        if replicas is not None:
            replicas_ready = int(replicas)
        return Sample(now, rps, p95_s, replicas_ready)
