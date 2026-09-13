import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from operator_todos import PRESENCE_TTL, Store


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)

    def test_historical_mcp_and_policy_receipts_are_not_live(self):
        self.store.record_connection('codex', 'mcp', 'past client')
        self.store.record_connection('claude', 'policy', 'session hook')
        self.assertEqual(self.store.snapshot()['live_agents'], [])

    def test_multiple_clients_disconnect_independently(self):
        self.store.open_connection('one', 'codex', 'first')
        self.store.open_connection('two', 'codex', 'second')
        self.assertEqual(self.store.live_agents(), [{'source': 'codex', 'clients': 2}])
        self.store.close_connection('one')
        self.assertEqual(self.store.live_agents(), [{'source': 'codex', 'clients': 1}])
        self.store.close_connection('two')
        self.assertEqual(self.store.live_agents(), [])

    def test_expired_heartbeat_and_reused_pid_do_not_show_green(self):
        self.store.open_connection('one', 'codex', 'client')
        with mock.patch('operator_todos.time.time', return_value=time.time() + PRESENCE_TTL + 1):
            self.assertEqual(self.store.live_agents(), [])
        with mock.patch('operator_todos.process_identity', return_value='different-boot-or-start'):
            self.assertEqual(self.store.live_agents(), [])

    def client(self):
        process = subprocess.Popen([sys.executable, str(Path(__file__).resolve().parents[1] / 'operator_todos.py'),
                                    'mcp', '--source', 'codex'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True,
                                   env={**os.environ, 'OPERATOR_TODOS_DATA': self.temp.name})
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
        self.addCleanup(cleanup)
        process.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
            'params': {'protocolVersion': '2024-11-05', 'clientInfo': {'name': 'presence-test'}}}) + '\n')
        process.stdin.flush()
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(ready.select(5), 'MCP initialization timed out')
        result = json.loads(process.stdout.readline())
        self.assertIn('serverInfo', result['result'])
        deadline = time.monotonic() + 5
        while not self.store.live_agents() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertEqual(self.store.live_agents(), [{'source': 'codex', 'clients': 1}])
        return process

    def test_stdio_eof_removes_live_connection(self):
        process = self.client()
        process.stdin.close()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(self.store.live_agents(), [])

    def test_crashed_server_is_disconnected_without_waiting_for_ttl(self):
        process = self.client()
        process.kill()
        process.wait(timeout=5)
        self.assertEqual(self.store.live_agents(), [])


if __name__ == '__main__':
    unittest.main()
