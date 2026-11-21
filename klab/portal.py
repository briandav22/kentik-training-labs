"""Your Kentik portal, as the lab site sees it: the connection details, and what a reset would take out.

A first pass (Nov 20, 2026). Brian: "The crux is going to be API creds and emails, as a placeholder let's put
that in the UI you build and figure it out later." So the site keeps the portal's email, API token and region
on this host, can try them with one read-only call (the device list), and shows exactly what a reset would
remove. It changes nothing in the portal yet: adding a lab's devices for you and removing what the labs added
come next, once they have been tested against a real portal (PORTAL_WRITES). Until then the site says what to
remove by hand, and does the host's part of a reset for real.

The details live in ~/.kentik.env (of the user who ran sudo, if anyone did), readable only by that user, as
Brian's other labs keep them. They never go in the repo, and the site never sends the token back to a page.
"""
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

from . import catalog, site, state

# Switched on once adding and removing devices through the API has been tested against a real portal.
PORTAL_WRITES = False

REGIONS = {"us": "https://api.kentik.com/api/v5", "eu": "https://api.kentik.eu/api/v5"}
KEYS = ("KENTIK_EMAIL", "KENTIK_API_TOKEN", "KENTIK_REGION")


def env_path() -> str:
    if os.environ.get("KLAB_PORTAL_FILE"):
        return os.environ["KLAB_PORTAL_FILE"]
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            import pwd
            return os.path.join(pwd.getpwnam(user).pw_dir, ".kentik.env")
        except (ImportError, KeyError):
            pass
    return os.path.expanduser("~/.kentik.env")


def load() -> Dict[str, str]:
    """The portal details on this host: email, token and region ('' when unset)."""
    out = {"email": "", "token": "", "region": "us"}
    try:
        with open(env_path()) as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                v = v.strip().strip('"').strip("'")
                if k == "KENTIK_EMAIL":
                    out["email"] = v
                elif k == "KENTIK_API_TOKEN":
                    out["token"] = v
                elif k == "KENTIK_REGION" and v.lower() in REGIONS:
                    out["region"] = v.lower()
    except OSError:
        pass
    return out


def save(email: str, token: str, region: str) -> Optional[str]:
    """Write the details, keeping any other lines in the file. Returns a problem, or None."""
    email, token, region = email.strip(), token.strip(), (region or "us").strip().lower()
    if "@" not in email or len(email) > 254:
        return "That doesn't look like an email address."
    if region not in REGIONS:
        return "The region is US or EU."
    if token and (len(token) > 200 or any(c.isspace() for c in token)):
        return "That doesn't look like an API token."
    old = load()
    token = token or old["token"]                    # an empty token field keeps the saved one
    path = env_path()
    keep = []
    try:
        with open(path) as f:
            keep = [line.rstrip("\n") for line in f if line.partition("=")[0].strip() not in KEYS]
    except OSError:
        pass
    lines = keep + ["KENTIK_EMAIL=%s" % email, "KENTIK_API_TOKEN=%s" % token, "KENTIK_REGION=%s" % region]
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(path + ".tmp", path)
    os.chmod(path, 0o600)
    _give_to_sudo_user(path)
    return None


def forget() -> None:
    path = env_path()
    try:
        with open(path) as f:
            keep = [line.rstrip("\n") for line in f if line.partition("=")[0].strip() not in KEYS]
    except OSError:
        return
    if any(line.strip() for line in keep):
        with open(path, "w") as f:
            f.write("\n".join(keep) + "\n")
    else:
        os.remove(path)


def _give_to_sudo_user(path: str) -> None:
    """When the site runs under sudo, the file still belongs to the person who ran it."""
    uid, gid = os.environ.get("SUDO_UID"), os.environ.get("SUDO_GID")
    if uid and gid and hasattr(os, "chown"):
        try:
            os.chown(path, int(uid), int(gid))
        except OSError:
            pass


def public(cfg: Dict[str, str]) -> Dict:
    """What a page may see: never the token, only whether one is saved and its last four characters."""
    tok = cfg.get("token", "")
    return {"email": cfg.get("email", ""), "region": cfg.get("region", "us"), "token_set": bool(tok),
            "token_end": tok[-4:] if len(tok) >= 8 else "", "connected": bool(cfg.get("email") and tok),
            "file": env_path(), "writes": PORTAL_WRITES, "tested": _last_test()}


