"""Transactional visitor approvals. No dependency on the Ganas graph engines."""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import time
import uuid


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def text(value, label, limit=100):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise Problem(f"{label} must contain 1–{limit} characters.")
    if any(ord(c) < 32 for c in value):
        raise Problem(f"{label} contains control characters.")
    return value.strip()


class Service:
    def __init__(self, path, clock=time.time):
        self.path, self.clock = str(path), clock
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS actors (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
              society TEXT NOT NULL, unit TEXT, token_hash TEXT UNIQUE NOT NULL);
            CREATE TABLE IF NOT EXISTS visits (
              id TEXT PRIMARY KEY, society TEXT NOT NULL, unit TEXT NOT NULL,
              visitor TEXT NOT NULL, purpose TEXT NOT NULL, visitor_ref TEXT,
              source TEXT NOT NULL, external_id TEXT, status TEXT NOT NULL,
              created REAL NOT NULL, expires REAL NOT NULL, decided_by TEXT,
              rule_id TEXT, UNIQUE(society, source, external_id));
            CREATE TABLE IF NOT EXISTS rules (
              id TEXT PRIMARY KEY, society TEXT NOT NULL, unit TEXT NOT NULL,
              resident TEXT NOT NULL, visitor_ref TEXT NOT NULL, label TEXT NOT NULL,
              starts REAL NOT NULL, ends REAL NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, visit TEXT NOT NULL,
              at REAL NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS voice_sessions (
              id TEXT NOT NULL, resident TEXT NOT NULL, visit TEXT NOT NULL,
              action TEXT, expires REAL NOT NULL, PRIMARY KEY(id, resident));
            CREATE TABLE IF NOT EXISTS voice_replays (
              id TEXT NOT NULL, resident TEXT NOT NULL, fingerprint TEXT NOT NULL,
              response TEXT NOT NULL, PRIMARY KEY(id, resident));
            CREATE TABLE IF NOT EXISTS confirmations (
              id TEXT PRIMARY KEY, resident TEXT NOT NULL, kind TEXT NOT NULL,
              payload TEXT NOT NULL, expires REAL NOT NULL, used INTEGER NOT NULL,
              result TEXT);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def seed(self):
        """Create demo credentials once; retain tokens outside source control."""
        credentials_path = Path(self.path).parent / "credentials.json"
        if credentials_path.exists():
            return json.loads(credentials_path.read_text())
        specs = [("guard", "Main gate", "guard", None),
                 ("resident", "Ananya · A-101", "resident", "A-101"),
                 ("neighbour", "Kabir · B-202", "resident", "B-202"),
                 ("integration", "Mock society vendor", "integration", None)]
        credentials = {}
        with self.transaction() as db:
            if db.execute("SELECT COUNT(*) FROM actors").fetchone()[0]:
                raise RuntimeError("Demo actors exist but credentials are missing. Use a fresh demo data directory.")
            for actor_id, name, role, unit in specs:
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO actors VALUES (?,?,?,?,?,?)",
                           (actor_id, name, role, "demo-society", unit, digest(token)))
                credentials[actor_id] = token
        credentials_path.touch(mode=0o600)
        credentials_path.write_text(json.dumps(credentials, indent=2))
        return credentials

    def authenticate(self, token):
        if not isinstance(token, str) or not token:
            raise Problem("Enter a valid access token.", 401)
        with closing(self.connect()) as db:
            actor = db.execute("SELECT * FROM actors WHERE token_hash=?", (digest(token),)).fetchone()
        if not actor:
            raise Problem("Access token is invalid.", 401)
        return {k: actor[k] for k in actor.keys() if k != "token_hash"}

    @staticmethod
    def require(actor, *roles):
        if actor["role"] not in roles:
            raise Problem("This account cannot perform that action.", 403)

    def record(self, db, visit, actor, event, detail=""):
        db.execute("INSERT INTO audit(visit,at,actor,event,detail) VALUES (?,?,?,?,?)",
                   (visit, self.clock(), actor, event, detail))

    def expire(self, db):
        rows = db.execute("SELECT id FROM visits WHERE status IN ('pending','approved') AND expires<=?",
                          (self.clock(),)).fetchall()
        for row in rows:
            db.execute("UPDATE visits SET status='expired' WHERE id=?", (row["id"],))
            self.record(db, row["id"], "system", "expired")

    def scoped_visit(self, db, actor, visit_id):
        row = db.execute("SELECT * FROM visits WHERE id=? AND society=?",
                         (visit_id, actor["society"])).fetchone()
        if not row or (actor["role"] == "resident" and row["unit"] != actor["unit"]):
            raise Problem("Visitor request was not found.", 404)
        return dict(row)

    def snapshot(self, actor):
        with self.transaction() as db:
            self.expire(db)
            params = [actor["society"]]
            clause = "society=?"
            if actor["role"] == "resident":
                clause += " AND unit=?"
                params.append(actor["unit"])
            visits = [dict(r) for r in db.execute(f"SELECT * FROM visits WHERE {clause} ORDER BY created DESC", params)]
            rules = [dict(r) for r in db.execute(f"SELECT * FROM rules WHERE {clause} ORDER BY ends DESC", params)]
            audit = [dict(r) for r in db.execute(
                f"SELECT a.* FROM audit a JOIN visits v ON a.visit=v.id WHERE v.{clause} ORDER BY a.seq DESC LIMIT 100", params)]
            return {"actor": actor, "visits": visits, "rules": rules, "audit": audit,
                    "units": ["A-101", "B-202"], "now": self.clock()}

    def create_visit(self, actor, body):
        self.require(actor, "guard", "integration")
        unit = text(body.get("unit"), "Flat")
        visitor = text(body.get("visitor"), "Visitor name")
        purpose = text(body.get("purpose"), "Purpose", 200)
        source = "vendor" if actor["role"] == "integration" else "guard"
        external_id = text(body.get("external_id"), "External event ID") if source == "vendor" else None
        visitor_ref = text(body["visitor_ref"], "Visitor reference") if body.get("visitor_ref") else None
        verified = source == "vendor" and body.get("identity_verified") is True and visitor_ref
        with self.transaction() as db:
            self.expire(db)
            if not db.execute("SELECT 1 FROM actors WHERE society=? AND unit=? AND role='resident'",
                              (actor["society"], unit)).fetchone():
                raise Problem("This flat has no enrolled resident.")
            if external_id:
                prior = db.execute("SELECT * FROM visits WHERE society=? AND source=? AND external_id=?",
                                   (actor["society"], source, external_id)).fetchone()
                if prior:
                    if (prior["unit"], prior["visitor"], prior["purpose"], prior["visitor_ref"]) != (unit, visitor, purpose, visitor_ref):
                        raise Problem("External event ID already belongs to a different request.", 409)
                    return dict(prior)
            now = self.clock()
            rule = None
            if verified:
                rule = db.execute("""SELECT * FROM rules WHERE society=? AND unit=? AND visitor_ref=?
                  AND active=1 AND starts<=? AND ends>? ORDER BY ends,id LIMIT 1""",
                                  (actor["society"], unit, visitor_ref, now, now)).fetchone()
            visit_id = str(uuid.uuid4())
            db.execute("INSERT INTO visits VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (visit_id, actor["society"], unit, visitor, purpose, visitor_ref, source,
                        external_id, "approved" if rule else "pending", now,
                        min(now + 120, rule["ends"]) if rule else now + 300,
                        rule["resident"] if rule else None, rule["id"] if rule else None))
            self.record(db, visit_id, actor["id"], "requested", f"source={source}")
            if rule:
                self.record(db, visit_id, rule["resident"], "approved_by_rule", rule["id"])
            return self.scoped_visit(db, actor, visit_id)

    def decide_in_transaction(self, db, actor, visit_id, decision):
        self.require(actor, "resident")
        if decision not in ("approved", "denied"):
            raise Problem("Choose approved or denied.")
        visit = self.scoped_visit(db, actor, visit_id)
        if visit["status"] != "pending" or visit["expires"] <= self.clock():
            raise Problem(f"This request is already {visit['status']}.", 409)
        db.execute("UPDATE visits SET status=?,decided_by=?,expires=? WHERE id=?",
                   (decision, actor["id"], self.clock() + 120, visit_id))
        self.record(db, visit_id, actor["id"], decision)
        return self.scoped_visit(db, actor, visit_id)

    def decide(self, actor, visit_id, decision):
        # Commit expiration even if a subsequent decision is rejected.
        with self.transaction() as db:
            self.expire(db)
        with self.transaction() as db:
            return self.decide_in_transaction(db, actor, visit_id, decision)

    def move(self, actor, visit_id, action):
        self.require(actor, "guard")
        if action not in ("check-in", "check-out"):
            raise Problem("Unknown entry action.")
        with self.transaction() as db:
            self.expire(db)
        with self.transaction() as db:
            visit = self.scoped_visit(db, actor, visit_id)
            expected, target = ("approved", "checked_in") if action == "check-in" else ("checked_in", "checked_out")
            if visit["status"] != expected or (action == "check-in" and visit["expires"] <= self.clock()):
                raise Problem("Entry requires a current approval; exit requires a recorded entry.", 409)
            db.execute("UPDATE visits SET status=? WHERE id=?", (target, visit_id))
            self.record(db, visit_id, actor["id"], target)
            return self.scoped_visit(db, actor, visit_id)

    def create_rule(self, actor, body):
        self.require(actor, "resident")
        ref = text(body.get("visitor_ref"), "Verified vendor visitor ID")
        label = text(body.get("label"), "Rule label")
        hours = body.get("hours", 1)
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not 0 < hours <= 24:
            raise Problem("A rule may last from more than zero to 24 hours.")
        with self.transaction() as db:
            rule_id, now = str(uuid.uuid4()), self.clock()
            db.execute("INSERT INTO rules VALUES (?,?,?,?,?,?,?,?,1)",
                       (rule_id, actor["society"], actor["unit"], actor["id"], ref, label, now, now + hours * 3600))
            return dict(db.execute("SELECT * FROM rules WHERE id=?", (rule_id,)).fetchone())

    def revoke_rule(self, actor, rule_id):
        self.require(actor, "resident")
        with self.transaction() as db:
            changed = db.execute("UPDATE rules SET active=0 WHERE id=? AND resident=? AND society=?",
                                 (rule_id, actor["id"], actor["society"])).rowcount
            if not changed:
                raise Problem("Rule was not found.", 404)
            # Withdraw unconsumed passes created by this rule too.
            rows = db.execute("SELECT id FROM visits WHERE rule_id=? AND status='approved'", (rule_id,)).fetchall()
            for row in rows:
                db.execute("UPDATE visits SET status='denied' WHERE id=?", (row["id"],))
                self.record(db, row["id"], actor["id"], "rule_revoked", rule_id)
        return {"revoked": rule_id}

    def prepare_decision(self, actor, visit_id, decision):
        self.require(actor, "resident")
        if decision not in ("approved", "denied"):
            raise Problem("Choose approved or denied.")
        with self.transaction() as db:
            self.expire(db)
            visit = self.scoped_visit(db, actor, visit_id)
            if visit["status"] != "pending":
                raise Problem(f"This request is already {visit['status']}.", 409)
            confirmation = secrets.token_urlsafe(32)
            expires = min(self.clock() + 60, visit["expires"])
            db.execute("INSERT INTO confirmations VALUES (?,?,?,?,?,0,NULL)",
                       (digest(confirmation), actor["id"], "decision", json.dumps({"id": visit_id, "decision": decision}), expires))
            verb = "allow entry for" if decision == "approved" else "deny entry for"
            return {"confirmation_id": confirmation, "expires": expires, "visit_id": visit_id,
                    "confirmation_prompt": f"Do you want to {verb} {visit['visitor']} visiting {visit['unit']} for {visit['purpose']}?",
                    "requires_resident_confirmation": True, "status": "awaiting_confirmation"}

    def confirm_decision(self, actor, confirmation_id, confirmed):
        self.require(actor, "resident")
        if type(confirmed) is not bool:
            raise Problem("An explicit boolean confirmation is required.")
        with self.transaction() as db:
            self.expire(db)
            row = db.execute("SELECT * FROM confirmations WHERE id=? AND resident=?",
                             (digest(text(confirmation_id, "Confirmation ID", 300)), actor["id"])).fetchone()
            if not row:
                raise Problem("Confirmation was not found for this resident.", 404)
            if row["used"]:
                return json.loads(row["result"])
            if row["expires"] <= self.clock():
                raise Problem("Confirmation has expired. Review the visitor again.", 409)
            payload = json.loads(row["payload"])
            if confirmed:
                visit = self.decide_in_transaction(db, actor, payload["id"], payload["decision"])
                result = {"status": visit["status"], "visit_id": visit["id"], "visitor": visit["visitor"],
                          "unit": visit["unit"], "expires": visit["expires"], "guard_delivery": "companion_dashboard",
                          "vendor_delivery": "not_connected"}
            else:
                result = {"status": "cancelled", "visit_id": payload["id"]}
            db.execute("UPDATE confirmations SET used=1,result=? WHERE id=?", (json.dumps(result), row["id"]))
            return result
