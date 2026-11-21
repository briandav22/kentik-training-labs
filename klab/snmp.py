"""SNMP for the NMS lab: turn on the host's own snmpd with a known community, and ask it one question.

The device in this lab is real: the student's Linux host, answering with its real CPU, memory and interfaces.
"""
import binascii
import shutil
import socket
import subprocess
from typing import List, Optional, Tuple

CONF = "/etc/snmp/snmpd.conf"
MARK = "# klab"
COMMUNITY = "kentik-ro"            # what the host really answers to
WRONG_COMMUNITY = "netops-ro"      # what the customer's old document says
SYS_NAME = (1, 3, 6, 1, 2, 1, 1, 5, 0)


def installed() -> bool:
    return shutil.which("snmpd") is not None


def _lines() -> List[str]:
    try:
        with open(CONF) as f:
            return f.read().splitlines()
    except OSError:
        return []


def _restart() -> str:
    """Restart snmpd: systemctl where there is one, service on older hosts (Ubuntu 14.04 has upstart).
    Popen, not subprocess.run, which Python 3.4 doesn't have."""
    problem = "Neither systemctl nor service was found; restart snmpd yourself"
    for cmd in (["systemctl", "restart", "snmpd"], ["service", "snmpd", "restart"]):
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        except OSError:
            continue
        _, err = p.communicate()
        if p.returncode == 0:
            return ""
        problem = err.strip() or "couldn't restart snmpd"
    return problem


def configure(on: bool) -> str:
    """Add or remove the lab's own lines in snmpd.conf (each ends with the klab mark). Returns a problem, or ''."""
    lines = _lines()
    kept = [ln for ln in lines if not ln.rstrip().endswith(MARK)]
    if on:
        kept += ["rocommunity %s 127.0.0.1  %s" % (COMMUNITY, MARK)]
    if kept == lines:
        return ""
    try:
        with open(CONF, "w") as f:
            f.write("\n".join(kept) + "\n")
    except OSError as e:
        return "can't write %s: %s" % (CONF, e.strerror)
    return _restart()


# ------------------------------------------------------------------ one SNMPv2c GET, by hand

def _tlv(tag: int, body: bytes) -> bytes:
    n = len(body)
    if n < 128:
        return bytes([tag, n]) + body
    size = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(size)]) + size + body


def _int(v: int) -> bytes:
    return _tlv(0x02, v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big", signed=True))


def _oid(oid: Tuple[int, ...]) -> bytes:
    body = bytes([40 * oid[0] + oid[1]])
    for part in oid[2:]:
        chunk = [part & 0x7F]
        part >>= 7
        while part:
            chunk.append(0x80 | (part & 0x7F))
            part >>= 7
        body += bytes(reversed(chunk))
    return _tlv(0x06, body)


def get_request(community: str, oid: Tuple[int, ...] = SYS_NAME, request_id: int = 0x4B4C) -> bytes:
    varbinds = _tlv(0x30, _tlv(0x30, _oid(oid) + _tlv(0x05, b"")))
    pdu = _tlv(0xA0, _int(request_id) + _int(0) + _int(0) + varbinds)
    return _tlv(0x30, _int(1) + _tlv(0x04, community.encode()) + pdu)


def _read(buf: bytes, off: int) -> Tuple[int, bytes, int]:
    tag, n = buf[off], buf[off + 1]
    off += 2
    if n & 0x80:
        k = n & 0x7F
        n = int.from_bytes(buf[off:off + k], "big")
        off += k
    return tag, buf[off:off + n], off + n


def parse_value(reply: bytes) -> Optional[str]:
    """The first value in an SNMP response, as text. None if the reply isn't one we understand."""
    try:
        _, msg, _ = _read(reply, 0)
        off = 0
        for _ in range(2):                      # version, community
            _, _, off = _read(msg, off)
        tag, pdu, _ = _read(msg, off)
        if tag != 0xA2:
            return None
        off = 0
        for _ in range(3):                      # request id, error status, error index
            _, _, off = _read(pdu, off)
        _, vbl, _ = _read(pdu, off)
        _, vb, _ = _read(vbl, 0)
        _, _, off = _read(vb, 0)                # the OID
        tag, val, _ = _read(vb, off)
        if tag == 0x04:
            return val.decode(errors="replace")
        if tag in (0x02, 0x41, 0x42, 0x43):
            return str(int.from_bytes(val, "big"))
        return "(no such object)" if tag in (0x80, 0x81, 0x82) else binascii.hexlify(val).decode()   # not .hex(): 3.5+
    except (IndexError, ValueError):
        return None


def test(community: str, host: str = "127.0.0.1", port: int = 161, timeout: float = 2.0) -> Optional[str]:
    """Ask the host its name with this community. Returns the answer, or None if nothing came back."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(get_request(community), (host, port))
        return parse_value(s.recvfrom(65535)[0])
    except OSError:
        return None
    finally:
        s.close()
