import argparse
import json
import shutil
import socket
import subprocess
import sys
from load import read_profile, total_duration
from run import saved_calibrations
from settings import AEGIS_NAMESPACE, AFTER_SECONDS, CAMPAIGN_RUNS, PROFILES, ROOT, TESTS, TESTS_DIR

# Time a run takes besides its load: reset to 1 pod, cooldown, Aegis start, k6 polling, Prometheus export.
RUN_OVERHEAD_SECONDS = 200


def kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_cluster():
    code, out, err = kubectl(["get", "nodes", "-o", "json", "--request-timeout=10s"])
    if code != 0:
        return False, "the cluster does not answer: " + (err.splitlines() or ["?"])[-1]
    nodes = json.loads(out)["items"]
    ready = [n for n in nodes if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"]["conditions"])]
    return len(ready) == len(nodes), str(len(ready)) + "/" + str(len(nodes)) + " node(s) Ready"


def check_environment():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_env.py")], capture_output=True, text=True)
    failed = [line for line in result.stdout.splitlines() if line.startswith("FAIL")]
    if result.returncode != 0:
        return False, "; ".join(failed) or result.stdout[-200:]
    return True, "scripts/check_env.py: every check OK"


def check_calibration():
    code, out, err = kubectl(["get", "configmap", "aegis-calibration", "-o", "json"])
    if code != 0:
        return False, "no calibration: cd app && python3 -m aegis.calibrate (~17 min)"
    calibration = json.loads(json.loads(out)["data"]["calibration.json"])
    code, out, err = kubectl(["get", "deploy", "catalog-service", "-o", "json"])
    container = json.loads(out)["spec"]["template"]["spec"]["containers"][0]
    limits = (container.get("resources") or {}).get("limits") or {}
    saved = calibration.get("environment", {})
    changes = []
    if saved.get("image") not in (None, container["image"]):
        changes.append("image")
    if saved.get("cpu_limit") not in (None, limits.get("cpu", "")):
        changes.append("cpu limit")
    if changes:
        return False, "the service changed since the calibration (" + ", ".join(changes) + "): recalibrate"
    return True, ("C = " + str(calibration["capacity_rps"]) + " req/s, T = " + str(calibration["startup_time_seconds"])
                  + " s, measured " + calibration["measured_at"])


def current_calibration():
    code, out, err = kubectl(["get", "configmap", "aegis-calibration", "-o", "jsonpath={.data.measured_at}"])
    return out if code == 0 else None


def check_runs_consistent(tests):
    measured = current_calibration()
    if measured is None:
        return False, "no calibration"
    mixed = []
    for name in tests:
        other = saved_calibrations(TESTS_DIR / name) - {measured}
        if other:
            mixed.append(name)
    if mixed:
        return False, ("runs made with another calibration in " + ", ".join(mixed)
                       + ": run the campaign with --archive to move them to archive/")
    return True, "every saved run uses the current calibration (" + measured + ")"


def check_no_load():
    code, out, err = kubectl(["get", "jobs", "-o", "json"])
    running = [j["metadata"]["name"] for j in json.loads(out or '{"items": []}')["items"]
               if j["metadata"]["name"] in ["load-" + p for p in PROFILES] + ["aegis-calibration-load"]
               and not j["status"].get("succeeded") and not j["status"].get("failed")]
    if running:
        return False, "load running: " + ", ".join(running) + " (python3 reset.py)"
    return True, "no load running"


def check_no_local_aegis():
    result = subprocess.run(["pgrep", "-af", "aegis.(actuator|calibrate)"], capture_output=True, text=True)
    lines = [line for line in result.stdout.splitlines() if "pgrep" not in line]
    if lines:
        return False, "another Aegis runs on this machine (stop it, the campaign starts its own): " + lines[0]
    return True, "no other Aegis on this machine"


def check_port():
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8080)) == 0:
            return True, "port 8080 busy: the dashboard of the runs will not be served (the runs still work)"
    return True, "port 8080 free: watch the runs live on http://localhost:8080"


def check_metric_mode(tests):
    if not any(TESTS[name][1] == "metric" for name in tests):
        return True, "not needed"
    code, out, err = kubectl(["get", "deploy", "aegis", "-n", AEGIS_NAMESPACE, "-o", "name"])
    if code != 0:
        return False, "Aegis not deployed in the cluster: scripts/setup.sh --aegis --hpa aegis-metric"
    code, out, err = kubectl(["get", "apiservice", "v1beta1.custom.metrics.k8s.io", "-o",
                              "jsonpath={.status.conditions[?(@.type=='Available')].status}"])
    if out != "True":
        return False, "the Custom Metrics API is not available (prometheus-adapter)"
    return True, "in-cluster Aegis deployed, Custom Metrics API available"


def check_python():
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False, "matplotlib missing: pip install -r scripts/experiments/requirements.txt"
    if shutil.disk_usage(TESTS_DIR).free < 1_000_000_000:
        return False, "less than 1 GB free on disk"
    return True, "matplotlib installed, disk space OK"


# Expected minutes of the runs still missing.
def estimate(tests, runs):
    total = 0
    for name in tests:
        profile_name, mode, title = TESTS[name]
        done = len(list((TESTS_DIR / name / "data").glob("run-*-summary.json")))
        missing = max(0, runs[name] - done)
        total += missing * (total_duration(read_profile(profile_name)) + AFTER_SECONDS[mode] + RUN_OVERHEAD_SECONDS)
    return round(total / 60)


def preflight(tests, runs, archive=False):
    checks = [
        ("Cluster", check_cluster),
        ("Environment", check_environment),
        ("Calibration", check_calibration),
        ("No load running", check_no_load),
        ("No other Aegis", check_no_local_aegis),
        ("Dashboard port", check_port),
        ("Metric mode", lambda: check_metric_mode(tests)),
        ("Python and disk", check_python),
    ]
    if not archive:
        checks.append(("One calibration per test", lambda: check_runs_consistent(tests)))
    failed = 0
    for name, check in checks:
        try:
            ok, detail = check()
        except Exception as error:
            ok, detail = False, str(error)
        print("OK  " if ok else "FAIL", name, "-", detail)
        if not ok:
            failed += 1
            if name == "Cluster":
                break
    if failed:
        print(failed, "check(s) failed: fix them before running the tests")
        return False
    print("Ready. Missing runs:", ", ".join(name + " x" + str(runs[name]) for name in tests),
          "- about", estimate(tests, runs), "minutes")
    return True


def main():
    parser = argparse.ArgumentParser(description="Check that everything is in place before running the tests")
    parser.add_argument("tests", nargs="*", default=list(CAMPAIGN_RUNS), choices=list(TESTS))
    args = parser.parse_args()
    runs = {name: CAMPAIGN_RUNS.get(name, 1) for name in args.tests}
    sys.exit(0 if preflight(args.tests, runs) else 1)


if __name__ == "__main__":
    main()
