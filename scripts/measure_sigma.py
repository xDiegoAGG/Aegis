import json
import statistics
import urllib.parse
import urllib.request

PROMETHEUS_URL = "http://localhost:9090/api/v1/query_range"
QUERY = 'sum(rate(http_request_duration_seconds_count{route="/"}[10s]))'
START = "2026-09-27T07:56:45Z"
END = "2026-09-27T07:57:30Z"
STEP = "5s"


def query_range(query, start, end, step):
    params = urllib.parse.urlencode({
        "query": query,
        "start": start,
        "end": end,
        "step": step,
    })
    url = f"{PROMETHEUS_URL}?{params}"
    with urllib.request.urlopen(url) as response:
        return json.load(response)


# Sigma (traffic error margin) = standard deviation of req/s over a window where the service was healthy.
def main():
    data = query_range(QUERY, START, END, STEP)["data"]["result"]
    values = []
    if data:
        for _, v in data[0]["values"]:
            values.append(float(v))
    print("values:", values)
    if len(values) < 2:
        print("Not enough samples to calculate stdev (at least 2 are needed).")
        return
    sigma = statistics.stdev(values)
    print("sigma =", round(sigma, 2), "req/s")


if __name__ == "__main__":
    main()
