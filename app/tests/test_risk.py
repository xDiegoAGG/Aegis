import math
import random
import unittest
from aegis.collector import Sample
from aegis.risk import RiskCalculator, SigmaEstimator, normal_cdf, risk_probability
from tests.helpers import config, feed


class NormalCdfTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(normal_cdf(0), 0.5, places=12)
        self.assertAlmostEqual(normal_cdf(1.0), 0.8413447460685429, places=12)
        self.assertAlmostEqual(normal_cdf(-1.6448536269514722), 0.05, places=10)
        self.assertAlmostEqual(normal_cdf(1.6448536269514722), 0.95, places=10)

    def test_risk_is_half_at_capacity(self):
        self.assertAlmostEqual(risk_probability(24, 24, 2), 0.5)

    def test_risk_grows_with_projection(self):
        self.assertLess(risk_probability(20, 24, 2), risk_probability(23, 24, 2))
        self.assertLess(risk_probability(23, 24, 2), risk_probability(26, 24, 2))


class ProjectionTest(unittest.TestCase):
    # Scenario 1 of #6: an upward trend is projected T + lag seconds ahead, with a sigma.
    def test_upward_trend_is_extrapolated(self):
        calculator = RiskCalculator.from_config(config())
        result = feed(calculator, [10 + 0.5 * 5 * i for i in range(7)])
        self.assertAlmostEqual(result.slope, 0.5, places=6)
        self.assertAlmostEqual(result.projected_rps, result.rps + 0.5 * 35, places=6)
        self.assertEqual(result.sigma_rps, 2)

    # Scenario 4 of #6: stationary noisy traffic stays near the current demand, no false alarm.
    def test_stable_traffic_does_not_drift(self):
        rng = random.Random(7)
        calculator = RiskCalculator.from_config(config())
        result = None
        for index in range(120):
            result = calculator.update(Sample(1000 + index * 5, 12 + rng.gauss(0, 0.8), 0.1, 1))
            self.assertLess(result.risk_at(1), 0.70)
        self.assertLess(abs(result.projected_rps - 12), 6)

    def test_window_keeps_only_recent_samples(self):
        calculator = RiskCalculator.from_config(config())
        feed(calculator, [50] * 10 + [5] * 7)
        self.assertTrue(all(rps == 5 for _, rps in calculator.window))

    def test_missing_sample_keeps_previous_projection(self):
        calculator = RiskCalculator.from_config(config())
        feed(calculator, [10, 12, 14])
        result = calculator.update(Sample(1015, None, None, 1))
        self.assertEqual(result.rps, 14)

    def test_no_data_returns_none(self):
        calculator = RiskCalculator.from_config(config())
        self.assertIsNone(calculator.update(Sample(1000, None, None, None)))


class RiskTest(unittest.TestCase):
    # Scenario 2 of #6: projected demand above the capacity of the replicas crosses the scale-up threshold.
    def test_projected_overload_crosses_threshold(self):
        calculator = RiskCalculator.from_config(config())
        result = feed(calculator, [10 + 2.5 * i for i in range(7)])
        self.assertGreater(result.projected_rps, 24)
        self.assertGreaterEqual(result.risk_at(1), 0.70)

    # Scenario 3 of #6: enough replicas for the projection keep the risk low.
    def test_headroom_keeps_risk_low(self):
        calculator = RiskCalculator.from_config(config())
        result = feed(calculator, [10 + 2.5 * i for i in range(7)])
        self.assertLess(result.risk_at(3), 0.30)

    def test_risk_never_divides_by_zero_replicas(self):
        calculator = RiskCalculator.from_config(config())
        result = feed(calculator, [10, 10, 10])
        self.assertEqual(result.risk_at(0), result.risk_at(1))


class SigmaTest(unittest.TestCase):
    def estimator(self):
        return SigmaEstimator(initial_rps=2, min_rps=1.0, window_seconds=300, min_errors=3, match_tolerance_seconds=2.5)

    def test_initial_value_until_enough_errors(self):
        sigma = self.estimator()
        sigma.add_projection(1005, 10)
        sigma.observe(1005, 14)
        self.assertEqual(sigma.value(), 2)

    def test_only_errors_above_the_projection_count(self):
        sigma = self.estimator()
        for index, error in enumerate([4, -4, 4, -4]):
            moment = 1000 + index * 5
            sigma.add_projection(moment, 10)
            sigma.observe(moment, 10 + error)
        self.assertAlmostEqual(sigma.value(), math.sqrt(2 * (16 + 16) / 4))

    def test_floor(self):
        sigma = self.estimator()
        for index in range(5):
            sigma.add_projection(1000 + index * 5, 10)
            sigma.observe(1000 + index * 5, 10)
        self.assertEqual(sigma.value(), 1.0)

    def test_old_errors_are_forgotten(self):
        sigma = self.estimator()
        for index in range(4):
            sigma.add_projection(1000 + index * 5, 10)
            sigma.observe(1000 + index * 5, 20)
        sigma.observe(2000, 10)
        self.assertEqual(len(sigma.errors), 0)


if __name__ == "__main__":
    unittest.main()
