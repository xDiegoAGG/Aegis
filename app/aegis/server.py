import hmac
import json
import logging
import threading
from aegis.loads import LoadBusy, UnknownProfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)
MAX_BODY_BYTES = 4096


def parse_since(query):
    values = parse_qs(query).get("since")
    if not values:
        return None
    try:
        return float(values[0])
    except ValueError:
        return None


def key_matches(expected, given):
    if not expected or not given:
        return False
    return hmac.compare_digest(expected.encode(), given.encode())


# Builds the request handler: /metrics, the probes, /api/state and the load buttons (/api/load, with a key).
def make_handler(state, loads=None, load_key="", allowed_origins=None):
    origins = list(allowed_origins or [])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            logger.debug("http %s", format % args)

        def cors_headers(self):
            origin = self.headers.get("Origin")
            if not origin:
                return
            if origin not in origins and "*" not in origins:
                return
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aegis-Key")
            self.send_header("Access-Control-Max-Age", "600")

        def send(self, status, body, content_type):
            data = body
            if not isinstance(body, bytes):
                data = body.encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.cors_headers()
            self.end_headers()
            self.wfile.write(data)

        def send_json(self, status, payload):
            self.send(status, json.dumps(payload), "application/json")

        def do_OPTIONS(self):
            self.send(204, b"", "text/plain")

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
            elif url.path == "/api/load":
                self.load_status()
            else:
                self.send_json(404, {"error": "not found"})

        def load_status(self):
            if loads is None:
                self.send_json(200, {"enabled": False, "profiles": [], "running": None})
                return
            status = loads.status()
            status["enabled"] = bool(load_key)
            self.send_json(200, status)

        # True when the request may start or stop a load; otherwise it already answered.
        def load_allowed(self):
            if urlparse(self.path).path != "/api/load":
                self.send_json(404, {"error": "not found"})
                return False
            if loads is None or not load_key:
                self.send_json(403, {"error": "the load buttons are off (no AEGIS_LOAD_KEY)"})
                return False
            if not key_matches(load_key, self.headers.get("X-Aegis-Key")):
                self.send_json(401, {"error": "wrong key"})
                return False
            return True

        def read_json(self):
            try:
                length = min(int(self.headers.get("Content-Length") or 0), MAX_BODY_BYTES)
                body = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return None
            if not isinstance(body, dict):
                return None
            return body

        def do_POST(self):
            if not self.load_allowed():
                return
            body = self.read_json()
            if body is None:
                self.send_json(400, {"error": "expected {\"profile\": name}"})
                return
            try:
                running = loads.start(str(body.get("profile", "")))
            except UnknownProfile as error:
                self.send_json(400, {"error": "unknown profile " + str(error)})
                return
            except LoadBusy as error:
                self.send_json(409, {"error": "another load is running: " + str(error)})
                return
            except Exception as error:
                logger.warning("Could not start the load: %s", error)
                self.send_json(502, {"error": "Kubernetes did not create the load"})
                return
            self.send_json(202, {"running": running})

        def do_DELETE(self):
            if not self.load_allowed():
                return
            try:
                stopped = loads.stop()
            except Exception as error:
                logger.warning("Could not stop the load: %s", error)
                self.send_json(502, {"error": "Kubernetes did not delete the load"})
                return
            self.send_json(200, {"stopped": stopped})

    return Handler


# Serves /metrics and the JSON API in a background thread.
def start_server(state, port, host="0.0.0.0", loads=None, load_key="", allowed_origins=None):
    server = ThreadingHTTPServer((host, port), make_handler(state, loads, load_key, allowed_origins))
    thread = threading.Thread(target=server.serve_forever, name="aegis-http", daemon=True)
    thread.start()
    logger.info("API on http://localhost:%s/api/state  (metrics on /metrics)", port)
    return server
