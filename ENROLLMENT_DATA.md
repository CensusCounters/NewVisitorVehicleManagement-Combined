# Enrollment datasets

The admin Enrollment Data page exports, resets, and restores enrolled persons
and vehicles, their images/documents and the `default` Milvus face collection.
Import supports populated systems: identical duplicates are skipped; conflicting
records are reported and skipped while unrelated records continue. Missing images
and vectors for matching existing enrollments are repaired. Different existing
content is preserved; an orphaned face GUID without a PostgreSQL person remains
restorable and its vectors can be replaced as part of recreating that person.
Users, blacklist,
passes, trips, and ANPR history are not exported. Reset refuses to run when trips
or passes exist, including passes that PostgreSQL would otherwise cascade-delete.

This is application-level dataset portability, separate from physical database
backups and the existing timed image cleanup. ZIP files contain personal data and
face vectors. Store downloaded packages privately.

## Install (no production migration is performed automatically)

1. Back up the existing databases and files using the deployment's established
   procedure. Coordinate a maintenance window and finish in-flight registrations.
2. Apply the additive job tables and write guards against the visitor database:

   ```bash
   docker exec -i census_counters_postgres_db \
     psql -v ON_ERROR_STOP=1 -U postgres -d postgres_visitor_vehicle \
     < DB_Files/enrollment_data_jobs.sql
   ```

3. Create the shared private storage directory on the host:

   ```bash
   mkdir -p enrollment-data
   chmod 700 enrollment-data
   ```

4. Reconcile the tracked Compose example with the deployed Compose file,
   preserving the site's image mounts, credentials and profile. The local Compose
   file in this workspace has the new worker services too, but is gitignored.
   All participants must use the same local `./enrollment-data:/maintenance`
   bind mount. The worker must see enrollment images at the same paths as Flask.
5. Rebuild the frontend image to install the pinned RQ and pymilvus dependencies;
   recreate the frontend, face engine, cleanup, worker, dispatcher and private
   queue together. Restart the face engine to load its shared maintenance guard.

   ```bash
   docker compose -f docker-compose-census-counters-visitor-vehicle.yml config --quiet
   docker compose -f docker-compose-census-counters-visitor-vehicle.yml build \
     census_counters_webservice_fr
   docker compose -f docker-compose-census-counters-visitor-vehicle.yml up -d \
     census_counters_webservice_fr census_counters_fr_engine census_counters_cleanup_fr \
     census_counters_enrollment_redis census_counters_enrollment_worker \
     census_counters_enrollment_dispatcher
   ```

For an installation that already has the initial migration, finish any old
   import/recovery operation with the previous version, stop the worker and
   dispatcher, then apply `DB_Files/enrollment_data_merge.sql` before starting
   this version. Reapplying the updated initial migration also adds these columns.
   Do not upgrade a partially completed legacy import: its old recovery code
   assumes an empty system and is deliberately rejected by the additive importer.

6. Sign in as an existing Admin. On Home, expand **Administration** below the
   daily visitor actions, select **Enrollment data maintenance**, and confirm
   that you intend to open maintenance. Confirm healthy
   workers and run an export before using reset. Validate recognition and vehicle
   lookup on a nonproduction installation before operational use.

Do not run mixed old/new writer containers during maintenance. Direct database
administration, other Milvus clients and other PCs are outside the file guard;
stop those writers during operations. This design targets a single Docker host
with local shared storage, not a multi-host/NFS deployment.

## Operations

The maintenance page uses the application's dark theme and scoped SweetAlert
dialogs. Export, package review, import and interrupted-operation recovery each
require an explicit review before submission, with Cancel focused by default.
Import requires a completed package review and shows additions, identical records
and conflicts. Reset is collapsed separately at the bottom of the page: preview
the affected records, then type `RESET ENROLLMENTS` exactly in its confirmation
dialog. Reset recovery requires the same phrase. These prompts discourage
accidental use; backend Admin authorization, CSRF, locking and worker validation
remain the enforcement mechanisms. Opening the page does not start an operation.
Actions are disabled while status is unavailable or an operation is active.
The page also checks that a recent background worker and dispatcher heartbeat
are available and the queue responds. When unavailable, it shows plain-language
restart guidance and **Check again**; recent jobs, downloads and queued-job
cancellation remain accessible. New work and recovery submissions are refused
by the server before accepting a job or upload. A service can still fail after
admission; accepted requests remain durable and can wait for recovery. Heartbeat
checks are failure detection, not an instantaneous availability guarantee.

