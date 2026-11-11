"""Where the lab keeps what it is doing, so the commands and the background sender agree."""
import json
import os
from typing import Dict

from . import site


def home() -> str:
    return os.environ.get("KLAB_HOME", "/var/tmp/klab")


def path(name: str) -> str:
    return os.path.join(home(), name)


def baseline() -> Dict:
    """A healthy customer: every device sends from its Flow IP to the agent's port, unsampled, no firewall."""
    return {"lab": 0, "collector": "127.0.0.1", "port": site.AGENT_PORT,
            "source": {d: "ip" for d in site.DEVICES},       # "ip" (the Flow IP) or "other_ip"
            "sample": {d: 1 for d in site.DEVICES},
            "firewall": False, "bind": True}


def load() -> Dict:
    try:
        with open(path("state.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return baseline()


def save(st: Dict) -> None:
    os.makedirs(home(), exist_ok=True)
    tmp = path("state.json.tmp")
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, path("state.json"))
    os.chmod(path("state.json"), 0o644)


def read_json(name: str) -> Dict:
    try:
        with open(path(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
