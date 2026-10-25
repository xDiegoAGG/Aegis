import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = ROOT / "docs" / "tests"
CONFIG = yaml.safe_load((ROOT / "app" / "config.yaml").read_text())
PROFILES = {"linear": ROOT / "kubernetes" / "load" / "linear.yaml",
            "fluctuating": ROOT / "kubernetes" / "load" / "fluctuating.yaml",
            "spike": ROOT / "kubernetes" / "load" / "spike.yaml",
            "ramp-045": ROOT / "kubernetes" / "load" / "ramp-045.yaml",
            "ramp-050": ROOT / "kubernetes" / "load" / "ramp-050.yaml"}
# aegis: local Aegis writes minReplicas. metric: in-cluster Aegis, the HPA reads aegis_target_replicas.
HPA_FILES = {"aegis": ROOT / "kubernetes" / "hpa" / "aegis.yaml", "hpa": ROOT / "kubernetes" / "hpa" / "baseline.yaml",
             "metric": ROOT / "kubernetes" / "hpa" / "aegis-metric.yaml"}
TESTS = {
    "test1-linear-ramp": ("linear", "aegis", "Test 1 - Aegis, linear ramp"),
    "test2-fluctuating": ("fluctuating", "aegis", "Test 2 - Aegis, fluctuating traffic"),
    "test3-hpa-baseline": ("linear", "hpa", "Test 3 - HPA only, linear ramp"),
    "test4-spike-aegis": ("spike", "aegis", "Test 4 - Aegis, abrupt spike"),
    "test5-spike-hpa": ("spike", "hpa", "Test 5 - HPA only, abrupt spike"),
    "test6-ramp-045": ("ramp-045", "aegis", "Test 6 - Aegis, ramp at 0.45 req/s per s"),
    "test7-ramp-050": ("ramp-050", "aegis", "Test 7 - Aegis, ramp at 0.50 req/s per s"),
    "test8-metric-mode": ("linear", "metric", "Test 8 - Aegis through the Custom Metrics API, linear ramp"),
}
# Runs of each test in a full campaign (run_all.sh).
CAMPAIGN_RUNS = {"test1-linear-ramp": 5, "test3-hpa-baseline": 5, "test4-spike-aegis": 5, "test5-spike-hpa": 5,
                 "test2-fluctuating": 3, "test6-ramp-045": 3, "test7-ramp-050": 3, "test8-metric-mode": 3}
# Aegis tests with a trend at different speeds, for the boundary table of compare.py.
BOUNDARY_TESTS = ["test1-linear-ramp", "test6-ramp-045", "test7-ramp-050", "test4-spike-aegis"]
AEGIS_NAMESPACE = "aegis-system"
# Pairs with the same load, one with Aegis and one without, for compare.py.
COMPARISONS = [("test1-linear-ramp", "test3-hpa-baseline", "Gradual ramp"),
               ("test4-spike-aegis", "test5-spike-hpa", "Abrupt spike")]
# A scale-up is a false alarm if the planned traffic does not need the pod within this many seconds.
FALSE_ALARM_SECONDS = 60
# Load files are written for C = 24; runs scale them by C / 24 so they cross C at the same second anywhere.
REFERENCE_CAPACITY_RPS = 24
RUNS_PER_TEST = 1
STEP = 5
BEFORE_SECONDS = 30
AFTER_SECONDS = {"aegis": 75, "hpa": 30, "metric": 75}
COOLDOWN_SECONDS = 15
SUSTAINED_BUCKETS = 3
MAX_FAILED_RATIO = 0.01
L_SECONDS = CONFIG["degradation"]["p95_threshold_seconds"]
