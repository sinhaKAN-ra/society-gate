# Society access companion — product and integration scope

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

## Application model

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
