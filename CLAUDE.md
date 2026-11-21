# CLAUDE.md

The hands-on labs for Brian's Kentik training course. The course app is `briandav22/kentik-training`; the project's decisions, proposal and backlog are in `briandav22/kentik-training-docs` (read its `AGENTS.md`, `HANDOFF.md` and `docs/markdown/redesign-proposal.md` first).

## What this is

`python3 lab.py` plays a made-up network on a student's Linux host: devices send NetFlow v9 from loopback aliases to the Universal Agent on `127.0.0.1:9995`, which forwards to the student's own Kentik portal. In each lab the student is the SE and the lab plays the customer.

## Layout

- `lab.py`: the entry point.
- `klab/site.py`: the practice network (devices, addresses, interfaces, services, paths). The same place as the course's `public/js/core/lab.js`; keep them in step.
- `klab/netflow.py`: NetFlow v9 encode and decode, one exporter per device. From Brian's `webinarlabs`.
- `klab/traffic.py`: everyday traffic, what sampling does to it, and the extra traffic of each case (`scenario`).
- `klab/snmp.py`: the NMS lab: the lab's own marked lines in the host's `snmpd.conf`, and one hand-built SNMP GET.
- `klab/engine.py`: the background sender. Reads `state.json` every second, so a lab changes it live.
- `klab/labs.py`: the labs: ticket, customer answers, fault, hints, check.
- `klab/system.py`: everything that touches the host (loopback aliases, the one firewall rule, port checks).
- `klab/state.py`: the state directory (`/var/tmp/klab`, or `KLAB_HOME`).
- `klab/cli.py`: the commands.
- `klab/catalog.py`: the lab site's tiles and pages: tracks, steps (from the course's lab steps, Nov 20, 2026), what success looks like, what each lab needs in the portal and adds to it (so a reset can take it out), and the instructor's answer. Every lab in `labs.py` has one entry; a `replay` reruns a case's traffic for another lab (alerting, AI).
- `klab/portal.py`: the student's portal details (email, API token, region) in `~/.kentik.env`, a read-only test (the device list), and what a reset takes out (the agent always stays). `PORTAL_WRITES` is off: nothing changes the portal yet. `lab.py portal set` saves them from a terminal.
- `klab/web.py`: the lab site's server and JSON API (`lab.py ui`). It runs the same functions as the commands, under one lock. `--classroom` serves the class copy from the instructor's machine: it runs nothing, every button answers with the command for the student's own terminal, it refuses portal details, and only `/api/answer` needs the key.
- `klab/ui/`: the site's pages: `index.html`, `app.js` (all of the page), `app.css`, `art.js` (a drawing per tile) and `tokens.css` (a copy of the course's colors, light and dark, Kentik and Infoblox).
- `tests/`: `python3 -m unittest discover -s tests` (`test_site.py` covers the site)

## Rules

- Python 3.8+, standard library only. Students install nothing.
- **A lab must not give itself away.** The ticket, `status`, `labs` and the first hint never name the fault. Only `status --reveal` and later hints do. A test enforces this; extend it with every lab.
- The same goes for the lab site: a lab's tile, drawing and page, and `/api/status`, never name the fault. `tests/test_site.py` checks them with the same words. Answers come only from `/api/answer` (instructor view); the takeaway shows once a lab is marked done.
- The site: nothing loads from the internet, and the page runs only its own files (the server's Content-Security-Policy is `script-src 'self'`), so no inline scripts or `on…` handlers. Every API call needs the key; the token never goes back to a page.
- Brian's class (Nov 21, 2026): the Launchpad lab hosts have only a terminal, so the room uses the class copy and runs commands in their own hosts' terminals. Each student uses their own API token. A reset never removes the Universal Agent: the labs always need one. Step text stays true in both modes: don't name a button in a step.
- A new lab needs a `labs.py` entry, a `catalog.py` entry and a drawing in `ui/art.js` that shows the symptom, never the cause.
- Clean up after yourself: `down` leaves no alias, rule or process. The firewall code adds and removes only the rule tagged `klab`, never anyone else's.
- Nothing may depend on one cloud provider. A plain Linux host is the only assumption.
- Addresses: RFC 1918 inside; documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) outside. No real customer names.
- Never commit credentials. A student's API token lives in `~/.kentik.env` on their host.
- Don't state a Kentik menu path or label in a hint or check unless it has been confirmed; say "in the portal".
- Write for students: short, plain sentences.

## Labs and the course

The course app's lab steps quote these commands and the cases' answers (addresses, ports). If you change a lab's number, a command, or an address in `klab/site.py`, change the matching lesson in `kentik-training` (`public/js/lessons/d1-day-one.js`, `d2-day-two.js`) in the same piece of work.

Since Nov 20, 2026 the course's default plan (`two-day-labs`) doesn't run the labs on its own screens: it pauses at a lab break (`public/js/lessons/lab-breaks.js`) that names the lab's tile here, and the room opens it on the lab site. The break screens quote the tiles' labels and titles; change both together. The older plan, `two-day`, still has the labs inside the course.

## Checking a change

Run the tests. Then, as root on Linux, run the labs for real: `lab.py up`, `lab.py listen` in a second terminal as the agent, each lab's fault, fix and `check`, then `lab.py down` and confirm `ip addr show lo` and `iptables -S INPUT` are clean.

For the site, start it with a scratch state folder (`KLAB_HOME=… KLAB_PORTAL_FILE=… KLAB_KEY=devkey sudo -E python3 lab.py ui`), click through a lab (Launch, Ask, Hint, Check, Back to healthy, Stop) in light and dark at 1280 and 1440 wide, and confirm the host is clean afterwards. `KLAB_PORTAL_BASE` points the portal test at a stand-in API.

## Not built yet

sFlow for `core-sw-01`, made-up SNMP for the three devices (lab 11 uses the host's real `snmpd` instead), and onboarding and reset by API: the site has the place for both (`portal.py`, the disabled **Set it up for me** button, the reset lists), but no call that changes a portal (see the docs repo's proposal, "Brian's lab ideas"). Brian's `vxlanlab` has working sFlow, SNMP and Kentik API code to start from. How students get API tokens is Brian's call (docs repo, `HANDOFF.md`).
