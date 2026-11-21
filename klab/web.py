"""The lab site: python3 lab.py ui. A small web server on this host, standard library only.

It serves the pages in klab/ui and a JSON API the pages call. The same functions as the terminal commands
do the work, so the site and the terminal always agree: launching a lab from the site is `lab.py start`.

Safety: it listens on 127.0.0.1 unless told otherwise, every API call needs the key printed with the link
(so another page open in the browser can't drive it), the Host header must be this server's (so a web page
can't reach it through DNS tricks), and it only serves files from klab/ui. Launching labs needs root, as the
commands do: run it with sudo, or the site shows the command to run instead.
"""
import argparse
import base64
import contextlib
import hmac
import http.server
import io
import ipaddress
import json
import mimetypes
import os
import socket
import socketserver
import sys
import threading
import time
import urllib.parse
from typing import Callable, Dict, Optional, Tuple

from . import catalog, cli, labs, portal, site, state, system

UI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
LOCK = threading.Lock()                      # one lab action at a time, as in one terminal


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


@contextlib.contextmanager
def _captured(out):
    """Both stdout and stderr into out. (contextlib.redirect_stderr is Python 3.5+; lab hosts run 3.4.)"""
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = out
    try:
        yield
    finally:
        sys.stdout, sys.stderr = old


def run(fn: Callable, **kw) -> Dict:
    """Run a lab.py command and return what it printed, as the terminal would have shown it."""
    args = argparse.Namespace(**kw)
    out = io.StringIO()
    with LOCK, _captured(out):
        try:
            rc = fn(args)
        except PermissionError:
            print("This needs sudo. Start the site with: sudo python3 lab.py ui")
            rc = 1
        except Exception as e:                 # a broken command must not take the site down with it
            print("Something went wrong: %s" % e)
            rc = 1
    return {"ok": rc == 0, "output": out.getvalue().strip()}


def status() -> Dict:
    st, stats = state.load(), state.read_json("stats.json")
    pid = cli._pid()
    n = st.get("lab") or 0
    open_lab = catalog.for_engine(n) if n else None
    sc = st.get("scenario")
    now = time.time()
    case = None
    if sc and sc.get("start"):
        case = {"starts_in": max(0, int(sc["start"] - now)), "ends_in": max(0, int(sc["end"] - now)),
                "running": sc["start"] <= now < sc["end"], "finished": now >= sc["end"]}
    return {
        "root": is_root(), "linux": sys.platform.startswith("linux"),
        "network": bool(pid), "open": n, "open_id": open_lab["id"] if open_lab else None,
        "open_title": labs.LABS[n]["title"] if n else None, "case": case,
        # Whether the agent is up on its own port, never the port the lab's devices send to: that, and how much
        # each device sends, would give labs 2 and 5 away. lab.py status --reveal has them, for the instructor.
        "listening": system.listening(site.AGENT_PORT), "agent_port": site.AGENT_PORT,
        "sending_for": int(stats["updated"] - stats["since"]) if pid and stats.get("since") else 0,
        "portal": portal.public(portal.load()),
    }


