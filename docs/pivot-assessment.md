# From organization knowledge health to a society access companion

## The new product

The resident's Alexa becomes another interface to the society's visitor workflow.
The home account is linked to an enrolled household. The guard creates an arrival
request, the resident approves or denies that exact visitor, and the decision
returns to the guard. Resident rules can authorize a known regular visitor during
a bounded time window. Alexa conveys a resident's authority; an LLM does not
guess whether an unfamiliar person should enter.

The user confirmed that an existing society app is in use, no vendor API access
is available, and regular-visitor rules are wanted. Therefore the immediate
deliverable is a local companion with an integration boundary, rather than a
claim that the vendor app is connected.

## What the existing repository actually contains

The original suite was run before building this project: **29 tests passed**.
There is already a Git baseline, despite the older onboarding notes saying
initialization is still needed. Existing working-tree changes in AGENTS.md,
docs/16-product-vision-unified.md, and uv.lock were left as they were.

Ganas has an abstract graph interface, a working in-memory backend, a FalkorDB
skeleton, typed evidence/freshness logic, coverage and counterfactual risk,
centrality, successor ranking, explanations, action planning, organizational
diagnostics, team health, and an MCP surface. It runs deterministic reasoning
over seeded software-organization fixtures.

The canonical vision also describes artifact ingestion and durable side
discussions, neither fully implemented. There was no society household model,
guard application, visitor lifecycle, Alexa skill, OAuth account linking, or
vendor visitor-management connector in the existing build.

## What carries forward

The useful design principles are explicit authority, provenance, freshness,
separation between an interface and its storage backend, and deterministic gates
when information is missing. This project implements those principles with an
audit log, scoped actor permissions, expiring approvals, and a confirmed workflow.

The graph engines themselves do not need to be dependencies of entry approval.
PageRank, operator coverage, and simulated employee absence answer different
questions. Reinterpreting an employee's verified operational capability as a
resident's permission to admit a visitor would change the meaning of the
canonical graph. No existing core component is modified or imported here.

## Changes required for the pivot

The primary entities become society, household, enrolled resident, on-duty guard,
visitor, arrival request, decision, trusted-visitor rule, and audit event. The
main computation becomes a transactional lifecycle rather than graph traversal:
pending → approved or denied; approved → checked in → checked out. Pending and
unconsumed approvals can expire. All decisions are scoped to the correct society
and household.

The new interfaces are a guard desk, resident companion, Alexa custom skill,
and vendor adapter. SQLite replaces graph storage for the local prototype.
An authenticated vendor event is deduplicated by its external ID. Automatic
approval requires a stable, verified vendor identity matched to a resident's rule.

The Alexa conversation selects a specific pending request, asks for a decision,
then asks for confirmation. Server-side session state binds the answer to that
request, resident, and session for at most 90 seconds. A casual yes, a new
session, or caller-supplied session attributes cannot select a visitor.

## Milestones after this prototype

1. Validate the companion workflow with society management and guards. Establish
   which app is used and request a supported integration agreement or test API.
2. Add resident enrollment, tenancy verification, guard shift administration,
   credential rotation/revocation, and an OAuth provider for account linking.
3. Deploy a maintained HTTPS application server and IAM-restricted Alexa Lambda,
   then test an actual Echo and en-IN utterances. Check household/shared-device
   authorization and add a suitable extra confirmation method before live use.
4. Implement the vendor-specific inbound and outbound adapters with retryable
   delivery and reconciliation. Confirm how the vendor verifies visitor IDs.
5. Add an agreed notification channel, such as the companion phone app, and
   evaluate Alexa's supported notification mechanisms for the chosen experience.
6. Before a real rollout, add backups, retention/deletion, rate limiting,
   monitoring, account lifecycle management, and a documented offline guard flow.

These are deployment tasks, not features claimed by the local demo. A resident
voice response on a shared Echo is not proof of the speaker's personal identity.
