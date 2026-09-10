# Admin Work Sharing

Date: 2026-09-10
Status: Awaiting written-spec review. User approved read-only sharing in conversation.

## Scope

Administrators can select users allowed to view and use their own works.
Recipients may preview images, copy publishing text, and download images.
Recipients cannot edit, delete, regenerate, postprocess, change adopted image
versions, or reshare the source. No collaborative editing or work duplication
is included. Existing administrator oversight of other users' records remains,
but does not grant permission to share works owned by another account.

## User Experience

- On an administrator's own work card, add an icon with the tooltip
  "配置用户". A dialog lists active accounts with checkboxes and username
  search, restores saved selections, and offers Save/Cancel.
- The owner always retains access and is not a removable recipient.
  An empty recipient list means private, not public.
- Show an unobtrusive shared indicator and recipient count on owned cards.
- Add "共享给我" as a separate source filter in the works page, independent
  of completion-status filters. Shared cards identify the owner and expose
  preview/download only. Search, pagination, empty state, and counts apply
  consistently to the selected source.
- Shared preview includes image browsing and publishing text without loading
  the work into the creation workspace or replacing an in-progress draft.
  Return restores the prior works filter, search, and page.
- Prefer processed images where available, falling back to originals.
  Downloads retain processed/original/both choices and existing folder-picker
  fallback and completion feedback.
- Switching accounts clears cached shared content and pending dialogs.
  Reentering a cached page refreshes authorization and data.

## Data And API

- Add an additive recipient relationship to HistoryRecord referencing User.
  Existing records remain private; deleting a recipient removes that grant.
- Introduce one shared permission module with distinct read, modify, and
  configure-sharing decisions. Both owner and eligible selected recipient
  can read. Only the administrator who owns a work configures its sharing.
  Grants are effective only while the owner remains an administrator.
- Add authenticated GET/PUT sharing configuration under the work resource.
  The backend validates the complete recipient set and saves atomically;
  invalid or missing accounts fail without partially replacing the grant.
- Extend list/search/statistics with an explicit shared source. Preserve
  existing default listing behavior. Include owner display and capability
  flags, but do not expose recipient lists to recipients.
- Maintain a single source record: later administrator changes are visible
  on the recipient's next authorized refresh.

## Authorization Coverage

Read authorization must cover details, existence checks, thumbnails, original
images, processed images, postprocessing state, and all download routes.
Image authorization must verify the requested file belongs to the shared
record, not grant access to every image under the owner's directory.

Write authorization remains separate and covers record update/delete,
generation/retry/regeneration, processing preferences/jobs/adoption,
sharing changes, and history synchronization routes. Hiding controls alone
is not sufficient. Direct requests by recipients must fail.

Revocation/deletion denies subsequent online requests even with a remembered
record ID or image URL. Protected responses must avoid reusable public caches.
Already downloaded files, bytes already delivered to a browser, and in-flight
responses cannot be recalled. The UI removes inaccessible content on refresh
or authorization failure, with no claim of instantaneous remote erasure.

## Failure Handling

Disable repeated saves while pending. Keep the dialog and selections when a
save fails; publish new sharing counts only after successful confirmation.
Guard late responses against changed account, selected record, and navigation.
If a work is deleted or access revoked during preview/download, show a clear
access-unavailable state and allow return to works without exposing editing.

## Verification

- Backend permission matrix: owner administrator, selected recipient,
  unselected user, other administrator, unauthenticated request.
- Grant/revoke, owner demotion, recipient deletion, invalid user IDs, no
  partial grant changes, and existing records remaining private.
- Shared list/search/pagination/count isolation and filtered serialization.
- Original/thumbnail/processed reads and downloads before/after revocation;
  attempts to fetch unrelated owner images fail.
- Recipient writes rejected across history, generation, postprocessing, and
  synchronization endpoints.
- Frontend sharing dialog success/failure, read-only cards and preview,
  account/navigation races, return state, and in-progress draft preservation.
- Isolated browser fixtures for administrator and recipient flows at desktop
  and mobile widths. Do not alter live grants or invoke paid model APIs.
- Fresh tests, typechecks, build, migration consistency checks, and an actual
  verification report before declaring implementation complete.

## Implementation Boundaries

Reuse existing authentication, user selection patterns, gallery, image viewer,
publishing-text rendering, and download dialog. Add focused sharing and
read-only preview components instead of expanding the creation workspace.
No unrelated visual redesign, public links, model-secret sharing, or new
deployment infrastructure.
