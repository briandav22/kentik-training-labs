# Kentik training labs

Hands-on labs for the Kentik training course. One command plays a small made-up network on your Linux host. Its three devices send real NetFlow to the Kentik Universal Agent on the same host, and from there into your own Kentik portal.

In every lab you are the SE and the lab plays the customer. A ticket arrives. You ask questions, look at the host, fix what's wrong, and confirm it in Kentik.

Python 3.8 or later, standard library only. Nothing to install.

## Before you start

- A Linux host (2 CPUs, 2 GB of memory is enough) with `python3`, `git`, `iproute2`, `iptables` and `tcpdump`.
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
| `python3 lab.py status` | Whether the network is running and which lab is open |
| `sudo python3 lab.py down` | Stops everything and cleans up the host |

Commands that change something need `sudo`. Leave the network running between labs: your portal gets more useful the longer it collects.

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

The tickets don't say what's wrong. That's the lab.

## How it works

Kentik tells devices apart by the address their flow comes from. `lab.py up` adds each device's address to the host's loopback interface, and a background sender exports NetFlow v9 from each address to the agent on `127.0.0.1`. Nothing leaves the host except what the agent sends to Kentik. `lab.py down` removes the addresses, the sender, and anything a lab added.

## For the instructor

- `python3 lab.py status --reveal` shows what each lab has really changed. It gives the lab away.
- `python3 lab.py listen` is a stand-in for the agent: it prints the flow that arrives on a port. Useful for trying a lab without a portal.
- Tests: `python3 -m unittest discover -s tests`

## Status

A first version, written Nov 11, 2026. Every lab was run end to end on Linux against the stand-in listener. **None has been run against a real Universal Agent or a Kentik portal yet.** `core-sw-01` sends NetFlow for now; in the course it is an sFlow switch.
