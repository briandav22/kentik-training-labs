"""The lab command: python3 lab.py <command>."""
import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional

from . import labs, netflow, site, state, system

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pid() -> Optional[int]:
    try:
        with open(state.path("sender.pid")) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        return None


def _need_root(what: str) -> bool:
    if os.geteuid() != 0:
        print("This needs sudo:  sudo python3 lab.py %s" % what, file=sys.stderr)
        return True
    return False


def _ticket(n: int) -> None:
    lab = labs.LABS[n]
    print("\n  Lab %d: %s" % (n, lab["title"]))
    print("  From: %s\n" % labs.CUSTOMER)
    for line in lab["ticket"]:
        print("    " + line)
    print("\n  Ask the customer:   python3 lab.py ask")
    print("  Stuck?              python3 lab.py hint")
    print("  Think it's fixed?   sudo python3 lab.py check\n")


def cmd_up(args) -> int:
    if _need_root("up"):
        return 1
    problems = system.aliases()
    if problems:
        print("Couldn't add the devices' addresses to loopback:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    if _pid():
        print("The lab is already running. See: python3 lab.py status")
        return 0
    os.makedirs(state.home(), exist_ok=True)
    if not os.path.exists(state.path("state.json")):
        state.save(state.baseline())
    log = open(state.path("sender.log"), "a")
    p = subprocess.Popen([sys.executable, "-m", "klab.engine"], cwd=ROOT, stdout=log, stderr=log,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    with open(state.path("sender.pid"), "w") as f:
        f.write(str(p.pid))
    time.sleep(1.2)
    if p.poll() is not None:
        print("The sender stopped straight away. See %s" % state.path("sender.log"), file=sys.stderr)
        return 1
    print("The lab network is up: %d devices are sending flow." % len(site.DEVICES))
    print("Next:  sudo python3 lab.py start 1")
    return 0


def cmd_down(args) -> int:
    if _need_root("down"):
        return 1
    pid = _pid()
    if pid:
        os.kill(pid, signal.SIGTERM)
    st = state.load()
    problem = system.firewall(int(st["port"]), False) or system.firewall(site.AGENT_PORT, False)
    system.aliases(remove=True)
    state.save(state.baseline())
    for name in ("sender.pid", "stats.json"):
        try:
            os.remove(state.path(name))
        except OSError:
            pass
    if problem:
        print(problem, file=sys.stderr)
    print("The lab network is down. Nothing of it is left on this host.")
    return 0


def cmd_start(args) -> int:
    if _need_root("start %d" % args.lab):
        return 1
    if args.lab != 0 and args.lab not in labs.LABS:
        print("No lab %d. See: python3 lab.py labs" % args.lab, file=sys.stderr)
        return 1
    old = state.load()
    st = state.baseline()
    st["collector"], st["bind"] = old.get("collector", "127.0.0.1"), old.get("bind", True)
    st["lab"] = args.lab
    if args.lab:
        labs.LABS[args.lab]["fault"](st)
    problem = system.firewall(int(old["port"]), False) or system.firewall(site.AGENT_PORT, st["firewall"])
    if problem:
        print(problem, file=sys.stderr)
        return 1
    state.save(st)
    if not _pid():
        print("Note: the lab network isn't running yet. Start it with: sudo python3 lab.py up")
    if args.lab == 0:
        print("Back to a healthy network: every device sends from its Flow IP to UDP %d." % site.AGENT_PORT)
    else:
        _ticket(args.lab)
    return 0


def cmd_ticket(args) -> int:
    n = state.load()["lab"]
    if not n:
        print("No lab is open. Start one: sudo python3 lab.py start 1")
        return 0
    _ticket(n)
    return 0


def cmd_labs(args) -> int:
    cur = state.load()["lab"]
    for n, lab in sorted(labs.LABS.items()):
        print("  %d  %s%s" % (n, lab["title"], "   (open now)" if n == cur else ""))
    print("  0  a healthy network, no problem")
    return 0


def cmd_ask(args) -> int:
    n = state.load()["lab"]
    if not args.topic:
        print("What do you want to ask the customer?")
        for t, q in labs.QUESTIONS.items():
            print("  python3 lab.py ask %-9s %s" % (t, q))
        return 0
    print("%s: %s" % (labs.CUSTOMER.split(",")[0], labs.answer(n, args.topic)))
    return 0


def cmd_tell(args) -> int:
    if _need_root("tell " + " ".join(args.request)):
        return 1
    st, r = state.load(), args.request
    who = labs.CUSTOMER.split(",")[0]
    if len(r) == 2 and r[0] == "port" and r[1].isdigit() and 0 < int(r[1]) < 65536:
        system.firewall(int(st["port"]), False)
        st["port"] = int(r[1])
        if st["firewall"]:
            system.firewall(st["port"], True)
        print("%s: Done. All three devices now export to UDP %d." % (who, st["port"]))
    elif len(r) == 3 and r[0] == "source" and r[1] in site.DEVICES and r[2] in ("loopback", "interface"):
        st["source"][r[1]] = "ip" if r[2] == "loopback" else "other_ip"
        d = site.DEVICES[r[1]]
        print("%s: Done. %s now exports from %s (%s)." % (
            who, r[1], d["source"] if r[2] == "loopback" else d["other_source"], d[st["source"][r[1]]]))
    else:
        print("Things you can ask the customer to change:\n"
              "  sudo python3 lab.py tell port <number>                      export to a different UDP port\n"
              "  sudo python3 lab.py tell source <device> loopback|interface   export from a different address",
              file=sys.stderr)
        return 1
    state.save(st)
    return 0


def cmd_hint(args) -> int:
    n = state.load()["lab"]
    if not n:
        print("No lab is open.")
        return 0
    hints = labs.LABS[n]["hints"]
    k = max(1, min(args.n, len(hints)))
    print("Hint %d of %d: %s" % (k, len(hints), hints[k - 1]))
    if k < len(hints):
        print("More:  python3 lab.py hint %d" % (k + 1))
    return 0


def cmd_check(args) -> int:
    st = state.load()
    n = st["lab"]
    if not n:
        print("No lab is open.")
        return 0
    if os.geteuid() != 0 and n == 4:
        return 1 if _need_root("check") else 0
    if not _pid():
        print("The lab network isn't running. Start it: sudo python3 lab.py up")
        return 1
    ok, lines = labs.LABS[n]["check"](st)
    print(("Solved on this host." if ok else "Not yet.") if n != 5 else "Check this one in Kentik.")
    for line in lines:
        print("  " + line)
    return 0 if ok else 1


def _age(secs: float) -> str:
    secs = int(secs)
    return "%dh %02dm" % (secs // 3600, secs % 3600 // 60) if secs >= 3600 else "%dm %02ds" % (secs // 60, secs % 60)


def cmd_status(args) -> int:
    st, stats, pid = state.load(), state.read_json("stats.json"), _pid()
    n = st["lab"]
    print("Lab network: %s" % ("running" if pid else "stopped  (sudo python3 lab.py up)"))
    print("Open lab:    %s" % ("%d, %s" % (n, labs.LABS[n]["title"]) if n else "none"))
    if pid and stats:
        print("Sending for: %s" % _age(stats["updated"] - stats["since"]))
        for d, s in stats["devices"].items():
            print("  %-14s %7d flow records sent" % (d, s["flows"]))
    if args.reveal:
        print("\nFor the instructor (this gives the lab away):")
        print("  devices send to   %s:%d" % (st["collector"], st["port"]))
        for d in site.DEVICES:
            print("  %-14s from %-10s sampling 1 in %d" % (d, site.DEVICES[d][st["source"][d]], st["sample"][d]))
        print("  firewall rule     %s" % ("present" if system.firewall_present(int(st["port"])) else "absent"))
        print("  listening on %d  %s" % (st["port"], "yes" if system.listening(int(st["port"])) else "no"))
        for d, s in (stats.get("devices") or {}).items():
            print("  %-14s true %.2f Mbps, exported %.2f Mbps" % (d, s["true_bps"] / 1e6, s["sent_bps"] / 1e6))
    return 0


def cmd_listen(args) -> int:
    """A stand-in for the Universal Agent, for testing the lab without one."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", args.port))
    except OSError as e:
        print("Can't listen on UDP %d: %s" % (args.port, e.strerror), file=sys.stderr)
        return 1
    s.settimeout(1.0)
    print("Listening on UDP %d. Ctrl-C to stop." % args.port)
    templates, seen, end = {}, {}, (time.time() + args.seconds if args.seconds else None)
    last = time.time()
    try:
        while end is None or time.time() < end:
            try:
                pkt, (src, _) = s.recvfrom(65535)
                _, recs = netflow.decode(pkt, templates)
                c = seen.setdefault(src, [0, 0, 0])
                c[0] += len(recs)
                c[1] += sum(r["bytes"] for r in recs)
                c[2] += 1
            except socket.timeout:
                pass
            except ValueError:
                continue
            if time.time() - last >= 5:
                last = time.time()
                print("  " + ("   ".join("%s: %d packets, %d flows" % (k, v[2], v[0]) for k, v in sorted(seen.items()))
                              or "nothing yet"))
    except KeyboardInterrupt:
        pass
    for k, v in sorted(seen.items()):
        print("%-16s %d packets, %d flows, %d bytes" % (k, v[2], v[0], v[1]))
    if seen and not any(v[0] for v in seen.values()):
        print("Packets arrived but no flows were decoded yet: a device sends its template every 30 seconds.")
    if not seen:
        print("Nothing arrived.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="lab.py", description="Kentik training labs: a made-up network on this host.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("up", help="start the lab network (sudo)").set_defaults(fn=cmd_up)
    sub.add_parser("down", help="stop it and clean up this host (sudo)").set_defaults(fn=cmd_down)
    s = sub.add_parser("status", help="is it running, and which lab is open")
    s.add_argument("--reveal", action="store_true", help="instructor: show what is really going on")
    s.set_defaults(fn=cmd_status)
    sub.add_parser("labs", help="list the labs").set_defaults(fn=cmd_labs)
    s = sub.add_parser("start", help="open a lab (sudo)")
    s.add_argument("lab", type=int)
    s.set_defaults(fn=cmd_start)
    sub.add_parser("ticket", help="read the open lab's ticket again").set_defaults(fn=cmd_ticket)
    s = sub.add_parser("ask", help="ask the customer a question")
    s.add_argument("topic", nargs="?", choices=list(labs.QUESTIONS))
    s.set_defaults(fn=cmd_ask)
    s = sub.add_parser("tell", help="ask the customer to change something (sudo)")
    s.add_argument("request", nargs="*")
    s.set_defaults(fn=cmd_tell)
    s = sub.add_parser("hint", help="a hint for the open lab")
    s.add_argument("n", nargs="?", type=int, default=1)
    s.set_defaults(fn=cmd_hint)
    sub.add_parser("check", help="is the open lab solved?").set_defaults(fn=cmd_check)
    s = sub.add_parser("listen", help="a stand-in for the agent, for testing")
    s.add_argument("--port", type=int, default=site.AGENT_PORT)
    s.add_argument("--seconds", type=float, default=0)
    s.set_defaults(fn=cmd_listen)
    args = p.parse_args(argv)
    if not getattr(args, "fn", None):
        p.print_help()
        return 0
    try:
        return args.fn(args)
    except PermissionError:
        print("This needs sudo:  sudo python3 lab.py %s" % " ".join(argv if argv is not None else sys.argv[1:]),
              file=sys.stderr)
        return 1
