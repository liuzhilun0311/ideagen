# Responses Relay Verification

Date: 2026-09-09

- Backend initial red: `manage.py test generation` failed on the missing Responses adapter.
- Backend final: `.venv\Scripts\python.exe backend/manage.py test generation providers --verbosity 1`: 20 passed; Django system checks clean.
- Frontend: `npm test`: 201 tests passed across 14 files.
- Frontend: `npm run typecheck`, `npm run test:typecheck`, `npm run build`: exit 0.
- `git diff --check`: exit 0 (Windows line-ending conversion warnings only).
- Browser: development-preview model navigation and add-provider modal inspected on desktop and 390x844 mobile.
- Browser: selecting Responses sets `/v1/responses`; manual `/responses` remains editable. Mobile document width and scroll width both 390, no horizontal overflow.
- Independent review found duplicate endpoint normalization during submission. Removed it and added a regression test that checks both save and test payloads preserve `/responses`.
- No actual API key used, real relay request sent, or real provider configuration changed. All automated network tests use mocks and synthetic credentials.
- Existing user Docker and YAML example changes are outside this implementation.

Limitations: real relay compatibility and model permission remain unverified; nonstreaming Responses only; upstream sampling/output limits apply.
