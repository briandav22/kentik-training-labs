"""The lab site (python3 lab.py ui): its catalog, the portal details and the server."""
import http.client
import http.server
import json
import os
import re
import stat
import tempfile
import threading
import unittest

os.environ.setdefault("KLAB_HOME", tempfile.mkdtemp(prefix="klab-test-"))

from klab import catalog, labs, portal, site, snmp, web   # noqa: E402

UI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "klab", "ui")

# The words that would give each lab away: the same as the ticket test in test_klab.py.
GIVEAWAYS = {2: ["2055"], 3: ["10.1.1.1", "GigabitEthernet0/0/4"], 4: ["iptables", "DROP"], 5: ["100", "sampl"],
             6: [site.UPDATE_SERVER, "update", "storm"], 7: [site.DB_SERVER, "5432", "trail"],
             8: ["udp", "port 53", "flood", "reflection"], 9: [site.SCANNER, "scan"],
             10: [site.COLD_DEST, site.DB_SERVER, "db-01", "port 22", "cold\""],
             11: [snmp.COMMUNITY]}


def strings(obj):
    """Every piece of text in a catalog entry, however deep."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from strings(v)


def drawings():
    """The source of each tile drawing in ui/art.js, by key."""
    with open(os.path.join(UI, "art.js")) as f:
        src = f.read()
    body = src[src.index("const ART = {"):]
    keys = list(re.finditer(r"^    '?([a-z][a-z-]*)'?: \(\) =>", body, re.M))
    return {m.group(1): body[m.start():(keys[i + 1].start() if i + 1 < len(keys) else len(body))]
            for i, m in enumerate(keys)}


class CatalogTest(unittest.TestCase):
    def test_every_lab_in_lab_py_has_one_page(self):
        for n in labs.LABS:
            pages = [lab for lab in catalog.LABS if lab["engine"] == n and not lab.get("replay")]
            self.assertEqual(len(pages), 1, "lab %d" % n)
            self.assertIs(catalog.for_engine(n), pages[0])

    def test_every_entry_is_complete(self):
        ids, tracks, art = set(), {t["id"] for t in catalog.TRACKS}, drawings()
        for lab in catalog.LABS:
            self.assertNotIn(lab["id"], ids)
            ids.add(lab["id"])
            self.assertIn(lab["track"], tracks, lab["id"])
            self.assertIn(lab["art"], art, lab["id"])
            for k in ("label", "line", "goal", "level", "course"):
                self.assertTrue(lab.get(k), "%s has no %s" % (lab["id"], k))
            self.assertIsInstance(lab["time"], int)
            self.assertTrue(lab.get("title") or lab["engine"], lab["id"])
            for k in lab["needs"] + lab["adds"]:
                self.assertIn(k, catalog.ADDS, lab["id"])
            if lab.get("page"):
                continue
            self.assertTrue(lab["steps"] and lab["look"] and lab["stuck"] and lab["key"] and lab["answer"], lab["id"])
            for s in lab["steps"]:
                self.assertTrue(isinstance(s, str) or (s.get("cmd") and s.get("text")), lab["id"])
            if lab["engine"] is not None:
                self.assertTrue(any("lab.py" in s.get("cmd", "") for s in lab["steps"] if isinstance(s, dict)),
                                "%s: a step should start it from the terminal too" % lab["id"])

    def test_nothing_a_student_reads_first_gives_a_lab_away(self):
        # Tile, page, ticket, steps, what to look for, what it adds, and the tile's drawing. Not the hints after
        # the first, the takeaway shown when done, or the instructor's answer.
        art = drawings()
        for lab in catalog.LABS:
            n = lab["engine"]
            if not n or lab.get("replay"):
                continue
            pub = catalog.public(lab)
            pub.pop("key")                  # shown once the lab is marked done
            pub.pop("asks", None)           # the same questions on every lab, as lab.py ask lists them
            text = " ".join(strings(pub)) + " " + art[lab["art"]]
            for w in GIVEAWAYS.get(n, []):
                self.assertNotIn(w.lower(), text.lower(), "%s leaks %r" % (lab["id"], w))

    def test_the_answers_stay_out_of_the_catalog(self):
        cat = catalog.catalog()
        self.assertFalse(any("answer" in lab for lab in cat["labs"]))
        dump = json.dumps(cat)
        for lab in catalog.LABS:
            if lab.get("answer"):
                self.assertNotIn(lab["answer"], dump)

    def test_a_replay_brings_back_traffic_not_a_ticket(self):
        for lab in catalog.LABS:
            if lab.get("replay"):
                pub = catalog.public(lab)
                self.assertNotIn("ticket", pub)
                self.assertEqual(pub["hints"], 0)

    def test_every_drawing_is_used_and_uses_only_the_course_colors(self):
        art = drawings()
        self.assertEqual(set(art), {lab["art"] for lab in catalog.LABS})
        for key, src in art.items():
            self.assertNotRegex(src, r"#[0-9a-fA-F]{3,6}\b", key)


class PortalTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="klab-portal-")
        self.file = os.path.join(self.dir, ".kentik.env")
        os.environ["KLAB_PORTAL_FILE"] = self.file
        os.environ.pop("KLAB_PORTAL_BASE", None)

    def tearDown(self):
        os.environ.pop("KLAB_PORTAL_FILE", None)
        os.environ.pop("KLAB_PORTAL_BASE", None)

    def test_details_are_kept_for_this_user_only(self):
        self.assertIsNone(portal.save("student@example.com", "abcdefgh12345678", "eu"))
        self.assertEqual(stat.S_IMODE(os.stat(self.file).st_mode), 0o600)
        self.assertEqual(portal.load(), {"email": "student@example.com", "token": "abcdefgh12345678", "region": "eu"})

    def test_a_page_never_sees_the_token(self):
        portal.save("student@example.com", "abcdefgh12345678", "us")
        pub = portal.public(portal.load())
        self.assertNotIn("abcdefgh12345678", json.dumps(pub))
        self.assertEqual(pub["token_end"], "5678")
        self.assertTrue(pub["connected"])

    def test_an_empty_token_keeps_the_saved_one(self):
        portal.save("student@example.com", "abcdefgh12345678", "us")
        portal.save("other@example.com", "", "us")
        self.assertEqual(portal.load()["token"], "abcdefgh12345678")

    def test_bad_details_are_refused(self):
        self.assertTrue(portal.save("not an email", "abc", "us"))
        self.assertTrue(portal.save("student@example.com", "has a space", "us"))
        self.assertTrue(portal.save("student@example.com", "abcdefgh", "mars"))
        self.assertFalse(os.path.exists(self.file))

    def test_forget_keeps_the_files_other_lines(self):
        with open(self.file, "w") as f:
            f.write("OTHER_TOOL=1\n")
        portal.save("student@example.com", "abcdefgh12345678", "us")
        portal.forget()
        with open(self.file) as f:
            self.assertEqual(f.read(), "OTHER_TOOL=1\n")

    def test_an_unreachable_portal_says_so_plainly(self):
        portal.save("student@example.com", "abcdefgh12345678", "us")
        os.environ["KLAB_PORTAL_BASE"] = "http://127.0.0.1:9/api/v5"
        r = portal.test(portal.load())
        self.assertFalse(r["ok"])
        self.assertIn("Couldn't reach", r["message"])

    def test_the_test_reads_the_device_list_with_the_users_details(self):
        seen = {}

        class FakeKentik(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                seen.update(path=self.path, email=self.headers.get("X-CH-Auth-Email"),
                            token=self.headers.get("X-CH-Auth-API-Token"))
                ok = seen["token"] == "abcdefgh12345678"
                body = json.dumps({"devices": [{"device_name": "edge-rtr-01"}, {"device_name": "a-real-router"}]}
                                  if ok else {"error": "no"}).encode()
                self.send_response(200 if ok else 401)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        srv = http.server.HTTPServer(("127.0.0.1", 0), FakeKentik)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            os.environ["KLAB_PORTAL_BASE"] = "http://127.0.0.1:%d/api/v5" % srv.server_address[1]
            portal.save("student@example.com", "abcdefgh12345678", "us")
            r = portal.test(portal.load())
            self.assertTrue(r["ok"], r)
            self.assertEqual(seen, {"path": "/api/v5/devices", "email": "student@example.com", "token": "abcdefgh12345678"})
            self.assertIn("2 devices, 1 of them the lab's", r["message"])
            portal.save("student@example.com", "wrongtoken123456", "us")
            self.assertIn("didn't accept", portal.test(portal.load())["message"])
        finally:
            srv.shutdown()
            srv.server_close()

    def test_a_reset_keeps_the_agent_unless_its_a_full_wipe(self):
        labs_plan, full = portal.plan("labs"), portal.plan("full")
        self.assertTrue(labs_plan["keep"])
        self.assertNotIn("agent", [x["kind"] for x in labs_plan["portal"]])
        self.assertEqual(full["keep"], [])
        self.assertIn("agent", [x["kind"] for x in full["portal"]])
        added = {a for lab in catalog.LABS for a in lab["adds"]} - {"agent"}
        self.assertEqual({x["kind"] for x in labs_plan["portal"]}, added)
        for x in full["portal"]:
            self.assertTrue(x["how"], x["kind"])


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = os.path.join(tempfile.mkdtemp(prefix="klab-portal-"), ".kentik.env")
        os.environ["KLAB_PORTAL_FILE"] = cls.env
        portal.save("student@example.com", "abcdefgh12345678", "us")
        cls.httpd = web.make_server("127.0.0.1", 0, "test-key")
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        os.environ.pop("KLAB_PORTAL_FILE", None)

    def req(self, method, path, body=None, key="test-key", host=None, ctype="application/json"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Host": host or "127.0.0.1:%d" % self.port}
        if key:
            headers["X-Lab-Key"] = key
        data = None
        if body is not None:
            data = json.dumps(body).encode() if ctype == "application/json" else body.encode()
            headers["Content-Type"] = ctype
        c.request(method, path, body=data, headers=headers)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw.decode()), r
        except ValueError:
            return r.status, raw, r

    def test_every_call_needs_the_key(self):
        self.assertEqual(self.req("GET", "/api/status", key=None)[0], 403)
        self.assertEqual(self.req("GET", "/api/status", key="wrong")[0], 403)
        self.assertEqual(self.req("GET", "/api/status", key="t\u00e9st-key")[0], 403)     # not ASCII: still just a no
        self.assertRegex(web.new_key(), r"^[A-Za-z0-9_-]{12}$")
        self.assertEqual(self.req("POST", "/api/check", {}, key=None)[0], 403)
        self.assertEqual(self.req("GET", "/api/status")[0], 200)

    def test_another_host_name_is_refused(self):
        self.assertEqual(self.req("GET", "/api/status", host="attacker.example:%d" % self.port)[0], 403)
        self.assertEqual(self.req("GET", "/", host="attacker.example")[0], 403)
        self.assertEqual(self.req("GET", "/api/status", host="10.9.8.7:%d" % (self.port + 1))[0], 403)

    def test_a_laptop_can_use_the_hosts_address(self):
        self.assertEqual(self.req("GET", "/api/status", host="10.9.8.7:%d" % self.port)[0], 200)
        self.assertEqual(self.req("GET", "/api/status", host="[::1]:%d" % self.port)[0], 200)
        self.assertEqual(self.req("GET", "/api/status", host="localhost:%d" % self.port)[0], 200)

    def test_it_serves_its_pages_and_nothing_else(self):
        code, body, r = self.req("GET", "/", key=None)
        self.assertEqual(code, 200)
        self.assertIn(b"app.js", body)
        self.assertIn("script-src 'self'", r.getheader("Content-Security-Policy"))
        for path in ("/../web.py", "/..%2fweb.py", "/../../lab.py", "/nothing.js"):
            self.assertEqual(self.req("GET", path, key=None)[0], 404, path)

    def test_a_change_must_come_as_json(self):
        self.assertEqual(self.req("POST", "/api/check", "x", ctype="text/plain")[0], 415)

    def test_the_status_never_hints_at_a_fault(self):
        code, st, _ = self.req("GET", "/api/status")
        self.assertEqual(code, 200)
        self.assertNotIn("devices", st)                  # how much each device sends would give lab 5 away
        self.assertEqual(st["agent_port"], site.AGENT_PORT)
        self.assertNotIn("abcdefgh12345678", json.dumps(st))
        self.assertEqual(st["portal"]["token_end"], "5678")

    def test_the_customer_answers_for_that_lab(self):
        code, r, _ = self.req("POST", "/api/ask", {"id": "lab-2", "topic": "port"})
        self.assertEqual(code, 200)
        self.assertEqual(r["a"], labs.answer(2, "port"))
        self.assertEqual(self.req("POST", "/api/ask", {"id": "lab-2", "topic": "secrets"})[0], 400)

    def test_hints_step_and_stop_at_the_last(self):
        self.assertEqual(self.req("GET", "/api/hint?id=lab-3&n=1")[1]["text"], labs.LABS[3]["hints"][0])
        self.assertEqual(self.req("GET", "/api/hint?id=lab-3&n=9")[1]["n"], 3)
        self.assertEqual(self.req("GET", "/api/hint?id=setup")[0], 404)
        self.assertEqual(self.req("GET", "/api/hint?id=alerting")[0], 404)

    def test_the_answer_comes_only_from_its_own_call(self):
        code, r, _ = self.req("GET", "/api/answer?id=lab-2")
        self.assertEqual(code, 200)
        self.assertIn("2055", r["answer"])
        self.assertNotIn("2055", json.dumps(self.req("GET", "/api/catalog")[1]))

    def test_a_full_wipe_needs_wipe_typed(self):
        code, r, _ = self.req("POST", "/api/reset", {"scope": "full"})
        self.assertEqual(code, 400)
        self.assertIn("WIPE", r["error"])

    def test_without_sudo_the_site_shows_the_command(self):
        real = web.is_root
        web.is_root = lambda: False
        try:
            for path, body in (("/api/launch", {"id": "lab-4"}), ("/api/healthy", {}), ("/api/stop", {}),
                               ("/api/tell", {"request": ["port", "9995"]})):
                code, r, _ = self.req("POST", path, body)
                self.assertEqual(code, 200, path)
                self.assertTrue(r["needs_root"], path)
                self.assertIn("sudo python3 lab.py", r["cmd"], path)
            self.assertIn("start 4", self.req("POST", "/api/launch", {"id": "lab-4"})[1]["cmd"])
        finally:
            web.is_root = real

    def test_a_lab_with_nothing_to_launch_says_so(self):
        code, r, _ = self.req("POST", "/api/launch", {"id": "synthetics"})
        self.assertEqual(code, 200)
        self.assertIn("Nothing to launch", r["output"])
        self.assertEqual(self.req("POST", "/api/launch", {"id": "no-such-lab"})[0], 404)


if __name__ == "__main__":
    unittest.main()
