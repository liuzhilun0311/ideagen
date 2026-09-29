# Platform-Aware Outline Template

**Goal:** Match the outline editor role to the selected platform and rename the topic heading to "用户创作的主题".

**Architecture:** Add a platform_name template variable resolved by the shared preview/generation composer. Update the shipped template and migrate only the known legacy introductory sentence and topic label in the persisted builtin template. Preserve unrelated custom content and immutable past records.

## Steps

- [x] Add platform, topic-label, preview/send consistency, and migration preservation tests.
- [x] Resolve platform_name and allow it in outline base templates.
- [x] Update the builtin file and versioned persisted template through a data migration.
- [x] Run generation/provider/prompt tests, apply the migration, and verify actual preview endpoints.

## Verification

- Regression tests reproduced seven failing cases before implementation.
- `python backend/manage.py test generation prompts providers --verbosity 0`: 195 passed.
- `python backend/manage.py migrate prompts --noinput`: migration 0003 applied.
- Preview view verified against local persisted catalog for all five platform selections.
- Existing builtin template advanced from revision 3 to 4; historical outline prompt unchanged.
- No model requests or provider configuration changes.
