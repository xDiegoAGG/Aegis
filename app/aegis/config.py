import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
def comma_list(text):
    values = []
    for part in text.split(","):
        if part.strip():
            values.append(part.strip())
    return values


ENV_OVERRIDES = [
    ("AEGIS_PROMETHEUS_URL", ("prometheus", "url"), str),
    ("AEGIS_HTTP_PORT", ("server", "port"), int),
    ("AEGIS_ALLOWED_ORIGIN", ("server", "allowed_origins"), comma_list),
]


# Reads app/config.yaml (or AEGIS_CONFIG) and applies the AEGIS_* overrides; AEGIS_PORT is set by Kubernetes.
def load_config():
    path = os.environ.get("AEGIS_CONFIG") or DEFAULT_CONFIG_PATH
    with open(path) as f:
        config = yaml.safe_load(f)
    for variable, (section, key), kind in ENV_OVERRIDES:
        value = os.environ.get(variable)
        if value:
            config.setdefault(section, {})[key] = kind(value)
    return config
