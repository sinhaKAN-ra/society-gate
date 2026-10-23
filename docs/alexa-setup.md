# Connecting a real Echo

The runnable default is a local conversation simulator. No Amazon resources,
skill registration, external hosting, OAuth service, or notifications are created
by starting the demo. This guide describes the remaining manual setup.

## Intended architecture

Echo → Alexa Skills Kit → restricted AWS Lambda → HTTPS companion backend →
resident authorization → visitor decision → guard dashboard.

Use [Amazon's custom skill workflow](https://developer.amazon.com/en-US/docs/alexa/custom-skills/steps-to-build-a-custom-skill.html)
and [Lambda hosting instructions](https://developer.amazon.com/en-US/docs/alexa/custom-skills/host-a-custom-skill-as-an-aws-lambda-function.html).
The Lambda trigger must restrict invocation to Alexa Skills Kit and the specific
skill ID. Do not configure a public Lambda Function URL. The relay code checks
the application ID as an additional guard, not a substitute for IAM restrictions.

## Setup steps

1. Create a custom skill in the Amazon developer console, locale English (India).
   Import `alexa/interaction-model-en-IN.json`. Build the interaction model.
2. Deploy `alexa/lambda_function.py` to a supported Python AWS Lambda runtime.
   Set the handler to `lambda_function.lambda_handler`. It uses only the
   standard library. Configure an Alexa Skills Kit trigger with **skill ID
   verification enabled**, then set the skill endpoint to that Lambda ARN.
3. Deploy the companion backend behind a maintained HTTPS service. The current
   `http.server` is a local development server, not an Internet deployment.
   For a temporary developer-only relay test, an HTTPS reverse proxy can forward
   only `/api/alexa` to loopback, rewrite the upstream Host header to
   `127.0.0.1:8091`, and preserve the Authorization header. Keep `/api/simulate`,
   the mock vendor, and local demo accounts off the public endpoint.
4. Set `ALEXA_SKILL_ID` on Lambda and the backend to the actual skill ID. Generate
   a random `ALEXA_RELAY_TOKEN` of at least 32 characters and set it on both.
   Set Lambda's `SOCIETY_API_ORIGIN` to the HTTPS origin, with no path or query.
   Secrets belong in environment/secret management, not source control.
5. Provide an OAuth authorization-code account-linking service for society
   residents and configure it in the Alexa developer console. The authenticated
   resident must map to a verified, enrolled household. The backend reads the
   linked token from `context.System.user.accessToken`; never use a spoken flat
   number as authorization. The local hashed demo-token store shows the lookup
   boundary, but is not an OAuth server and has no refresh-token lifecycle.
6. For a restricted developer test, an external test OAuth provider can issue a
   token matching a test resident record. Implement proper token verification,
   revocation, refresh, resident enrollment, and device/household policy before
   a live deployment. Do not use the demo credentials for real visitors.
7. Enable skill testing and say: “Alexa, open society gate.” Register a test
   visitor, hear the exact request, say “approve visitor,” then “yes.” Verify
   the guard dashboard and audit log. Test denial, no response, retries, expired
   requests, multiple visitors, and another household.

## Transport and authorization

The relay endpoint is disabled unless the backend has a skill ID and a relay
credential of at least 32 characters. It verifies the relay bearer credential,
skill ID, request timestamp (150-second window), and linked resident token.
The voice handler deduplicates request IDs and stores pending confirmation in
the database. Session attributes in the request cannot authorize entry.

This is a **Lambda ingress design**. If changing to a direct Alexa HTTPS webhook,
implement Amazon's certificate/signature verification with its supported SDK;
the relay bearer endpoint alone is not a direct Alexa web-service endpoint.

## Arrival alerts and identity

The resident must open the skill in this version. Amazon's
[proactive event API](https://developer.amazon.com/en-US/docs/alexa/smapi/proactive-events-api.html)
uses opted-in notifications and predefined schemas. That does not establish
that an arbitrary visitor arrival can start a two-way spoken approval session.
Do not promise automatic room announcements or an unsolicited conversation.
Use a validated companion notification channel as the next step and evaluate
Alexa's supported options with the exact locale and skill type.

Account linking identifies the household account; it does not prove which person
is speaking to a shared Echo. Decide the household authorization policy and an
appropriate step-up confirmation mechanism before using voice for live access.
The local prototype deliberately has no physical gate actuation.
