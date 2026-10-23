# Society Gate

A separate, local prototype for extending Alexa from the home to the society gate.

For the **Alexa+ experience**, start the real Streamable HTTP MCP server and
use the browser's MCP panel: [setup and demo](docs/mcp-setup.md). It negotiates
protocol 2025-11-25, discovers five tools, and commits decisions only after a
resident-bound confirmation. The classic Alexa skill simulator below remains
available separately.

**Visitor arrives → guard records arrival → resident hears the request through
Alexa → resident confirms → guard receives the decision.** A resident can also
create a time-limited rule for a regular visitor with a verified vendor identity.

You said the society already has an app, but you do not have its API access.
This build therefore works as a **companion system**. It does not read, modify,
or synchronize that app. The integration endpoint and mock vendor account let
us develop and test the connection contract until the vendor provides access.

## Run locally

Python 3.11+; no installation, Docker, cloud account, or paid service needed
for the base companion. Run from this application's directory:

```bash
python3 -m society_gate.server
```

Open **http://127.0.0.1:8091**. In a second terminal, read the generated demo
credentials (keep these local):

```bash
cat .local/credentials.json
```

Paste the `guard` token into one browser tab and the `resident` token into
another. The resident is enrolled in A-101; `neighbour` is enrolled in B-202.
Tokens stay in the current browser tab's session storage until disconnect.
All visitors, audit entries, rules, and voice sessions persist in SQLite across
server restarts. `.local/` is ignored by Git.

For a second isolated demo, run `python3 -m society_gate.server --port 8092
--data-dir /tmp/society-gate-demo` as one command. The demo binds only to loopback.

## Try the full flow

1. Guard tab: register Rahul for A-101, purpose Delivery.
2. Resident tab: click **Open skill**, **Approve visitor**, then **Yes, confirm**.
   These buttons exercise the Alexa conversation handler without an Echo or
   microphone. The resident can also approve or deny directly on the dashboard.
3. Guard tab: the request updates to Approved within 3 seconds. Click
   **Record entry**, then **Record exit** when the visitor leaves.
4. Review the activity log. Every transition identifies its actor.

Unanswered requests expire after five minutes. An approval is valid for two
minutes. A timeout never grants entry. The guard still checks visitor identity
and physically manages entry; this project does not operate a gate motor.

## Try a regular-visitor rule

1. Resident tab: add a rule labelled Housekeeper for vendor ID
   `vendor:regular-001`, valid for one hour.
2. Open a third tab with the `integration` token. This is a **mock vendor**, not
   a connection to your existing app.
3. Submit an arrival for A-101 using that ID and check the mock identity-verified
   box. The resident's active rule approves the arrival automatically.
4. Repeat with an unverified identity or a different ID: it requires approval.
   A guard-entered name or reference never activates an automatic rule.
5. Revoke the rule from the resident tab: future arrivals need approval and any
   unused approval from that rule is withdrawn. Already recorded entries remain
   in the log.

Rules last at most 24 hours and apply only to the resident's flat. The mock
vendor's verified flag is a test assertion; a real adapter must derive it from
the vendor's documented identity verification, never visitor-supplied data.

## What is implemented

- Responsive guard/resident dashboard and mock vendor workspace.
- Persistent requests, rules, actor identities, audit records, and voice sessions.
- Flat-scoped decisions, explicit voice confirmation, expiration, and single-use entry.
- Transactional decisions and deduplication for vendor events and Alexa retries.
- Alexa request/response handler, en-IN interaction model, and Lambda relay code.
- Alexa+ web simulation using a real MCP client and server, with protocol trace.
- A generic authenticated inbound integration contract.
- Automated domain and HTTP tests, using Python's standard library.

## What still needs external setup

**A real Echo is not connected yet.** See [Alexa setup](docs/alexa-setup.md).
It requires an Amazon developer skill, an IAM-restricted Lambda trigger, a
deployed HTTPS backend, and OAuth account linking to enrolled residents. The
adapter accepts linked access tokens; this prototype does not implement a
production OAuth authorization server or account enrollment service.

Those steps are for the optional **classic Alexa custom skill**. The Alexa+
MCP simulation runs locally without preview access or a physical device; see
[MCP setup](docs/mcp-setup.md) for its separate integration limits.

**Your existing society app is not connected.** See the
[integration contract](docs/integration.md). We need vendor-supported inbound
arrival events, household mappings, stable verified visitor IDs, and an outbound
decision API. The fallback available today is the companion guard dashboard.

The local version does not send phone push alerts or unsolicited Alexa speech.
Residents open the skill or dashboard to see pending requests. Alexa proactive
events require opt-in and predefined event schemas; we have not established a
suitable visitor-approval notification type. See
[Amazon's proactive events documentation](https://developer.amazon.com/en-US/docs/alexa/smapi/proactive-events-api.html).

## Verification

```bash
python3 -m unittest discover -s tests -v
```

This suite tests the state machine, cross-flat authorization, pending/approval
timeouts, concurrent decisions, durable records, explicit voice confirmation,
session boundaries, replay handling, verified-ID rules, revocation, HTTP
authorization, and the Alexa relay boundary. It does not test a physical Echo,
Amazon certification, or a society vendor integration.

The code in this standalone project is MIT licensed. To export a source archive
without credentials or local state, run `python3 scripts/package_source.py`.

Read [the product assessment](docs/pivot-assessment.md) for the integration scope
and [the architecture decision](docs/adr-001-companion.md) for the application design.
