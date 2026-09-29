# Creation Navigation

Approved behavior: returning to creation settings preserves the current work.
Only explicit new creation or confirmed regeneration replaces it.

1. Remove draft replacement from WorkspaceView's back action; retain last workspace route.
2. Show creation settings/continue when an outline exists in HomeView; do not require a model request.
3. Share a new-creation button and accessible native confirmation dialog across both pages.
   Offer save-and-new, discard-and-new, and cancel. Failed saves must not reset the draft.
4. Lock replacement during ongoing work and save operations. Preserve generation preferences.
5. Add regression tests for navigation, cancellation, successful/failed saves, and empty outlines.
6. Run focused tests, type checking and production build. Verify port 12399 serves the build.
