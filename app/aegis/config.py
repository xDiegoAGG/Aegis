import os
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


# AEGIS_CONFIG: path to a different config file.
# AEGIS_PROMETHEUS_URL: overrides prometheus.url (e.g. http://localhost:9090 through the port-forward).
def load_config(path=None):
    config_path = Path(path or os.environ.get("AEGIS_CONFIG") or DEFAULT_CONFIG_PATH)
    with open(config_path) as f:
        config = yaml.safe_load(f)

    prometheus_url = os.environ.get("AEGIS_PROMETHEUS_URL")
    if prometheus_url:
        config["prometheus"]["url"] = prometheus_url

    return config
