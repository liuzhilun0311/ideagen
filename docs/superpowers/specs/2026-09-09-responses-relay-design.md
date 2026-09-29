# Responses Relay Support

Date: 2026-09-09. User supplied relay documentation after approving the proposed dual-protocol approach.

## Scope

Add an explicit Responses / Chat Completions selector to text provider configuration. Keep existing provider type, custom model names, base URLs, endpoint customization and masked-key editing. Existing configurations without a protocol retain Chat Completions, except a Responses endpoint infers Responses.

Responses powers outline and copy generation, including reference-image input for outlines. It does not change the image generator or add Claude Messages or tool orchestration.

## Contract

Public relay documentation retrieved from `https://docs.heihuzi.ai/cn/api-reference/responses.md` on 2026-09-09 specifies `POST /v1/responses`, Bearer authorization and `model`, `input`, optional `stream`, `tools`, and model-dependent `temperature`.

Use `model`, `input`, `stream:false` for the initial Responses integration. Optional sampling and output-token parameters are deliberately omitted because this relay's documented subset does not guarantee support. System text and reference images are encoded within Responses input messages, not Chat Completions messages. Parse textual message output, not reasoning or tool calls; reject failed, incomplete, refused, empty, malformed or unexpected streaming responses.

Use the same Responses client for connection tests and production text generation. A returned nonempty text answer is required to pass the test. Preserve existing Chat Completions behavior.

## Safety

Do not use or persist the API key pasted in the conversation. Advise rotation and entry of a replacement directly in the application. No real provider requests, auto-imported credentials, secret-bearing fixtures or repository YAML edits. Model IDs are opaque strings; support of a specific model/account is not claimed without a real authorized test.

## Validation

Mocked backend tests cover protocol selection, payload/URL construction, reference-image MIME types, output extraction, refusal/incomplete/error responses and smoke-test integration. Frontend tests cover protocol defaults, persistence, masked editing and connection-test payloads. Browser checks use isolated preview fixtures. Run Django checks/tests, frontend suite/typechecks/build and production mock exclusion checks.
