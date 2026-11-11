#!/usr/bin/env bash
# Prepares one student host for the Kentik training labs. Run once, as root, on a fresh Ubuntu or
# Debian machine (2 CPUs and 2 GB of memory are enough). It works the same on any provider.
#
#   sudo bash setup-host.sh
#
# It installs what the labs use and nothing else. It does NOT install the Kentik Universal Agent:
# each student does that themselves, with the command from their own portal. That is the first lab.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this as root: sudo bash setup-host.sh" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3 iproute2 iptables tcpdump snmpd curl

# snmpd is only needed for the NMS lab, which turns it on. Keep it off until then.
if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
  systemctl disable --now snmpd >/dev/null 2>&1 || true
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 8):
    sys.exit("The labs need Python 3.8 or later; this host has %d.%d" % sys.version_info[:2])
print("Python %d.%d is fine." % sys.version_info[:2])
PY

echo
echo "This host is ready for the labs."
echo "Next, as the student: clone the labs repo and run  python3 lab.py labs"
