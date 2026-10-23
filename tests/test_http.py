from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from society_gate.server import make_server
from society_gate.service import Service


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = Service(Path(self.temp.name) / "http.sqlite3")
        self.tokens = self.service.seed()
        self.relay = "r" * 40
        self.server = make_server(self.service, port=0, skill_id="test-skill", relay_token=self.relay)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, actor=None, body=None, headers=None):
        request_headers = {}
        if actor:
            request_headers["Authorization"] = "Bearer " + self.tokens.get(actor, actor)
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        req = Request(self.base + path, headers=request_headers, data=json.dumps(body).encode() if body is not None else None)
        try:
            response = urlopen(req, timeout=3)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read()
            payload = json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
            return response.status, payload

    def test_static_health_and_protected_state(self):
        self.assertEqual(self.request("/")[0], 200)
        self.assertEqual(self.request("/app.js")[0], 200)
        self.assertEqual(self.request("/health")[1]["vendor_connected"], False)
        self.assertEqual(self.request("/api/state")[0], 401)
        self.assertEqual(self.request("/api/state", "resident")[1]["actor"]["unit"], "A-101")
        self.assertEqual(self.request("/.local/credentials.json")[0], 401)

    def test_http_guard_to_resident_to_guard(self):
        status, visit = self.request("/api/visitors", "guard", {"visitor":"Sam", "purpose":"Delivery", "unit":"A-101"})
        self.assertEqual(status, 200)
        self.assertEqual(self.request("/api/decision", "guard", {"id":visit["id"],"decision":"approved"})[0], 403)
        self.assertEqual(self.request("/api/decision", "resident", {"id":visit["id"],"decision":"approved"})[0], 200)
        self.assertEqual(self.request("/api/movement", "guard", {"id":visit["id"],"action":"check-in"})[1]["status"], "checked_in")

    def test_reject_cross_origin_and_dns_rebinding(self):
        self.assertEqual(self.request("/api/state", "resident", headers={"Origin":"https://elsewhere.example"})[0], 403)
        self.assertEqual(self.request("/health", headers={"Host":"evil.example"})[0], 403)

    def test_vendor_contract_requires_integration_credential(self):
        body = {"visitor":"Sam", "purpose":"Delivery", "unit":"A-101", "external_id":"event-1"}
        self.assertEqual(self.request("/api/integrations/visitors", "guard", body)[0], 403)
        self.assertEqual(self.request("/api/integrations/visitors", "integration", body)[0], 200)

    def envelope(self, token=None):
        return {"context":{"System":{"application":{"applicationId":"test-skill"},"user":{"accessToken":token or self.tokens["resident"]}}},
                "session":{"sessionId":"real-alexa-session"},
                "request":{"requestId":"real-alexa-request","type":"LaunchRequest","timestamp":datetime.now(timezone.utc).isoformat()}}

    def test_alexa_auth_skill_id_timestamp_and_linking(self):
        envelope = self.envelope()
        self.assertEqual(self.request("/api/alexa", "resident", envelope)[0], 401)
        self.assertEqual(self.request("/api/alexa", self.relay, envelope)[0], 200)
        envelope["context"]["System"]["application"]["applicationId"] = "wrong"
        self.assertEqual(self.request("/api/alexa", self.relay, envelope)[0], 403)
        envelope = self.envelope()
        envelope["request"]["timestamp"] = "2001-01-01T00:00:00Z"
        self.assertEqual(self.request("/api/alexa", self.relay, envelope)[0], 401)
        self.assertEqual(self.request("/api/alexa", self.relay, self.envelope("unknown"))[1]["response"]["card"]["type"], "LinkAccount")

    def test_simulator_rejects_guard_and_bad_session(self):
        self.assertEqual(self.request("/api/simulate", "guard", {"session_id":"s","intent":"LaunchRequest"})[0], 403)
        self.assertEqual(self.request("/api/simulate", "resident", {"intent":"LaunchRequest"})[0], 400)
