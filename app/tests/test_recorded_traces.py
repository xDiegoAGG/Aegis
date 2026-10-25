import json
import unittest
from aegis.collector import Sample
from aegis.config import load_config
from aegis.decision import DecisionEngine
from aegis.risk import RiskCalculator
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "tests"
TRACES = ["test1-linear-ramp", "test2-fluctuating"]


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# The engine fed with the demand Aegis saw in a recorded run must take the same decisions again.
class RecordedTraceTest(unittest.TestCase):
    def replay(self, name):
        calibration = json.loads((TESTS_DIR / "calibration.json").read_text())
        config = load_config()
        config["capacity_rps"] = float(calibration["capacity_rps"])
        config["startup_time_seconds"] = float(calibration["startup_time_seconds"])
        records = read(TESTS_DIR / name / "data" / "run-1-aegis.ndjson")
        calculator = RiskCalculator.from_config(config)
        engine = DecisionEngine.from_config(config, records[0]["previous_target"])
        decided = []
        for record in records:
            result = calculator.update(Sample(record["time"], record["rps"], record["p95_s"], record["replicas_ready"]))
            decided.append((result, engine.decide(result, record["time"])))
        return records, decided

    # The log rounds the demand, so a risk near 70% may cross it one cycle later.
    def test_same_decisions(self):
        for name in TRACES:
            with self.subTest(name):
                records, decided = self.replay(name)
                recorded = [(i, r["action"], r["target"]) for i, r in enumerate(records) if r["action"] != "hold"]
                replayed = [(i, d.action, d.target) for i, (_, d) in enumerate(decided) if d.action != "hold"]
                self.assertEqual([c[1:] for c in recorded], [c[1:] for c in replayed])
                for (i, _, _), (j, _, _) in zip(recorded, replayed):
                    self.assertLessEqual(abs(i - j), 1)

if __name__ == "__main__":
    unittest.main()
