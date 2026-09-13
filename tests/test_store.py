import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operator_todos import Store


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def request(self, **extra):
        data = dict(request_key="domain", title="Choose the site domain", context="A domain is needed before launch.", recommendation="Use the existing domain.", consequence="A new domain costs $20/year; the existing domain costs nothing extra.", important=True, kind="approval", term="short", session_id="test-session")
        data.update(extra)
        return self.store.post(data, "test-agent")

    def test_gate_and_context(self):
        with self.assertRaises(ValueError):
            self.request(important=False)
        with self.assertRaises(ValueError):
            self.request(context="")
        with self.assertRaises(ValueError):
            self.request(consequence="")
        self.assertEqual(self.request(important=False, explicitly_requested=True)["status"], "open")

    def test_response_ack_and_no_implicit_approval(self):
        r = self.request()
        self.assertEqual(self.store.snapshot()["attention"], 1)
        with self.assertRaises(ValueError):
            self.store.act(dict(id=r["id"], action="done"))
        r = self.store.act(dict(id=r["id"], action="approve"))
        self.assertEqual(r["delivery"], "saved")
        with self.assertRaises(ValueError):
            self.store.ack(r["id"], "invented-response")
        r = self.store.ack(r["id"], r["response"]["id"])
        self.assertEqual(r["status"], "done")
        self.assertEqual(self.store.snapshot()["attention"], 0)

    def test_dismiss_does_not_repost(self):
        r = self.request()
        result = self.store.act(dict(id=r["id"], action="dismiss"))
        self.assertEqual(result["response"]["action"], "dismiss")
        self.assertEqual(self.request()["status"], "dismissed")
        self.assertEqual(self.store.snapshot()["attention"], 0)

    def test_delete_removes_content_but_preserves_deduplication(self):
        r = self.request()
        self.store.act(dict(id=r["id"], action="delete"))
        self.assertEqual(self.store.snapshot()["items"], [])
        self.assertNotIn("context", self.request())
        self.assertEqual(self.request()["status"], "deleted")

    def test_terms_and_manual_tasks(self):
        r = self.store.post(dict(title="Plan the garden", term="long"))
        self.assertEqual(self.store.snapshot()["attention"], 0)
        r = self.store.act(dict(id=r["id"], action="move", term="short"))
        self.assertEqual(r["term"], "short")
        self.assertEqual(self.store.act(dict(id=r["id"], action="done"))["status"], "done")

    def test_concurrent_agents_do_not_lose_items(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(lambda n: self.request(request_key=f"request-{n}"), range(24)))
        self.assertEqual(len(self.store.snapshot()["items"]), 24)
        self.assertEqual(len({i["id"] for i in items}), 24)

    def test_restore_history_reopens_in_original_term(self):
        manual = self.store.post(dict(title="Plan the garden", term="long"))
        self.store.act(dict(id=manual["id"], action="done"))
        restored = self.store.act(dict(id=manual["id"], action="restore"))
        self.assertEqual((restored["status"], restored["term"]), ("open", "long"))
        self.assertIsNone(restored["response"])
        agent = self.request()
        self.store.act(dict(id=agent["id"], action="dismiss"))
        restored = self.store.act(dict(id=agent["id"], action="restore"))
        self.assertEqual(self.store.snapshot()["attention"], 1)
        self.assertEqual(self.request()["status"], "open")
        self.store.act(dict(id=agent["id"], action="delete"))
        with self.assertRaises(ValueError):
            self.store.act(dict(id=agent["id"], action="restore"))

    def test_restore_requires_fresh_response_and_ignores_old_delivery(self):
        r = self.request()
        r = self.store.act(dict(id=r["id"], action="approve"))
        old_response = r["response"]["id"]
        self.store.ack(r["id"], old_response)
        restored = self.store.act(dict(id=r["id"], action="restore"))
        self.assertIsNone(restored["response"])
        self.assertEqual(restored["delivery"], "")
        with self.assertRaises(ValueError):
            self.store.ack(r["id"], old_response)
        self.store.mark_delivery(r["id"], "sent", response_id=old_response)
        self.assertEqual(self.store.get(r["id"])["delivery"], "")
        fresh = self.store.act(dict(id=r["id"], action="reject"))
        self.assertNotEqual(fresh["response"]["id"], old_response)
        self.store.ack(r["id"], fresh["response"]["id"])

    def test_concurrent_duplicates_are_one_request(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            items = list(pool.map(lambda _: self.request(), range(12)))
        self.assertEqual(len({i["id"] for i in items}), 1)

    def test_wait_receives_exact_user_response(self):
        r = self.request()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(self.store.wait, r["id"], 3)
            time.sleep(.1)
            self.store.act(dict(id=r["id"], action="reply", text="Use the existing domain."))
            result = future.result(timeout=4)
        self.assertEqual(result["response"]["text"], "Use the existing domain.")
        self.assertEqual(result["delivery"], "received")

    def test_reply_is_sent_once_and_failed_send_stays_visible(self):
        r = self.store.post(dict(request_key="test", title="Review", kind="reply", term="short", context="Need final direction.", important=True, session_id="test"), "codex")
        self.store.act(dict(id=r["id"], action="reply", text="Proceed"))
        with self.store.db(True) as db:
            r = self.store.fetch(db, r["id"])
            r["response"]["at"] -= 5
            self.store.save(db, r)
        with mock.patch("codex_desktop.deliver", side_effect=RuntimeError("offline")) as send:
            self.store.dispatch_one()
            self.store.dispatch_one()
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.store.get(r["id"])["delivery"], "failed")
        self.assertEqual(self.store.snapshot()["attention"], 1)

    def test_mcp_round_trip_and_no_approval_tool(self):
        script = Path(__file__).resolve().parents[1] / "operator_todos.py"
        p = subprocess.Popen([sys.executable, str(script), "mcp", "--source", "test-agent"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env={**os.environ, "OPERATOR_TODOS_DATA": self.temp.name})
        self.addCleanup(lambda: p.poll() is None and p.kill())
        def call(n, method, params):
            p.stdin.write(json.dumps(dict(jsonrpc="2.0", id=n, method=method, params=params)) + "\n")
            p.stdin.flush()
            return json.loads(p.stdout.readline())["result"]
        self.assertIn("instructions", call(1, "initialize", {"protocolVersion": "2024-11-05"}))
        tools = call(2, "tools/list", {})["tools"]
        self.assertFalse(any("approve" in t["name"] or "act" == t["name"] for t in tools))
        r = self.request()
        self.store.act(dict(id=r["id"], action="reject"))
        result = call(3, "tools/call", {"name": "operator_wait", "arguments": {"id": r["id"], "seconds": 1}})
        payload = json.loads(result["content"][0]["text"])
        self.assertEqual(payload["response"]["action"], "reject")
        p.stdin.close()
        p.wait(timeout=3)
        p.stdout.close()


if __name__ == "__main__":
    unittest.main()
