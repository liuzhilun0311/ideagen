# Responses Relay Implementation Plan

**Goal:** Support the documented relay Responses protocol for outline, copy and connection tests.

**Architecture:** Add a small protocol resolver and Responses text client behind the existing text-client factory. Persist `api_protocol` alongside the existing endpoint, model and base URL. Keep image providers unchanged.

**Tech Stack:** Existing Django, requests, Pillow, Vue, Pinia, Vitest; no new dependencies.

## Constraints

No real key use or provider calls. No edits to existing user Docker/YAML files. Model names are not hardcoded or substituted. Responses uses the relay's minimal supported field set.

## Tasks

- [x] Backend: add `generation/utils/text_protocol.py` with `resolve_text_protocol(config)`; add `responses_client.py` exposing `ResponsesTextClient(api_key, base_url=None, endpoint_type=None, timeout=300)` and the existing `generate_text` signature.
- [x] Backend tests: mocked requests must see Responses `input` and never Chat `messages/max_tokens`; cover text/image/system input, custom URLs and model IDs, failed/empty/refusal/incomplete responses, and HTTP/transport errors without key disclosure.
- [x] Factory: `get_text_chat_client` selects Responses by explicit `api_protocol` or inferred Responses endpoint; legacy/Gemini paths remain unchanged.
- [x] Provider smoke test: carry `api_protocol` through request/saved configuration and dispatch Responses through the same client with a short timeout; require actual output text.
- [x] Frontend: selector plus endpoint defaults, backward-compatible inference, save/edit/test propagation; mock-only regression tests.
- [x] Verify frontend tests/typechecks/build, Django tests/checks, desktop/mobile provider modal in preview and whitespace. Record real-provider validation as not performed. No credentials were added and no changes were staged.
