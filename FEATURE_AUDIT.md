# Combined Four-Site Feature Audit

OCR was intentionally removed from the combined project because it is not part of the required consolidated workflow. The `/ocr`, `/recognize_image`, and `/recognize_qr` endpoints, Google Vision integration, Tesseract assets, credentials, templates, helpers, and configuration were removed.

Audit date: 2026-08-17 IST

Profiles: `kupwara`, `ncpass`, `ganganagar`, `tangdhar`

## Result

All application features listed in `Branch_Differences_4_Sites (1).xlsx` are represented in the combined project. Shared workflows use common implementations, while genuinely different vehicle, trip, lookup and report workflows are selected through the active site profile. Optional deployment services are isolated behind Compose profiles.

NCPass ID lookup intentionally supports Aadhaar, driving licence and pass for both Driver and Passenger. This follows the later project requirement and supersedes the older spreadsheet statement that described it as Aadhaar-only.

## Page and workflow matrix

| Spreadsheet feature | Combined implementation | Audit result |
|---|---|---|
| `login.html` | Shared login; title/logo/auth policy from `SITE_PROFILE` | Pass |
| `layout.html` | Shared layout; configurable branding, logo geometry and cache-busted assets | Pass |
| `home.html` | Shared gettext/i18n three-option menu | Pass |
| `aadhar_lookup.html` | Profile-dispatched all-ID lookup with visitor/ID rule validation | Pass |
| `recognize_person.html` | Shared resilient face-recognition and blacklist interception | Pass |
| `manual_face_verification.html` | Shared comparison and decision workflow | Pass |
| `reregister_face.html` | Shared re-registration review and routing | Pass |
| `known_person.html` | Shared form/API; one common schema and server-side validation | Pass |
| `unknown_person.html` | Shared schema-driven form; validated visitor/ID combinations, ID images and NCPass supplemental-DL rule | Pass |
| `blacklist_alert.html` | Shared acknowledgement/resume/stop workflow | Pass |
| `enroll_blacklisted_person.html` | Shared blacklist collection enrollment with validation and timeouts | Pass |
| `blacklisted_persons_list.html` | Shared deterministic card list and configurable columns | Pass |
| `recognize_vehicle.html` | Profile-selected template and helper | Pass |
| `known_vehicle.html` | Profile-selected fields and shared vehicle persistence layer | Pass |
| `unknown_vehicle.html` | Profile-selected form; NCPass extended metadata retained through Redis/trip flow | Pass |
| `add_trip.html` | Profile-selected trip terminology, duration, permit and passenger behaviour | Pass |
| `trip_summary.html` | Profile-selected summary presentation | Pass |
| End-trip recognition | Shared `/get_unfinished_trips` workflow; redundant compatibility route removed | Pass |
| `close_trip.html` | Profile template with common close backend; optional Ganganagar ANPR worker | Pass |
| `unfinished_trips.html` | Profile template plus common server-side table/query | Pass |
| `report_home.html` | Profile-selected report navigation | Pass |
| `person_report.html` | Profile-selected columns/presentation with shared SQL schema | Pass |
| `trip_report.html` | Profile-selected presentation with common paginated API | Pass |
| `vehicle_report.html` | Profile-selected presentation with common paginated API | Pass |
| `person_lookup.html` | Profile-selected audited markup/helper | Pass |
| `person_lookup_result_list.html` | Profile-selected audited results table | Pass |
| `static-recognize.html` | Profile-selected audited component | Pass |
| `static-recognize-vehicle.html` | Profile-selected audited component | Pass |
| `static_trip_summary.html` | Profile-selected audited component | Pass |
| `401.html`, `404.html`, `500.html` | Profile-selected audited error templates | Pass |

## Backend and deployment matrix

| Capability | Combined implementation | Audit result |
|---|---|---|
| Common SQL/schema | One `sqlCommands.py` and one schema source | Pass |
| Authentication policy | NCPass secure-cookie and single-login behavior shared by every profile | Pass |
| Static cache policy | Shared `asset_url` plus version environment variable | Pass |
| Face threshold/service | `FACE_MATCH_CONFIDENCE` and `FACE_RECOGNITION_SERVICE` environment settings | Pass |
| Report limits | Environment-overridable trip/vehicle row limits | Pass |
| Ganganagar download bundle | Feature-gated CSV/PDF endpoint; empty-report generation tested | Pass |
| Ganganagar automatic close | `auto_close` Compose profile with configurable polling/window and DB credentials | Pass (static/config) |
| NCPass top-report service | `top_report` profile with Kafka/Zookeeper, monitoring and optional image sharing | Pass (static/config) |
| Reverse proxy | `reverse_proxy` profile; certificates are mounted externally and not committed | Pass (config) |
| Bundled DB/Redis | `bundled_infra` profile | Pass (config) |
| ANPR camera counts | Camera profiles support 1, 2, 3 or 6 instances | Pass (config) |
| Cleanup | Container cleanup with configurable retention and corrected image-extension filtering | Pass (static/config) |
| Database/path secrets | DB, Redis, report root and application secret are environment-driven | Pass |

## Test evidence

- Eight repeatable unit/audit tests pass with `python3 -m unittest discover -s tests -v`.
- Python syntax passes for the frontend, auto-close and top-report sources.
- All site templates compile under all four Flask/Jinja profile loaders.
- Audited profile-specific templates and helpers match their four branch snapshots byte-for-byte.
- Every profile imports and registers all required endpoints.
- Docker Compose validates, including `auto_close`, `top_report`, `reverse_proxy`, `bundled_infra` and camera-count profiles.
- Live NCPass login returned HTTP 200 with SM Hill title, 7RR logo and CSRF token.
- Live Redis `PING` and PostgreSQL `SELECT 1` passed.
- An isolated authenticated smoke session tested 21 non-mutating routes for every profile. All returned HTTP 200 or the expected feature-disabled 404.
- Recent live web-service logs contain no traceback or application error after the final smoke matrix.

## External acceptance still required

The audit deliberately did not create, update, blacklist or close real production records. Real camera streams, face enrollment/matching, report sharing, email alerts and TLS certificates require deployment credentials/hardware and should be covered by a controlled site acceptance test.

The running image also warns that Python 3.10 support in the Google client libraries ends on 2026-10-04. Upgrade the web-service image to Python 3.11 or newer before that date.
