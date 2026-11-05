import unittest
from statistics import NormalDist
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

    # Risk with one pod less ~0%: the shortest wait, 15 s.
    def test_scale_down_fast_when_one_less_is_clearly_safe(self):
        engine = self.engine(initial=2)
        for second in range(0, 15, 5):
            self.assertEqual(engine.decide(result(5), second).action, HOLD)
        decision = engine.decide(result(5), 15)
        self.assertEqual(decision.action, SCALE_DOWN)
        self.assertEqual(decision.target, 1)

    # Risk with one pod less 25% (just under 30%): wait 15 + 45 * 25/30 = 52.5 s.
    def test_scale_down_waits_longer_near_the_threshold(self):
        engine = self.engine(initial=2)
        projected = 24 + 2 * NormalDist().inv_cdf(0.25)
        for second in range(0, 55, 5):
            self.assertEqual(engine.decide(result(projected), second).action, HOLD, second)
        self.assertEqual(engine.decide(result(projected), 55).action, SCALE_DOWN)

    # The wait follows the highest risk seen while low, not only the current one.
    def test_wait_uses_the_highest_risk_while_low(self):
        engine = self.engine(initial=2)
        engine.decide(result(24 + 2 * NormalDist().inv_cdf(0.25)), 0)
        for second in range(5, 55, 5):
            self.assertEqual(engine.decide(result(5), second).action, HOLD, second)
        self.assertEqual(engine.decide(result(5), 55).action, SCALE_DOWN)

    def test_drops_several_pods_at_once(self):
        engine = self.engine(initial=3)
        for second in range(0, 15, 5):
            engine.decide(result(5), second)
        decision = engine.decide(result(5), 15)
        self.assertEqual((decision.action, decision.previous_target, decision.target), (SCALE_DOWN, 3, 1))

    def test_keeps_the_pods_still_needed(self):
        engine = self.engine(initial=3)
        for second in range(0, 200, 5):
            decision = engine.decide(result(30), second)
        self.assertEqual(engine.target, 2)

    def test_a_risky_cycle_restarts_the_wait(self):
        engine = self.engine(initial=2)
        engine.decide(result(5), 0)
        engine.decide(result(5), 5)
        engine.decide(result(23), 10)  # risk with 1 pod 31%
        self.assertEqual(engine.decide(result(5), 15).action, HOLD)
        self.assertEqual(engine.decide(result(5), 25).action, HOLD)
        self.assertEqual(engine.decide(result(5), 30).action, SCALE_DOWN)

    # A config without the minimum wait keeps a fixed wait (the rule of the October 2026 runs).
    def test_without_min_wait_the_wait_is_fixed(self):
        settings = config()
        del settings["risk_thresholds"]["scale_down_min_wait_seconds"]
        engine = DecisionEngine.from_config(settings, 2)
        for second in range(0, 60, 5):
            self.assertEqual(engine.decide(result(5), second).action, HOLD)
        self.assertEqual(engine.decide(result(5), 60).action, SCALE_DOWN)

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
