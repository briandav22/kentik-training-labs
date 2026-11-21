# Kentik training labs

Hands-on labs for the Kentik training course. One command plays a small made-up network on your Linux host. Its three devices send real NetFlow to the Kentik Universal Agent on the same host, and from there into your own Kentik portal.

In every lab you are the SE and the lab plays the customer. A ticket arrives. You ask questions, look at the host, fix what's wrong, and confirm it in Kentik.

Python 3.8 or later, standard library only. Nothing to install.

## Before you start

- A Linux host (2 CPUs, 2 GB of memory is enough) with `python3`, `git`, `iproute2`, `iptables`, `tcpdump` and, for lab 11, `snmpd`. On a fresh Ubuntu or Debian machine, `sudo bash setup-host.sh` installs them all. It works the same on any provider.
- The Kentik Universal Agent installed on that host from your own portal. It listens for flow on UDP 9995.

## Run it

```bash
git clone https://github.com/briandav22/kentik-training-labs.git
cd kentik-training-labs
sudo python3 lab.py up          # start the made-up network
sudo python3 lab.py start 1     # open the first lab and read its ticket
```

| Command | What it does |
|---|---|
| `sudo python3 lab.py up` | Starts the network: three devices begin sending flow |
| `python3 lab.py labs` | Lists the labs |
| `sudo python3 lab.py start <n>` | Opens lab n and shows its ticket. `start 0` is a healthy network |
| `python3 lab.py ticket` | Shows the open ticket again |
| `python3 lab.py ask` | Lists what you can ask the customer; `ask port` asks it |
| `sudo python3 lab.py tell …` | Asks the customer to change something on their devices |
| `python3 lab.py hint` | A hint. `hint 2` and `hint 3` say more |
| `sudo python3 lab.py check` | Tells you whether the lab is solved on this host |
| `python3 lab.py snmp test <community>` | Lab 11: asks this host its name over SNMP, the way the agent would |
| `python3 lab.py status` | Whether the network is running and which lab is open |
| `python3 lab.py portal set` | Saves your Kentik email, API token and region on this host, and tests them |
| `sudo python3 lab.py ui` | The lab site on this host (see below); `python3 lab.py ui --classroom` is the class copy |
| `sudo python3 lab.py down` | Stops everything and cleans up the host |

Commands that change something need `sudo`. Leave the network running between labs: your portal gets more useful the longer it collects.

## The lab site

Every lab is also a page in a browser: its ticket, its steps, the customer to ask, hints, and the commands to run. There are two ways to use it.

**In class, from the instructor's laptop** (for lab hosts with only a terminal, such as the Launchpad hosts). The instructor runs the class copy next to the course:

```bash
python3 lab.py ui --classroom   # prints a link for the room, and one with a key for you
```

- Students open the room's link. They read each lab there, ask the customer and take hints, and copy each command into their own lab host's terminal: `sudo python3 lab.py start 2`, `sudo python3 lab.py check`, and so on.
- The class copy runs nothing and keeps no one's portal details. Only the instructor's link, with the key, shows the answers (**Instructor view**, at the foot of the page).
- It needs no sudo and runs on any machine with Python 3, a Mac included.

**On the lab host itself**, where a browser can reach it:

```bash
sudo python3 lab.py ui          # prints a link with a key in it: open it in a browser
```

- On a lab's page, **Launch this lab** runs `lab.py up` (if the network isn't running) and `lab.py start <n>`. **Check my work** is `lab.py check`, **Back to healthy** is `start 0`, and **Stop the lab network** is `lab.py down`. What the host prints shows on the page.
- It listens on `127.0.0.1` only, and every call must carry the key from the link. To use it from a laptop: `ssh -L 8090:127.0.0.1:8090 <you>@<lab host>` and open the same link, or start it with `--host 0.0.0.0`, which prints a link with the host's address (anyone with that link who can reach the host can use it).
- Started without `sudo`, it shows every lab and gives you the command to run instead of launching.

**Your portal.** Each student uses their own Kentik portal and their own API token. Save them on your lab host, in its terminal:

