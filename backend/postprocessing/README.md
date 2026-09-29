# Image Postprocessing

Record-scoped local image processing. This app never calls image providers.

## API

`GET /api/postprocessing/<record_id>` returns the shared `ProcessingState`
contract from `docs/superpowers/plans/2026-09-09-image-postprocessing.md`.
Only successfully generated, decodable originals appear in `pages`.
Preferences are persisted per account, initially automatic off and light strength.
GET reconciles sources but never submits processing jobs.

Polling computes a read-only view of current source revisions; it does not
persist reconciliation or acquire a SQLite writer lock, including for legacy
records. Polling still hashes available originals/current outputs to detect
external changes safely. Submissions and generation publication persist the
reconciled state under the database lock. Thus very large records still incur
file I/O per poll, but not a long database write transaction.

`POST /api/postprocessing/<record_id>` accepts:

```json
{"action":"process","indices":[0,1],"strength":"light","force":false}
{"action":"preferences","automatic":true,"strength":"light"}
{"action":"adopt","index":0,"version":"processed","source_revision":"<revision>"}
```

All successful mutations return fresh state. Indices are page indices, not
positions in the returned array. Strength values are `light`, `medium`, `heavy`.
Process requests snapshot the source revisions and strength. Default submissions
skip pages with usable processed images or active jobs. `force:true` replaces a
completed result, but never duplicates an active job. Failed pages without a
usable result can be retried with an ordinary process request. A failed rerun with
a retained result requires `force:true`.

Adoption conflicts return 409; malformed requests return 400. Foreign and missing
records both return 404, including for administrator accounts. Unauthenticated
requests return 401. Unavailable storage/database errors return sanitized 503s.
Errors use the existing structured API error envelope.

Images are authenticated using the existing bearer header or token query:

```text
/api/postprocessing/images/<record_id>/<index>/original/<source_revision>
/api/postprocessing/images/<record_id>/<index>/processed/<job_uuid>
```

Returned URLs never include tokens. These endpoints check ownership and the
current source revision. Successful job URLs remain immutable while that source
revision is current. An old source URL is rejected after regeneration. Responses
are private/no-store and snapshot the validated bytes before streaming.
Image GET uses SELECT-only database access and validates only the requested
page's source and requested output. It never invokes whole-record reconciliation.
Runtime UI errors are Chinese. Processor diagnostics log job identifiers and
fixed failure categories, never exception strings, commands, stderr or paths.

## Worker

```text
python backend/manage.py migrate
python backend/manage.py process_images
python backend/manage.py process_images --once
python backend/manage.py process_images --poll-interval 2
```

`--once` consumes at most one job, including one recovered lease. A normal worker
continues polling; ordinary processing failures do not stop other pages.
The bundled `deai-image/scripts/deai.py`, Pillow, and NumPy must be installed.
Web and worker must share the database and the whole `HISTORY_ROOT`.
Outputs are stored under `HISTORY_ROOT/<owner>/_postprocessing/<record-id-hash>`.
Deleting a history record cleans only its processing directory. History list and
detail responses include `adopted_thumbnail_url`, or null; this read-only helper
validates candidate source/output files without reconciling every page.

The script timeout is 300 seconds, lease 360 seconds, and maximum recovered
attempts 3 (settings in `config/settings.py`). Explicit processing failures
require manual retry; interrupted leases are automatically reclaimed. Conditional
database claims and per-attempt tokens fence late workers. Input files are copied
to isolated temporary directories. Outputs must decode as PNG, are hashed, and
are atomically published to unique job/attempt paths before page adoption changes.
Only one result is current; superseded output files are not garbage-collected.

Generation's existing `HistoryService.sync_record_images` publication invokes
the hook after each image. Merely reading a record or editing its outline does
not enqueue work. Enabling automatic processing does not backfill older files;
disabling it leaves queued jobs intact. An explicit adoption choice made after
submission is preserved when processing completes.

## Verification

`python backend/manage.py test postprocessing`

Tests use temporary databases/directories, synthetic images and mocks. They
include the real local processing script and independent-process SQLite
submission/claim races. Real symlink testing is skipped where OS privileges do
not permit creation; resolved-path containment is also tested with a mock.
