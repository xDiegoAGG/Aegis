import json
import unittest
from aegis.collector import Sample
from aegis.config import load_config
from aegis.decision import DecisionEngine
from aegis.risk import RiskCalculator
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TRACES = ["linear-ramp-aegis.ndjson", "fluctuating-aegis.ndjson"]


def read(path):
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def changes(pairs):
    found = []
    index = 0
    for action, target in pairs:
        if action != "hold":
            found.append((index, action, target))
        index += 1
    return found


def scale_up_cycles(decided):
    found = []
    index = 0
    for result, decision in decided:
        if decision.action == "scale_up":
            found.append(index)
        index += 1
    return found


def pod_cycles(decided):
    total = 0
    for result, decision in decided:
        total += decision.target
    return total


# The engine fed with the demand Aegis saw in a recorded run (October 2026) must take the same decisions again.
class RecordedTraceTest(unittest.TestCase):
    def replay(self, name, min_wait=60):
        calibration = json.loads((FIXTURES / "calibration-2026-10-25.json").read_text())
        config = load_config()
        config["risk_thresholds"]["scale_down_min_wait_seconds"] = min_wait
        config["capacity_rps"] = float(calibration["capacity_rps"])
        config["startup_time_seconds"] = float(calibration["startup_time_seconds"])
        records = read(FIXTURES / name)
        calculator = RiskCalculator.from_config(config)
        engine = DecisionEngine.from_config(config, records[0]["previous_target"])
        decided = []
        for record in records:
            result = calculator.update(Sample(record["time"], record["rps"], record["p95_s"], record["replicas_ready"]))
            decided.append((result, engine.decide(result, record["time"])))
        return records, decided

    # With the fixed 60 s wait the runs used; the log rounds the demand, so a decision may come one cycle later.
    def test_same_decisions(self):
        for name in TRACES:
            with self.subTest(name):
                records, decided = self.replay(name)
                recorded_pairs = []
                for record in records:
                    recorded_pairs.append((record["action"], record["target"]))
                replayed_pairs = []
                for result, decision in decided:
                    replayed_pairs.append((decision.action, decision.target))
                recorded = changes(recorded_pairs)
                replayed = changes(replayed_pairs)
                self.assertEqual(len(recorded), len(replayed))
                for first, second in zip(recorded, replayed):
                    self.assertEqual(first[1:], second[1:])
                    self.assertLessEqual(abs(first[0] - second[0]), 1)

    # The risk-based wait (15-60 s) asks for pods at the same moments and gives them back sooner.
    def test_risk_based_wait_saves_pods_without_changing_scale_ups(self):
        for name in TRACES:
            with self.subTest(name):
                records, fixed = self.replay(name, min_wait=60)
                records, adaptive = self.replay(name, min_wait=15)
                self.assertEqual(scale_up_cycles(fixed), scale_up_cycles(adaptive))
                self.assertLess(pod_cycles(adaptive), pod_cycles(fixed))
                for first, second in zip(adaptive, fixed):
                    self.assertLessEqual(first[1].target, second[1].target)


if __name__ == "__main__":
    unittest.main()
