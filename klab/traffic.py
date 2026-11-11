"""Everyday traffic on the practice network: who talks to what, and which devices see it."""
import random
from typing import Dict, List

from . import site
from .netflow import rec

SYN, ACK, PSH, FIN = 0x02, 0x10, 0x08, 0x01
FULL = SYN | ACK | PSH | FIN


def conversation(group: str, client: str, service: str, now: float, rng: random.Random) -> Dict[str, List[Dict]]:
    """One client talks to one service. Returns the records each device on the path exports (both directions)."""
    _, server, port, proto, where, (qp, qb), (rp, rb), _ = site.SERVICES[service]
    sport = rng.randint(49152, 65535)
    scale = rng.uniform(0.5, 2.0)
    qpk = max(1, int(qp * scale))
    rpk = max(1, int(rp * scale))
    flags = FULL if proto == 6 else 0
    first = now - rng.uniform(0.2, 4.0)
    out = {}
    for device, in_if, out_if in site.PATHS[(group, where)]:
        out.setdefault(device, []).append(
            rec(client, server, sport, port, proto, flags, in_if, out_if, qpk, qpk * qb, first, now))
        out[device].append(
            rec(server, client, port, sport, proto, flags, out_if, in_if, rpk, rpk * rb, first, now))
    return out


def generate(interval: float, now: float, rng: random.Random, period: float = 6.0) -> Dict[str, List[Dict]]:
    """All records for one tick, by device. Each host starts a conversation about every `period` seconds."""
    names, weights = site.service_choices()
    out = {d: [] for d in site.DEVICES}
    p = min(1.0, interval / period)
    for group in site.GROUPS:
        for h in site.hosts(group):
            if rng.random() < p:
                svc = rng.choices(names, weights)[0]
                for device, records in conversation(group, h, svc, now, rng).items():
                    out[device] += records
    return out


def sample(records: List[Dict], rate: int, rng: random.Random) -> List[Dict]:
    """What a device sampling 1 packet in `rate` exports: fewer, smaller records, and no word of the rate."""
    if rate <= 1:
        return records
    out = []
    for r in records:
        expect = r["pkts"] / float(rate)
        pk = int(expect) + (1 if rng.random() < expect - int(expect) else 0)
        if pk:
            size = r["bytes"] // r["pkts"]
            out.append(dict(r, pkts=pk, bytes=pk * size))
    return out


def bits(records: List[Dict]) -> int:
    return 8 * sum(r["bytes"] for r in records)


# ------------------------------------------------------------------ the cases
# Each case adds traffic on top of the everyday traffic. st["scenario"] is {"name", "start", "end"}.

RST = 0x04
SCENARIO_MINUTES = {"storm": 30, "trail": 20, "flood": 30, "scan": 40, "cold": 60}
_OUTSIDE = ["192.0.2.%d", "198.51.100.%d", "203.0.113.%d"]


def _along(path_key, out, make):
    """Add one record per device on a path. make(in_if, out_if) builds the record."""
    for device, in_if, out_if in site.PATHS[path_key]:
        out.setdefault(device, []).append(make(in_if, out_if))


def _pair(path_key, out, client, server, sport, dport, proto, qpk, qb, rpk, rb, now, flags=FULL):
    """A request and its reply, seen by every device on the path."""
    first = now - 1.0
    for device, in_if, out_if in site.PATHS[path_key]:
        recs = out.setdefault(device, [])
        recs.append(rec(client, server, sport, dport, proto, flags, in_if, out_if, qpk, qpk * qb, first, now))
        if rpk:
            recs.append(rec(server, client, dport, sport, proto, flags, out_if, in_if, rpk, rpk * rb, first, now))


def beacon(interval: float, now: float, rng: random.Random, period: float = 240.0) -> Dict[str, List[Dict]]:
    """Always on: one laptop checks in with an outside address every few minutes. The DNS case finds it."""
    out = {}
    if rng.random() < interval / period:
        _pair(("hq_users", "internet"), out, site.TRAIL_LAPTOP, site.BAD_HOST, rng.randint(49152, 65535), 443, 6,
              5, 120, 5, 180, now)
    return out


def _storm(interval, now, age, rng, out):
    """Nearly every user pulls the same big update at once."""
    for group in site.GROUPS:
        for host in site.hosts(group):
            if rng.random() < interval / 5.0:
                pk = rng.randint(400, 900)
                _pair((group, "internet"), out, host, site.UPDATE_SERVER, rng.randint(49152, 65535), 443, 6,
                      pk // 20, 80, pk, 1400, now)


def _trail(interval, now, age, rng, out):
    """The laptop talks to the database, then sends a lot of data to the outside address."""
    if age < 180:
        if rng.random() < interval / 3.0:
            _pair(("hq_users", "servers"), out, site.TRAIL_LAPTOP, site.DB_SERVER, rng.randint(49152, 65535), 5432, 6,
                  40, 120, rng.randint(150, 300), 1200, now)
    elif age < 180 + 900:
        pk = int(800 * interval)
        _pair(("hq_users", "internet"), out, site.TRAIL_LAPTOP, site.BAD_HOST, 51515, 443, 6, pk, 1400, pk // 10, 60, now)


def _flood(interval, now, age, rng, out):
    """Hundreds of outside addresses send UDP from source port 53 to the web server. Nothing answers."""
    for _ in range(int(250 * interval)):
        src = rng.choice(_OUTSIDE) % rng.randint(1, 254)
        pk = rng.randint(200, 600)
        dport = rng.randint(1024, 65535)
        _along(("internet", "servers"), out,
               lambda i, o: rec(src, site.WEB_SERVER, 53, dport, 17, 0, i, o, pk, pk * 1400, now - 1.0, now))


def _scan(interval, now, age, rng, out):
    """One branch address tries hundreds of ports on the HQ servers. Each try is one packet; each gets refused."""
    for _ in range(int(30 * interval)):
        dst = "10.1.60.%d" % rng.randint(10, 60)
        sport, dport = rng.randint(49152, 65535), rng.randint(1, 10000)
        for device, in_if, out_if in site.PATHS[("branch_users", "servers")]:
            recs = out.setdefault(device, [])
            recs.append(rec(site.SCANNER, dst, sport, dport, 6, SYN, in_if, out_if, 1, 60, now - 0.5, now))
            recs.append(rec(dst, site.SCANNER, dport, sport, 6, RST | ACK, out_if, in_if, 1, 40, now - 0.5, now))


def _cold(interval, now, age, rng, out):
    """A database server sends a steady stream to an outside address on port 22."""
    pk = int(3000 * interval)
    first = now - 1.0
    for device, in_if, out_if in site.PATHS[("servers", "internet")]:
        recs = out.setdefault(device, [])
        recs.append(rec(site.DB_SERVER, site.COLD_DEST, 40222, 22, 6, ACK | PSH, in_if, out_if, pk, pk * 1400, first, now))
        recs.append(rec(site.COLD_DEST, site.DB_SERVER, 22, 40222, 6, ACK, out_if, in_if, pk // 8, (pk // 8) * 52, first, now))


_SCENARIOS = {"storm": _storm, "trail": _trail, "flood": _flood, "scan": _scan, "cold": _cold}


def scenario(st: Dict, interval: float, now: float, rng: random.Random) -> Dict[str, List[Dict]]:
    """The extra traffic for this tick: the laptop's check-ins, plus the open case if it is under way."""
    out = beacon(interval, now, rng)
    sc = st.get("scenario") or {}
    fn = _SCENARIOS.get(sc.get("name"))
    if fn and sc["start"] <= now < sc["end"]:
        fn(interval, now, now - sc["start"], rng, out)
    return out
