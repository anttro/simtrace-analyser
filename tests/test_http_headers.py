"""API JSON and PCAP downloads must not be cached by the browser.

The service worker bypasses /api/ (it must not mediate a download), but the
response headers are the second line of defence: a stale status or a cached
download would otherwise survive a reload.
"""

import os
import struct
import tempfile
import threading
import unittest
import urllib.request
from http.server import HTTPServer

from simtrace_analyser.database import Database
from simtrace_analyser.server import RequestHandler
from simtrace2_pysniff.pcap import PCAP_MAGIC


class TestApiResponsesAreNotCached(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Database(os.path.join(self.tmp.name, 'sessions.db'))
        saved = (RequestHandler.db, RequestHandler.capture,
                 RequestHandler.capture_mode, RequestHandler.log_requests)
        RequestHandler.db = self.db
        RequestHandler.capture = None
        RequestHandler.capture_mode = 'disabled'
        RequestHandler.log_requests = False
        self.addCleanup(self._restore_handler, saved)

        self.server = HTTPServer(('127.0.0.1', 0), RequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop_server)
        self.base = 'http://127.0.0.1:%d' % self.server.server_address[1]

    def _restore_handler(self, saved):
        (RequestHandler.db, RequestHandler.capture,
         RequestHandler.capture_mode, RequestHandler.log_requests) = saved

    def _stop_server(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        with urllib.request.urlopen(self.base + path, timeout=5) as resp:
            return resp, resp.read()

    def test_api_json_is_no_store(self):
        resp, body = self._get('/api/status')
        self.assertEqual(resp.status, 200)
        self.assertIn('application/json', resp.headers['Content-Type'])
        self.assertEqual(resp.headers['Cache-Control'], 'no-store')
        self.assertIn(b'simtrace-analyser-server', body)

    def test_pcap_download_is_no_store_and_complete(self):
        sid = self.db.create_session('pcap')
        self.db.insert_message(sid, 0.0, 'atr', bytes.fromhex('3b00'))
        self.db.insert_message(sid, 0.1, 'tpdu', bytes.fromhex('00a40004023f00'))
        resp, body = self._get('/api/sessions/%d/pcap' % sid)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers['Content-Type'], 'application/vnd.tcpdump.pcap')
        self.assertEqual(resp.headers['Cache-Control'], 'no-store')
        self.assertTrue(resp.headers['Content-Disposition'].startswith('attachment;'))
        self.assertEqual(int(resp.headers['Content-Length']), len(body))
        self.assertEqual(struct.unpack('<I', body[:4])[0], PCAP_MAGIC)
        self.assertGreater(len(body), 24)


if __name__ == '__main__':
    unittest.main()
