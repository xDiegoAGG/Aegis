import os
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


# Reads app/config.yaml, or the file given in AEGIS_CONFIG.
def load_config():
    path = os.environ.get("AEGIS_CONFIG") or DEFAULT_CONFIG_PATH
    with open(path) as f:
        return yaml.safe_load(f)
