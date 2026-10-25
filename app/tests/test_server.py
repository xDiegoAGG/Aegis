import json
import time
import unittest
import urllib.error
import urllib.request
from aegis.server import AegisState, start_server

META = {"namespace": "default", "deployment": "catalog-service", "interval_seconds": 5,
        "pod_capacity_rps": 24.0, "startup_time_seconds": 15, "scale_up_threshold": 0.7, "scale_down_threshold": 0.3}


def record(moment, action="hold", target=1, applied=1, risk=0.1):
    return {"time": moment, "rps": 10.0, "slope": 0.5, "projected_rps": 27.5, "sigma_rps": 2.0, "p95_s": 0.2,
            "replicas_ready": 1, "capacity_rps": 24.0, "risk": risk, "action": action, "previous_target": 1,
            "target": target, "applied": applied, "reason": "", "risk_one_less": None}


class ConfigTest(unittest.TestCase):
    # Kubernetes sets AEGIS_PORT=tcp://ip:port for a Service named aegis; it must not break the config.
    def test_service_link_variable_is_ignored(self):
        from unittest import mock
        from aegis.config import load_config
        with mock.patch.dict("os.environ", {"AEGIS_PORT": "tcp://10.0.0.1:8080", "AEGIS_HTTP_PORT": "9000",
                                            "AEGIS_ACTUATOR_MODE": "metric"}):
            config = load_config()
        self.assertEqual(config["server"]["port"], 9000)
        self.assertEqual(config["actuator"]["mode"], "metric")


class StateTest(unittest.TestCase):
    def test_snapshot_since(self):
        state = AegisState(META)
        state.push(record(1.0))
        state.push(record(2.0))
        self.assertEqual(len(state.snapshot(None)["records"]), 2)
        self.assertEqual([r["time"] for r in state.snapshot(1.0)["records"]], [2.0])

    def test_metrics_text(self):
        state = AegisState(META)
        state.push(record(time.time(), action="scale_up", target=2, applied=2, risk=0.81))
        text = state.metrics_text()
        self.assertIn('aegis_risk{target_deployment="catalog-service",target_namespace="default"} 0.81', text)
        self.assertIn('aegis_target_replicas{target_deployment="catalog-service",target_namespace="default"} 2.0', text)
        self.assertIn('aegis_decisions_total{action="scale_up",target_deployment="catalog-service",'
                      'target_namespace="default"} 1.0', text)
        self.assertNotIn("aegis_risk_one_less", text)

    def test_failed_apply_is_counted(self):
        state = AegisState(META)
        state.push(record(1.0, action="scale_up", target=2, applied=1))
        self.assertIn("aegis_failed_applies_total", state.metrics_text())
        self.assertEqual(state.failed_applies, 1)

    def test_fresh(self):
        state = AegisState(META)
        self.assertFalse(state.fresh())
        state.push(record(time.time()))
        self.assertTrue(state.fresh())


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = AegisState(META)
        cls.state.push(record(time.time()))
        cls.server = start_server(cls.state, 0, tests_dir=None)
        cls.base = "http://127.0.0.1:" + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return response.status, response.read().decode()

    def test_api_state(self):
        status, body = self.get("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["records"]), 1)

    def test_metrics_and_probes(self):
        self.assertIn("aegis_demand_rps", self.get("/metrics")[1])
        self.assertEqual(self.get("/healthz")[0], 200)
        self.assertEqual(self.get("/readyz")[0], 200)

    def test_dashboard_and_no_traversal(self):
        status, body = self.get("/")
        self.assertIn("Aegis", body)
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.get("/../config.yaml")
        self.assertEqual(error.exception.code, 404)

    def post(self, path, payload):
        request = urllib.request.Request(self.base + path, data=json.dumps(payload).encode(), method="POST")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_replay_switch(self):
        self.assertEqual(self.post("/api/replay", {"test": "test1", "run": 1})[0], 404)
        chosen = []
        self.state.select = lambda test, run: chosen.append((test, run)) or (None if run == 4 else "no log")
        try:
            self.assertEqual(self.post("/api/replay", {"test": "test1-linear-ramp", "run": 4}), (200, {"ok": True}))
            self.assertEqual(self.post("/api/replay", {"test": "test1-linear-ramp", "run": 9})[0], 400)
            self.assertEqual(self.post("/api/replay", {"test": "x", "run": "a"})[0], 400)
        finally:
            self.state.select = None
        self.assertEqual(chosen, [("test1-linear-ramp", 4), ("test1-linear-ramp", 9)])


class ReplayTest(unittest.TestCase):
    def test_only_saved_aegis_runs(self):
        from aegis.replay import Replayer
        state = AegisState(META)
        replayer = Replayer(state, None, None, 1000, False)
        self.assertEqual(replayer.select("../../etc", 1), "unknown run")
        self.assertIn("no Aegis log", replayer.select("test3-hpa-baseline", 1))


if __name__ == "__main__":
    unittest.main()
