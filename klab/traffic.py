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


def _pick(names: List[str], weights: List[float], rng: random.Random) -> str:
    """One name, chosen by weight. Not rng.choices: Python 3.4 doesn't have it."""
    r = rng.random() * sum(weights)
    for name, w in zip(names, weights):
        r -= w
        if r < 0:
            return name
    return names[-1]


def generate(interval: float, now: float, rng: random.Random, period: float = 6.0) -> Dict[str, List[Dict]]:
    """All records for one tick, by device. Each host starts a conversation about every `period` seconds."""
    names, weights = site.service_choices()
    out = {d: [] for d in site.DEVICES}
    p = min(1.0, interval / period)
    for group in site.GROUPS:
        for h in site.hosts(group):
            if rng.random() < p:
                svc = _pick(names, weights, rng)
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
