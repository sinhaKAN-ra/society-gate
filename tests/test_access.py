import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from society_gate.service import Problem, Service
from society_gate.voice import handle


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000000.0
        self.service = Service(Path(self.temp.name) / "test.sqlite3", lambda: self.now)
        self.tokens = self.service.seed()
        self.actors = {name: self.service.authenticate(token) for name, token in self.tokens.items()}

    def visit(self, unit="A-101", **extra):
        return self.service.create_visit(self.actors["guard"], {"visitor": "Rahul", "unit": unit, "purpose": "Delivery", **extra})

    def voice(self, intent, session="session-1", request_id=None, **extra):
        request = {"requestId": request_id or str(uuid.uuid4()), "type": "LaunchRequest" if intent == "launch" else "IntentRequest"}
        if intent != "launch":
            request["intent"] = {"name": intent}
        return handle(self.service, self.actors["resident"], {"request": request, "session": {"sessionId": session}, **extra})

    def status(self, visit):
        return next(v for v in self.service.snapshot(self.actors["guard"])["visits"] if v["id"] == visit["id"])["status"]

    def test_end_to_end_approval_entry_exit_persists(self):
        visit = self.visit()
        self.service.decide(self.actors["resident"], visit["id"], "approved")
        self.service.move(self.actors["guard"], visit["id"], "check-in")
        self.service.move(self.actors["guard"], visit["id"], "check-out")
        reopened = Service(self.service.path, lambda: self.now)
        self.assertEqual(reopened.snapshot(self.actors["resident"])["visits"][0]["status"], "checked_out")
        self.assertEqual([e["event"] for e in reopened.snapshot(self.actors["guard"])["audit"]][::-1], ["requested", "approved", "checked_in", "checked_out"])

    def test_flat_scope_for_read_and_write(self):
        visit = self.visit("B-202")
        self.assertEqual(self.service.snapshot(self.actors["resident"])["visits"], [])
        with self.assertRaises(Problem) as error:
            self.service.decide(self.actors["resident"], visit["id"], "approved")
        self.assertEqual(error.exception.status, 404)

    def test_guard_cannot_approve_and_resident_cannot_record_entry(self):
        visit = self.visit()
        with self.assertRaises(Problem): self.service.decide(self.actors["guard"], visit["id"], "approved")
        with self.assertRaises(Problem): self.service.move(self.actors["resident"], visit["id"], "check-in")
        with self.assertRaises(Problem): self.service.move(self.actors["guard"], visit["id"], "check-in")

    def test_denial_blocks_entry(self):
        visit = self.visit()
        self.service.decide(self.actors["resident"], visit["id"], "denied")
        with self.assertRaises(Problem): self.service.move(self.actors["guard"], visit["id"], "check-in")

    def test_request_timeout_never_approves(self):
        visit = self.visit()
        self.now += 300
        with self.assertRaises(Problem): self.service.decide(self.actors["resident"], visit["id"], "approved")
        self.assertEqual(self.status(visit), "expired")

    def test_approved_pass_expires_and_cannot_be_reused(self):
        visit = self.visit()
        self.service.decide(self.actors["resident"], visit["id"], "approved")
        self.now += 120
        with self.assertRaises(Problem): self.service.move(self.actors["guard"], visit["id"], "check-in")
        self.assertEqual(self.status(visit), "expired")

    def test_voice_requires_selection_and_explicit_confirmation(self):
        visit = self.visit()
        self.voice("AMAZON.YesIntent", sessionAttributes={"visit": visit["id"], "action": "approved"})
        self.assertEqual(self.status(visit), "pending")
        self.voice("launch")
        self.voice("ApproveVisitorIntent")
        self.assertEqual(self.status(visit), "pending")
        self.voice("AMAZON.YesIntent")
        self.assertEqual(self.status(visit), "approved")

    def test_voice_does_not_switch_to_new_arrival(self):
        first = self.visit()
        self.voice("launch")
        second = self.visit()
        self.voice("DenyVisitorIntent")
        self.voice("AMAZON.YesIntent")
        self.assertEqual(self.status(first), "denied")
        self.assertEqual(self.status(second), "pending")

    def test_voice_confirmation_is_bound_to_session_and_expires(self):
        visit = self.visit()
        self.voice("launch")
        self.voice("ApproveVisitorIntent")
        self.voice("AMAZON.YesIntent", session="other-session")
        self.assertEqual(self.status(visit), "pending")
        self.now += 90
        self.voice("AMAZON.YesIntent")
        self.assertEqual(self.status(visit), "pending")

    def test_voice_no_cancels_choice(self):
        visit = self.visit()
        self.voice("launch")
        self.voice("ApproveVisitorIntent")
        self.voice("AMAZON.NoIntent")
        self.voice("AMAZON.YesIntent")
        self.assertEqual(self.status(visit), "pending")

    def test_alexa_retry_is_idempotent_and_changed_replay_rejected(self):
        visit = self.visit()
        self.voice("launch")
        self.voice("ApproveVisitorIntent")
        first = self.voice("AMAZON.YesIntent", request_id="repeated")
        self.assertEqual(first, self.voice("AMAZON.YesIntent", request_id="repeated"))
        with self.assertRaises(Problem): self.voice("DenyVisitorIntent", request_id="repeated")
        self.assertEqual(sum(e["event"] == "approved" for e in self.service.snapshot(self.actors["guard"])["audit"]), 1)

    def test_two_concurrent_decisions_only_one_wins(self):
        visit = self.visit()
        def decide(decision):
            try:
                self.service.decide(self.actors["resident"], visit["id"], decision)
                return True
            except Problem:
                return False
        with concurrent.futures.ThreadPoolExecutor() as pool:
            results = list(pool.map(decide, ["approved", "denied"]))
        self.assertEqual(sum(results), 1)

    def rule(self, **extra):
        return self.service.create_rule(self.actors["resident"], {"visitor_ref": "vendor:42", "label": "Housekeeper", "hours": 1, **extra})

    def vendor(self, **extra):
        return self.service.create_visit(self.actors["integration"], {"unit":"A-101", "visitor":"Rahul", "purpose":"Housekeeping", "external_id":str(uuid.uuid4()), "visitor_ref":"vendor:42", "identity_verified":True, **extra})

    def test_rule_only_matches_verified_vendor_identity(self):
        rule = self.rule()
        self.assertEqual(self.visit(visitor_ref="vendor:42", identity_verified=True)["status"], "pending")
        self.assertEqual(self.vendor(identity_verified=False)["status"], "pending")
        self.assertEqual(self.vendor(visitor_ref="vendor:wrong")["status"], "pending")
        self.assertEqual(self.vendor(unit="B-202")["status"], "pending")
        approved = self.vendor()
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["rule_id"], rule["id"])

    def test_rule_expiry_and_revocation_withdraw_unused_approvals(self):
        rule = self.rule()
        visit = self.vendor()
        self.service.revoke_rule(self.actors["resident"], rule["id"])
        self.assertEqual(self.status(visit), "denied")
        self.assertEqual(self.vendor()["status"], "pending")
        self.rule()
        self.now += 3600
        self.assertEqual(self.vendor()["status"], "pending")

    def test_rule_cannot_outlive_window_or_be_revoked_by_neighbour(self):
        rule = self.rule(hours=0.01)
        self.assertEqual(self.vendor()["expires"], rule["ends"])
        with self.assertRaises(Problem): self.service.revoke_rule(self.actors["neighbour"], rule["id"])
        with self.assertRaises(Problem): self.rule(hours=25)

    def test_vendor_delivery_is_idempotent(self):
        first = self.vendor(external_id="stable-id")
        self.assertEqual(first["id"], self.vendor(external_id="stable-id")["id"])
        with self.assertRaises(Problem): self.vendor(external_id="stable-id", visitor="Someone else")

    def test_unknown_flat_and_invalid_tokens(self):
        with self.assertRaises(Problem): self.visit("C-303")
        with self.assertRaises(Problem): self.service.authenticate("fake")
        self.assertEqual(self.service.seed(), self.tokens)