```bash
python3 lab.py portal set       # your email, API token (hidden as you type) and region; then a read-only test
```

`python3 lab.py portal` shows what's saved and tests it again; `python3 lab.py portal forget` removes it. They're kept in `~/.kentik.env`, readable only by you, and never shown again: a page sees only the token's last four characters. The labs don't change your portal yet: adding each lab's devices for you and removing them on reset come next (`PORTAL_WRITES` in `klab/portal.py`).

**Reset** stops the lab network (`sudo python3 lab.py down`) and lists what the labs added to your portal, for you to remove by hand for now. Your Universal Agent always stays: the labs need it.

Steps you tick and labs you mark done are kept in your browser. Marking a lab done shows its takeaway.

## The network

| Device | Sends flow from | Interfaces |
|---|---|---|
| `edge-rtr-01` (router) | `10.1.0.1`, Loopback0 | to the ISP, to the branch, to the core switch |
| `core-sw-01` (switch) | `10.1.0.2`, Loopback0 | users, servers, uplink |
| `branch-rtr-01` (router) | `10.2.0.1`, Loopback0 | WAN, LAN |

Forty users at HQ (`10.1.20.0/24`) and fifteen at a branch (`10.2.20.0/24`) use a web shop, a CRM app, software updates and DNS on the internet, and an app and a database in the HQ server room (`10.1.60.0/24`). Every device a conversation crosses exports it, so the same traffic shows up on more than one device, as it does on a real network.

It's the same practice network the course's lessons use. Every address is made up: private ranges inside, documentation ranges outside.

## The labs

| # | Ticket |
|---|---|
| 1 | First flows: the customer is sending flow, but nothing is in Kentik |
| 2 | Still nothing |
| 3 | One device missing |
| 4 | It was working yesterday |
| 5 | The numbers are wrong |
| 6 | The internet is crawling |
| 7 | One DNS alert |
| 8 | Under attack |
| 9 | What happened overnight? |
| 10 | The cold case |
| 11 | The server with no health |

The tickets don't say what's wrong. That's the lab.

Labs 1 to 5 are about getting flow into Kentik: something in the setup is wrong and you fix it on the host or in the portal. Labs 6 to 10 are cases: the setup is fine and the answer is in the traffic, so you solve them in your portal and close them in the course. Lab 9 is armed in the evening (`sudo python3 lab.py start 9`) and happens about six hours later; `--in 5` makes it five minutes. Lab 11 turns on SNMP on the host itself, so the host can be added to Kentik NMS; it needs the `snmpd` package (`sudo apt-get install -y snmpd`).

## How it works

Kentik tells devices apart by the address their flow comes from. `lab.py up` adds each device's address to the host's loopback interface, and a background sender exports NetFlow v9 from each address to the agent on `127.0.0.1`. Nothing leaves the host except what the agent sends to Kentik. `lab.py down` removes the addresses, the sender, and anything a lab added.

## For the instructor

- `python3 lab.py status --reveal` shows what each lab has really changed. It gives the lab away.
- `python3 lab.py agent` prints the Universal Agent's own status page (seen on agent 5.0.29: plain text on `127.0.0.1:9996`). It lists the sending addresses the agent hears from and which of them match no device in Kentik, which makes labs 1 and 3 visible. How quickly it updates after a device is added is not known yet.
- `python3 lab.py listen` is a stand-in for the agent: it prints the flow that arrives on a port. Useful for trying a lab without a portal.
- On the lab site, **Instructor view** (at the foot of every page) adds each lab's answer to its page, and for the open lab what `status --reveal` shows. On the class copy it needs your link with the key; on a student's own host anyone can turn it on, so keep it off a shared screen.
- Tests: `python3 -m unittest discover -s tests`

## Status

Written Nov 11, 2026. Every lab was run end to end on Linux against the stand-in listener, and lab 11 against a real `snmpd`. **Labs 6 to 11 have not been run against a real Universal Agent or a Kentik portal yet**; labs 1 to 5 are being proven on a test host. `core-sw-01` sends NetFlow for now; in the course it is an sFlow switch.
