import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import yaml
import run
from charts import degraded_intervals, deficit_seconds, serving_pods
from compare import climb
from load import first_crossing, planned_rate, read_profile, total_duration
from metrics import false_alarms, needed_pod_minutes
from run import metric_path_delays
from settings import (AUTOSCALERS, BLOCKS, BOUNDARY_TESTS, COMPARISONS, DESIGN_TESTS, HPA_FILES, LOADS, PROFILES,
                      ROOT, TESTS)
import campaign
import design_analysis
from metrics import reasks, window_pod_minutes


# Checks of the experiment tooling that need no cluster: profiles, metrics, charts helpers, campaign rules.
class ProfilesTest(unittest.TestCase):
    def test_every_test_has_its_files(self):
        for name, (profile, mode, title) in TESTS.items():
            self.assertIn(profile, PROFILES, name)
            self.assertTrue(PROFILES[profile].exists(), name)
            self.assertTrue(HPA_FILES[mode].exists(), name)
        for name in list(DESIGN_TESTS) + BOUNDARY_TESTS + [n for pair in COMPARISONS for n in pair[:2]]:
            self.assertIn(name, TESTS)

    def test_profiles_parse_and_jobs_match(self):
        for name, path in PROFILES.items():
            profile = read_profile(name)
            self.assertGreater(len(profile["stages"]), 2, name)
            documents = list(yaml.safe_load_all(path.read_text()))
            names = {d["kind"]: d["metadata"]["name"] for d in documents}
            self.assertEqual(names["Job"], "load-" + name)
            self.assertEqual(names["ConfigMap"], "load-" + name)
            volumes = documents[1]["spec"]["template"]["spec"]["volumes"]
            self.assertEqual(volumes[0]["configMap"]["name"], "load-" + name)

    def test_planned_rate_and_crossing(self):
        linear = read_profile("linear")
        self.assertEqual(total_duration(linear), 240)
        self.assertAlmostEqual(planned_rate(linear, 90), 5 + 45 * 60 / 120)
        self.assertEqual(first_crossing(linear, 24), 81.0)

    # A faster pod gets proportionally more traffic with the same timing: base to C takes the same seconds.
    def test_load_scales_with_capacity(self):
        reference = read_profile("linear")
        doubled = read_profile("linear", 48)
        self.assertEqual(doubled["scale"], 2.0)
        self.assertEqual(doubled["start_rate"], 2 * reference["start_rate"])
        self.assertEqual([d for _, d in doubled["stages"]], [d for _, d in reference["stages"]])
        self.assertIn("maxVUs: 1200", doubled["text"])
        self.assertEqual(first_crossing(doubled, 48), first_crossing(reference, 24))
        self.assertEqual(climb(doubled, 48)[1], climb(reference, 24)[1])
        documents = list(yaml.safe_load_all(doubled["text"]))
        self.assertEqual(documents[1]["metadata"]["name"], "load-linear")

    def test_boundary_slopes(self):
        self.assertEqual(climb(read_profile("linear"), 24), (0.375, 50.7))
        self.assertEqual(climb(read_profile("ramp-045"), 24), (0.45, 42.2))
        self.assertEqual(climb(read_profile("ramp-050"), 24), (0.5, 38.0))
        self.assertEqual(climb(read_profile("spike"), 24)[0], 8.0)