def launch(lab: Dict, when: Optional[str] = None) -> Dict:
    """Start a lab the way its steps do: the network first if it isn't up, then lab.py start."""
    n = lab["engine"]
    if n is None:
        return {"ok": True, "output": "Nothing to launch on this host for this one: follow its steps."}
    if not is_root():
        cmd = "sudo python3 lab.py start %d" % n
        if not cli._pid():
            cmd = "sudo python3 lab.py up && " + cmd
        return {"ok": False, "needs_root": True, "cmd": cmd,
                "output": "The site isn't running with sudo, so it can't launch labs. Run this in a terminal:\n  " + cmd}
    outputs = []
    if not cli._pid():
        r = run(cli.cmd_up)
        # up's own "Next: ..." line is for the terminal; here the next step is the lab being launched.
        outputs.append("\n".join(x for x in r["output"].splitlines() if not x.startswith("Next:")))
        if not r["ok"]:
            return {"ok": False, "output": "\n".join(outputs)}
    after = None
    if n == 9:
        after = 5 if when == "soon" else 360
    r = run(cli.cmd_start, lab=n, after=after)
    outputs.append(r["output"])
    return {"ok": r["ok"], "output": "\n\n".join(o for o in outputs if o)}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "klab"
    key = ""
    hosts = set()

    def log_message(self, fmt, *args):                 # quiet: the terminal stays readable
        pass

    # ---- plumbing
    def _send(self, code: int, body: bytes, ctype: str, extra: Optional[Dict] = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _host_ok(self) -> bool:
        """This server's own name or an address, on its own port. A name that isn't ours is how a web page
        reaches a local server through DNS tricks, so it's refused; a plain address can't be used that way,
        and lets a laptop open the site on a host started with --host 0.0.0.0."""
        host = (self.headers.get("Host") or "").lower()
        if host in self.hosts:
            return True
        name, _, port = host.rpartition(":")
        if port != str(self.server.server_address[1]):
            return False
        try:
            ipaddress.ip_address(name.strip("[]"))
            return True
        except ValueError:
            return False

    def _key_ok(self) -> bool:
        given = (self.headers.get("X-Lab-Key") or "").encode("utf-8")
        return hmac.compare_digest(given, self.key.encode("utf-8"))

    def _body(self) -> Dict:
        try:
            n = min(int(self.headers.get("Content-Length") or 0), 65536)
            data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}

    # ---- requests
    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "Wrong host"})
        url = urllib.parse.urlsplit(self.path)
        if url.path.startswith("/api/"):
            if not self._key_ok():
                return self._json(403, {"error": "key"})
            return self._api("GET", url.path, dict(urllib.parse.parse_qsl(url.query)), {})
        self._static(url.path)

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "Wrong host"})
        url = urllib.parse.urlsplit(self.path)
        if not url.path.startswith("/api/") or not self._key_ok():
            return self._json(403, {"error": "key"})
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self._json(415, {"error": "JSON only"})
        self._api("POST", url.path, {}, self._body())

    def _static(self, path: str) -> None:
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        full = os.path.normpath(os.path.join(UI, rel))
        if not full.startswith(UI + os.sep) or not os.path.isfile(full):
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype, {"Content-Security-Policy":
                       "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                       "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"})

    def _api(self, method: str, path: str, q: Dict, body: Dict) -> None:
        route = (method, path)
        lab = catalog.by_id(body.get("id") or q.get("id") or "")
        if route == ("GET", "/api/catalog"):
            return self._json(200, catalog.catalog())
        if route == ("GET", "/api/status"):
            return self._json(200, status())
        if route == ("GET", "/api/hint"):
            if not lab or not lab["engine"] or lab.get("replay"):
                return self._json(404, {"error": "No hints for this one: its steps say what to look for."})
            hints = labs.LABS[lab["engine"]]["hints"]
            k = max(1, min(int(q.get("n") or 1), len(hints)))
            return self._json(200, {"n": k, "of": len(hints), "text": hints[k - 1]})
        if route == ("GET", "/api/answer"):
            if not lab:
                return self._json(404, {"error": "No such lab"})
            reveal = run(cli.cmd_status, reveal=True)["output"] if lab["engine"] and state.load().get("lab") == lab["engine"] else ""
            return self._json(200, {"answer": lab.get("answer", ""), "reveal": reveal})
        if route == ("GET", "/api/agent"):
            return self._json(200, run(cli.cmd_agent))
        if route == ("GET", "/api/portal"):
            return self._json(200, portal.public(portal.load()))
        if route == ("GET", "/api/reset"):
            return self._json(200, portal.plan("full" if q.get("scope") == "full" else "labs"))
        if route == ("POST", "/api/ask"):
            topic = body.get("topic")
            if not lab or topic not in labs.QUESTIONS:
                return self._json(400, {"error": "Ask about one of: " + ", ".join(labs.QUESTIONS)})
            n = lab["engine"] or 0
            return self._json(200, {"q": labs.QUESTIONS[topic], "a": labs.answer(n, topic),
                                    "who": labs.CUSTOMER.split(",")[0]})
        if route == ("POST", "/api/launch"):
            if not lab:
                return self._json(404, {"error": "No such lab"})
            return self._json(200, launch(lab, body.get("when")))
        if route == ("POST", "/api/check"):
            return self._json(200, run(cli.cmd_check))
        if route == ("POST", "/api/healthy"):
            if not is_root():
                return self._json(200, {"ok": False, "needs_root": True, "cmd": "sudo python3 lab.py start 0",
                                        "output": "Run this in a terminal:\n  sudo python3 lab.py start 0"})
            return self._json(200, run(cli.cmd_start, lab=0, after=None))
        if route == ("POST", "/api/stop"):
            if not is_root():
                return self._json(200, {"ok": False, "needs_root": True, "cmd": "sudo python3 lab.py down",
                                        "output": "Run this in a terminal:\n  sudo python3 lab.py down"})
            return self._json(200, run(cli.cmd_down))
        if route == ("POST", "/api/tell"):
            req = [str(x) for x in (body.get("request") or [])][:3]
            if not is_root():
                cmd = "sudo python3 lab.py tell " + " ".join(req)
                return self._json(200, {"ok": False, "needs_root": True, "cmd": cmd, "output": "Run this in a terminal:\n  " + cmd})
            return self._json(200, run(cli.cmd_tell, request=req))
        if route == ("POST", "/api/portal"):
            problem = portal.save(str(body.get("email", "")), str(body.get("token", "")), str(body.get("region", "us")))
            if problem:
                return self._json(400, {"error": problem})
            return self._json(200, portal.public(portal.load()))
        if route == ("POST", "/api/portal/test"):
            return self._json(200, portal.test(portal.load()))
        if route == ("POST", "/api/portal/forget"):
            portal.forget()
            return self._json(200, portal.public(portal.load()))
        if route == ("POST", "/api/reset"):
            scope = "full" if body.get("scope") == "full" else "labs"
            if scope == "full" and body.get("confirm") != "WIPE":
                return self._json(400, {"error": "Type WIPE to confirm a full wipe."})
            result = {"plan": portal.plan(scope), "host": None}
            if is_root():
                result["host"] = run(cli.cmd_down)
            else:
                result["host"] = {"ok": False, "needs_root": True, "cmd": "sudo python3 lab.py down",
                                  "output": "Run this in a terminal to stop the lab network:\n  sudo python3 lab.py down"}
            return self._json(200, result)
        self._json(404, {"error": "No such call"})


def new_key() -> str:
    """Twelve random URL-safe characters. (The secrets module is Python 3.6+.)"""
    return base64.urlsafe_b64encode(os.urandom(9)).decode()


def _lan_address() -> str:
    """This host's address on its main network, for the link a laptop opens. Connecting a UDP socket sends
    nothing; it only asks the kernel which address it would use (192.0.2.1 is a documentation address)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return ""
    finally:
        s.close()


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(host: str, port: int, key: str) -> Server:
    handler = type("LabHandler", (Handler,), {})
    httpd = Server((host, port), handler)
    real_port = httpd.server_address[1]
    names = {"127.0.0.1", "localhost", host}
    handler.key = key
    handler.hosts = {"%s:%d" % (n, real_port) for n in names if n not in ("", "0.0.0.0")}
    return httpd


def serve(host: str = "127.0.0.1", port: int = 8090, key: Optional[str] = None, open_browser: bool = False) -> int:
    key = key or os.environ.get("KLAB_KEY") or new_key()
    try:
        httpd = make_server(host, port, key)
    except OSError as e:
        print("Can't start the lab site on %s:%d: %s" % (host, port, e.strerror), file=sys.stderr)
        return 1
    port = httpd.server_address[1]
    shown = "127.0.0.1" if host in ("0.0.0.0", "") else host
    url = "http://%s:%d/?key=%s" % (shown, port, key)
    print("The lab site is running. Open:\n\n  %s\n" % url)
    if host not in ("127.0.0.1", "localhost"):
        lan = _lan_address() if host in ("0.0.0.0", "") else host
        if lan and lan != shown:
            print("From your laptop:\n\n  http://%s:%d/?key=%s\n" % (lan, port, key))
        print("Other machines can reach it with the key, so keep the link to yourself.\n")
    if not is_root():
        print("Started without sudo: you can read every lab, but launching them needs sudo python3 lab.py ui.\n")
    print("Ctrl-C to stop.")
    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
