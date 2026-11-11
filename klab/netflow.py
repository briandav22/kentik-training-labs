"""NetFlow v9 (RFC 3954): encode, decode, and one exporter per made-up device.

The encoder follows the one in Brian's webinarlabs (staledns-lab), which is known to work with the Universal Agent.
"""
import socket
import struct
import time
from typing import Dict, List, Optional, Tuple

TEMPLATE_ID = 256
# (field type, length): src addr, dst addr, src port, dst port, protocol, tcp flags, tos,
# input snmp, output snmp, packets, bytes, first switched, last switched, src mask, dst mask
FIELDS = [(8, 4), (12, 4), (7, 2), (11, 2), (4, 1), (6, 1), (5, 1), (10, 2), (14, 2),
          (2, 4), (1, 4), (22, 4), (21, 4), (9, 1), (13, 1)]
REC_FMT = "!4s4sHHBBBHHIIIIBB"
REC_LEN = struct.calcsize(REC_FMT)   # 37
MAX_PER_PACKET = 30


def rec(src, dst, sport, dport, proto, flags, in_if, out_if, pkts, octets, first, last) -> Dict:
    return {"src": src, "dst": dst, "sport": sport, "dport": dport, "proto": proto, "flags": flags, "tos": 0,
            "in_if": in_if, "out_if": out_if, "pkts": pkts, "bytes": octets, "first": first, "last": last}


def _pad(b: bytes) -> bytes:
    return b + b"\0" * (-len(b) % 4)


def template_flowset() -> bytes:
    body = struct.pack("!HH", TEMPLATE_ID, len(FIELDS)) + b"".join(struct.pack("!HH", t, l) for t, l in FIELDS)
    return struct.pack("!HH", 0, 4 + len(body)) + body


def encode(records: List[Dict], seq: int, boot: float, now: float, source_id: int, with_template: bool) -> bytes:
    def up(t):
        return max(0, int((t - boot) * 1000)) & 0xFFFFFFFF
    body = b"".join(struct.pack(REC_FMT, socket.inet_aton(r["src"]), socket.inet_aton(r["dst"]), r["sport"],
                                r["dport"], r["proto"], r["flags"], r["tos"], r["in_if"], r["out_if"],
                                r["pkts"], r["bytes"], up(r["first"]), up(r["last"]), 24, 24)
                    for r in records)
    sets = template_flowset() if with_template else b""
    if records:
        data = _pad(struct.pack("!HH", TEMPLATE_ID, 0) + body)
        sets += struct.pack("!HH", TEMPLATE_ID, len(data)) + data[4:]
    count = len(records) + (1 if with_template else 0)
    return struct.pack("!HHIIII", 9, count, up(now), int(now), seq, source_id) + sets


def decode(pkt: bytes, templates: Dict) -> Tuple[Dict, List[Dict]]:
    """Decode one v9 packet. templates maps (source id, template id) to its fields and fills as templates arrive."""
    ver, count, uptime, secs, seq, sid = struct.unpack("!HHIIII", pkt[:20])
    if ver != 9:
        raise ValueError("not NetFlow v9 (version %d)" % ver)
    hdr = {"count": count, "uptime": uptime, "secs": secs, "seq": seq, "source_id": sid}
    out, off = [], 20
    while off + 4 <= len(pkt):
        fid, ln = struct.unpack("!HH", pkt[off:off + 4])
        if ln < 4:
            break
        body = pkt[off + 4:off + ln]
        if fid == 0:
            p = 0
            while p + 4 <= len(body):
                tid, n = struct.unpack("!HH", body[p:p + 4])
                templates[(sid, tid)] = [struct.unpack("!HH", body[p + 4 + 4 * i:p + 8 + 4 * i]) for i in range(n)]
                p += 4 + 4 * n
        elif fid >= 256 and (sid, fid) in templates:
            fl = templates[(sid, fid)]
            size = sum(l for _, l in fl)
            p = 0
            while p + size <= len(body):
                vals, q = {}, p
                for t, l in fl:
                    raw = body[q:q + l]
                    vals[t] = socket.inet_ntoa(raw) if t in (8, 12) else int.from_bytes(raw, "big")
                    q += l
                out.append({"src": vals[8], "dst": vals[12], "sport": vals[7], "dport": vals[11],
                            "proto": vals[4], "flags": vals[6], "in_if": vals[10], "out_if": vals[14],
                            "pkts": vals[2], "bytes": vals[1]})
                p += size
        off += ln
    return hdr, out


class Exporter:
    """One made-up device: its own UDP socket, bound to the address it sends from."""

    def __init__(self, name: str, ip: Optional[str], source_id: int, template_every: float = 30.0):
        self.name, self.ip, self.source_id = name, ip, source_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if ip:
            self.sock.bind((ip, 0))     # fails if the loopback alias is missing
        self.boot = time.time() - 86400
        self.seq = 0
        self.last_template = 0.0
        self.template_every = template_every
        self.sent_flows = 0

    def send(self, records: List[Dict], now: float, collector: Tuple[str, int]) -> None:
        chunks = [records[i:i + MAX_PER_PACKET] for i in range(0, len(records), MAX_PER_PACKET)] or [[]]
        for chunk in chunks:
            tmpl = now - self.last_template >= self.template_every
            if not chunk and not tmpl:
                continue
            try:
                self.sock.sendto(encode(chunk, self.seq, self.boot, now, self.source_id, tmpl), collector)
            except OSError:
                pass                    # nothing listening, or a firewall said no: a real router wouldn't notice either
            if tmpl:
                self.last_template = now
            self.seq += len(chunk)
            self.sent_flows += len(chunk)

    def close(self) -> None:
        self.sock.close()