def base(cfg: Dict[str, str]) -> str:
    return os.environ.get("KLAB_PORTAL_BASE") or REGIONS.get(cfg.get("region", "us"), REGIONS["us"])


def _get(cfg: Dict[str, str], path: str, timeout: float = 8) -> Tuple[int, Dict]:
    req = urllib.request.Request(base(cfg) + path, headers={
        "X-CH-Auth-Email": cfg["email"], "X-CH-Auth-API-Token": cfg["token"],
        "Accept": "application/json", "User-Agent": "kentik-training-labs"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, json.loads(r.read().decode() or "{}")


def test(cfg: Dict[str, str]) -> Dict:
    """One read-only call: list the portal's devices. Says whether the details work, and what it found."""
    if not (cfg.get("email") and cfg.get("token")):
        return _remember({"ok": False, "message": "Save your email and API token first."})
    try:
        _, body = _get(cfg, "/devices")
    except urllib.error.HTTPError as e:
        msg = ("Kentik didn't accept that email and API token." if e.code in (401, 403)
               else "Kentik answered with an error (HTTP %d)." % e.code)
        return _remember({"ok": False, "message": msg})
    except (urllib.error.URLError, OSError, ValueError) as e:
        why = getattr(e, "reason", e)
        return _remember({"ok": False, "message": "Couldn't reach %s: %s. Can this host reach the internet over HTTPS?"
                          % (base(cfg).split("/api")[0], why)})
    devices = body.get("devices", []) if isinstance(body, dict) else []
    names = sorted(d.get("device_name", "") for d in devices if isinstance(d, dict))
    lab = [n for n in names if n in site.DEVICES]
    return _remember({"ok": True, "message": "Connected. Your portal has %d device%s%s." % (
        len(names), "" if len(names) == 1 else "s",
        ", %d of them the lab's" % len(lab) if lab else ""), "devices": names})


def _remember(result: Dict) -> Dict:
    result["at"] = time.time()
    try:
        os.makedirs(state.home(), exist_ok=True)
        with open(state.path("portal-test.json"), "w") as f:
            json.dump({k: result[k] for k in ("ok", "message", "at")}, f)
    except OSError:
        pass
    return result


def _last_test() -> Dict:
    return state.read_json("portal-test.json")


def plan(scope: str) -> Dict:
    """What a reset would do, on this host and in the portal. scope: 'labs' (keeps the agent) or 'full'."""
    host = ["Stop the lab network: the devices' addresses on loopback, the background sender, the lab's firewall "
            "rule and its SNMP lines come off this host (the same as lab.py down)",
            "Clear the site's progress: steps ticked and labs marked done"]
    seen = []
    for lab in catalog.LABS:
        for a in lab["adds"]:
            if a not in seen and a != "agent":
                seen.append(a)
    portal = [{"what": catalog.ADDS[a], "kind": a, "how": _how(a)} for a in seen]
    keep = ["Your Universal Agent, installed and authorized, so the next lab starts straight away"]
    if scope == "full":
        portal.append({"what": catalog.ADDS["agent"], "kind": "agent",
                       "how": "In the portal, remove the agent; then uninstall it from this host with the steps from "
                              "your portal. Kentik SE team: confirm an API call for this."})
        keep = []
    return {"scope": scope, "host": host, "portal": portal, "keep": keep, "writes": PORTAL_WRITES,
            "note": "" if PORTAL_WRITES else
            "The portal part is a list for now: the site doesn't change your portal yet. Remove these by hand; "
            "the next version does it for you."}


def _how(kind: str) -> str:
    return {
        "devices": "In your portal, remove edge-rtr-01, core-sw-01 and branch-rtr-01. Their old traffic may stay.",
        "device-setting": "Goes with the devices.",
        "alert-policy": "In your portal's alerting, delete the policy you built for web-01.",
        "nms-device": "In your portal's NMS, remove the device at 127.0.0.1.",
        "tests": "In your portal's synthetics, delete the two tests to example.com.",
        "network-context": "In AI Advisor's custom network context, remove the three subnets you added.",
        "runbook": "Delete the runbook \"Full internet link\".",
    }.get(kind, "")


def lab_devices() -> List[Dict]:
    """The devices a lab expects in the portal: name, sending address, kind. The site will add them (next)."""
    return [{"name": n, "ip": d["ip"], "kind": d["kind"]} for n, d in site.DEVICES.items()]
