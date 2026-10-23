"""Alexa envelopes and local simulator share the same durable conversation logic.

Only call handle after authenticating the resident and the transport. Session
attributes supplied by callers are never accepted as authorization to approve.
"""
import json
from .service import Problem, digest, text


def say(message, end=False, link=False):
    response = {"outputSpeech": {"type": "PlainText", "text": message}, "shouldEndSession": end}
    if not end:
        response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": "Say visitors, approve visitor, deny visitor, or stop."}}
    if link:
        response["card"] = {"type": "LinkAccount"}
    return {"version": "1.0", "response": response}


def handle(service, actor, envelope):
    service.require(actor, "resident")
    request = envelope.get("request", {})
    request_id = text(request.get("requestId"), "Alexa request ID", 300)
    session_id = text(envelope.get("session", {}).get("sessionId"), "Alexa session ID", 300)
    fingerprint = digest(json.dumps(envelope, sort_keys=True))
    with service.transaction() as db:
        service.expire(db)
        prior = db.execute("SELECT * FROM voice_replays WHERE id=? AND resident=?", (request_id, actor["id"])).fetchone()
        if prior:
            if prior["fingerprint"] != fingerprint:
                raise Problem("Alexa request ID was reused with different content.", 409)
            return json.loads(prior["response"])
        result = respond(service, db, actor, request, session_id)
        db.execute("INSERT INTO voice_replays VALUES (?,?,?,?)",
                   (request_id, actor["id"], fingerprint, json.dumps(result)))
        return result


def respond(service, db, actor, request, session_id):
    kind = request.get("type")
    if kind == "SessionEndedRequest":
        db.execute("DELETE FROM voice_sessions WHERE id=? AND resident=?", (session_id, actor["id"]))
        return {"version": "1.0", "response": {}}
    intent = request.get("intent", {}).get("name")
    if kind == "LaunchRequest" or intent == "PendingVisitorsIntent":
        visits = db.execute("""SELECT * FROM visits WHERE society=? AND unit=? AND status='pending'
          ORDER BY created,id""", (actor["society"], actor["unit"])).fetchall()
        db.execute("DELETE FROM voice_sessions WHERE id=? AND resident=?", (session_id, actor["id"]))
        if not visits:
            return say("There are no visitors waiting for your flat.", end=True)
        visit = visits[0]
        db.execute("INSERT INTO voice_sessions VALUES (?,?,?,?,?)",
                   (session_id, actor["id"], visit["id"], None, min(service.clock() + 90, visit["expires"])))
        return say(f"You have {len(visits)} visitor request(s). First, {visit['visitor']} is at the gate for {visit['purpose']}. Say approve visitor or deny visitor.")
    if intent in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
        db.execute("DELETE FROM voice_sessions WHERE id=? AND resident=?", (session_id, actor["id"]))
        return say("Goodbye. No further approval was made.", end=True)
    if intent in ("AMAZON.HelpIntent", "AMAZON.FallbackIntent"):
        return say("Say visitors to hear the first waiting visitor. Then say approve visitor or deny visitor and confirm your choice.")
    session = db.execute("SELECT * FROM voice_sessions WHERE id=? AND resident=? AND expires>?",
                         (session_id, actor["id"], service.clock())).fetchone()
    if not session:
        return say("Say visitors first so I can identify the exact request.")
    visit = service.scoped_visit(db, actor, session["visit"])
    if visit["status"] != "pending":
        db.execute("DELETE FROM voice_sessions WHERE id=? AND resident=?", (session_id, actor["id"]))
        return say(f"That visitor request is {visit['status']}. Say visitors to check again.")
    if intent in ("ApproveVisitorIntent", "DenyVisitorIntent"):
        action = "approved" if intent == "ApproveVisitorIntent" else "denied"
        db.execute("UPDATE voice_sessions SET action=? WHERE id=? AND resident=?", (action, session_id, actor["id"]))
        verb = "allow entry for" if action == "approved" else "deny entry for"
        return say(f"Confirm: {verb} {visit['visitor']} at {visit['unit']}? Say yes or no.")
    if intent == "AMAZON.NoIntent":
        db.execute("UPDATE voice_sessions SET action=NULL WHERE id=? AND resident=?", (session_id, actor["id"]))
        return say("Cancelled that choice. Say approve visitor, deny visitor, or stop.")
    if intent == "AMAZON.YesIntent" and session["action"]:
        service.decide_in_transaction(db, actor, visit["id"], session["action"])
        db.execute("DELETE FROM voice_sessions WHERE id=? AND resident=?", (session_id, actor["id"]))
        return say(f"Entry for {visit['visitor']} is {session['action']}. The guard dashboard has been updated.", end=True)
    return say("Say approve visitor or deny visitor before confirming.")
