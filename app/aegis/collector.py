import json
import logging
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

from aegis.config import load_config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Sample:
    timestamp: float                 # Unix seconds (UTC) when the sample was taken
    rps: Optional[float]             # requests per second
    p95_s: Optional[float]           # P95 latency in seconds
    replicas_ready: Optional[int]    # replicas currently receiving traffic


class PrometheusCollector:
    def __init__(self, url, query_rps, query_p95, query_replicas_ready, timeout_seconds=3):
        self.query_url = url.rstrip("/") + "/api/v1/query"
        self.query_rps = query_rps
        self.query_p95 = query_p95
        self.query_replicas_ready = query_replicas_ready
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, config):
        prometheus = config["prometheus"]
        return cls(
            url=prometheus["url"],
            query_rps=prometheus["query_rps"],
            query_p95=prometheus["query_p95"],
            query_replicas_ready=prometheus["query_replicas_ready"],
            timeout_seconds=prometheus.get("timeout_seconds", 3),
        )

    # If a query fails or has no data, that field is None and the rest of the sample
    # is still returned: a network error never brings Aegis down.
    def collect(self):
        timestamp = time.time()
        rps = self._query_scalar(self.query_rps, timestamp)
        p95_s = self._query_scalar(self.query_p95, timestamp)
        replicas = self._query_scalar(self.query_replicas_ready, timestamp)

        replicas_ready = None
        if replicas is not None:
            replicas_ready = int(replicas)

        return Sample(
            timestamp=timestamp,
            rps=rps,
            p95_s=p95_s,
            replicas_ready=replicas_ready,
        )

    # Runs an instant query and returns its single value, or None if there is no data.
    def _query_scalar(self, query, timestamp):
        params = urllib.parse.urlencode({"query": query, "time": timestamp})
        try:
            with urllib.request.urlopen(self.query_url + "?" + params, timeout=self.timeout_seconds) as response:
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            logger.warning("Prometheus did not respond to %r: %s", query, error)
            return None

        if body.get("status") != "success":
            logger.warning("Prometheus rejected %r: %s", query, body.get("error"))
            return None

        result = body["data"]["result"]
        if not result:
            # No series: for example, the pod has not received any request yet.
            return None

        value = float(result[0]["value"][1])
        if math.isnan(value) or math.isinf(value):
            # histogram_quantile returns NaN when there were no requests in the window.
            return None
        return value


def format_value(value, decimals=2):
    if value is None:
        return "-"
    return str(round(value, decimals))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    collector = PrometheusCollector.from_config(config)
    interval = config["sampling"]["interval_seconds"]

    logger.info("Querying %s every %s s (Ctrl+C to stop)", collector.query_url, interval)
    next_run = time.monotonic()
    try:
        while True:
            sample = collector.collect()
            logger.info(
                "rps=%s p95=%ss replicas_ready=%s",
                format_value(sample.rps),
                format_value(sample.p95_s, 3),
                format_value(sample.replicas_ready, 0),
            )
            # Scheduled against the clock so samples do not drift
            next_run += interval
            time.sleep(max(0.0, next_run - time.monotonic()))
    except KeyboardInterrupt:
        logger.info("Collector stopped")


if __name__ == "__main__":
    main()
