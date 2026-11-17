import json
import time
import unittest
import urllib.error
import urllib.request
from aegis.config import load_config
from aegis.loads import LoadBusy, LoadController, UnknownProfile, profile_seconds
from aegis.server import start_server
from aegis.state import AegisState

KEY = "secret-key"


# Stands in for the k6 Job: records what the controller asked for.
class FakeJob:
    def __init__(self):
        self.created = []
        self.deleted = 0
        self.done = False

    def delete(self, wait_seconds=120):
        self.deleted += 1

    def create(self, options):
        self.created.append(options)
        self.done = False

    def finished(self):
        return self.done


def controller(capacity=24.0):
    config = load_config()
    config["capacity_rps"] = capacity
    return LoadController(config, FakeJob())


class LoadControllerTest(unittest.TestCase):
    def test_stages_follow_the_capacity(self):
        loads = controller(capacity=20.0)
        loads.start("ramp")
        scenario = loads.job.created[0]["scenarios"]["load"]
        self.assertEqual(scenario["startRate"], 4)
        self.assertEqual(scenario["stages"][1], {"target": 42, "duration": "120s"})
        self.assertTrue(loads.job.created[0]["noConnectionReuse"])

    # k6 rejects fractional rates (C = 16 gives 3.2 req/s at 0.2 C).
    def test_rates_are_whole_numbers(self):
        loads = controller(capacity=16.0)
        loads.start("waves")
        scenario = loads.job.created[0]["scenarios"]["load"]
        self.assertIsInstance(scenario["startRate"], int)
        for stage in scenario["stages"]:
            self.assertIsInstance(stage["target"], int)

    def test_one_load_at_a_time(self):
        loads = controller()
        loads.start("spike")
        with self.assertRaises(LoadBusy):
            loads.start("ramp")
        loads.job.done = True
        loads.start("ramp")
        self.assertEqual(len(loads.job.created), 2)

    def test_unknown_profile(self):
        with self.assertRaises(UnknownProfile):
            controller().start("forever")

    def test_stop_clears_the_running_load(self):
        loads = controller()
        loads.start("waves")
        self.assertEqual(loads.stop()["profile"], "waves")
        self.assertIsNone(loads.status()["running"])

    def test_profiles_fit_the_time_limit(self):
        loads = controller()
        for item in loads.status()["profiles"]:
            self.assertLessEqual(item["seconds"], loads.max_seconds)
        self.assertEqual(profile_seconds(loads.profiles["ramp"]), 240)


class LoadHttpTest(unittest.TestCase):
    def setUp(self):
        self.state = AegisState({"interval_seconds": 5})
        self.state.push({"time": time.time(), "action": "hold", "target": 1, "applied": 1})
        self.loads = controller()

    def serve(self, key):
        server = start_server(self.state, 0, host="127.0.0.1", loads=self.loads, load_key=key,
                              allowed_origins=["http://monitor.example"])
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return "http://127.0.0.1:" + str(server.server_address[1])

    def call(self, base, method, path, payload=None, headers=None):
        data = None
        if payload is not None:
            data = json.dumps(payload).encode()
        request = urllib.request.Request(base + path, data=data, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def test_key_is_required(self):
        base = self.serve(KEY)
        self.assertEqual(self.call(base, "POST", "/api/load", {"profile": "ramp"})[0], 401)
        self.assertEqual(self.call(base, "POST", "/api/load", {"profile": "ramp"}, {"X-Aegis-Key": "nope"})[0], 401)
        self.assertEqual(self.loads.job.created, [])

    def test_start_busy_and_stop(self):
        base = self.serve(KEY)
        headers = {"X-Aegis-Key": KEY}
        status, sent, body = self.call(base, "POST", "/api/load", {"profile": "ramp"}, headers)
        self.assertEqual(status, 202)
        self.assertEqual(json.loads(body)["running"]["profile"], "ramp")
        self.assertEqual(self.call(base, "POST", "/api/load", {"profile": "spike"}, headers)[0], 409)
        self.assertEqual(self.call(base, "POST", "/api/load", {"profile": "x"}, headers)[0], 400)
        status, sent, body = self.call(base, "GET", "/api/load")
        self.assertEqual(json.loads(body)["running"]["profile"], "ramp")
        self.assertEqual(self.call(base, "DELETE", "/api/load", None, headers)[0], 200)

    def test_without_a_key_the_buttons_are_off(self):
        base = self.serve("")
        self.assertEqual(self.call(base, "POST", "/api/load", {"profile": "ramp"}, {"X-Aegis-Key": ""})[0], 403)
        status, sent, body = self.call(base, "GET", "/api/load")
        self.assertFalse(json.loads(body)["enabled"])

    def test_cors_only_for_the_monitor(self):
        base = self.serve(KEY)
        status, sent, body = self.call(base, "GET", "/api/state", None, {"Origin": "http://monitor.example"})
        self.assertEqual(sent["Access-Control-Allow-Origin"], "http://monitor.example")
        status, sent, body = self.call(base, "GET", "/api/state", None, {"Origin": "http://evil.example"})
        self.assertIsNone(sent["Access-Control-Allow-Origin"])

    def test_preflight(self):
        base = self.serve(KEY)
        status, sent, body = self.call(base, "OPTIONS", "/api/load", None, {"Origin": "http://monitor.example"})
        self.assertEqual(status, 204)
        self.assertIn("X-Aegis-Key", sent["Access-Control-Allow-Headers"])
        self.assertIn("DELETE", sent["Access-Control-Allow-Methods"])


if __name__ == "__main__":
    unittest.main()
