"""Local companion HTTP server. Real Alexa traffic enters through an IAM-gated Lambda relay."""
import argparse
from datetime import datetime
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse
import uuid

from .service import Problem, Service
from .voice import handle, say

WEB = Path(__file__).resolve().parent / "web"


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, service, skill_id="", relay_token="", **kwargs):
        self.service, self.skill_id, self.relay_token = service, skill_id, relay_token
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Do not log visitor details, bearer tokens, or request bodies.
        pass

    def send(self, status, payload, content_type="application/json"):
        data = json.dumps(payload).encode() if content_type == "application/json" else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' http://127.0.0.1:* http://localhost:*; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def route(self, post=False):
        try:
            host = urlparse("http://" + self.headers.get("Host", ""))
            if host.hostname not in ("localhost", "127.0.0.1", "[::1]", "::1"):
                raise Problem("Local server requires a loopback Host header.", 403)
            origin = self.headers.get("Origin")
            if origin and origin != f"http://{self.headers.get('Host')}":
                raise Problem("Cross-origin requests are not accepted.", 403)
            path = urlparse(self.path).path
            if not post and path in ("/", "/app.js", "/mcp-client.js", "/style.css"):
                file = WEB / ({"/": "index.html"}.get(path, path[1:]))
                mime = {".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css"}[file.suffix]
                self.send(200, file.read_bytes(), mime)
                return
            if not post and path == "/health":
                self.send(200, {"status": "ok", "mode": "local-companion", "vendor_connected": False})
                return
            body = {}
            if post:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise Problem("Send application/json.", 415)
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise Problem("Invalid request length.")
                if not 0 < size <= 32768:
                    raise Problem("Request body must be 1–32768 bytes.", 413)
                try:
                    body = json.loads(self.rfile.read(size))
                except (ValueError, UnicodeDecodeError):
                    raise Problem("Invalid JSON.")
                if not isinstance(body, dict):
                    raise Problem("Send a JSON object.")
            header = self.headers.get("Authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            if post and path == "/api/alexa":
                result = self.alexa(token, body)
            else:
                actor = self.service.authenticate(token)
                if not post and path == "/api/state":
                    result = self.service.snapshot(actor)
                elif post and path == "/api/visitors":
                    self.service.require(actor, "guard")
                    result = self.service.create_visit(actor, body)
                elif post and path == "/api/integrations/visitors":
                    self.service.require(actor, "integration")
                    result = self.service.create_visit(actor, body)
                elif post and path == "/api/decision":
                    result = self.service.decide(actor, text_id(body), body.get("decision"))
                elif post and path == "/api/movement":
                    result = self.service.move(actor, text_id(body), body.get("action"))
                elif post and path == "/api/rules":
                    result = self.service.create_rule(actor, body)
                elif post and path == "/api/rules/revoke":
                    result = self.service.revoke_rule(actor, text_id(body))
                elif post and path == "/api/simulate":
                    self.service.require(actor, "resident")
                    allowed = {"LaunchRequest", "PendingVisitorsIntent", "ApproveVisitorIntent", "DenyVisitorIntent",
                               "AMAZON.YesIntent", "AMAZON.NoIntent", "AMAZON.StopIntent", "AMAZON.HelpIntent"}
                    intent = body.get("intent")
                    if intent not in allowed:
                        raise Problem("Unknown simulator action.")
                    session_id = body.get("session_id")
                    if not isinstance(session_id, str) or not 1 <= len(session_id) <= 300:
                        raise Problem("A simulator session ID is required.")
                    request = {"requestId": str(uuid.uuid4()), "type": "LaunchRequest" if intent == "LaunchRequest" else "IntentRequest"}
                    if intent != "LaunchRequest":
                        request["intent"] = {"name": intent}
                    result = handle(self.service, actor, {"request": request, "session": {"sessionId": session_id}})
                else:
                    raise Problem("Route was not found.", 404)
            self.send(200, result)
        except Problem as exc:
            self.send(exc.status, {"error": str(exc)})
        except (TypeError, KeyError, AttributeError, ValueError):
            self.send(400, {"error": "Malformed request."})

    def alexa(self, token, envelope):
        if not self.skill_id or len(self.relay_token) < 32:
            raise Problem("Alexa relay is not configured.", 503)
        if not secrets.compare_digest(token, self.relay_token):
            raise Problem("Alexa relay authentication failed.", 401)
        system = envelope.get("context", {}).get("System", {})
        if system.get("application", {}).get("applicationId") != self.skill_id:
            raise Problem("Alexa skill ID does not match.", 403)
        try:
            timestamp = datetime.fromisoformat(envelope["request"]["timestamp"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None or abs(self.service.clock() - timestamp.timestamp()) > 150:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise Problem("Alexa request timestamp is invalid or stale.", 401)
        try:
            actor = self.service.authenticate(system.get("user", {}).get("accessToken"))
        except Problem:
            return say("Link your Society Gate resident account in the Alexa app first.", end=True, link=True)
        return handle(self.service, actor, envelope)

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route(post=True)


def text_id(body):
    value = body.get("id")
    if not isinstance(value, str) or not 1 <= len(value) <= 100:
        raise Problem("A valid record ID is required.")
    return value


def make_server(service, port=8091, skill_id="", relay_token=""):
    return ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, service=service, skill_id=skill_id, relay_token=relay_token))


def main():
    parser = argparse.ArgumentParser(description="Run the local Society Gate companion demo")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / ".local")
    args = parser.parse_args()
    service = Service(args.data_dir / "society.sqlite3")
    service.seed()
    server = make_server(service, args.port, os.getenv("ALEXA_SKILL_ID", ""), os.getenv("ALEXA_RELAY_TOKEN", ""))
    print(f"Society Gate local demo: http://127.0.0.1:{server.server_port}", flush=True)
    print("Demo credentials are in " + str(args.data_dir / "credentials.json"), flush=True)
    print("Copy the appropriate token into the dashboard. These are local demo accounts.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
