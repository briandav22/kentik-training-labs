"""The background sender: every second, each made-up device exports the flows it saw."""
import json
import os
import random
import signal
import sys
import time
from typing import Dict, Optional

from . import site, state, traffic
from .netflow import Exporter


class Engine:
    WINDOW = 60.0

    def __init__(self, seed: Optional[int] = None, log=None):
        self.rng = random.Random(seed)
        self.exporters = {}             # device -> (source address, Exporter)
        self.window = []                # (time, {device: true bits}, {device: sent bits}), the last minute
        self.since = time.time()
        self.errors = {}
        self.log = log or (lambda msg: None)

    def _exporter(self, device: str, st: Dict) -> Optional[Exporter]:
        ip = site.DEVICES[device][st["source"].get(device, "ip")] if st.get("bind", True) else None
        have = self.exporters.get(device)
        if have and have[0] == ip:
            return have[1]
        if have:
            have[1].close()
        try:
            ex = Exporter(device, ip, source_id=1 + list(site.DEVICES).index(device))
        except OSError as e:
            if self.errors.get(device) != ip:
                self.log("%s can't send from %s (%s). Is the loopback alias there? Run: sudo python3 lab.py up"
                         % (device, ip, e.strerror))
            self.errors[device] = ip
            self.exporters.pop(device, None)
            return None
        self.errors.pop(device, None)
        self.exporters[device] = (ip, ex)
        return ex

    def tick(self, interval: float, now: float, st: Dict) -> int:
        """Send one interval's flows. Returns the number of records sent."""
        collector = (st.get("collector", "127.0.0.1"), int(st["port"]))
        sent = 0
        flows = traffic.generate(interval, now, self.rng)
        for device, records in traffic.scenario(st, interval, now, self.rng).items():
            flows[device] = flows.get(device, []) + records
        true_bits, sent_bits = {}, {}
        self.window.append((now, true_bits, sent_bits))
        while self.window and self.window[0][0] < now - self.WINDOW:
            self.window.pop(0)
        for device, records in flows.items():
            true_bits[device] = traffic.bits(records)
            records = traffic.sample(records, int(st["sample"].get(device, 1)), self.rng)
            sent_bits[device] = traffic.bits(records)
            ex = self._exporter(device, st)
            if ex:
                ex.send(records, now, collector)
                sent += len(records)
        return sent

    def close(self) -> None:
        for _, ex in self.exporters.values():
            ex.close()
        self.exporters = {}

    def stats(self, now: float) -> Dict:
        """Rates over the last minute, so they follow a lab or a case as soon as it starts."""
        secs = max(1.0, min(self.WINDOW, now - self.since))
        return {"updated": now, "since": self.since,
                "devices": {d: {"flows": (self.exporters[d][1].sent_flows if d in self.exporters else 0),
                                "true_bps": int(sum(t.get(d, 0) for _, t, _ in self.window) / secs),
                                "sent_bps": int(sum(s.get(d, 0) for _, _, s in self.window) / secs)}
                            for d in site.DEVICES}}


def main() -> int:
    """Run until told to stop. Started by `lab.py up`; reads state.json every second so labs can change it live."""
    os.makedirs(state.home(), exist_ok=True)

    def log(msg):
        sys.stdout.write("%s %s\n" % (time.strftime("%H:%M:%S"), msg))
        sys.stdout.flush()

    eng = Engine(log=log)
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    signal.signal(signal.SIGINT, lambda *a: stop.append(1))
    log("sender started")
    last = time.time()
    last_stats = 0.0
    while not stop:
        time.sleep(1.0)
        now = time.time()
        eng.tick(now - last, now, state.load())
        last = now
        if now - last_stats >= 5:
            tmp = state.path("stats.json.tmp")
            with open(tmp, "w") as f:
                json.dump(eng.stats(now), f)
            os.replace(tmp, state.path("stats.json"))
            last_stats = now
    log("sender stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
