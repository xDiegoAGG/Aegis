import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HPA_FILE = ROOT / "kubernetes" / "hpa" / "aegis.yaml"
LOAD_SELECTOR = "app.kubernetes.io/part-of=aegis-load"


def kubectl(args):
    result = subprocess.run(["kubectl"] + args, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("kubectl " + " ".join(args) + ": " + result.stderr.decode().strip())
    return result.stdout


# Stops any load and leaves 1 Ready catalog-service pod with the Aegis HPA, for example between two demos.
def main():
    kubectl(["delete", "job", "-l", LOAD_SELECTOR, "--ignore-not-found", "--wait=true", "--cascade=foreground"])
    kubectl(["delete", "hpa", "catalog-service", "--ignore-not-found", "--wait=true"])
    kubectl(["scale", "deploy/catalog-service", "--replicas=1"])
    deadline = time.monotonic() + 600
    while True:
        deployment = json.loads(kubectl(["get", "deploy", "catalog-service", "-o", "json"]))
        ready = deployment["status"].get("readyReplicas", 0)
        total = deployment["status"].get("replicas", 0)
        if ready == 1 and total == 1:
            break
        if time.monotonic() > deadline:
            print("The service did not go back to 1 pod")
            sys.exit(1)
        time.sleep(5)
    kubectl(["apply", "-f", str(HPA_FILE)])
    print("Reset done: no load, 1 pod, Aegis HPA")


if __name__ == "__main__":
    main()
