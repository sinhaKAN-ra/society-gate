"""Deploy only behind an Alexa Skills Kit Lambda trigger with skill ID verification.

No public Lambda Function URL. Never expose the local simulator as an Alexa endpoint.
The society backend performs resident authorization and transaction handling.
"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect must not forward the relay bearer credential elsewhere.
        return None


def lambda_handler(event, context):
    skill_id = os.environ["ALEXA_SKILL_ID"]
    origin = os.environ["SOCIETY_API_ORIGIN"]
    relay_token = os.environ["ALEXA_RELAY_TOKEN"]
    parsed = urlparse(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/") or len(relay_token) < 32):
        raise ValueError("Configure an HTTPS society API origin and a strong relay credential.")
    if event.get("context", {}).get("System", {}).get("application", {}).get("applicationId") != skill_id:
        raise ValueError("Unexpected Alexa skill ID.")
    request = Request(origin.rstrip("/") + "/api/alexa", data=json.dumps(event).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + relay_token}, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=5) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError):
        return {"version": "1.0", "response": {"outputSpeech": {"type": "PlainText", "text":
            "I could not confirm the result with your society. Please check the resident companion or contact the guard before retrying."}, "shouldEndSession": True}}
