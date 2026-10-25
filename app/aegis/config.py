import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"

# Environment variables that override one value of the file (used by the in-cluster Deployment).
# Not AEGIS_PORT: Kubernetes sets that one (tcp://...) for the Service named aegis.
ENV_OVERRIDES = [
    ("AEGIS_PROMETHEUS_URL", ("prometheus", "url"), str),
    ("AEGIS_ACTUATOR_MODE", ("actuator", "mode"), str),
    ("AEGIS_HTTP_PORT", ("server", "port"), int),
]


# Reads app/config.yaml, or the file given in AEGIS_CONFIG.
def load_config():
    path = os.environ.get("AEGIS_CONFIG") or DEFAULT_CONFIG_PATH
    with open(path) as f:
        config = yaml.safe_load(f)
    for variable, (section, key), kind in ENV_OVERRIDES:
        value = os.environ.get(variable)
        if value:
            config.setdefault(section, {})[key] = kind(value)
    return config