- **Export:** creates a version-1 checksummed ZIP. Required missing images,
  orphaned face GUIDs, missing vectors or unsupported schema fail validation.
  Exports include all records in `persons` and `vehicles`, and every `default`
  vector must belong to one of those persons. `blacklist` is untouched.
- **Check package:** upload and validate in the background. The preview shows
  records to add, enrollments to repair, identical duplicates to skip and conflicts with reasons. Review
  these results before importing. The importer checks the preview again under
  the maintenance guard; changed target data requires another preview.
- **Import:** adds only non-conflicting records, allocates local PostgreSQL IDs,
  maps vehicle owners to their new or matched local person IDs, and fixes portable
  image locations. `created_by` is the importing admin for new rows; original
  creator IDs stay in the package. Existing business fields and record IDs are
  preserved. Missing image references can be filled with portable private paths;
  existing image contents are not overwritten. For matching existing persons,
  missing vectors are appended, including a missing subset of their vectors;
  different or extra existing vectors are conflicts. Existing history and
  blacklist entries do not prevent import.
  Import/reset invalidate numeric per-user registration workflow keys only after
  actual changes, preserving login locks and unrelated Redis keys.
- **Duplicates and conflicts:** person GUIDs identify enrollments. A matching
  person must have matching business fields, image/document content and vectors
  to be skipped as identical; missing content instead plans a repair. SQL IDs,
  creator IDs and creation timestamps do not
  determine identity. Aadhaar/license/other-ID collisions under different GUIDs
  are conflicts, not automatic identity merges. Vehicle plates are compared
  case-insensitively without whitespace or hyphens; matching details, image and
  resolved owner are required for an identical duplicate. Ambiguous plates are
  conflicts. A vehicle whose imported owner conflicts is also skipped. New
  vehicles can be added for an existing identical person. No fuzzy name or facial
  similarity matching is used to combine identities.
- **Files and recovery:** new document filenames include person GUIDs and image
  hashes; new vehicle images use content hashes. Matching content may be reused,
  but differing existing files are conflicts. The journal records new row IDs and
  the exact GUIDs/files owned by this import and authorized image-reference
  repairs. Recovery replays new enrollments and missing-content repairs,
  preserves existing vectors during repairs, and refuses a modified source
  package. Vector-repair retries count already-restored vectors rather than
  deleting them. Re-importing a completed unchanged dataset is a no-op for
  identical records. No new SQL migration is needed for repair journals; they
  use the existing import-plan JSON. Restart frontend, worker and dispatcher
  together to load these changes; do not mix old and new executors.
  Structural archive errors still reject the package; per-record conflicts do
  not abort unrelated imports. Conflict details stay in the job result and UI.
- **Reset:** previews PostgreSQL counts; the worker rechecks dependencies and
  creates/validates a recovery ZIP before deletion. It removes vehicles before
  persons, deletes only those persons' default vectors, and removes their private
  enrollment files. Shared ANPR/snapshot images and placeholders remain owned by
  their existing lifecycle. Download the recovery export from the completed job.

The package contains `manifest.json`, `persons.json`, `vehicles.json`,
`faces.jsonl`, and referenced files under `images/`. The format supports the
checked-in visitor schema, 512-dimensional face vectors and the deployment's
existing face recognition model. The manifest records its model name and import
rejects a mismatch with `ENROLLMENT_EMBEDDING_MODEL` (default
`auraface_glintr100`). Keep this setting consistent with the face engine REC_NAME;
use the same embedding model on the target;
this feature does not regenerate or migrate embeddings across models.

