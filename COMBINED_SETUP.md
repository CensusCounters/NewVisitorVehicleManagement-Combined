# Combined four-site project

This directory is a separate project assembled from the current four branches. The original `Kupwara`, `NCPass`, `ganganagar` and `tangdhar` directories are not modified by this combined-project work.

## Select a site

Supply `SITE_PROFILE` from the shell or deployment system as one of:

- `kupwara`
- `ncpass`
- `ganganagar`
- `tangdhar`

Example:

```bash
SITE_PROFILE=ncpass docker compose \
  -f docker-compose-census-counters-visitor-vehicle.yml \
  --profile bundled_infra \
  --profile visitor_vehicle up -d
```

Or use `./run_all_containers.sh` with `SITE_PROFILE` set in the environment. That script defaults to `SITE_PROFILE=ncpass` if unset, and syncs ANPR images before start.

**Note:** Postgres and Redis use the `bundled_infra` profile. Starting with `visitor_vehicle` alone will cause a 500 error because the app cannot reach `census_counters_postgres_db`.

Ensure the Docker network exists first (one-time):

```bash
docker network create census_counters_network
```

**First run (empty volume only):** if Postgres uses a new empty volume, load schema and users as below. To reuse **existing NCPass branch data** (persons, vehicles, trips), the compose file mounts the external volume `visitor-vehicle-management_census_counters_postgres_db` instead of starting fresh.

**ANPR vehicle thumbnails:** `./run_all_containers.sh` runs `./sync_anpr_images.sh` first. The cleanup service deletes files in `src/ANPR/anpr_webhook/images/` when their modification time is older than 15 days, so a one-off copy from `Downloads/images` (often dated 2025) disappears quickly. The sync script copies from the NCPass branch image folder and refreshes mtimes on each start.

Empty-volume bootstrap:

```bash
docker cp DB_Files/table_schema_May172025.sql census_counters_postgres_db:/table_schema_May172025.sql
docker exec census_counters_postgres_db psql -U postgres -d postgres_visitor_vehicle -f /table_schema_May172025.sql
docker exec census_counters_postgres_db psql -U postgres -d postgres_visitor_vehicle -c \
  "INSERT INTO users (created_by, user_name, email, password, user_type) VALUES ('Super Admin', 'ayush', 'ayush@censuscounters.com', crypt('password', gen_salt('bf')), 'Admin');"
```

The default is `kupwara`. An unknown profile stops application startup with a clear error.

## Configuration source

The profile registry is maintained in:

```text
src/frontend/finalfrsproject/__init__.py
```

Each profile controls:

- application title and logo identity;
- visitor categories;
- available ID types and allowed IDs by visitor type;
- the complete branch-specific ID lookup workflow (the existing route remains named `aadhar_lookup` for compatibility);
- Known Person editable/required fields and ID labels;
- Unknown Person purpose input, ID capture sides and visitor types that require a supplemental driving licence;
- visible Blacklist list columns;
- cache-busting asset version.

Secrets and service endpoints should continue to come from environment variables rather than the site-profile dictionary.

## First seven consolidated pages

1. `login.html` — one gettext-enabled form; every deployment uses the NCPass 30-minute JWT, secure-cookie and Redis single-login behavior.
2. `layout.html` — one layout using the configured title/logo identity and shared dimensions, columns, fallback and cache-busted `asset_url()` references.
3. `home.html` — one three-option gettext-enabled home page.
4. ID lookup — the legacy `aadhar_lookup` route dispatches by profile. NCPass accepts **Aadhar only** (no ID type dropdown); Kupwara and Ganganagar support Aadhar, driving licence and pass with visitor-specific rules; Tangdhar follows the Kupwara-style workflow.
5. `recognize_person.html` — one capture/recognition page and resilient helper with a 30-second service timeout.
6. `manual_face_verification.html` — one gettext-enabled image comparison and Yes/No workflow.
7. `reregister_face.html` — one gettext-enabled comparison/modal workflow and helper.

## Logo note

The repository contains the NCPass and Ganganagar logo files. The configured Kupwara and Tangdhar logo filenames were referenced by their branches but were not present in the supplied repositories. The common layout therefore falls back to `images/census-logo.png` if either deployment-specific logo is missing. Add the real files at:

```text
src/frontend/finalfrsproject/static/images/vajr-28-div-logo.jpeg
src/frontend/finalfrsproject/static/images/shakti-vijay-logo.jpeg
```

## Cache busting

Templates call:

```jinja2
{{ asset_url('css/style.css') }}
```

which renders like:

```text
/static/css/style.css?v=combined-1
```

Increment `ASSET_URL_VERSION` when static files change.

## Known, unknown and blacklist workflows

- `known_person.html` and `/api/update_known_person` are shared. The profile schema controls editable fields, required fields and generic ID labels while the helper validates updates and refreshes Redis.
- `unknown_person.html` is shared and schema-driven. All sites capture ID front/back; NCPass uses the configured purpose dropdown and requires a separate driving-licence number/image for `DRIVER` when the primary ID is not already a driving licence.
- Blacklist recognition intercept, alert confirmation, enrollment and list pages are shared. Enrollment always targets and flushes the `blacklist` face collection, service calls have timeouts, and list records are sorted with profile-configurable columns.

## Scope

Only the first seven pages and the configuration/authentication paths needed by them have been consolidated. Remaining person, vehicle, trip, report and deployment differences still follow the copied Kupwara baseline and must be migrated in later phases.
