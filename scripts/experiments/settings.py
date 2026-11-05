import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TESTS_DIR = ROOT / "docs" / "tests"
CONFIG = yaml.safe_load((ROOT / "app" / "config.yaml").read_text())
PROFILES = {"linear": ROOT / "kubernetes" / "load" / "linear.yaml",
            "fluctuating": ROOT / "kubernetes" / "load" / "fluctuating.yaml",
            "spike": ROOT / "kubernetes" / "load" / "spike.yaml",
            # Boundary ramps of the October campaign (tests 6 and 7); not in the design, kept to read those runs.
            "ramp-045": ROOT / "kubernetes" / "load" / "ramp-045.yaml",
            "ramp-050": ROOT / "kubernetes" / "load" / "ramp-050.yaml"}
# aegis: local Aegis writes minReplicas. hpa: the default HPA (CPU 70%, 300 s scale-down window).
# hpa-tuned: an HPA tuned a priori (CPU 50%, 60 s window). metric: in-cluster Aegis through the Custom Metrics API.
HPA_FILES = {"aegis": ROOT / "kubernetes" / "hpa" / "aegis.yaml", "hpa": ROOT / "kubernetes" / "hpa" / "baseline.yaml",
             "hpa-tuned": ROOT / "kubernetes" / "hpa" / "tuned.yaml",
             "metric": ROOT / "kubernetes" / "hpa" / "aegis-metric.yaml"}

# The experimental design (docs/experiments/design.md): randomized complete block design, 3 x 3 factorial.
# Factor A, autoscaler; factor B, load; every block runs the 9 cells once in a random order; 6 blocks.
AUTOSCALERS = ["aegis", "hpa", "hpa-tuned"]
LOADS = {"ramp": "linear", "spike": "spike", "waves": "fluctuating"}
BLOCKS = 6
DESIGN_SEED = 20261104
DESIGN_TESTS = {load + "-" + autoscaler: (profile, autoscaler, "Design, " + load + ", " + autoscaler)
                for load, profile in LOADS.items() for autoscaler in AUTOSCALERS}
# Primary response (one per load and comparison, Holm-corrected) and secondary responses.
PRIMARY_METRIC = "failed_percent"
SECONDARY_METRICS = ["degraded_seconds", "pod_minutes_window", "first_scale_up_s", "reasks"]
# Every run records this long after k6 ends, the same for every autoscaler: the default HPA keeps its
# pods 300 s after the last high recommendation, so all of them are back at 1 pod in the cost window.
TAIL_SECONDS = 360

# The October 2026 campaign (32 runs, one factor at a time, not randomized). Kept only to read and
# report its saved runs in docs/tests; campaign.py does not run it. Why it was replaced: design.md.
OCTOBER_2026_TESTS = {
    "test1-linear-ramp": ("linear", "aegis", "Test 1 - Aegis, linear ramp"),
    "test2-fluctuating": ("fluctuating", "aegis", "Test 2 - Aegis, fluctuating traffic"),
    "test3-hpa-baseline": ("linear", "hpa", "Test 3 - HPA only, linear ramp"),
    "test4-spike-aegis": ("spike", "aegis", "Test 4 - Aegis, abrupt spike"),
    "test5-spike-hpa": ("spike", "hpa", "Test 5 - HPA only, abrupt spike"),
    "test6-ramp-045": ("ramp-045", "aegis", "Test 6 - Aegis, ramp at 0.45 req/s per s"),
    "test7-ramp-050": ("ramp-050", "aegis", "Test 7 - Aegis, ramp at 0.50 req/s per s"),
    "test8-metric-mode": ("linear", "metric", "Test 8 - Aegis through the Custom Metrics API, linear ramp"),
}
# Every test the tools can read or report; only DESIGN_TESTS are run by campaign.py.
TESTS = dict(DESIGN_TESTS, **OCTOBER_2026_TESTS)
# Aegis tests with a trend at different speeds, for the boundary table of compare.py (October campaign).
BOUNDARY_TESTS = ["test1-linear-ramp", "test6-ramp-045", "test7-ramp-050", "test4-spike-aegis"]
AEGIS_NAMESPACE = "aegis-system"
# Pairs with the same load, one with Aegis and one without, for compare.py (October campaign).
COMPARISONS = [("test1-linear-ramp", "test3-hpa-baseline", "Gradual ramp"),
               ("test4-spike-aegis", "test5-spike-hpa", "Abrupt spike")]
# A scale-up is a false alarm if the planned traffic does not need the pod within this many seconds.
FALSE_ALARM_SECONDS = 60
# Load files are written for C = 24; runs scale them by C / 24 so they cross C at the same second anywhere.
REFERENCE_CAPACITY_RPS = 24
RUNS_PER_TEST = 1
STEP = 5
BEFORE_SECONDS = 30
# October campaign tails; design runs use TAIL_SECONDS for every autoscaler.
AFTER_SECONDS = {"aegis": 75, "hpa": 30, "metric": 75, "hpa-tuned": 30}
COOLDOWN_SECONDS = 15
SUSTAINED_BUCKETS = 3
MAX_FAILED_RATIO = 0.01
L_SECONDS = CONFIG["degradation"]["p95_threshold_seconds"]
