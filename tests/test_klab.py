import contextlib
import io
import os
import random
import socket
import tempfile
import time
import unittest

os.environ["KLAB_HOME"] = tempfile.mkdtemp(prefix="klab-test-")

from klab import cli, labs, netflow, site, state, traffic   # noqa: E402
from klab.engine import Engine                               # noqa: E402


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cli.main(list(argv))
    return rc, out.getvalue() + err.getvalue()


class NetflowTest(unittest.TestCase):
    def test_round_trip(self):
        now = time.time()
        recs = [netflow.rec("10.1.20.15", "203.0.113.10", 50000, 443, 6, 0x1b, 12, 49, 10, 900, now - 1, now),
                netflow.rec("10.1.20.16", "198.51.100.53", 50001, 53, 17, 0, 12, 49, 1, 70, now - 1, now)]
        pkt = netflow.encode(recs, 0, now - 100, now, 7, True)
        hdr, got = netflow.decode(pkt, {})
        self.assertEqual(hdr["source_id"], 7)
        self.assertEqual(hdr["count"], 3)
        self.assertEqual([(r["src"], r["dst"], r["dport"], r["proto"], r["pkts"], r["bytes"]) for r in got],
                         [("10.1.20.15", "203.0.113.10", 443, 6, 10, 900), ("10.1.20.16", "198.51.100.53", 53, 17, 1, 70)])

    def test_data_without_template_decodes_nothing(self):
        now = time.time()
        pkt = netflow.encode([netflow.rec("10.1.20.15", "203.0.113.10", 1, 2, 6, 0, 1, 2, 1, 1, now, now)],
                             0, now - 1, now, 1, False)
        self.assertEqual(netflow.decode(pkt, {})[1], [])

    def test_record_length_matches_template(self):
        self.assertEqual(netflow.REC_LEN, sum(l for _, l in netflow.FIELDS))


class SiteTest(unittest.TestCase):
    def test_addresses_follow_the_course_rules(self):
        import ipaddress
        docs = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
        for name, s in site.SERVICES.items():
            ip = ipaddress.ip_address(s[1])
            if s[4] == "internet":
                self.assertTrue(any(ip in n for n in docs), name)
            else:
                self.assertTrue(ip.is_private, name)
        for d in site.DEVICES.values():
            self.assertTrue(ipaddress.ip_address(d["ip"]).is_private)
        self.assertIn("10.1.20.15", site.hosts("hq_users"))      # laptop-07
        self.assertEqual(len(set(site.alias_ips())), 2 * len(site.DEVICES))

    def test_every_path_uses_real_interfaces(self):
        for path in site.PATHS.values():
            for device, a, b in path:
                self.assertIn(a, site.DEVICES[device]["ifs"])
                self.assertIn(b, site.DEVICES[device]["ifs"])


class TrafficTest(unittest.TestCase):
    def test_a_conversation_is_seen_by_every_device_on_its_path(self):
        out = traffic.conversation("branch_users", "10.2.20.30", "app", time.time(), random.Random(1))
        self.assertEqual(set(out), {"branch-rtr-01", "edge-rtr-01", "core-sw-01"})
        for recs in out.values():
            self.assertEqual(len(recs), 2)                         # request and reply
            self.assertEqual(recs[0]["in_if"], recs[1]["out_if"])  # the reply goes back the way it came

    def test_sampling_keeps_about_one_in_n(self):
        rng = random.Random(2)
        recs = []
        for _ in range(300):
            for r in traffic.generate(1.0, time.time(), rng).values():
                recs += r
        kept = traffic.sample(recs, 100, rng)
        ratio = traffic.bits(recs) / float(traffic.bits(kept))
        self.assertTrue(70 < ratio < 140, ratio)
        self.assertEqual(traffic.sample(recs, 1, rng), recs)


