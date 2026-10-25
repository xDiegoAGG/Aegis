import unittest
from types import SimpleNamespace
from unittest import mock
from aegis.actuator import MODE_METRIC, MODE_MIN_REPLICAS, HpaActuator, build_record
from aegis.collector import Sample
from aegis.decision import Decision
from aegis.risk import RiskResult


def hpa(min_replicas=1, max_replicas=3, current=2, desired=2):
    return SimpleNamespace(spec=SimpleNamespace(min_replicas=min_replicas, max_replicas=max_replicas),
                           status=SimpleNamespace(current_replicas=current, desired_replicas=desired))


class ActuatorTest(unittest.TestCase):
    def actuator(self, mode):
        actuator = HpaActuator("catalog-service", "default", False, mode)
        actuator.api = mock.Mock()
        actuator.api.read_namespaced_horizontal_pod_autoscaler.return_value = hpa()
        return actuator

    def test_min_replicas_mode_patches_only_on_change(self):
        actuator = self.actuator(MODE_MIN_REPLICAS)
        self.assertEqual(actuator.read_limits(), (1, 3))
        actuator.apply(1)
        actuator.api.patch_namespaced_horizontal_pod_autoscaler.assert_not_called()
        actuator.apply(2)
        actuator.api.patch_namespaced_horizontal_pod_autoscaler.assert_called_once_with(
            "catalog-service", "default", {"spec": {"minReplicas": 2}})
        self.assertEqual(actuator.applied, 2)

    def test_metric_mode_never_writes(self):
        actuator = self.actuator(MODE_METRIC)
        self.assertEqual(actuator.read_limits(), (2, 3))
        actuator.apply(3)
        actuator.api.patch_namespaced_horizontal_pod_autoscaler.assert_not_called()
        self.assertEqual(actuator.applied, 3)

    def test_observe(self):
        observed = self.actuator(MODE_MIN_REPLICAS).observe()
        self.assertEqual(observed, {"hpa_min": 1, "hpa_current": 2, "hpa_desired": 2})

    def test_record_has_risk_with_one_pod_less(self):
        result = RiskResult(10, 30.0, 0.5, 40.0, 2.0, 6, 24.0)
        decision = Decision(10, "hold", 2, 2, result.risk_at(2), "")
        record = build_record(Sample(10, 30.0, 0.2, 2), result, decision, 2, 24.0, {"hpa_min": 2})
        self.assertEqual(record["capacity_rps"], 48.0)
        self.assertAlmostEqual(record["risk_one_less"], round(result.risk_at(1), 4))
        self.assertEqual(record["hpa_min"], 2)


if __name__ == "__main__":
    unittest.main()
