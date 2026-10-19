import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = ROOT / "docs" / "tests"
CONFIG = yaml.safe_load((ROOT / "app" / "config.yaml").read_text())
PROFILES = {"linear": ROOT / "kubernetes" / "load" / "linear.yaml",
            "fluctuating": ROOT / "kubernetes" / "load" / "fluctuating.yaml"}
HPA_FILES = {"aegis": ROOT / "kubernetes" / "hpa" / "aegis.yaml", "hpa": ROOT / "kubernetes" / "hpa" / "baseline.yaml"}
TESTS = {
    "test1-linear-ramp": ("linear", "aegis", "Test 1 - Aegis, linear ramp"),
    "test2-fluctuating": ("fluctuating", "aegis", "Test 2 - Aegis, fluctuating traffic"),
    "test3-hpa-baseline": ("linear", "hpa", "Test 3 - HPA only, linear ramp"),
}
RUNS_PER_TEST = 5
STEP = 5
BEFORE_SECONDS = 30
AFTER_SECONDS = {"aegis": 75, "hpa": 30}
COOLDOWN_SECONDS = 15
SUSTAINED_BUCKETS = 3
MAX_FAILED_RATIO = 0.01
L_SECONDS = CONFIG["degradation"]["p95_threshold_seconds"]
