import unittest
from aegis.decision import HOLD, SCALE_DOWN, SCALE_UP, DecisionEngine
from aegis.risk import RiskResult
from tests.helpers import config


def result(projected_rps, sigma_rps=2.0, capacity_rps=24.0):
    return RiskResult(0, projected_rps, 0, projected_rps, sigma_rps, 0, capacity_rps)


class DecisionTest(unittest.TestCase):
    def engine(self, initial=1):
        return DecisionEngine.from_config(config(), initial)

    def test_scale_up_at_threshold(self):
        engine = self.engine()
        decision = engine.decide(result(26), 0)
        self.assertEqual(decision.action, SCALE_UP)
        self.assertEqual((decision.previous_target, decision.target), (1, 2))

    def test_one_replica_per_cycle(self):
        engine = self.engine()
        engine.decide(result(100), 0)
        decision = engine.decide(result(100), 5)
        self.assertEqual(decision.target, 3)

    def test_hold_at_max_replicas(self):
        engine = self.engine(initial=3)
        decision = engine.decide(result(200), 0)
        self.assertEqual(decision.action, HOLD)
        self.assertEqual(decision.target, 3)

    def test_no_data_holds(self):
        decision = self.engine(initial=2).decide(None, 0)
        self.assertEqual(decision.action, HOLD)
        self.assertIsNone(decision.risk)

    # Scale-in only after the risk with one pod less stays low for 60 s (flapping suppression).
    def test_scale_down_waits_sustained_low_risk(self):
        engine = self.engine(initial=2)
        for second in range(0, 60, 5):
            self.assertEqual(engine.decide(result(5), second).action, HOLD)
        decision = engine.decide(result(5), 60)
        self.assertEqual(decision.action, SCALE_DOWN)
        self.assertEqual(decision.target, 1)

    def test_a_risky_cycle_restarts_the_wait(self):
        engine = self.engine(initial=2)
        engine.decide(result(5), 0)
        engine.decide(result(5), 30)
        engine.decide(result(23), 35)
        self.assertEqual(engine.decide(result(5), 90).action, HOLD)
        self.assertEqual(engine.decide(result(5), 150).action, SCALE_DOWN)

    def test_no_scale_down_when_one_less_would_be_risky(self):
        engine = self.engine(initial=2)
        for second in range(0, 200, 5):
            decision = engine.decide(result(24), second)
        self.assertEqual(decision.target, 2)

    def test_initial_target_is_clamped(self):
        self.assertEqual(self.engine(initial=9).target, 3)
        self.assertEqual(self.engine(initial=0).target, 1)


if __name__ == "__main__":
    unittest.main()
