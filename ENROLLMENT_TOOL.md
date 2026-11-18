# Enrollment & Blacklist Backup, Reset, and Restore Tool

`scripts/enrollment_tool.py` is an offline maintenance CLI for backing up, resetting, and restoring Visitor & Vehicle enrollment data without running the web UI or background workers.

## What Is Included vs. Excluded

| Data | `save` | `reset` | `restore` |
| --- | --- | --- | --- |
| `persons` & `vehicles` (PostgreSQL) | Yes | Yes | Yes (one by one) |
| Person/document/vehicle images (`known_persons`, `known_vehicles`, `aadhars`, `drivers_licenses`, `other_ids`) | Yes | Yes (preserves `No-Image-Available.*`) | Yes |
| Milvus `default` face vectors | Yes | Yes | Yes |
| Milvus `blacklist` vectors & `static/blacklisted_persons/` images | Yes | Only with `--wipe-blacklist` or `--all` | Yes |
| `trips`, `passes`, `anpr_vehicle_readings`, `passes/`, `permit_images/` | No | Only with `--wipe-history` or `--all` | No |
| `users` (PostgreSQL accounts) | No | **Preserved** | Reused via `--actor-id` |
| Redis cache/sessions | No | Flushed (skip with `--keep-redis`) | No |

---

## 1. Prerequisites (Build Once After Pulling)

`Dockerfile_webservice` installs `pymilvus` alongside `psycopg2` and `redis`. Rebuild the webservice image before running the tool:

```bash
docker compose -f docker-compose-census-counters-visitor-vehicle.yml build census_counters_webservice_fr
mkdir -p backups
```

Ensure `ENROLLMENT_EMBEDDING_MODEL` (default `auraface_glintr100`) matches `REC_NAME` on `census_counters_fr_engine`. Do not restore vectors built with a different recognition model.

---

## 2. Maintenance Window (Stop Writers, Keep DBs Running)

Run `save`, `reset`, and `restore` while all application writers are stopped, leaving `census_counters_postgres_db`, `census_counters_redis`, `census_counters_fr_etcd`, and `census_counters_facedb` running:

```bash
docker compose -f docker-compose-census-counters-visitor-vehicle.yml stop \
  census_counters_nginx \
  census_counters_webservice_fr \
  census_counters_fr_engine \
  census_counters_cleanup_fr \
  census_counters_auto_close
```

Wait until Milvus (`census_counters_facedb`) is healthy, then run commands via `docker compose run --rm --no-deps`:

```bash
TOOL="docker compose -f docker-compose-census-counters-visitor-vehicle.yml run --rm --no-deps \
  -v $PWD/scripts:/scripts:ro \
  -v $PWD/backups:/backups \
  --entrypoint python3 \
  census_counters_webservice_fr /scripts/enrollment_tool.py"
```

*(Note: if `reset` prompts interactively without `--yes`, omit `-T` so stdin stays attached, which is the default for `docker compose run`.)*

---

## 3. Usage

### A. Save (Export Archive)

Strict export (aborts with exit code `2` if any integrity issue is found):

```bash
$TOOL save /backups/enrollments-2026-05-01.zip --report /backups/save-report.json
```

Warn, skip broken/orphaned items, export valid records, and write a full integrity report:

```bash
$TOOL save /backups/enrollments-2026-05-01.zip \
  --skip-invalid \
  --report /backups/save-report.json
```

**What `--skip-invalid` reports & skips:**
- `orphan_default_face`: Milvus `default` vector whose `guid` has no `persons` row.
- `person`: Missing `person_image_location`, missing image/document file on disk, filename collision, or missing Milvus `default` face vector.
- `vehicle`: Vehicle whose owner was skipped, or whose `vehicle_image_location` file is missing or collides.
- `blacklist`: Milvus `blacklist` vector with no matching photo in `static/blacklisted_persons/`.
- `orphan_blacklist_image`: Photo in `static/blacklisted_persons/` with no matching Milvus `blacklist` vector.

### B. Reset (Clean System to Fresh State)

- Preserves `users` accounts and `No-Image-Available.*` placeholder images.
- Refuses to proceed if `trips`, `passes`, or `anpr_vehicle_readings` contain rows unless `--wipe-history` (or `--all`) is passed.
- Requires `--confirm RESET` plus an interactive `RESET` prompt (unless `--yes` is passed).

Reset enrollments only (system has no trips/passes/ANPR history) while taking a pre-reset backup:

```bash
$TOOL reset --confirm RESET --backup-first /backups/pre-reset.zip
```

Full wipe including trips, passes, ANPR history, and blacklist:

```bash
$TOOL reset --confirm RESET --all --backup-first /backups/pre-reset.zip --backup-skip-invalid
```

Reset enrollments and history while **keeping** the blacklist:

```bash
$TOOL reset --confirm RESET --wipe-history
```

Optional flags:
- `--wipe-blacklist`: Also clears Milvus `blacklist` and `static/blacklisted_persons/`.
- `--keep-redis`: Skip `FLUSHDB` on Redis.
- `--yes`: Skip interactive confirmation prompt (still requires `--confirm RESET`).

### C. Restore (One-by-One, Collision-Safe)

Dry run first to inspect imports and any collisions without modifying PostgreSQL, Milvus, or disk:

```bash
$TOOL restore /backups/enrollments-2026-05-01.zip \
  --dry-run \
  --report /backups/restore-dry-run.json
```

Restore an archive into an empty or populated system (repeats safely, skipping conflicts by default):

```bash
$TOOL restore /backups/enrollments-2026-05-01.zip \
  --report /backups/restore-report.json
```

If restoring onto a system that already has some records, the tool processes each person, vehicle, and blacklist GUID **one by one**:
- **Identical existing record:** Skipped cleanly. (If an existing person/vehicle/blacklist record matches in business fields/vectors but is missing an image file or Milvus vector locally, pass `--repair-missing` to fill only the missing piece without overwriting differing data.)
- **Conflicting record** (different details, differing vector/image bytes, document number belonging to another GUID, or plate collision): Recorded in `collisions` in the JSON report and skipped (`--on-conflict skip`, default), or aborts immediately on the first conflict with `--on-conflict abort`.
- **Orphaned local `default` vector** for a new person's GUID: Flagged as a collision unless `--replace-orphan-faces` is passed.
- **`created_by` attribution:** Uses `--actor-id <users.id>` if provided, otherwise the first `admin` user in `users`.
- **ID remapping:** Inserted `persons` and `vehicles` receive fresh local PostgreSQL sequence IDs (`vehicle_owner_id` and Milvus `default.aadhaar` are automatically remapped to the new local `persons.id`, while `blacklist.aadhaar` preserves the blacklisted ID value verbatim).

To load multiple archives sequentially, run `restore` one archive at a time and inspect each `--report`.

---

## 4. Restart Services

Once `save`, `reset`, or `restore` finishes:

```bash
docker compose -f docker-compose-census-counters-visitor-vehicle.yml up -d
```

If you wiped or restored Milvus collections on a freshly initialized volume where `default`/`blacklist` did not yet exist, start `census_counters_fr_engine` briefly first so it creates the Milvus collections, then stop it and run `restore`.

---

## 5. Security & Handling of Backup Files

- Backup `.zip` archives and JSON reports contain PII (names, Aadhaar/license numbers, addresses, facial images, and face embeddings). Store them in a restricted directory and delete temporary copies once no longer needed.
