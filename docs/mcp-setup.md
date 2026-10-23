# Alexa+ experience through open MCP

The resident companion includes a real MCP client and server. This is a local
simulation of an Alexa+ experience, not a connection to a live Alexa+ device.
The classic Alexa Skills Kit Lambda adapter is a separate optional route.

## Start both servers

From this application's directory:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-mcp.lock
.venv/bin/python -m society_gate.server
```

In a second terminal, from the same directory:

```bash
.venv/bin/python -m society_gate.mcp_server
```

The dashboard is at `http://127.0.0.1:8091`. The MCP endpoint is
`http://127.0.0.1:8092/mcp`. Both use the same `.local/society.sqlite3` database.
Both accept `--data-dir`; use the same value for each. If changing dashboard
ports, supply its exact origin using MCP's `--web-origin` option. Open the
dashboard on `127.0.0.1` to match the default allowed origin.

Use the guard token in one tab to register an arrival. Use the resident token
in another tab, scroll to the Alexa+ panel, and click **Connect & discover
tools**. It sends `initialize`, `notifications/initialized`, and `tools/list`.
The panel displays the negotiated protocol and discovered tools. Click **Who
is at the gate?**, choose an arrival, prepare approval/denial, read the exact
confirmation, and explicitly confirm. The guard can then record entry.
Expand Protocol activity to inspect actual requests and responses; bearer
headers are never included in that display.

## Tools

- `list_waiting_visitors`: pending arrivals for the authenticated household.
- `prepare_visitor_decision`: bind one approved/denied choice to a request and
  issue a 60-second confirmation. This does not approve entry.
- `confirm_visitor_decision`: consume or cancel that resident-bound confirmation.
  Retrying returns the saved receipt without applying the decision twice.
- `get_visitor_receipt`: current state and actor-stamped audit trail for one visit.
- `list_trusted_visitor_rules`: rules and their validity windows for this flat.

Confirmations survive server reconstruction because they are stored in SQLite.
The transport is stateless; resident authority is checked on every request.
The agent/client must wait for the resident's explicit answer before invoking
the confirmation tool. A tool call alone cannot establish who physically spoke.

## Verify an actual HTTP session

With both servers running:

```bash
.venv/bin/python scripts/smoke_mcp.py
```

This creates a synthetic arrival, uses the official SDK client to initialize
and discover tools, prepares a choice, proves it is still pending, confirms it,
retries confirmation, records guard entry and exit, and checks the MCP receipt.
It writes a credential-free report to `.local/mcp-proof.json`.

Run all tests, including the HTTP MCP transport tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Integration limits

The official Python MCP SDK is pinned to 1.30.0. Protocol 2025-11-25 is supported
and tested; Streamable HTTP is implemented by the SDK. See the
[protocol transport specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
and [official SDK](https://github.com/modelcontextprotocol/python-sdk).

Static bearer tokens, restricted loopback origins, and host checks protect this
local demonstration. This does not provide production MCP OAuth discovery,
resident account enrollment, or a public deployment. Add a real OAuth resource
server, credential lifecycle, tenancy verification, HTTPS deployment, and a
shared-device confirmation policy before live use.

Alexa+ onboarding is currently partner-based; see
[Alexa+ for Builders](https://developer.amazon.com/alexaplus/). This build does
not claim private-preview access, certification, Amazon affiliation, autonomous
spoken alerts, or an existing society-vendor connection.

Desktop rendering, the guard/resident tab flow, and the protocol panel were
verified using native Chrome control on 2026-10-21. See [validation](validation.md).
Mobile rendering and physical-device integration have not been verified.
