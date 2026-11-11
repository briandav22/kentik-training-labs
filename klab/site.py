"""The practice network. The same place the course's lessons use (kentik-training: public/js/core/lab.js).

All addresses are illustrative: RFC 1918 inside, documentation ranges outside.
"""
import ipaddress
import random
from typing import Dict, List, Tuple

AGENT_PORT = 9995          # the Universal Agent's flow port (Brian, Nov 11, 2026)

# name -> sending IP (the Flow IP), another address the device owns, interfaces {ifIndex: name}
DEVICES = {
    "edge-rtr-01":   {"ip": "10.1.0.1", "other_ip": "10.1.1.1", "kind": "router",
                      "source": "Loopback0", "other_source": "GigabitEthernet0/0/4",
                      "ifs": {2: "Gi0/0/1 to ISP", 3: "Gi0/0/2 to branch", 5: "Gi0/0/4 to core-sw-01"}},
    "core-sw-01":    {"ip": "10.1.0.2", "other_ip": "10.1.1.2", "kind": "switch",
                      "source": "Loopback0", "other_source": "Ethernet1/49",
                      "ifs": {12: "Eth1/12 users", 20: "Eth1/20 servers", 49: "Eth1/49 uplink"}},
    "branch-rtr-01": {"ip": "10.2.0.1", "other_ip": "10.2.1.1", "kind": "router",
                      "source": "Loopback0", "other_source": "GigabitEthernet0/0/0",
                      "ifs": {1: "Gi0/0/0 WAN", 2: "Gi0/0/1 LAN"}},
}

# group -> (label, subnet, host count, offsets that must exist)
GROUPS = {
    "hq_users":     ("HQ users", "10.1.20.0/24", 40, (15, 77)),     # laptop-07 is .15; .77 is the laptop in the DNS case
    "branch_users": ("Branch users", "10.2.20.0/24", 15, (44,)),    # .44 is the overnight visitor
}

# service -> (label, ip, port, protocol, where it lives, request (pkts, bytes/pkt), reply (pkts, bytes/pkt), weight)
SERVICES = {
    "shop":    ("shop.example.com", "203.0.113.10", 443, 6, "internet", (12, 90), (40, 1100), 30),
    "crm":     ("CRM app", "198.51.100.40", 443, 6, "internet", (10, 120), (25, 900), 15),
    "updates": ("software updates", "192.0.2.80", 443, 6, "internet", (8, 80), (60, 1300), 5),
    "dns":     ("DNS resolver", "198.51.100.53", 53, 17, "internet", (1, 70), (1, 140), 30),
    "app":     ("app-01", "10.1.60.25", 8443, 6, "servers", (15, 200), (30, 700), 15),
    "db":      ("db-01", "10.1.60.40", 5432, 6, "servers", (20, 150), (20, 500), 5),
}

# (client group, where the service lives) -> [(device, in ifIndex, out ifIndex)] in the client-to-server direction.
# The reply crosses the same devices the other way round, with the interfaces swapped.
PATHS = {
    ("hq_users", "internet"):     [("core-sw-01", 12, 49), ("edge-rtr-01", 5, 2)],
    ("hq_users", "servers"):      [("core-sw-01", 12, 20)],
    ("branch_users", "internet"): [("branch-rtr-01", 2, 1), ("edge-rtr-01", 3, 2)],
    ("branch_users", "servers"):  [("branch-rtr-01", 2, 1), ("edge-rtr-01", 3, 5), ("core-sw-01", 49, 20)],
    ("internet", "servers"):      [("edge-rtr-01", 2, 5), ("core-sw-01", 49, 20)],
    ("servers", "internet"):      [("core-sw-01", 20, 49), ("edge-rtr-01", 5, 2)],
}

# The cast of the cases. Outside addresses are from the documentation ranges.
WEB_SERVER = "10.1.60.10"        # web-01, the target in "under attack"
DB_SERVER = "10.1.60.40"         # db-01
UPDATE_SERVER = "192.0.2.80"
TRAIL_LAPTOP = "10.1.20.77"
BAD_HOST = "203.0.113.66"        # what update-cdn[.]example resolves to
SCANNER = "10.2.20.44"
COLD_DEST = "198.51.100.200"


def hosts(group: str) -> List[str]:
    """The group's host addresses: the required ones, then a fixed pseudo-random fill."""
    _, subnet, count, must = GROUPS[group]
    net = ipaddress.ip_network(subnet)
    rng = random.Random(subnet)
    offs = list(must)
    pool = [o for o in range(10, 250) if o not in offs]
    rng.shuffle(pool)
    offs += pool[:count - len(offs)]
    return [str(net.network_address + o) for o in sorted(offs)]


def alias_ips() -> List[str]:
    """Every address a device may send from. Each becomes a /32 on the loopback interface."""
    out = []
    for d in DEVICES.values():
        out += [d["ip"], d["other_ip"]]
    return out


def service_choices() -> Tuple[List[str], List[int]]:
    names = list(SERVICES)
    return names, [SERVICES[n][7] for n in names]
