# Society app integration boundary

There is **no active vendor connection**. No app name or API documentation was
provided, and the user does not have API access. The following is our companion
contract, not a claim that an existing vendor implements these endpoints.

## Inbound arrival

`POST /api/integrations/visitors` accepts JSON and a bearer token for an actor with
the integration role. The credential maps to one society on the server; callers
cannot select another society in the body.

```json
{
  "external_id": "vendor-arrival-0001",
  "unit": "A-101",
  "visitor": "Rahul",
  "purpose": "Housekeeping",
  "visitor_ref": "vendor:regular-001",
  "identity_verified": true
}
```

The external ID identifies one arrival, not a person. Retrying the same event
returns the existing request. Reusing its ID with different visitor details is
rejected. The visitor reference identifies the regular person in the vendor's
namespace. The identity-verified assertion is trusted only from the configured
integration adapter; a guard's manual request never qualifies for a rule.

In the prototype, the integration account is a mock event source. A real adapter
must validate the vendor's webhook authentication, map vendor households to
enrolled flats, normalize timestamps and identity assertions, and authenticate
to this service. The UI checkbox is only a simulation of that evidence.

## Outbound decision

Today, the guard dashboard polls `GET /api/state` with a guard token and receives
the current request status. No decision is written into the existing society app.
The resident companion and Alexa handler both write into the same SQLite service.

After vendor access is granted, add a delivery outbox in the same database
transaction as each decision. A worker should deliver a signed, idempotent
vendor-specific decision, retry failures, and record acknowledgement. A guard
must see when delivery is still pending. Do not represent a local approval as
vendor-delivered until the vendor has acknowledged it. Handle expiry/revocation
and entry reconciliation in that contract too.

## Available companion endpoints

- `GET /api/state`: actor-scoped visitor, rule, and audit snapshot.
- `POST /api/visitors`: guard registers `{unit, visitor, purpose}`.
- `POST /api/decision`: resident submits `{id, decision: "approved"|"denied"}`.
- `POST /api/movement`: guard submits `{id, action: "check-in"|"check-out"}`.
- `POST /api/rules`: resident submits `{label, visitor_ref, hours}`.
- `POST /api/rules/revoke`: resident submits `{id}`.
- `POST /api/simulate`: resident-only local Alexa conversation simulator.
- `POST /api/alexa`: configured Lambda relay only; additionally requires the
  account-linked resident token inside the Alexa envelope.

All data endpoints require authentication. The local UI and `/health` are public
only on loopback. Credentials, sessions, and prototype snapshots are not an
account-enrollment or production tenancy-management implementation.
