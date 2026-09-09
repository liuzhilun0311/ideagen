# Responsive Studio Verification

Date: 2026-09-09

## Scope

Delivered the responsive UI subproject: minimal creation home, expandable model/reference options, a shared outline/image/copy workspace, and a result preview. Existing Vue/Pinia/Django APIs remain in place. Legacy outline and generate routes redirect to the workspace.

This is not a claim that the complete product roadmap or cloud deployment is finished.

## Automated Checks

- `npm test`: 117 tests passed in 10 files. No paid provider requests.
- `npm run typecheck`: passed.
- `npm run test:typecheck`: passed.
- `npm run build`: passed.
- `.venv\Scripts\python.exe backend/manage.py check`: no issues.
- `git diff --check`: passed; Git reports expected Windows LF/CRLF warnings.
- Production output search for `local-preview-not-a-real-token`, `Development preview only`, `preview-record`, and `dev-preview`: no matches.

Coverage includes save snapshots, failed creation/update, changes during saving, workspace remounts, generation gating, cancellation ownership, late content responses, reference arguments, model selection, and existing generation reliability regressions.

Review fixes include a logout/new-login race and image URL authentication scope. Logout uses its original token without global response redirects. Shared image URLs retain external signatures and only attach the session token to same-origin image API paths.

## Browser Checks

Used `frontend/dev-preview.html` with simulated API responses and page-local ephemeral storage. Real account tokens and drafts were not changed. Fixture photos illustrate layout; they are not AI-generated output.

- Home: inspiration fills the topic; outline generation opens the workspace.
- Workspace: generated three mock images, generated copy, saved before preview, and returned to editing with the confirmed saved state retained.
- Structure: added a fourth page, entered text, moved it up, and saved. Existing image results disable structural changes.
- Mobile: switched editor/generation sections and inspected the whole-kit copy form.
- Home, workspace, result, and login checked at 375, 390, 768, 1024, and 1440 pixels. No horizontal overflow. Visible photo assets loaded.
- Desktop/mobile screenshots were inspected and emitted in the conversation; no separate screenshot files were exported.
- The actual `/login` entry displayed the authentication form. No real login was submitted.
- Subagent browser checks additionally covered uploads, IME/newlines, cancellation, result empty/partial states, and simulated download feedback.

The preview uses a memory router and does not replace verification of production auth guards or server history hydration. The production route guard remains present by code inspection.

## Known Limits

- Server-side save version conflicts and multi-device concurrent editing are not yet handled.
- Local drafts still use the existing storage model, not per-user isolation.
- A page refresh without a confirmed in-memory server snapshot conservatively displays unsaved status.
- The current backend cancel endpoint is user-wide and process-local; the frontend serializes generation but does not solve cross-worker cancellation.
- Full SSE syntax coverage and persisted task resumption remain pending.
- Real providers, real downloads, HTTPS/mobile hardware, Docker builds, and cloud deployment were not exercised.
- Existing user edits to Docker files and provider example files were preserved.

## Preview

Real application: `http://127.0.0.1:5173/`

Isolated mock UI: `http://127.0.0.1:5173/dev-preview.html?screen=home`
