# Developer friction

## 2026-10-20 — Alexa+ device onboarding is gated

- Area: Alexa+ add-on setup and preview access.
- Task: determine how a self-hosted society service connects to an Echo.
- Expected: a generally available developer enrollment and device test path.
- Observed: the published developer-access FAQ says the add-on tooling and web
  simulator are limited to selected partners. A classic custom skill is a
  separate integration route and does not establish Alexa+ add-on access.
- Severity: high for real-device validation.
- Planned workaround: implement open-standard MCP over Streamable HTTP, then
  demonstrate it through a web client that sends real protocol messages.
- Suggestion: put preview eligibility and a working open-standard alternative
  next to every gated add-on setup guide.
- Reference: https://developer.amazon.com/alexaplus/

## 2026-10-20 — Browser preview unavailable in this environment

- Area: local browser verification.
- Task: open the local companion dashboard in the available browser tool.
- Expected: a controllable browser tab for visual and interactive QA.
- Observed: the in-app browser was unavailable; browser inventory was empty.
- Severity: medium.
- Workaround: validate HTTP flows and JavaScript syntax here; document that
  rendered layout and browser interactions still need a manual check.
- Suggestion: expose a browser session in the development environment.
