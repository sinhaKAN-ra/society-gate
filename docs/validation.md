# Validation record

Verified 2026-10-20 with Python 3.13.3 and official MCP Python SDK 1.30.0.

- New application: **29 tests passed**, including six tests of the actual SDK's
  Streamable HTTP ASGI application. No MCP tests were skipped in this run.
- A separate live-socket check started both local servers and used the official
  MCP client. It negotiated **2025-11-25**, discovered all five tools, and
  completed pending → approved → checked in through the HTTP interfaces.
- Preparation left the arrival pending. Repeating confirmation returned the
  same receipt. The guard's movement appeared in the resident's MCP receipt.
- Both JavaScript files passed `node --check`.
- No external vendor, Echo, Alexa+ add-on, or AWS deployment was connected.
- Initial browser verification was unavailable on 2026-10-20. A follow-up on
  2026-10-21 used native Chrome control in a clean Incognito window and verified
  desktop rendering, separate guard/resident sessions, actual browser MCP
  negotiation, preparation, explicit confirmation, guard entry, and the receipt.
- The same browser run created a trusted rule, submitted a mock verified arrival,
  observed rule approval, revoked the rule, and observed the unused approval
  become denied. Eleven screenshots were captured as separate review evidence.
- Mobile layout, a physical Echo, and a production vendor connection remain
  outside the verified scope. The 29 application tests passed again on 2026-10-21.

Reproduce with the commands in [MCP setup](mcp-setup.md). The live check writes
its credential-free report to `.local/mcp-proof.json`. Local servers used for
verification were stopped afterward.