## Worker reliability

The PostgreSQL queued job row also serves as an outbox. The dispatcher delivers
it to RQ and redelivers unclaimed requests after 60 seconds. Workers atomically
claim rows, so duplicate queue delivery does not duplicate execution. Redis is a
separate AOF-enabled queue with no eviction, on an internal Docker network.
Permanent status and checkpoints live in PostgreSQL, not Redis.

An accepted job blocks new foreground work so maintenance cannot be starved by
continuous registrations. Queued jobs that have not started can be cancelled
from the page; interrupted operations must be recovered, not cancelled.

A shared POSIX lock serializes maintenance with web requests, face API requests,
and cleanup. A persistent marker blocks normal requests after worker failure;
statement triggers protect PostgreSQL enrollment/history writes too. Admin
maintenance, login and static routes stay accessible. This briefly blocks normal
application requests, not just the UI buttons. Never manually delete the marker.

The worker records relational restoration and its checkpoint in one transaction.
Images are checksummed. Recovery can replace vectors for newly restored persons,
including orphan GUIDs being merged back into PostgreSQL. Missing-vector repairs
for existing persons only append what is absent. These run under the maintenance
guard. There is no distributed transaction
across PostgreSQL, Milvus and files; partially completed operations intentionally
remain blocked until recovery. Do not force-stop a running job to cancel it.

Heartbeats update every 15 seconds. After a missing heartbeat for 90 seconds,
the dispatcher must acquire both operation locks before declaring the executor
stopped. It marks interrupted work **recovery_required**. Review the error and
last step, restore any unavailable dependency, and click **Review recovery**.
Confirm the recovery dialog. Recovery resumes the same journaled operation; it is not a fresh
import. Database failures and locks prevent unsafe concurrent execution.

Failed validation and failures before any mutation can finish as **failed**. If a preview is stale, check the package again; no
enrollment writes occur before that check.
An interrupted import/reset retains its private package and work files. Do not
remove uploads, exports or work directories for unfinished jobs. Completed export
work directories duplicate sensitive files; retention is currently manual and
must preserve any packages needed for recovery. No automatic deletion policy is
introduced by this feature.

Useful checks:

```bash
docker compose -f docker-compose-census-counters-visitor-vehicle.yml ps
docker compose -f docker-compose-census-counters-visitor-vehicle.yml logs --tail 100 \
  census_counters_enrollment_worker census_counters_enrollment_dispatcher
```

Worker/dispatcher health probes check database connectivity and live worker or
dispatcher heartbeats. The UI shows phase progress and job IDs. The default
per-job timeout is 7200 seconds; package compressed/expanded limits are 512 MiB.
Configure `ENROLLMENT_JOB_TIMEOUT`, `ENROLLMENT_MAX_BYTES`, database connection
variables and image mounts consistently for Flask, the worker and dispatcher.
These endpoints require a valid Admin account and CSRF tokens for browser writes.

## Milvus startup change

The manager's separate-etcd migration is independent of these enrollment jobs.
It is not applied automatically by this feature. Before that migration, back up
the stopped Milvus volume and configuration, preserve the existing etcd metadata
and advertised URL, and verify recognition/restarts on the affected PC. Once etcd
is separate, both etcd and Milvus must be stopped for an offline shared-volume
archive. Never use `docker compose down -v` as a recovery step.

## Development verification

The development test suite is maintained separately and is not included in this
client checkout. A verified archive is retained outside the repository before
removing the suite. Restore it into a development checkout when extending or
retesting this feature; the root `tests/` directory is intentionally gitignored.
The last feature verification passed 60 backend/integration checks and four
isolated browser checks using synthetic records and disposable services.
The test suite is not required by the application, maintenance worker or
production database migrations.

Generated report CSV/PDF files are also excluded from source distribution.
Application reports can be generated again through the existing report pages.
Private enrollment datasets, backups and runtime job files remain under the
ignored `enrollment-data/` directory and must not be removed as code cleanup.
