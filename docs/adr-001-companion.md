# ADR 001 — Build the society companion as a separate application

Status: accepted for the local prototype, 2026-10-20.

The original Ganas graph measures evidence of operational knowledge. The new
product controls visitor approval for enrolled households. These have different
entities, authorities, data sources, and transaction requirements. The user
explicitly requested a separate folder, an existing-app connection, and support
for resident-configured regular-visitor rules; vendor API access is unavailable.

Keep all new code under `society-alexa/`. Preserve the Ganas graph schema and
engines. Use a dependency-free Python application and SQLite for the local
companion. The local HTTP server binds to loopback and is a development server.
The guard dashboard is the working fallback until a supported vendor integration
is available. Do not invent vendor API endpoints or scrape app credentials.

Build Alexa as an adapter to the same resident-authorized service. Use an Alexa
Skills Kit Lambda trigger with skill ID verification as the real ingress design.
The local simulator is separately named and requires a resident credential.
Keep a relay credential separate from guard/resident/vendor tokens. A production
deployment must provide OAuth account linking and a proper HTTPS server.

Only a resident decision or an active resident-configured rule can authorize a
visitor. A rule requires a verified vendor identity, never a name match. Rules
are flat-scoped and time-bounded. Expiry and missing information leave entry
unapproved. No LLM or vector search is needed for this authorization workflow.

This introduces a second application with its own tests and documentation. It
does not change the meaning of `graph_core`, `risk_engine`, or `mcp_surface`.
