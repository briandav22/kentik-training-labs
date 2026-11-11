import contextlib
import io
import os
import random
import socket
import tempfile
import time
import unittest

os.environ["KLAB_HOME"] = tempfile.mkdtemp(prefix="klab-test-")

from klab import cli, labs, netflow, site, snmp, state, traffic   # noqa: E402
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

    def test_stats_follow_a_change_within_the_window(self):
        eng = Engine(seed=6)
        self.addCleanup(eng.close)
        t0 = 1_900_000_000.0
        eng.since = t0
        for i in range(60):
            eng.tick(1.0, t0 + i, self.st)
        quiet = eng.stats(t0 + 60)["devices"]["edge-rtr-01"]["true_bps"]
        self.st["scenario"] = {"name": "cold", "start": t0 + 60, "end": t0 + 9999}
        for i in range(60, 150):
            eng.tick(1.0, t0 + i, self.st)
        self.drain()
        busy = eng.stats(t0 + 150)["devices"]["edge-rtr-01"]["true_bps"]
        self.assertGreater(busy, 8 * quiet)
        self.assertGreater(busy, 25e6)            # the case's own rate, not an average since the start

    def test_stats_show_the_gap_sampling_makes(self):
        eng = Engine(seed=5)
        self.addCleanup(eng.close)
        self.st["sample"]["core-sw-01"] = 100
        t0 = time.time()
        eng.since = t0
        for i in range(200):
            eng.tick(1.0, t0 + i, self.st)
        self.drain()
        d = eng.stats(t0 + 200)["devices"]
        self.assertEqual(d["edge-rtr-01"]["true_bps"], d["edge-rtr-01"]["sent_bps"])
        self.assertGreater(d["core-sw-01"]["true_bps"], 20 * d["core-sw-01"]["sent_bps"])


class LabsTest(unittest.TestCase):
    def test_each_fault_changes_exactly_what_it_should(self):
        want = {1: {}, 2: {"port": 2055}, 3: {"source": "edge-rtr-01"}, 4: {"firewall": True}, 5: {"sample": "core-sw-01"},
                6: {"scenario": 1}, 7: {"scenario": 1}, 8: {"scenario": 1}, 9: {"scenario": 1}, 10: {"scenario": 1},
                11: {"snmp": True}}
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
        giveaways = {2: ["2055"], 3: ["10.1.1.1", "GigabitEthernet0/0/4"], 4: ["iptables", "DROP"], 5: ["100", "sampl"],
                     6: [site.UPDATE_SERVER, "update", "storm"], 7: [site.DB_SERVER, "5432", "trail"],
                     8: ["udp", "port 53", "flood", "reflection"], 9: [site.SCANNER, "scan"],
                     10: [site.COLD_DEST, site.DB_SERVER, "db-01", "port 22", "cold\""],
                     11: [snmp.COMMUNITY]}
        for n, words in giveaways.items():
            st = state.baseline()
            st["lab"] = n
            labs.LABS[n]["fault"](st)
            if st.get("scenario"):
                st["scenario"].update(start=0, end=2e10)
            state.save(st)
            text = run("ticket")[1] + run("status")[1] + run("labs")[1] + run("hint")[1]
            for w in words:
                self.assertNotIn(w.lower(), text.lower(), "lab %d leaks %r" % (n, w))

    def test_the_customer_can_be_wrong(self):
        self.assertIn("10.1.0.1", labs.answer(3, "ips"))            # what she believes, not what the router does
        self.assertNotIn("2055", labs.answer(2, "port"))
        self.assertIn("100", labs.answer(5, "sampling"))            # but she tells the truth when asked the right thing


