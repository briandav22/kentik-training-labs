"""The parts that touch the host: loopback aliases, the firewall rule, and what is listening."""
import errno
import platform
import socket
import subprocess
from typing import List, Tuple

from . import site

FW_COMMENT = "klab"


def _run(cmd: List[str]) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    except FileNotFoundError:
        return 127, "%s not found" % cmd[0]
    return r.returncode, (r.stderr or r.stdout).strip()


def alias_cmds(remove: bool = False) -> List[List[str]]:
    out = []
    for ip in site.alias_ips():
        if platform.system() == "Darwin":
            out.append(["ifconfig", "lo0", "-alias" if remove else "alias", ip + "/32"])
        else:
            out.append(["ip", "addr", "del" if remove else "add", ip + "/32", "dev", "lo"])
    return out


def aliases(remove: bool = False) -> List[str]:
    """Add or remove the devices' addresses on loopback. Returns the problems, if any."""
    problems = []
    for c in alias_cmds(remove):
        rc, msg = _run(c)
        if rc and "File exists" not in msg and "Cannot assign" not in msg:
            problems.append("%s: %s" % (" ".join(c), msg or "failed"))
    return problems


def _fw_rule(port: int) -> List[str]:
    return ["INPUT", "-p", "udp", "--dport", str(port), "-m", "comment", "--comment", FW_COMMENT, "-j", "DROP"]


def firewall_present(port: int) -> bool:
    return _run(["iptables", "-C"] + _fw_rule(port))[0] == 0


def firewall(port: int, on: bool) -> str:
    """Add or remove the lab's one drop rule. Returns a problem, or ''. Never touches any other rule."""
    have = firewall_present(port)
    if on and not have:
        rc, msg = _run(["iptables", "-I"] + _fw_rule(port))
        return "" if rc == 0 else "iptables: " + msg
    while not on and firewall_present(port):
        rc, msg = _run(["iptables", "-D"] + _fw_rule(port))
        if rc:
            return "iptables: " + msg
    return ""


def listening(port: int) -> bool:
    """Is some program already bound to this UDP port? (The Universal Agent should be, on its flow port.)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", port))
    except OSError as e:
        return e.errno == errno.EADDRINUSE
    finally:
        s.close()
    return False