class DesignTest(unittest.TestCase):
    def test_factorial_cells(self):
        self.assertEqual(len(DESIGN_TESTS), len(AUTOSCALERS) * len(LOADS))
        self.assertEqual(sorted({mode for _, mode, _ in DESIGN_TESTS.values()}), sorted(AUTOSCALERS))

    # Every block holds every cell exactly once; orders differ between blocks and are reproducible.
    def test_schedule_is_a_randomized_complete_block_design(self):
        plan = campaign.schedule()
        self.assertEqual(len(plan), BLOCKS)
        for entry in plan:
            self.assertEqual(sorted(entry["order"]), sorted(DESIGN_TESTS))
        self.assertGreater(len({tuple(e["order"]) for e in plan}), 1)
        self.assertEqual(plan, campaign.schedule())
        self.assertEqual(campaign.parse_blocks("2-4"), [2, 3, 4])
        self.assertEqual(campaign.parse_blocks("5"), [5])

    def runs(self, effect, noise, blocks=6, seed=1):
        import random
        rnd = random.Random(seed)
        runs = {}
        for load in LOADS:
            for autoscaler in AUTOSCALERS:
                for block in range(1, blocks + 1):
                    drift = block * 0.5  # a session effect the blocks must absorb
                    value = (2.0 if autoscaler == "aegis" else 2.0 + effect) + drift + rnd.gauss(0, noise)
                    runs.setdefault((load, autoscaler), {})[block] = {"failed_percent": max(0.0, value), "run": block,
                                                                      "block": block}
        return runs

    def test_analysis_finds_a_real_effect(self):
        result = design_analysis.analyze(self.runs(effect=30, noise=2))
        self.assertEqual(len(result["primary"]), 6)
        for row in result["primary"]:
            self.assertTrue(row["significant"], row)
            self.assertLess(row["diff"], 0)
            self.assertAlmostEqual(row["p_within_block"], 2 / 64)
            self.assertEqual(row["cliffs_delta"], -1.0)

    def test_analysis_finds_nothing_without_effect(self):
        result = design_analysis.analyze(self.runs(effect=0, noise=2, seed=3))
        self.assertFalse(any(row["significant"] for row in result["primary"]))

    # The dashboard reads the JSON: booleans and numbers must be JSON ones, not numpy scalars written as text.
    def test_results_are_plain_json(self):
        result = design_analysis.plain(design_analysis.analyze(self.runs(effect=0, noise=2, seed=3)))
        text = json.dumps(result)
        for row in json.loads(text)["primary"]:
            self.assertIsInstance(row["significant"], bool)
            self.assertIsInstance(row["p_decision"], float)

    def test_holm(self):
        self.assertEqual(design_analysis.holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06])

    def test_blocks_absorb_drift(self):
        # Same effect, a large drift between blocks: the block term removes it from the error.
        runs = self.runs(effect=5, noise=0.5)
        for key in runs:
            for block, summary in runs[key].items():
                summary["failed_percent"] += 20 * block
        row = design_analysis.analyze(runs)["primary"][0]
        self.assertTrue(row["significant"])


class MetricsTest(unittest.TestCase):
    def test_reasks(self):
        downs = [{"s": 100, "from": 2, "to": 1}]
        self.assertEqual(reasks([{"s": 150, "from": 1, "to": 2}], downs), 1)
        self.assertEqual(reasks([{"s": 400, "from": 1, "to": 2}, {"s": 50, "from": 1, "to": 2}], downs), 0)

    def test_window_pod_minutes(self):
        changes = [{"time": 1060, "from": 1, "to": 2}, {"time": 1120, "from": 2, "to": 1}]
        self.assertEqual(window_pod_minutes(changes, 1000, 180), 4.0)

    def test_false_alarm(self):
        linear = read_profile("linear")
        self.assertEqual(false_alarms([{"s": 71, "from": 1, "to": 2}], linear, 24), 0)
        self.assertEqual(false_alarms([{"s": 250, "from": 1, "to": 2}], linear, 24), 1)

    def test_needed_pod_minutes(self):
        self.assertAlmostEqual(needed_pod_minutes(read_profile("linear"), 24), 7.57, places=2)

    def test_metric_path_delays(self):
        records = [{"time": 100, "action": "scale_up", "target": 2}, {"time": 105, "action": "hold", "target": 2}]
        changes = [{"time": 90, "from": 1, "to": 1}, {"time": 112, "from": 1, "to": 2}]
        self.assertEqual(metric_path_delays(records, changes), [12])


class ChartHelpersTest(unittest.TestCase):
    def test_degraded_intervals_need_three_buckets(self):
        rows = [{"seconds": s, "client_p95_s": 2.0 if 10 <= s <= 20 else 0.1, "client_failed_ratio": 0}
                for s in range(0, 60, 5)]
        self.assertEqual(degraded_intervals(rows), [(7.5, 22.5)])
        rows[3]["client_p95_s"] = 0.1
        self.assertEqual(degraded_intervals(rows), [])

    def test_serving_pods_wait_for_startup(self):
        summary = {"scale_ups": [{"s": 70, "from": 1, "to": 2}], "scale_downs": [{"s": 200, "from": 2, "to": 1}],
                   "second_pod_ready_s": 83, "first_scale_up_s": 70, "startup_time_seconds": 15}
        xs, pods = serving_pods(summary, 250)
        self.assertEqual(pods[xs.index(82)], 1)
        self.assertEqual(pods[xs.index(83)], 2)
        self.assertEqual(pods[xs.index(200)], 1)

    # Headline numbers of the first evaluation (2026-10-19 runs).
    def test_recorded_deficit(self):
        from compare import complete
        from report import load_rows
        from settings import TESTS_DIR
        for name, expected in (("test1-linear-ramp", 3), ("test3-hpa-baseline", 131)):
            found = [p for p in (TESTS_DIR / name).glob("**/run-1-summary.json")
                     if "calibration_measured_at" not in json.loads(p.read_text())]
            self.assertTrue(found, name)
            summary = json.loads(found[0].read_text())
            rows = load_rows(found[0].with_name("run-1.csv"))
            self.assertEqual(deficit_seconds(rows, complete(summary, rows)), expected, name)


class CalibrationRuleTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "t" / "data").mkdir(parents=True)
        (self.root / "calibration.json").write_text(json.dumps({"measured_at": "old"}))
        (self.root / "t" / "data" / "run-1-summary.json").write_text(json.dumps({"run": 1}))
        (self.root / "t" / "chart.png").write_text("")
        self.patch = mock.patch.object(run, "TESTS_DIR", self.root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.root)

    def test_same_calibration_passes(self):
        run.check_calibration("t", self.root / "t", {"measured_at": "old"}, False)

    def test_other_calibration_stops_the_campaign(self):
        with self.assertRaises(SystemExit):
            run.check_calibration("t", self.root / "t", {"measured_at": "new"}, False)

    def test_archive_moves_old_runs(self):
        run.check_calibration("t", self.root / "t", {"measured_at": "new"}, True)
        self.assertEqual(list((self.root / "t" / "data").iterdir()), [])
        archived = list((self.root / "t" / "archive").iterdir())[0]
        self.assertTrue((archived / "run-1-summary.json").exists())
        self.assertTrue((archived / "chart.png").exists())


class ForecastTest(unittest.TestCase):
    # The offline linear forecaster must project exactly what Aegis projects.
    def test_linear_trend_matches_aegis(self):
        from forecast_accuracy import LinearTrend
        from settings import CONFIG
        from aegis.collector import Sample
        from aegis.risk import RiskCalculator
        config = dict(CONFIG, capacity_rps=22.0, startup_time_seconds=15.0)
        calculator = RiskCalculator.from_config(config)
        model = LinearTrend(35)
        for index, rps in enumerate([5, 6, 8, 11, 15, 20, 26, 30, 31, 31, 28]):
            expected = calculator.update(Sample(1000 + 5 * index, rps, None, None)).projected_rps
            self.assertAlmostEqual(model.update(1000 + 5 * index, rps)[0], expected, places=9)

    def test_damping(self):
        from forecast_accuracy import DampedHolt, LinearTrend
        steady = LinearTrend(35, 0.9)
        holt = DampedHolt(35, 0.5, 0.3, 0.9)
        for index in range(10):
            linear_forecast = steady.update(5 * index, 10 + 2 * index)[0]
            holt_forecast = holt.update(5 * index, 10 + 2 * index)[0]
        current = 10 + 2 * 9
        self.assertLess(linear_forecast, current + 0.4 * 35)
        self.assertGreater(linear_forecast, current)
        self.assertGreater(holt_forecast, current)


class ManifestsTest(unittest.TestCase):
    def test_every_manifest_parses(self):
        for path in (ROOT / "kubernetes").rglob("*.yaml"):
            for document in yaml.safe_load_all(path.read_text()):
                if document is not None and "kind" in document:
                    self.assertIn("metadata", document, path)


class ReplicaChangesTest(unittest.TestCase):
    # Metric-mode run 2 lost its 2->3 SuccessfulRescale event; the pods themselves show all three changes.
    def test_changes_from_pods(self):
        from cluster import replica_changes
        from rebuild_changes import timeline_inputs
        from settings import TESTS_DIR
        pods, events, _ = timeline_inputs(TESTS_DIR / "test8-metric-mode" / "data" / "run-2-timeline.csv")
        changes = replica_changes(pods, events, -31)
        self.assertEqual([(c["from"], c["to"]) for c in changes], [(1, 2), (2, 3), (3, 2)])

    def test_pods_created_together_are_one_change(self):
        from cluster import replica_changes
        pods = {"a": {"created": 10.0}, "b": {"created": 11.0}}
        self.assertEqual(replica_changes(pods, [], 0), [{"time": 10.0, "from": 1, "to": 3}])


if __name__ == "__main__":
    unittest.main()
