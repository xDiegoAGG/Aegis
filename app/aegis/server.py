import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


def parse_since(query):
    values = parse_qs(query).get("since")
    if not values:
        return None
    try:
        return float(values[0])
    except ValueError:
        return None


# Builds the request handler: /metrics, the probes and the read-only /api/state.
def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.debug("http %s", format % args)

        def send(self, status, body, content_type):
            data = body
            if not isinstance(body, bytes):
                data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status, payload):
            self.send(status, json.dumps(payload), "application/json")

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/metrics":
                self.send(200, state.metrics_text(), "text/plain; version=0.0.4")
            elif url.path == "/healthz":
                self.send(200, "ok\n", "text/plain")
            elif url.path == "/readyz":
                if state.fresh():
                    self.send(200, "ok\n", "text/plain")
                else:
                    self.send(503, "no recent cycle\n", "text/plain")
            elif url.path == "/api/state":
                self.send_json(200, state.snapshot(parse_since(url.query)))
            else:
                self.send_json(404, {"error": "not found"})

    return Handler


# Serves /metrics and the JSON API in a background thread.
def start_server(state, port, host="0.0.0.0"):
    server = ThreadingHTTPServer((host, port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, name="aegis-http", daemon=True)
    thread.start()
    logger.info("API on http://localhost:%s/api/state  (metrics on /metrics)", port)
    return server
