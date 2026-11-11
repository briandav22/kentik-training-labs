"""The labs. In each one the student is the SE and the lab plays the customer.

A lab is a ticket, what the customer says when asked, what is really going on (the fault), hints, and a check.
Nothing a student can print without asking for a hint may give the fault away: not the ticket, not `status`.
"""
from typing import Callable, Dict, List, Tuple

from . import site, system

CUSTOMER = "Maya, network lead at the customer"

BASE_ANSWERS = {
    "devices": "Three, all sending NetFlow v9: edge-rtr-01 (router), core-sw-01 (switch), branch-rtr-01 (router).",
    "ips": "Each one exports from its Loopback0: " + ", ".join(
        "%s is %s" % (n, d["ip"]) for n, d in site.DEVICES.items()) + ".",
    "port": "UDP %d, to the Universal Agent on this host." % site.AGENT_PORT,
    "sampling": "No sampling. Every packet is counted.",
    "firewall": "Nothing changed on our firewalls that I know of.",
    "changes": "Nothing has changed recently.",
}

QUESTIONS = {
    "devices": "Which devices are sending flow?",
    "ips": "Which address does each device send from?",
    "port": "Which port do they send to?",
    "sampling": "Do any of them sample?",
    "firewall": "Is a firewall involved?",
    "changes": "What changed recently?",
}


def _healthy(st: Dict) -> None:
    pass


def _wrong_port(st: Dict) -> None:
    st["port"] = 2055


def _wrong_source(st: Dict) -> None:
    st["source"]["edge-rtr-01"] = "other_ip"


def _firewall(st: Dict) -> None:
    st["firewall"] = True


def _sampled(st: Dict) -> None:
    st["sample"]["core-sw-01"] = 100


def _check_1(st: Dict) -> Tuple[bool, List[str]]:
    if not system.listening(st["port"]):
        return False, ["Nothing on this host is listening on UDP %d. Is the Universal Agent installed and running?"
                       % st["port"]]
    return True, ["Flow is reaching the agent's port on this host.",
                  "The rest is in Kentik: has every device been added, each with the address it sends from?",
                  "You're done when all three devices show traffic in the portal."]


def _check_2(st: Dict) -> Tuple[bool, List[str]]:
    if system.listening(st["port"]):
        return True, ["The devices send to UDP %d and something on this host is listening there." % st["port"],
                      "Give it a few minutes, then look for the devices' traffic in the portal."]
    return False, ["The devices are sending, but nothing on this host is listening where they send."]


def _check_3(st: Dict) -> Tuple[bool, List[str]]:
    if st["source"]["edge-rtr-01"] == "ip":
        return True, ["edge-rtr-01 now sends from the address the customer gave you.",
                      "Give it a few minutes, then look for its traffic in the portal."]
    return False, ["On this host nothing has changed. If you fixed it in Kentik instead, that can be right too:",
                   "you're done when edge-rtr-01 shows traffic in the portal."]


def _check_4(st: Dict) -> Tuple[bool, List[str]]:
    if system.firewall_present(st["port"]):
        return False, ["Flow still isn't reaching the agent."]
    return True, ["Flow is reaching the agent again.", "Give it a few minutes, then confirm in the portal."]


def _check_5(st: Dict) -> Tuple[bool, List[str]]:
    return False, ["The fix for this one is in Kentik, so this host can't see it.",
                   "You're done when core-sw-01 and edge-rtr-01 show about the same traffic for HQ users."]


LABS = {
    1: {"title": "First flows",
        "ticket": ["We installed the Universal Agent on this host like you asked, and our three devices have been",
                   "sending flow to it since this morning. But there's nothing in Kentik.",
                   "What do you need from us to get them showing up?"],
        "fault": _healthy, "answers": {}, "check": _check_1,
        "hints": ["Kentik only accepts flow from devices it knows. What does it need to know about each one?",
                  "Ask the customer which devices there are and which address each sends from: lab.py ask",
                  "Add each device in the portal with its name and its sending IP. The agent forwards flow only "
                  "for sending IPs that match a device."]},
    2: {"title": "Still nothing",
        "ticket": ["A second site. Same story: agent installed, devices added in Kentik with the right addresses,",
                   "our engineer says flow export is configured. Kentik shows no traffic from any of them.",
                   "Can you find out why?"],
        "fault": _wrong_port,
        "answers": {"port": "The default, I assume. Our engineer built it from an old template and he's out today.",
                    "changes": "It's a brand new setup. Nothing has ever worked."},
        "check": _check_2,
        "hints": ["Don't take anyone's word for it. Is flow arriving at this host at all? You can look.",
                  "sudo tcpdump -i lo -n udp    Look at where the packets are going, not only where they're from.",
                  "The devices send to a different port from the one the agent listens on. Either side can change: "
                  "ask the customer (lab.py tell port <number>), or have the agent listen on their port too."]},
    3: {"title": "One device missing",
        "ticket": ["Two of our three devices look fine in Kentik now. edge-rtr-01 shows nothing.",
                   "It's our internet edge, so it's the one we care about most."],
        "fault": _wrong_source,
        "answers": {"changes": "We swapped edge-rtr-01's hardware last night and loaded its config again."},
        "check": _check_3,
        "hints": ["The other two work, so the agent and the port are fine. What is different about this device?",
                  "sudo tcpdump -i lo -n udp port %d    Compare each packet's source address with what the "
                  "customer told you." % site.AGENT_PORT,
                  "edge-rtr-01 exports from an interface address, not its Loopback0. Fix it at the customer "
                  "(lab.py tell source edge-rtr-01 loopback) or change the device's sending IP in Kentik."]},
    4: {"title": "It was working yesterday",
        "ticket": ["Everything was fine yesterday. This morning Kentik shows no new flow from any device.",
                   "Our network team swears nothing changed on the routers."],
        "fault": _firewall,
        "answers": {"changes": "The server team hardened this Linux host last night. They said it was routine.",
                    "firewall": "Not on the network. But the server team did something on this host."},
        "check": _check_4,
        "hints": ["Is flow still arriving at this host? And is the agent still listening? Check both.",
                  "tcpdump shows the packets, and the agent is listening, yet the agent gets nothing. tcpdump sees "
                  "a packet before the host's firewall does.",
                  "sudo iptables -L INPUT -n -v    One rule drops the flow; watch its packet counter climb. "
                  "Delete that rule with sudo iptables -D INPUT <its number>."]},
    5: {"title": "The numbers are wrong",
        "ticket": ["Kentik says core-sw-01 carries far less traffic than edge-rtr-01 for the same HQ users.",
                   "Our own tools say they carry about the same. Which one is lying?"],
        "fault": _sampled,
        "answers": {"sampling": "Oh. core-sw-01 samples 1 packet in 100, it's a busy switch. Did we not say?"},
        "check": _check_5,
        "hints": ["Flow is arriving, so this isn't about delivery. How far off are the numbers? Is it a round figure?",
                  "Ask the customer about sampling: lab.py ask sampling",
                  "The switch samples but doesn't say so in its flow. Set the device's sample rate in Kentik so "
                  "Kentik multiplies its numbers back up."]},
}


def answer(lab: int, topic: str) -> str:
    return LABS.get(lab, {}).get("answers", {}).get(topic, BASE_ANSWERS[topic])
