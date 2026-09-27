"""Calcula sigma (margen de error del trafico) a partir de la varianza real
de req/s medida por Prometheus, en un tramo donde el servicio estaba sano."""
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


def main():
    data = query_range(QUERY, START, END, STEP)["data"]["result"]
    valores = [float(v) for _, v in data[0]["values"]] if data else []
    print("valores:", valores)
    if len(valores) < 2:
        print("No hay suficientes muestras para calcular stdev (se necesitan al menos 2).")
        return
    sigma = statistics.stdev(valores)
    print("sigma =", round(sigma, 2), "req/s")


if __name__ == "__main__":
    main()
