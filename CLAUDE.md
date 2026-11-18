# CLAUDE.md

The hands-on labs for Brian's Kentik training course. The course app is `briandav22/kentik-training`; the project's decisions, proposal and backlog are in `briandav22/kentik-training-docs` (read its `AGENTS.md`, `HANDOFF.md` and `docs/markdown/redesign-proposal.md` first).

## What this is

`python3 lab.py` plays a made-up network on a student's Linux host: devices send NetFlow v9 from loopback aliases to the Universal Agent on `127.0.0.1:9995`, which forwards to the student's own Kentik portal. In each lab the student is the SE and the lab plays the customer.

## Layout

- `lab.py`: the entry point.
- `klab/site.py`: the practice network (devices, addresses, interfaces, services, paths). The same place as the course's `public/js/core/lab.js`; keep them in step.
- `klab/netflow.py`: NetFlow v9 encode and decode, one exporter per device. From Brian's `webinarlabs`.
- `klab/traffic.py`: everyday traffic, and what sampling does to it.
- `klab/engine.py`: the background sender. Reads `state.json` every second, so a lab changes it live.
- `klab/labs.py`: the labs: ticket, customer answers, fault, hints, check.
- `klab/system.py`: everything that touches the host (loopback aliases, the one firewall rule, port checks).
- `klab/state.py`: the state directory (`/var/tmp/klab`, or `KLAB_HOME`).
- `klab/cli.py`: the commands.
- `tests/`: `python3 -m unittest discover -s tests`

## Rules

- Python 3.4+, standard library only. Students install nothing. Lab hosts include Ubuntu 14.04 (Python 3.4): no `subprocess.run`, `random.choices`, f-strings, `typing` without the fallback in `klab/__init__.py`, or anything else newer than 3.4. Version checkers such as vermin miss methods called on objects (`rng.choices`), so check those by hand.
- **A lab must not give itself away.** The ticket, `status`, `labs` and the first hint never name the fault. Only `status --reveal` and later hints do. A test enforces this; extend it with every lab.
- Clean up after yourself: `down` leaves no alias, rule or process. The firewall code adds and removes only the rule tagged `klab`, never anyone else's.
- Nothing may depend on one cloud provider. A plain Linux host is the only assumption.
- Addresses: RFC 1918 inside; documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) outside. No real customer names.
- Never commit credentials. A student's API token lives in `~/.kentik.env` on their host.
- Don't state a Kentik menu path or label in a hint or check unless it has been confirmed; say "in the portal".
- Write for students: short, plain sentences.

## Checking a change

Run the tests. Then, as root on Linux, run the labs for real: `lab.py up`, `lab.py listen` in a second terminal as the agent, each lab's fault, fix and `check`, then `lab.py down` and confirm `ip addr show lo` and `iptables -S INPUT` are clean.

## Not built yet

sFlow for `core-sw-01`, made-up SNMP, onboarding by API, scenario labs with several scenarios each, and reset (see the docs repo's proposal, "Brian's lab ideas"). Brian's `vxlanlab` has working sFlow, SNMP and Kentik API code to start from.
