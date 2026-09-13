import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codex_desktop import Desktop


class DesktopTests(unittest.TestCase):
    def test_missing_owner_never_sends_a_turn(self):
        desktop = Desktop.__new__(Desktop)
        for owner in [None, '', ' ', 7]:
            with mock.patch.object(desktop, 'request', return_value={'handledByClientId': owner}) as request:
                with self.assertRaises(RuntimeError):
                    desktop.send('00000000-0000-4000-8000-000000000001', 'Test response')
                self.assertEqual(request.call_count, 1)

    def test_send_targets_only_the_discovered_conversation_owner(self):
        desktop = Desktop.__new__(Desktop)
        session = '00000000-0000-4000-8000-000000000001'
        with mock.patch.object(desktop, 'request', side_effect=[{'handledByClientId': 'owner-42'}, {'ok': True}]) as request:
            self.assertEqual(desktop.send(session, 'Exact response'), {'ok': True})
        method, params, version, owner = request.call_args.args
        self.assertEqual((method, version, owner), ('thread-follower-start-turn', 2, 'owner-42'))
        self.assertEqual(params['conversationId'], session)
        self.assertEqual(params['turnStart']['request']['threadId'], session)
        self.assertEqual(params['turnStart']['request']['input'][0]['text'], 'Exact response')

    def test_failed_initialize_closes_socket(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / 'test.sock'
            listener = socket.socket(socket.AF_UNIX)
            self.addCleanup(listener.close)
            listener.bind(str(endpoint))
            endpoint.chmod(0o600)
            fake = mock.Mock()
            with mock.patch('codex_desktop.socket.socket', return_value=fake), mock.patch.object(Desktop, 'request', side_effect=RuntimeError('changed protocol')):
                with self.assertRaises(RuntimeError):
                    Desktop(endpoint)
            fake.close.assert_called_once()

    def test_fragmented_frames_and_oversize_rejection(self):
        desktop = Desktop.__new__(Desktop)
        payload = json.dumps({'type': 'response', 'result': 'ok'}).encode()
        desktop.sock = mock.Mock()
        header = struct.pack('<I', len(payload))
        desktop.sock.recv.side_effect = [header[:1], header[1:], payload[:3], payload[3:]]
        self.assertEqual(desktop.read()['result'], 'ok')
        desktop.sock.recv.side_effect = [struct.pack('<I', 17 * 1024 * 1024)]
        with self.assertRaises(RuntimeError):
            desktop.read()


if __name__ == '__main__':
    unittest.main()
