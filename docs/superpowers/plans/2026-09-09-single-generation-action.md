# Single Generation Action

User-approved scope: remove duplicate image/copy generation controls from settings; keep one primary action per workspace page. Retain per-image retry and collapsed outline adjustment. Do not change model integrations.

- [x] Regression test first demonstrated the duplicate image action in the settings region.
- [x] Image page primary action is `生成全部图片`; copy page uses `生成文案` or `重新生成文案` according to existing body content.
- [x] Settings expose model/prompt selection and progress, without image/copy generation or duplicate cancellation.
- [x] Outline regeneration stays collapsed and requires confirmation before replacing manual edits.
- [x] Mobile settings navigation is named `设置`.
- [x] Full frontend suite: 210 tests passed. Typechecks and production build passed.
- [x] Desktop and 390px mobile preview checked; no real provider requests made.
