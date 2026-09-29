# Outline Error Reporting Implementation Plan

**Goal:** Stop misclassifying outline failures as network failures and retain safe, actionable diagnostics.

**Approved Design:** Classify the actual failure, not appended troubleshooting text. Distinguish Responses transport failures without exposing upstream bodies, credentials, or prompts. Keep the existing service result and API normalization contracts.

**Architecture:** The outline service returns a sanitized error string. Responses translates transport exception types into safe messages; the common classifier preserves those messages for network diagnostics.

**Tech Stack:** Python, Django, requests, unittest.

## Constraints

- Preserve existing uncommitted work and provider configuration.
- Do not include raw transport errors or upstream bodies in Responses failures.
- Do not change request payloads, retry policy, model selection, or timeouts.

## Steps

- [x] Add regression tests for non-network outline failures, transport categories, and redacted logs/results.
- [x] Run the targeted tests before implementation and confirm the failures.
- [x] Replace the outline troubleshooting wrapper with sanitized original errors.
- [x] Categorize Responses transport exceptions and preserve safe network details.
- [x] Run focused tests and the related generation/provider suites.
- [x] Replay the saved failed outline without modifying saved settings; report its outcome separately from the code fix.

## Live Diagnosis

The saved failed request reproduced a protocol error. A second probe confirmed HTTP 200
and a completed JSON response incorrectly labeled `text/event-stream`. The adapter had
rejected the response based on its header without inspecting the valid JSON body.

- [x] Add tests for mislabeled completed/incomplete JSON and actual SSE.
- [x] Parse JSON before rejecting actual SSE; keep final-output validation unchanged.
- [x] Reproduce and correct Latin-1 decoding of UTF-8 Chinese caused by the same text/event-stream header.
- [x] Repeat regression suites and replay the saved failed outline.

## Verification

- Initial error regressions: 14 failing subcases before the fix.
- Header regressions: completed/incomplete mislabeled JSON both failed before the fix.
- Encoding regression: reproduced corrupted Chinese with a real requests.Response.
- `python backend/manage.py test generation providers --verbosity 0`: 145 tests passed.
- Replayed the saved September 28 failed request using its original prompt, preferences,
  provider and model: succeeded in 16.1 seconds with one cover page and 198 outline characters.
- Saved provider configuration and the original generation record were not modified.
- `git diff --check` on the modified tracked Python files: no whitespace errors.