class EngineTest(unittest.TestCase):
    def setUp(self):
        self.rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rx.bind(("127.0.0.1", 0))
        self.rx.settimeout(0.3)
        self.st = state.baseline()
        self.st.update(bind=False, port=self.rx.getsockname()[1])

    def tearDown(self):
        self.rx.close()

    def drain(self):
        templates, recs = {}, []
        try:
            while True:
                recs += netflow.decode(self.rx.recvfrom(65535)[0], templates)[1]
        except socket.timeout:
            return recs

    def test_sends_decodable_flow_to_the_port_in_the_state(self):
        eng = Engine(seed=3)
        self.addCleanup(eng.close)
        sent = sum(eng.tick(1.0, time.time(), self.st) for _ in range(5))
        got = self.drain()
        self.assertGreater(sent, 20)
        self.assertEqual(len(got), sent)
        self.assertTrue(all(r["bytes"] >= r["pkts"] > 0 for r in got))

    def test_a_port_change_takes_effect_on_the_next_tick(self):
        eng = Engine(seed=4)
        self.addCleanup(eng.close)
        eng.tick(1.0, time.time(), self.st)
        self.drain()
        other = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        other.bind(("127.0.0.1", 0))
        self.st["port"] = other.getsockname()[1]
        other.close()
        for _ in range(3):
            eng.tick(1.0, time.time(), self.st)
        self.assertEqual(self.drain(), [])

    def test_stats_show_the_gap_sampling_makes(self):
        eng = Engine(seed=5)
        self.addCleanup(eng.close)
        self.st["sample"]["core-sw-01"] = 100
        for _ in range(200):
            eng.tick(1.0, time.time(), self.st)
        self.drain()
        d = eng.stats(time.time())["devices"]
        self.assertEqual(d["edge-rtr-01"]["true_bps"], d["edge-rtr-01"]["sent_bps"])
        self.assertGreater(d["core-sw-01"]["true_bps"], 20 * d["core-sw-01"]["sent_bps"])


class LabsTest(unittest.TestCase):
    def test_each_fault_changes_exactly_what_it_should(self):
        want = {1: {}, 2: {"port": 2055}, 3: {"source": "edge-rtr-01"}, 4: {"firewall": True}, 5: {"sample": "core-sw-01"}}
        for n, lab in labs.LABS.items():
            st, base = state.baseline(), state.baseline()
            lab["fault"](st)
            changed = {k for k in base if st[k] != base[k]}
            self.assertEqual(changed, set(want[n]), n)

    def test_every_lab_is_complete(self):
        for n, lab in labs.LABS.items():
            self.assertTrue(lab["title"] and lab["ticket"] and len(lab["hints"]) == 3, n)
            for topic in lab["answers"]:
                self.assertIn(topic, labs.QUESTIONS)
        for topic in labs.QUESTIONS:
            self.assertTrue(labs.answer(0, topic))

    def test_ticket_and_status_never_give_the_fault_away(self):
        giveaways = {2: ["2055"], 3: ["10.1.1.1", "GigabitEthernet0/0/4"], 4: ["iptables", "DROP"], 5: ["100", "sampl"]}
        for n, words in giveaways.items():
            st = state.baseline()
            st["lab"] = n
            labs.LABS[n]["fault"](st)
            state.save(st)
            text = run("ticket")[1] + run("status")[1] + run("labs")[1] + run("hint")[1]
            for w in words:
                self.assertNotIn(w.lower(), text.lower(), "lab %d leaks %r" % (n, w))

    def test_the_customer_can_be_wrong(self):
        self.assertIn("10.1.0.1", labs.answer(3, "ips"))            # what she believes, not what the router does
        self.assertNotIn("2055", labs.answer(2, "port"))
        self.assertIn("100", labs.answer(5, "sampling"))            # but she tells the truth when asked the right thing


class CliTest(unittest.TestCase):
    def test_hints_step_and_stop_at_the_last(self):
        st = state.baseline()
        st["lab"] = 2
        state.save(st)
        self.assertIn("Hint 1 of 3", run("hint")[1])
        self.assertIn("Hint 3 of 3", run("hint", "9")[1])

    def test_commands_that_change_things_ask_for_sudo(self):
        if os.geteuid() == 0:
            self.skipTest("running as root")
        for argv in (["up"], ["down"], ["start", "1"], ["tell", "port", "9995"]):
            rc, text = run(*argv)
            self.assertEqual(rc, 1)
            self.assertIn("sudo python3 lab.py", text)

    def test_ask_lists_questions_then_answers(self):
        state.save(state.baseline())
        self.assertIn("lab.py ask port", run("ask")[1])
        self.assertIn("9995", run("ask", "port")[1])


if __name__ == "__main__":
    unittest.main()