class ScenarioTest(unittest.TestCase):
    def run_case(self, name, seconds=120, age=0):
        rng, now = random.Random(7), 1_800_000_000.0
        st = {"scenario": {"name": name, "start": now - age, "end": now + 9999}}
        out = {}
        for i in range(seconds):
            for dev, recs in traffic.scenario(st, 1.0, now + i, rng).items():
                out.setdefault(dev, []).extend(recs)
        return out

    def test_the_laptop_checks_in_even_with_no_case_open(self):
        rng, hits = random.Random(8), 0
        for i in range(3600):
            for recs in traffic.scenario({"scenario": None}, 1.0, 1e9 + i, rng).values():
                hits += sum(1 for r in recs if r["src"] == site.TRAIL_LAPTOP and r["dst"] == site.BAD_HOST)
        self.assertTrue(10 <= hits <= 80, hits)          # about every four minutes, seen on two devices

    def test_storm_is_everyone_pulling_from_one_server(self):
        edge = [r for r in self.run_case("storm")["edge-rtr-01"] if r["src"] == site.UPDATE_SERVER]
        self.assertGreater(len({r["dst"] for r in edge}), 40)
        self.assertGreater(8 * sum(r["bytes"] for r in edge) / 120.0, 20e6)      # tens of Mbps, far above everyday

    def test_trail_talks_to_the_database_then_uploads(self):
        early = self.run_case("trail", seconds=170)
        self.assertTrue(any(r["dst"] == site.DB_SERVER and r["dport"] == 5432 for r in early["core-sw-01"]))
        late = [r for r in self.run_case("trail", seconds=60, age=300)["edge-rtr-01"]
                if r["src"] == site.TRAIL_LAPTOP and r["dst"] == site.BAD_HOST]
        self.assertGreater(sum(r["bytes"] for r in late), 30e6)

    def test_flood_is_many_sources_one_target_one_kind_of_packet(self):
        recs = [r for r in self.run_case("flood", seconds=20)["edge-rtr-01"] if r["dst"] == site.WEB_SERVER]
        self.assertGreater(len({r["src"] for r in recs}), 300)
        self.assertEqual({(r["proto"], r["sport"]) for r in recs}, {(17, 53)})
        self.assertEqual({(r["in_if"], r["out_if"]) for r in recs}, {(2, 5)})     # in from the ISP

    def test_scan_is_one_source_many_ports_one_packet_each(self):
        recs = [r for r in self.run_case("scan", seconds=60)["core-sw-01"] if r["src"] == site.SCANNER]
        self.assertGreater(len({r["dport"] for r in recs}), 500)
        self.assertEqual({r["pkts"] for r in recs}, {1})
        self.assertTrue(all(r["flags"] == traffic.SYN for r in recs))

    def test_cold_case_is_a_server_sending_out_on_port_22(self):
        recs = [r for r in self.run_case("cold", seconds=30)["edge-rtr-01"] if r["src"] == site.DB_SERVER]
        self.assertEqual({(r["dst"], r["dport"]) for r in recs}, {(site.COLD_DEST, 22)})
        self.assertEqual({(r["in_if"], r["out_if"]) for r in recs}, {(5, 2)})     # out to the ISP

    def test_a_case_sends_nothing_before_it_starts_or_after_it_ends(self):
        st = {"scenario": {"name": "flood", "start": 2000.0, "end": 3000.0}}
        rng = random.Random(9)
        for now in (1000.0, 3500.0):
            recs = sum((v for v in traffic.scenario(st, 1.0, now, rng).values()), [])
            self.assertFalse([r for r in recs if r["dst"] == site.WEB_SERVER])

    def test_case_addresses_follow_the_course_rules(self):
        import ipaddress
        docs = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
        for ip in (site.UPDATE_SERVER, site.BAD_HOST, site.COLD_DEST):
            self.assertTrue(any(ipaddress.ip_address(ip) in n for n in docs), ip)
        self.assertIn(site.TRAIL_LAPTOP, site.hosts("hq_users"))
        self.assertIn(site.SCANNER, site.hosts("branch_users"))


class SnmpTest(unittest.TestCase):
    def test_request_is_a_v2c_get_for_the_host_name(self):
        pkt = snmp.get_request("kentik-ro")
        self.assertEqual(pkt[0], 0x30)
        self.assertIn(b"kentik-ro", pkt)
        self.assertIn(bytes([0x06, 0x08, 0x2B, 6, 1, 2, 1, 1, 5, 0]), pkt)      # 1.3.6.1.2.1.1.5.0
        self.assertIn(b"\xa0", pkt)                                              # a GetRequest

    def test_asks_a_responder_and_reads_its_answer(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        srv.bind(("127.0.0.1", 0))
        self.addCleanup(srv.close)

        def serve():
            pkt, addr = srv.recvfrom(4096)
            if b"right" not in pkt:
                return                                                            # a real agent stays silent
            vb = snmp._tlv(0x30, snmp._oid(snmp.SYS_NAME) + snmp._tlv(0x04, b"lab-host"))
            pdu = snmp._tlv(0xA2, snmp._int(1) + snmp._int(0) + snmp._int(0) + snmp._tlv(0x30, vb))
            srv.sendto(snmp._tlv(0x30, snmp._int(1) + snmp._tlv(0x04, b"right") + pdu), addr)

        import threading
        for community, want in (("right", "lab-host"), ("wrong", None)):
            t = threading.Thread(target=serve)
            t.start()
            self.assertEqual(snmp.test(community, port=srv.getsockname()[1], timeout=0.5), want)
            if want is None:
                snmp.test("right", port=srv.getsockname()[1], timeout=0.5)       # let the responder finish
            t.join()

    def test_the_customer_gives_the_old_string_first(self):
        self.assertIn(snmp.WRONG_COMMUNITY, labs.answer(11, "snmp"))
        self.assertIn(snmp.COMMUNITY, labs.answer(11, "changes"))


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
