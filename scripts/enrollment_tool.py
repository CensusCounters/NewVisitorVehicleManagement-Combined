#!/usr/bin/env python3
"""Offline backup, reset, and collision-safe restore for Visitor & Vehicle enrollments.

Covers:
  - PostgreSQL `persons` and `vehicles`
  - Enrollment images/documents (`known_persons`, `known_vehicles`, `aadhars`,
    `drivers_licenses`, `other_ids`)
  - Milvus `default` face vectors
  - Milvus `blacklist` face vectors and `blacklisted_persons` images

Intended to run during a maintenance window while `webservice`, `fr_engine`,
`cleanup`, and `auto_close` are stopped, leaving PostgreSQL, Milvus, and Redis
running.
"""

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import sys
import tempfile
from urllib.parse import urlsplit
import uuid
import zipfile

psycopg2 = None
sql = None
RealDictCursor = None
Collection = None
connections = None
utility = None


def load_runtime_dependencies() -> None:
    global psycopg2, sql, RealDictCursor, Collection, connections, utility
    if psycopg2 is not None and Collection is not None:
        return
    try:
        import psycopg2 as _psycopg2
        from psycopg2 import sql as _sql
        from psycopg2.extras import RealDictCursor as _RealDictCursor
        from pymilvus import Collection as _Collection, connections as _connections, utility as _utility
    except ModuleNotFoundError as exc:
        raise ToolError(
            f"Missing Python dependency '{exc.name}'. Run this script inside the "
            "`census_counters_webservice_fr` container (rebuild it after updating Dockerfile_webservice)."
        ) from exc
    psycopg2 = _psycopg2
    sql = _sql
    RealDictCursor = _RealDictCursor
    Collection = _Collection
    connections = _connections
    utility = _utility

FORMAT = "census-enrollments"
ARCHIVE_VERSION = 2
SUPPORTED_ARCHIVE_VERSIONS = {1, 2}

DEFAULT_COLLECTION = "default"
BLACKLIST_COLLECTION = "blacklist"

PERSON_FIELDS = (
    "id",
    "created_by",
    "date_created",
    "enrollment_id",
    "person_name",
    "person_image_location",
    "aadhar_number",
    "aadhar_image_location",
    "drivers_license_number",
    "drivers_license_image",
    "gender",
    "vid",
    "dob",
    "guardians_name",
    "address",
    "mobile_number",
    "visiting_person_name",
    "other_id_type",
    "other_id_number",
    "other_id_image_location",
)

VEHICLE_FIELDS = (
    "id",
    "created_by",
    "date_created",
    "vehicle_number_plate",
    "vehicle_image_location",
    "vehicle_make",
    "vehicle_model",
    "vehicle_color",
    "vehicle_type",
    "vehicle_registered_to",
    "vehicle_registration_number",
    "vehicle_owner_id",
)

IMAGE_FIELDS = {
    "persons": {
        "person_image_location": "known_persons",
        "aadhar_image_location": "aadhars",
        "drivers_license_image": "drivers_licenses",
        "other_id_image_location": "other_ids",
    },
    "vehicles": {
        "vehicle_image_location": "known_vehicles",
    },
}

PRIVATE_IMAGE_FOLDERS = {
    "known_persons",
    "known_vehicles",
    "aadhars",
    "drivers_licenses",
    "other_ids",
}
SOURCE_IMAGE_FOLDERS = PRIVATE_IMAGE_FOLDERS | {"anpr_vehicles", "images"}
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf"}
BLACKLIST_EXTENSIONS = {".jpg", ".jpeg", ".png"}
PROVENANCE_FIELDS = {"id", "created_by", "date_created"}
PLACEHOLDER_FILENAMES = {"no-image-available.jpg", "no-image-available.png"}

PERSON_LENGTH_LIMITS = {
    "person_name": 100,
    "person_image_location": 200,
    "aadhar_number": 100,
    "aadhar_image_location": 200,
    "drivers_license_number": 100,
    "drivers_license_image": 200,
    "gender": 20,
    "vid": 100,
    "guardians_name": 100,
    "mobile_number": 100,
    "visiting_person_name": 100,
}

VEHICLE_LENGTH_LIMITS = {
    "vehicle_number_plate": 50,
    "vehicle_image_location": 200,
    "vehicle_make": 50,
    "vehicle_model": 50,
    "vehicle_color": 50,
    "vehicle_type": 50,
    "vehicle_registered_to": 50,
    "vehicle_registration_number": 50,
}


class ToolError(RuntimeError):
    """Expected operational or validation error."""


def default_project_path() -> Path:
    env_path = os.environ.get("PROJECT_BASE_PATH")
    if env_path:
        return Path(env_path).resolve()
    container_path = Path("/project/finalfrsproject")
    if container_path.exists():
        return container_path.resolve()
    return (Path(__file__).resolve().parent.parent / "src" / "frontend" / "finalfrsproject").resolve()


def static_root(project_path: Path) -> Path:
    return (project_path / "static").resolve()


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(value) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def normalized(value) -> str:
    return re.sub(r"[\s-]+", "", str(value or "")).upper()


def sanitize_filename(value: str, max_length: int = 80) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return (cleaned or "unknown")[:max_length]


def safe_relative_subpath(relative: str, allowed_roots: set[str]) -> bool:
    if not relative or relative.startswith("/") or "\\" in relative:
        return False
    parts = PurePosixPath(relative).parts
    if not parts or parts[0] not in allowed_roots:
        return False
    return all(part not in {"", ".", ".."} for part in parts)


def write_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, default=str, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def pg_connection():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRESQL_URL", "census_counters_postgres_db"),
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ.get("DB_NAME", "postgres_visitor_vehicle"),
        user=os.environ.get("DB_USER_NAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", "postgres"),
        connect_timeout=10,
    )
    try:
        yield conn
    finally:
        conn.close()


class MilvusStore:
    def __init__(self, uri: str):
        self.alias = f"enrollment-tool-{os.getpid()}"
        connections.connect(alias=self.alias, uri=uri, timeout=30)
        self.collections: dict[str, Collection] = {}
        for name in (DEFAULT_COLLECTION, BLACKLIST_COLLECTION):
            if not utility.has_collection(name, using=self.alias):
                raise ToolError(
                    f"Milvus collection '{name}' is missing; start census_counters_fr_engine once first to initialize collections."
                )
            col = Collection(name, using=self.alias)
            fields = {f.name: f for f in col.schema.fields}
            if (
                set(fields) != {"id", "guid", "vector", "aadhaar", "name"}
                or fields["vector"].params.get("dim") != 512
                or not col.schema.auto_id
            ):
                raise ToolError(f"Unsupported Milvus schema on collection '{name}'.")
            col.load(timeout=60)
            self.collections[name] = col

    def close(self) -> None:
        connections.disconnect(self.alias)

    def count(self, name: str) -> int:
        col = self.collections[name]
        rows = col.query(expr="id >= 0", output_fields=["id"], consistency_level="Strong", timeout=60)
        return len(rows)

    def rows(self, name: str):
        col = self.collections[name]
        iterator = col.query_iterator(
            batch_size=500,
            expr="id >= 0",
            output_fields=["guid", "vector", "name", "aadhaar"],
            consistency_level="Strong",
            timeout=60,
        )
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                for r in batch:
                    yield {
                        "guid": str(r["guid"]),
                        "vector": [float(v) for v in r["vector"]],
                        "name": str(r["name"] or ""),
                        "aadhaar": str(r["aadhaar"] or ""),
                    }
        finally:
            iterator.close()

    def delete_guids(self, name: str, guids: list[str]) -> None:
        col = self.collections[name]
        for start in range(0, len(guids), 200):
            col.delete(expr="guid in " + json.dumps(guids[start : start + 200]), timeout=60)

    def clear_all(self, name: str) -> int:
        col = self.collections[name]
        iterator = col.query_iterator(
            batch_size=500,
            expr="id >= 0",
            output_fields=["id"],
            consistency_level="Strong",
            timeout=60,
        )
        ids = []
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                ids.extend(r["id"] for r in batch)
        finally:
            iterator.close()
        for start in range(0, len(ids), 500):
            col.delete(expr="id in " + json.dumps(ids[start : start + 500]), timeout=60)
        col.flush(timeout=120)
        return len(ids)

    def insert_rows(self, name: str, rows: list[dict]) -> None:
        col = self.collections[name]
        for start in range(0, len(rows), 200):
            col.insert(rows[start : start + 200], timeout=60)

    def flush(self, name: str) -> None:
        self.collections[name].flush(timeout=120)


def ensure_pg_schema(conn) -> None:
    with conn.cursor() as cur:
        for table, expected in (("persons", PERSON_FIELDS), ("vehicles", VEHICLE_FIELDS)):
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                (table,),
            )
            actual = {r[0] for r in cur.fetchall()}
            if actual != set(expected):
                raise ToolError(
                    f"PostgreSQL table '{table}' columns {sorted(actual)} differ from expected {sorted(expected)}."
                )


def snapshot_pg(conn) -> dict[str, list[dict]]:
    result = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for table, fields in (("persons", PERSON_FIELDS), ("vehicles", VEHICLE_FIELDS)):
            cur.execute(
                sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                    sql.SQL(",").join(map(sql.Identifier, fields)),
                    sql.Identifier(table),
                )
            )
            result[table] = [dict(r) for r in cur.fetchall()]
    return result


def resolve_source_image(project_path: Path, value: str) -> Path:
    static = static_root(project_path)
    raw = urlsplit(str(value)).path
    marker = raw.find("/static/")
    if marker < 0:
        raise ToolError(f"Unsupported image path (missing /static/): {value}")
    relative = raw[marker + len("/static/") :]
    if not safe_relative_subpath(relative, SOURCE_IMAGE_FOLDERS):
        raise ToolError(f"Image path outside supported directories: {value}")
    candidate = static / relative
    if not candidate.is_symlink() and candidate.resolve().is_relative_to(static) and candidate.is_file():
        return candidate
    # Vehicles can store a historic capture path after promotion to known_vehicles.
    fallback = static / "known_vehicles" / Path(relative).name
    if not fallback.is_symlink() and fallback.resolve().is_relative_to(static) and fallback.is_file():
        return fallback
    raise ToolError(f"Referenced file does not exist on disk: {value}")


def resolve_destination_image(project_path: Path, archive_name: str, allowed_roots: set[str]) -> Path:
    if not archive_name.startswith("images/"):
        raise ToolError(f"Invalid archive image path: {archive_name}")
    relative = archive_name[len("images/") :]
    if not safe_relative_subpath(relative, allowed_roots):
        raise ToolError(f"Unsafe image destination: {archive_name}")
    static = static_root(project_path)
    dest = static / relative
    if dest.is_symlink() or not dest.resolve().is_relative_to(static):
        raise ToolError(f"Image destination escapes static directory: {archive_name}")
    return dest


def atomic_copy_from_zip(zf: zipfile.ZipFile, src_member: str, dest: Path, expected_sha256: str) -> bool:
    """Copy a zip member to dest atomically. Returns True if newly written, False if identical file already existed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if digest_file(dest) != expected_sha256:
            raise ToolError(f"Existing file differs at {dest}")
        return False

    token = hashlib.sha256(str(dest).encode("utf-8")).hexdigest()[:16]
    temp = dest.with_name(f".enrollment-tool-{token}.partial")
    if temp.is_symlink():
        raise ToolError(f"Unsafe staging path: {temp}")
    temp.unlink(missing_ok=True)
    try:
        with temp.open("xb") as out:
            with zf.open(src_member) as src:
                shutil.copyfileobj(src, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        if digest_file(temp) != expected_sha256:
            raise ToolError(f"Checksum mismatch while restoring {src_member}")
        temp.replace(dest)
        fsync_dir(dest.parent)
        return True
    finally:
        temp.unlink(missing_ok=True)


def face_vector_bytes(vector: list[float]) -> bytes:
    return b"".join(struct.pack("<f", float(v)) for v in vector)


def default_face_fingerprint(row: dict, ignore_aadhaar: bool = True) -> str:
    meta = [row["guid"], row["name"]] if ignore_aadhaar else [row["guid"], row["name"], row["aadhaar"]]
    return hashlib.sha256(
        json.dumps(meta, ensure_ascii=True).encode("utf-8") + face_vector_bytes(row["vector"])
    ).hexdigest()


def blacklist_face_fingerprint(row: dict) -> str:
    return hashlib.sha256(
        json.dumps([row["guid"], row["name"], row["aadhaar"]], ensure_ascii=True).encode("utf-8")
        + face_vector_bytes(row["vector"])
    ).hexdigest()


def match_blacklist_image(files: list[str], row: dict) -> str | None:
    """Match blacklist image filename using the same precedence as blacklist_alert_helper.py."""
    guid = str(row.get("guid") or "").strip()
    aadhaar = str(row.get("aadhaar") or "").strip()
    safe_name = sanitize_filename(str(row.get("name") or ""))

    if guid:
        for fname in files:
            if fname.startswith(f"{guid}_"):
                return fname
    if aadhaar:
        for fname in files:
            root, _ = os.path.splitext(fname)
            if root.endswith(f"_{aadhaar}"):
                return fname
    if safe_name:
        for fname in files:
            if f"_{safe_name}_" in fname:
                return fname
    return None


def validate_archive(path: Path, expected_model: str, max_bytes: int) -> dict:
    if not path.is_file():
        raise ToolError(f"Archive not found: {path}")
    if path.stat().st_size > max_bytes:
        raise ToolError(f"Compressed archive exceeds max size limit ({max_bytes} bytes).")

    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        names = [i.filename for i in infos]
        if len(names) > 100000 or len(set(names)) != len(names):
            raise ToolError("Duplicate or excessive archive entries.")
        if sum(i.file_size for i in infos) > max_bytes:
            raise ToolError(f"Expanded archive exceeds max size limit ({max_bytes} bytes).")
        for i in infos:
            if not i.filename or i.is_dir() or stat.S_ISLNK(i.external_attr >> 16) or (i.flag_bits & 1):
                raise ToolError(f"Unsafe or unsupported archive entry: {i.filename}")
            if i.filename.startswith("/") or "\\" in i.filename or ".." in PurePosixPath(i.filename).parts:
                raise ToolError(f"Unsafe archive path: {i.filename}")

        if "manifest.json" not in names:
            raise ToolError("Archive missing manifest.json.")
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("format") != FORMAT or manifest.get("version") not in SUPPORTED_ARCHIVE_VERSIONS:
            raise ToolError(f"Unsupported dataset format/version: {manifest.get('format')} v{manifest.get('version')}")
        if manifest.get("embedding_model") != expected_model:
            raise ToolError(
                f"Embedding model mismatch: archive has '{manifest.get('embedding_model')}', "
                f"system expects '{expected_model}'."
            )

        files = manifest["files"]
        required_meta = {"persons.json", "vehicles.json", "faces.jsonl"}
        if manifest["version"] >= 2:
            required_meta |= {"blacklist_faces.jsonl", "blacklist_manifest.json"}
        if set(files) != set(names) - {"manifest.json"} or not required_meta <= set(files):
            raise ToolError("Manifest file list does not match archive contents.")

        for name, entry in files.items():
            if name not in required_meta and not name.startswith("images/"):
                raise ToolError(f"Unexpected archive file: {name}")
            h = hashlib.sha256()
            with zf.open(name) as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != entry["sha256"] or zf.getinfo(name).file_size != entry["bytes"]:
                raise ToolError(f"Checksum or size mismatch for {name}")

        people = json.loads(zf.read("persons.json"))
        vehicles = json.loads(zf.read("vehicles.json"))
        if not isinstance(people, list) or not isinstance(vehicles, list):
            raise ToolError("persons.json and vehicles.json must be JSON lists.")

        person_ids: set[int] = set()
        person_guids: set[str] = set()
        used_images: set[str] = set()

        for row in people:
            if not isinstance(row, dict) or set(row) != set(PERSON_FIELDS):
                raise ToolError("Invalid person record columns.")
            if type(row["id"]) is not int or row["id"] in person_ids:
                raise ToolError("Invalid or duplicate person ID in archive.")
            person_ids.add(row["id"])

            guid = str(uuid.UUID(str(row["enrollment_id"])))
            if guid != row["enrollment_id"] or guid in person_guids or not row["person_name"]:
                raise ToolError(f"Invalid or duplicate enrollment_id: {row.get('enrollment_id')}")
            if row["person_image_location"] != f"/static/known_persons/{guid}.png":
                raise ToolError(f"Unexpected person_image_location for {guid}: {row['person_image_location']}")
            person_guids.add(guid)

            for field, folder in IMAGE_FIELDS["persons"].items():
                val = row[field]
                if val is None:
                    if field == "person_image_location":
                        raise ToolError(f"Missing required person_image_location for {guid}")
                    continue
                prefix = f"/static/{folder}/"
                if not isinstance(val, str) or not val.startswith(prefix) or "/" in val[len(prefix) :]:
                    raise ToolError(f"Invalid image reference {field}={val}")
                if PurePosixPath(val).suffix.lower() not in ALLOWED_EXTENSIONS:
                    raise ToolError(f"Unsupported image extension: {val}")
                img_entry = "images/" + val[len("/static/") :]
                if img_entry not in files:
                    raise ToolError(f"Missing referenced image in archive: {img_entry}")
                used_images.add(img_entry)

            for f, limit in PERSON_LENGTH_LIMITS.items():
                if row[f] is not None and len(str(row[f])) > limit:
                    raise ToolError(f"Person field {f} exceeds max length {limit}")

        vehicle_ids: set[int] = set()
        for row in vehicles:
            if not isinstance(row, dict) or set(row) != set(VEHICLE_FIELDS):
                raise ToolError("Invalid vehicle record columns.")
            if type(row["id"]) is not int or row["id"] in vehicle_ids:
                raise ToolError("Invalid or duplicate vehicle ID in archive.")
            vehicle_ids.add(row["id"])
            if type(row["vehicle_owner_id"]) is not int or row["vehicle_owner_id"] not in person_ids:
                raise ToolError(f"Vehicle {row['id']} references unknown owner {row['vehicle_owner_id']}")
            val = row["vehicle_image_location"]
            if not isinstance(val, str) or not val.startswith("/static/known_vehicles/") or "/" in val[len("/static/known_vehicles/") :]:
                raise ToolError(f"Invalid vehicle_image_location: {val}")
            if PurePosixPath(val).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise ToolError(f"Unsupported vehicle image extension: {val}")
            img_entry = "images/" + val[len("/static/") :]
            if img_entry not in files:
                raise ToolError(f"Missing referenced vehicle image in archive: {img_entry}")
            used_images.add(img_entry)
            for f, limit in VEHICLE_LENGTH_LIMITS.items():
                if row[f] is not None and len(str(row[f])) > limit:
                    raise ToolError(f"Vehicle field {f} exceeds max length {limit}")

        # Validate default faces
        default_faces_by_guid: dict[str, list[dict]] = defaultdict(list)
        default_face_count = 0
        with zf.open("faces.jsonl") as f:
            for raw in f:
                row = json.loads(raw)
                if set(row) != {"guid", "vector", "name", "aadhaar"} or row["guid"] not in person_guids:
                    raise ToolError(f"Invalid or orphaned face record in faces.jsonl: {row.get('guid')}")
                vec = row["vector"]
                if not isinstance(vec, list) or len(vec) != 512 or any(type(v) not in (float, int) or not math.isfinite(v) for v in vec):
                    raise ToolError(f"Invalid 512-dim vector for {row['guid']}")
                default_faces_by_guid[row["guid"]].append(row)
                default_face_count += 1

        if set(default_faces_by_guid) != person_guids:
            missing = sorted(person_guids - set(default_faces_by_guid))
            raise ToolError(f"Some persons in archive have no face vector: {missing[:5]}")

        # Validate blacklist (if v2)
        blacklist_faces: list[dict] = []
        blacklist_map: dict[str, str] = {}
        if manifest["version"] >= 2:
            blacklist_map = json.loads(zf.read("blacklist_manifest.json"))
            if not isinstance(blacklist_map, dict):
                raise ToolError("blacklist_manifest.json must be a JSON object.")
            bl_guids: set[str] = set()
            with zf.open("blacklist_faces.jsonl") as f:
                for raw in f:
                    row = json.loads(raw)
                    if set(row) != {"guid", "vector", "name", "aadhaar"}:
                        raise ToolError("Invalid blacklist face record schema.")
                    vec = row["vector"]
                    if not isinstance(vec, list) or len(vec) != 512 or any(type(v) not in (float, int) or not math.isfinite(v) for v in vec):
                        raise ToolError(f"Invalid 512-dim blacklist vector for {row['guid']}")
                    guid = str(row["guid"])
                    img_entry = blacklist_map.get(guid)
                    if not img_entry or not img_entry.startswith("images/blacklisted_persons/") or img_entry not in files:
                        raise ToolError(f"Missing blacklist image entry for {guid}: {img_entry}")
                    if "/" in img_entry[len("images/blacklisted_persons/") :]:
                        raise ToolError(f"Invalid blacklist image path: {img_entry}")
                    used_images.add(img_entry)
                    bl_guids.add(guid)
                    blacklist_faces.append(row)
            if set(blacklist_map) != bl_guids:
                raise ToolError("blacklist_manifest.json keys do not match blacklist_faces.jsonl.")

        archive_images = {n for n in files if n.startswith("images/")}
        if used_images != archive_images:
            extra = sorted(archive_images - used_images)
            raise ToolError(f"Archive contains unreferenced images: {extra[:5]}")

        expected_counts = {
            "persons": len(people),
            "vehicles": len(vehicles),
            "faces": default_face_count,
        }
        if manifest["version"] >= 2:
            expected_counts["blacklist_faces"] = len(blacklist_faces)
        if manifest.get("counts") != expected_counts:
            raise ToolError(f"Manifest counts {manifest.get('counts')} do not match {expected_counts}")

    return {
        "manifest": manifest,
        "persons": people,
        "vehicles": vehicles,
        "files": files,
        "default_faces_by_guid": dict(default_faces_by_guid),
        "blacklist_faces": blacklist_faces,
        "blacklist_map": blacklist_map,
    }


def write_report(report_path: Path | None, report: dict) -> None:
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(report_path, report)
        print(f"Report written to: {report_path}")


def cmd_save(args) -> int:
    project_path = default_project_path()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    embedding_model = args.embedding_model or os.environ.get("ENROLLMENT_EMBEDDING_MODEL", "auraface_glintr100")
    max_bytes = int(os.environ.get("ENROLLMENT_MAX_BYTES", str(512 * 1024 * 1024)))

    integrity_issues: list[dict] = []

    def add_issue(entity: str, reason: str, **details):
        integrity_issues.append({"entity": entity, "reason": reason, **details})

    milvus = MilvusStore(args.milvus_uri)
    try:
        with pg_connection() as conn:
            ensure_pg_schema(conn)
            pg_data = snapshot_pg(conn)

        default_rows = list(milvus.rows(DEFAULT_COLLECTION))
        blacklist_rows = list(milvus.rows(BLACKLIST_COLLECTION))
    finally:
        milvus.close()

    default_by_guid: dict[str, list[dict]] = defaultdict(list)
    for r in default_rows:
        default_by_guid[r["guid"]].append(r)

    pg_person_guids = {str(p["enrollment_id"]) for p in pg_data["persons"]}
    for guid in sorted(set(default_by_guid) - pg_person_guids):
        add_issue(
            "orphan_default_face",
            "Facial vector in Milvus 'default' collection has no matching PostgreSQL person row.",
            guid=guid,
            vector_count=len(default_by_guid[guid]),
        )

    with tempfile.TemporaryDirectory(prefix="enrollment-save-") as tmp:
        work = Path(tmp)
        valid_persons: list[dict] = []
        valid_person_ids: set[int] = set()
        skipped_person_ids: set[int] = set()
        valid_person_guids: set[str] = set()

        # 1. Persons & their documents + default vectors
        for person in pg_data["persons"]:
            pid = person["id"]
            guid = str(person["enrollment_id"])
            person_copy = json.loads(json.dumps(person, default=str))
            person_issues = []

            if guid not in default_by_guid:
                person_issues.append(("missing_face_vector", "person_image_location", None, "No facial vector in Milvus 'default' collection."))

            staged_copies: list[tuple[Path, Path]] = []
            for field, folder in IMAGE_FIELDS["persons"].items():
                val = person_copy[field]
                if not val:
                    if field == "person_image_location":
                        person_issues.append(("missing_db_image", field, val, "person_image_location is empty."))
                    continue
                try:
                    src = resolve_source_image(project_path, val)
                except ToolError as exc:
                    person_issues.append(("missing_file", field, val, str(exc)))
                    continue
                filename = f"{guid}.png" if field == "person_image_location" else src.name
                dest = work / "images" / folder / filename
                if dest.exists() and digest_file(dest) != digest_file(src):
                    person_issues.append(("filename_conflict", field, val, f"Conflicting destination filename {dest.name}"))
                    continue
                staged_copies.append((src, dest))
                person_copy[field] = f"/static/{folder}/{filename}"

            if person_issues:
                for kind, field, path_val, reason in person_issues:
                    add_issue(
                        "person",
                        reason,
                        issue_type=kind,
                        person_id=pid,
                        enrollment_id=guid,
                        person_name=person.get("person_name"),
                        field=field,
                        path=path_val,
                    )
                skipped_person_ids.add(pid)
                continue

            for src, dest in staged_copies:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
            valid_persons.append(person_copy)
            valid_person_ids.add(pid)
            valid_person_guids.add(guid)

        # 2. Vehicles
        valid_vehicles: list[dict] = []
        for vehicle in pg_data["vehicles"]:
            vid = vehicle["id"]
            owner_id = vehicle["vehicle_owner_id"]
            if owner_id in skipped_person_ids or owner_id not in valid_person_ids:
                add_issue(
                    "vehicle",
                    "Owner person was skipped due to an integrity issue.",
                    issue_type="skipped_owner",
                    vehicle_id=vid,
                    plate=vehicle.get("vehicle_number_plate"),
                    owner_id=owner_id,
                )
                continue
            vehicle_copy = json.loads(json.dumps(vehicle, default=str))
            val = vehicle_copy["vehicle_image_location"]
            if not val:
                add_issue(
                    "vehicle",
                    "vehicle_image_location is empty.",
                    issue_type="missing_db_image",
                    vehicle_id=vid,
                    plate=vehicle.get("vehicle_number_plate"),
                    owner_id=owner_id,
                )
                continue
            try:
                src = resolve_source_image(project_path, val)
            except ToolError as exc:
                add_issue(
                    "vehicle",
                    str(exc),
                    issue_type="missing_file",
                    vehicle_id=vid,
                    plate=vehicle.get("vehicle_number_plate"),
                    owner_id=owner_id,
                    path=val,
                )
                continue
            dest = work / "images" / "known_vehicles" / src.name
            if dest.exists() and digest_file(dest) != digest_file(src):
                add_issue(
                    "vehicle",
                    f"Conflicting destination vehicle image filename {src.name}",
                    issue_type="filename_conflict",
                    vehicle_id=vid,
                    plate=vehicle.get("vehicle_number_plate"),
                    path=val,
                )
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            vehicle_copy["vehicle_image_location"] = f"/static/known_vehicles/{src.name}"
            valid_vehicles.append(vehicle_copy)

        # 3. Blacklist vectors + images
        bl_folder = static_root(project_path) / "blacklisted_persons"
        bl_files = (
            sorted(
                f
                for f in os.listdir(bl_folder)
                if not (bl_folder / f).is_symlink()
                and (bl_folder / f).is_file()
                and Path(f).suffix.lower() in BLACKLIST_EXTENSIONS
            )
            if bl_folder.is_dir()
            else []
        )
        valid_blacklist_faces: list[dict] = []
        blacklist_manifest: dict[str, str] = {}
        matched_bl_files: set[str] = set()

        for row in blacklist_rows:
            guid = row["guid"]
            fname = match_blacklist_image(bl_files, row)
            if not fname:
                add_issue(
                    "blacklist",
                    "No matching image found in static/blacklisted_persons/ for blacklist Milvus vector.",
                    issue_type="missing_file",
                    guid=guid,
                    name=row.get("name"),
                    aadhaar=row.get("aadhaar"),
                )
                continue
            src = bl_folder / fname
            dest = work / "images" / "blacklisted_persons" / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copyfile(src, dest)
            matched_bl_files.add(fname)
            blacklist_manifest[guid] = f"images/blacklisted_persons/{fname}"
            valid_blacklist_faces.append(row)

        for fname in sorted(set(bl_files) - matched_bl_files):
            add_issue(
                "orphan_blacklist_image",
                "Image in static/blacklisted_persons/ has no matching Milvus 'blacklist' vector.",
                issue_type="orphan_file",
                path=f"/static/blacklisted_persons/{fname}",
            )

        report = {
            "operation": "save",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "output_archive": str(output),
            "skip_invalid": bool(args.skip_invalid),
            "exported_counts": {
                "persons": len(valid_persons),
                "vehicles": len(valid_vehicles),
                "faces": sum(len(default_by_guid[g]) for g in valid_person_guids),
                "blacklist_faces": len(valid_blacklist_faces),
            },
            "integrity_issue_count": len(integrity_issues),
            "integrity_issues": integrity_issues,
        }

        if integrity_issues and not args.skip_invalid:
            write_report(Path(args.report) if args.report else None, report)
            print(
                f"ERROR: Found {len(integrity_issues)} integrity issue(s). "
                "Re-run with --skip-invalid to warn, skip affected items, and export valid records.",
                file=sys.stderr,
            )
            for issue in integrity_issues:
                print(f"  - [{issue['entity']}] {issue['reason']} ({issue})", file=sys.stderr)
            return 2

        if integrity_issues:
            print(f"WARNING: Skipping {len(integrity_issues)} integrity issue(s):", file=sys.stderr)
            for issue in integrity_issues:
                print(f"  - [{issue['entity']}] {issue['reason']} ({issue})", file=sys.stderr)

        # Write metadata & archive
        write_json(work / "persons.json", valid_persons)
        write_json(work / "vehicles.json", valid_vehicles)
        face_count = 0
        with (work / "faces.jsonl").open("w", encoding="utf-8") as f:
            for person in valid_persons:
                for face_row in default_by_guid[str(person["enrollment_id"])]:
                    f.write(json.dumps(face_row, allow_nan=False) + "\n")
                    face_count += 1
            f.flush()
            os.fsync(f.fileno())

        with (work / "blacklist_faces.jsonl").open("w", encoding="utf-8") as f:
            for row in valid_blacklist_faces:
                f.write(json.dumps(row, allow_nan=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        write_json(work / "blacklist_manifest.json", blacklist_manifest)

        entries = {}
        for p in sorted(work.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                entries[p.relative_to(work).as_posix()] = {
                    "sha256": digest_file(p),
                    "bytes": p.stat().st_size,
                }
        manifest = {
            "format": FORMAT,
            "version": ARCHIVE_VERSION,
            "embedding_model": embedding_model,
            "counts": {
                "persons": len(valid_persons),
                "vehicles": len(valid_vehicles),
                "faces": face_count,
                "blacklist_faces": len(valid_blacklist_faces),
            },
            "skipped_integrity_count": len(integrity_issues),
            "files": entries,
        }
        write_json(work / "manifest.json", manifest)

        partial = output.with_suffix(output.suffix + ".partial")
        partial.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                zf.write(work / "manifest.json", "manifest.json")
                for name in entries:
                    zf.write(work / name, name)
            validate_archive(partial, embedding_model, max_bytes)
            with partial.open("rb") as f:
                os.fsync(f.fileno())
            partial.replace(output)
            fsync_dir(output.parent)
        finally:
            partial.unlink(missing_ok=True)

    write_report(Path(args.report) if args.report else None, report)
    print(
        f"Saved archive {output}: "
        f"{report['exported_counts']['persons']} persons, "
        f"{report['exported_counts']['vehicles']} vehicles, "
        f"{report['exported_counts']['faces']} default faces, "
        f"{report['exported_counts']['blacklist_faces']} blacklist faces "
        f"(skipped integrity issues: {len(integrity_issues)})."
    )
    return 0


def clear_directory_contents(folder: Path, preserve_names: set[str]) -> int:
    if not folder.is_dir():
        return 0
    removed = 0
    for item in list(folder.iterdir()):
        if item.name.lower() in preserve_names or item.name.startswith("."):
            continue
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
            removed += 1
        else:
            item.unlink()
            removed += 1
    return removed


def cmd_reset(args) -> int:
    if args.confirm != "RESET":
        raise ToolError("Refusing reset: pass --confirm RESET to proceed.")

    wipe_history = args.wipe_history or args.all
    wipe_blacklist = args.wipe_blacklist or args.all
    project_path = default_project_path()
    static = static_root(project_path)

    with pg_connection() as conn:
        ensure_pg_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT (SELECT count(*) FROM persons), "
                "(SELECT count(*) FROM vehicles), "
                "(SELECT count(*) FROM trips), "
                "(SELECT count(*) FROM passes), "
                "(SELECT count(*) FROM anpr_vehicle_readings)"
            )
            p_cnt, v_cnt, t_cnt, pass_cnt, anpr_cnt = cur.fetchone()

    milvus = MilvusStore(args.milvus_uri)
    try:
        default_cnt = milvus.count(DEFAULT_COLLECTION)
        blacklist_cnt = milvus.count(BLACKLIST_COLLECTION)
    finally:
        milvus.close()

    print("Current system state:")
    print(f"  PostgreSQL: persons={p_cnt}, vehicles={v_cnt}, trips={t_cnt}, passes={pass_cnt}, anpr_readings={anpr_cnt}")
    print(f"  Milvus:     default={default_cnt}, blacklist={blacklist_cnt}")
    print(f"  Options:    wipe_history={wipe_history}, wipe_blacklist={wipe_blacklist}")

    if (t_cnt or pass_cnt or anpr_cnt) and not wipe_history:
        raise ToolError(
            "Dependent history exists (trips/passes/anpr_vehicle_readings). "
            "Pass --wipe-history (or --all) to confirm wiping history as well."
        )

    if not args.yes:
        reply = input("Type 'RESET' to permanently erase the selected data: ").strip()
        if reply != "RESET":
            raise ToolError("Reset aborted by operator.")

    if args.backup_first:
        save_args = argparse.Namespace(
            output=args.backup_first,
            skip_invalid=args.backup_skip_invalid,
            report=None,
            embedding_model=None,
            milvus_uri=args.milvus_uri,
        )
        rc = cmd_save(save_args)
        if rc != 0:
            raise ToolError("Pre-reset backup failed; aborting reset.")

    # 1. PostgreSQL wipe
    with pg_connection() as conn:
        with conn, conn.cursor() as cur:
            if wipe_history:
                cur.execute("DELETE FROM trips")
                cur.execute("DELETE FROM passes")
                cur.execute("DELETE FROM anpr_vehicle_readings")
            cur.execute("DELETE FROM vehicles")
            cur.execute("DELETE FROM persons")
            tables_to_reset = ["vehicles", "persons"] + (
                ["trips", "passes", "anpr_vehicle_readings"] if wipe_history else []
            )
            for table in tables_to_reset:
                cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)", (table,))

    # 2. Milvus wipe
    milvus = MilvusStore(args.milvus_uri)
    try:
        deleted_default = milvus.clear_all(DEFAULT_COLLECTION)
        deleted_blacklist = milvus.clear_all(BLACKLIST_COLLECTION) if wipe_blacklist else 0
    finally:
        milvus.close()

    # 3. Filesystem wipe
    folders = list(PRIVATE_IMAGE_FOLDERS) + ["images/uploads"]
    if wipe_history:
        folders += ["passes", "permit_images"]
    if wipe_blacklist:
        folders += ["blacklisted_persons"]

    removed_files = 0
    for rel in folders:
        removed_files += clear_directory_contents(static / rel, PLACEHOLDER_FILENAMES)

    # 4. Redis flush
    if not args.keep_redis:
        try:
            import redis

            redis_url = os.environ.get("REDIS_URL", "redis://census_counters_redis:6379/0")
            client = redis.Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
            client.flushdb()
            client.close()
        except Exception as exc:
            print(f"WARNING: Could not flush Redis ({exc}); flush manually if needed.", file=sys.stderr)

    print(
        f"Reset complete. Cleared Milvus default={deleted_default}, blacklist={deleted_blacklist}, "
        f"removed {removed_files} file/dir entries. User accounts were preserved."
    )
    return 0


def document_keys(row: dict) -> list[tuple]:
    keys = []
    for field in ("aadhar_number", "drivers_license_number"):
        if row.get(field):
            keys.append((field, normalized(row[field])))
    if row.get("other_id_type") and row.get("other_id_number"):
        keys.append(("other_id", row["other_id_type"].strip().casefold(), normalized(row["other_id_number"])))
    return keys


def sql_unique_keys(row: dict) -> list[tuple]:
    constraints = [
        ("enrollment_id",),
        ("person_image_location",),
        ("aadhar_number",),
        ("drivers_license_number",),
        ("drivers_license_image",),
        ("other_id_type", "other_id_number"),
        ("other_id_number", "other_id_image_location"),
    ]
    return [
        (fields, tuple(str(row[f]) for f in fields))
        for fields in constraints
        if all(row.get(f) is not None for f in fields)
    ]


def business_fields(row: dict, table: str) -> dict:
    result = {k: v for k, v in row.items() if k not in PROVENANCE_FIELDS and k not in IMAGE_FIELDS[table]}
    for field in (
        "aadhar_number",
        "drivers_license_number",
        "other_id_number",
        "vehicle_number_plate",
        "vehicle_registration_number",
    ):
        if field in result and result[field]:
            result[field] = normalized(result[field])
    return json.loads(json.dumps(result, default=str))


def resolve_actor_id(conn, explicit_id: int | None) -> int:
    with conn.cursor() as cur:
        if explicit_id is not None:
            cur.execute("SELECT id FROM users WHERE id=%s", (explicit_id,))
            row = cur.fetchone()
            if not row:
                raise ToolError(f"Specified --actor-id {explicit_id} does not exist in users.")
            return int(row[0])
        cur.execute("SELECT id FROM users WHERE lower(user_type) = 'admin' ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row:
            return int(row[0])
        cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise ToolError("No users exist in PostgreSQL 'users' table to attribute created_by.")
        return int(row[0])


def cmd_restore(args) -> int:
    project_path = default_project_path()
    archive_path = Path(args.archive).resolve()
    embedding_model = args.embedding_model or os.environ.get("ENROLLMENT_EMBEDDING_MODEL", "auraface_glintr100")
    max_bytes = int(os.environ.get("ENROLLMENT_MAX_BYTES", str(512 * 1024 * 1024)))

    data = validate_archive(archive_path, embedding_model, max_bytes)
    files_meta = data["files"]

    summary = {
        "imported": {"persons": 0, "vehicles": 0, "default_faces": 0, "blacklist_faces": 0},
        "skipped": {"persons": 0, "vehicles": 0, "blacklist_faces": 0},
        "repaired": {
            "persons": 0,
            "vehicles": 0,
            "default_faces": 0,
            "blacklist_images": 0,
            "blacklist_faces": 0,
        },
        "collisions": [],
    }

    def record_collision(entity: str, identity, reason: str, **extra):
        entry = {"entity": entity, "identity": identity, "reason": reason, **extra}
        summary["collisions"].append(entry)
        if args.on_conflict == "abort":
            raise ToolError(f"Collision on {entity} '{identity}': {reason}")

    milvus = MilvusStore(args.milvus_uri)
    try:
        with pg_connection() as conn:
            ensure_pg_schema(conn)
            actor_id = resolve_actor_id(conn, args.actor_id)
            existing = snapshot_pg(conn)
            local_default_rows = list(milvus.rows(DEFAULT_COLLECTION))
            local_blacklist_rows = list(milvus.rows(BLACKLIST_COLLECTION))

            # Build lookup indexes from current state
            people_by_guid: dict[str, list[dict]] = defaultdict(list)
            local_doc_keys: dict[tuple, set[str]] = defaultdict(set)
            local_sql_keys: dict[tuple, set[str]] = defaultdict(set)
            for row in existing["persons"]:
                guid = str(row["enrollment_id"])
                people_by_guid[guid].append(row)
                for k in document_keys(row):
                    local_doc_keys[k].add(guid)
                for k in sql_unique_keys(row):
                    local_sql_keys[k].add(guid)

            incoming_doc_keys: dict[tuple, set[str]] = defaultdict(set)
            for row in data["persons"]:
                for k in document_keys(row):
                    incoming_doc_keys[k].add(row["enrollment_id"])

            local_default_by_guid: dict[str, list[dict]] = defaultdict(list)
            for r in local_default_rows:
                local_default_by_guid[r["guid"]].append(r)

            local_blacklist_by_guid: dict[str, list[dict]] = defaultdict(list)
            for r in local_blacklist_rows:
                local_blacklist_by_guid[r["guid"]].append(r)

            local_plates: dict[str, list[dict]] = defaultdict(list)
            for row in existing["vehicles"]:
                local_plates[normalized(row["vehicle_number_plate"])].append(row)
            source_plate_counts = Counter(normalized(r["vehicle_number_plate"]) for r in data["vehicles"])

            person_id_map: dict[int, int] = {}
            digest_cache: dict[Path, str] = {}

            def cached_digest(p: Path) -> str:
                if p not in digest_cache:
                    digest_cache[p] = digest_file(p)
                return digest_cache[p]

            with zipfile.ZipFile(archive_path) as zf:
                # --- 1. Restore Persons one by one ---
                for src_person in data["persons"]:
                    guid = src_person["enrollment_id"]
                    src_id = src_person["id"]
                    incoming_faces = data["default_faces_by_guid"][guid]
                    incoming_face_fps = Counter(default_face_fingerprint(r) for r in incoming_faces)

                    doc_collisions = any(
                        (local_doc_keys[k] | incoming_doc_keys[k]) - {guid} for k in document_keys(src_person)
                    )
                    if doc_collisions:
                        record_collision("person", guid, "Identity document number belongs to another enrollment GUID.")
                        continue

                    candidates = people_by_guid.get(guid, [])
                    if len(candidates) > 1:
                        record_collision("person", guid, "Multiple existing local person rows share this GUID.")
                        continue

                    if candidates:
                        local = candidates[0]
                        if business_fields(local, "persons") != business_fields(src_person, "persons"):
                            record_collision("person", guid, "Existing person details differ from backup.")
                            continue

                        local_faces = local_default_by_guid.get(guid, [])
                        local_face_fps = Counter(default_face_fingerprint(r) for r in local_faces)
                        if local_face_fps - incoming_face_fps:
                            record_collision("person", guid, "Existing facial vector(s) differ from backup.")
                            continue
                        missing_face_fps = incoming_face_fps - local_face_fps

                        # Compare images
                        repair_updates = {}
                        copy_tasks = []
                        image_conflict_reason = None
                        for field, folder in IMAGE_FIELDS["persons"].items():
                            src_val = src_person.get(field)
                            loc_val = local.get(field)
                            if not src_val and not loc_val:
                                continue
                            if not src_val and loc_val:
                                image_conflict_reason = f"Local person has {field} absent from backup."
                                break
                            src_member = "images/" + src_val[len("/static/") :]
                            meta = files_meta[src_member]
                            ext = PurePosixPath(src_val).suffix.lower()
                            fname = f"{guid}.png" if field == "person_image_location" else f"{guid}-{meta['sha256'][:16]}{ext}"
                            target_member = f"images/{folder}/{fname}"
                            dest_path = resolve_destination_image(project_path, target_member, PRIVATE_IMAGE_FOLDERS)
                            target_url = f"/static/{folder}/{fname}"

                            if loc_val:
                                try:
                                    existing_path = resolve_source_image(project_path, loc_val)
                                    if cached_digest(existing_path) != meta["sha256"]:
                                        image_conflict_reason = f"Existing {field} file content differs."
                                        break
                                except ToolError:
                                    if not args.repair_missing:
                                        image_conflict_reason = f"Existing {field} file is missing (use --repair-missing to heal)."
                                        break
                                    if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                                        image_conflict_reason = f"Target repair path {dest_path} has different content."
                                        break
                                    copy_tasks.append((src_member, dest_path, meta["sha256"]))
                                    if target_url != loc_val:
                                        repair_updates[field] = target_url
                            else:
                                if not args.repair_missing:
                                    image_conflict_reason = f"Local person is missing {field} (use --repair-missing to heal)."
                                    break
                                if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                                    image_conflict_reason = f"Target repair path {dest_path} has different content."
                                    break
                                copy_tasks.append((src_member, dest_path, meta["sha256"]))
                                repair_updates[field] = target_url

                        if image_conflict_reason:
                            record_collision("person", guid, image_conflict_reason)
                            continue

                        if missing_face_fps and not args.repair_missing:
                            record_collision(
                                "person",
                                guid,
                                "Local person is missing facial vector(s) (use --repair-missing to heal).",
                            )
                            continue

                        repaired_preview = dict(local, **repair_updates)
                        if any(local_sql_keys[k] - {guid} for k in sql_unique_keys(repaired_preview)):
                            record_collision("person", guid, "Repaired unique image/document conflicts with another person.")
                            continue

                        if copy_tasks or repair_updates or missing_face_fps:
                            if not args.dry_run:
                                created_files: list[Path] = []
                                try:
                                    for src_member, dest_path, sha in copy_tasks:
                                        if atomic_copy_from_zip(zf, src_member, dest_path, sha):
                                            created_files.append(dest_path)
                                    if repair_updates:
                                        with conn, conn.cursor() as cur:
                                            cur.execute(
                                                sql.SQL("UPDATE persons SET {} WHERE id=%s").format(
                                                    sql.SQL(",").join(
                                                        sql.SQL("{}=%s").format(sql.Identifier(f))
                                                        for f in repair_updates
                                                    )
                                                ),
                                                [*repair_updates.values(), local["id"]],
                                            )
                                    if missing_face_fps:
                                        remaining = Counter(local_face_fps)
                                        to_insert = []
                                        for r in incoming_faces:
                                            fp = default_face_fingerprint(r)
                                            if remaining[fp]:
                                                remaining[fp] -= 1
                                                continue
                                            to_insert.append({**r, "aadhaar": str(local["id"])})
                                        if to_insert:
                                            milvus.insert_rows(DEFAULT_COLLECTION, to_insert)
                                except Exception:
                                    for fpath in created_files:
                                        fpath.unlink(missing_ok=True)
                                    raise
                            for k in sql_unique_keys(repaired_preview):
                                local_sql_keys[k].add(guid)
                            summary["repaired"]["persons"] += 1
                            summary["repaired"]["default_faces"] += sum(missing_face_fps.values())
                        else:
                            summary["skipped"]["persons"] += 1

                        person_id_map[src_id] = local["id"]
                        continue

                    # New person path
                    if guid in local_default_by_guid and not args.replace_orphan_faces:
                        record_collision(
                            "person",
                            guid,
                            "Orphaned facial vector already exists in Milvus 'default' for this GUID (pass --replace-orphan-faces to replace).",
                        )
                        continue

                    mapped_person = dict(src_person)
                    copy_tasks = []
                    dest_error = None
                    for field, folder in IMAGE_FIELDS["persons"].items():
                        val = src_person.get(field)
                        if not val:
                            continue
                        src_member = "images/" + val[len("/static/") :]
                        meta = files_meta[src_member]
                        ext = PurePosixPath(val).suffix.lower()
                        fname = f"{guid}.png" if field == "person_image_location" else f"{guid}-{meta['sha256'][:16]}{ext}"
                        target_member = f"images/{folder}/{fname}"
                        dest_path = resolve_destination_image(project_path, target_member, PRIVATE_IMAGE_FOLDERS)
                        if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                            dest_error = f"Destination file already exists with different content: {dest_path}"
                            break
                        mapped_person[field] = f"/static/{folder}/{fname}"
                        copy_tasks.append((src_member, dest_path, meta["sha256"]))

                    if dest_error:
                        record_collision("person", guid, dest_error)
                        continue

                    if any(local_sql_keys[k] - {guid} for k in sql_unique_keys(mapped_person)):
                        record_collision("person", guid, "Unique identity or document image already belongs to another person.")
                        continue

                    if args.dry_run:
                        local_id = -src_id
                        summary["imported"]["persons"] += 1
                        summary["imported"]["default_faces"] += len(incoming_faces)
                    else:
                        created_files = []
                        try:
                            for src_member, dest_path, sha in copy_tasks:
                                if atomic_copy_from_zip(zf, src_member, dest_path, sha):
                                    created_files.append(dest_path)
                            fields_to_insert = [f for f in PERSON_FIELDS if f != "id"]
                            row_values = dict(mapped_person, created_by=actor_id)
                            stmt = sql.SQL("INSERT INTO persons ({}) VALUES ({}) RETURNING id").format(
                                sql.SQL(",").join(map(sql.Identifier, fields_to_insert)),
                                sql.SQL(",").join(sql.Placeholder() for _ in fields_to_insert),
                            )
                            with conn:
                                with conn.cursor() as cur:
                                    cur.execute(stmt, [row_values[f] for f in fields_to_insert])
                                    local_id = int(cur.fetchone()[0])
                                if guid in local_default_by_guid:
                                    milvus.delete_guids(DEFAULT_COLLECTION, [guid])
                                remapped_faces = [{**r, "aadhaar": str(local_id)} for r in incoming_faces]
                                milvus.insert_rows(DEFAULT_COLLECTION, remapped_faces)
                            summary["imported"]["persons"] += 1
                            summary["imported"]["default_faces"] += len(remapped_faces)
                        except Exception:
                            for fpath in created_files:
                                fpath.unlink(missing_ok=True)
                            raise

                    person_id_map[src_id] = local_id
                    for k in document_keys(mapped_person):
                        local_doc_keys[k].add(guid)
                    for k in sql_unique_keys(mapped_person):
                        local_sql_keys[k].add(guid)

                # --- 2. Restore Vehicles one by one ---
                for src_vehicle in data["vehicles"]:
                    plate = normalized(src_vehicle["vehicle_number_plate"])
                    src_owner_id = src_vehicle["vehicle_owner_id"]
                    if src_owner_id not in person_id_map:
                        record_collision(
                            "vehicle",
                            src_vehicle["vehicle_number_plate"],
                            "Owner person was skipped due to an earlier collision.",
                        )
                        continue
                    local_owner_id = person_id_map[src_owner_id]
                    candidates = local_plates.get(plate, [])
                    if source_plate_counts[plate] != 1 or len(candidates) > 1:
                        record_collision(
                            "vehicle",
                            src_vehicle["vehicle_number_plate"],
                            "Vehicle plate is ambiguous in backup or local database.",
                        )
                        continue

                    src_val = src_vehicle["vehicle_image_location"]
                    src_member = "images/" + src_val[len("/static/") :]
                    meta = files_meta[src_member]
                    ext = PurePosixPath(src_val).suffix.lower()
                    if PurePosixPath(src_val).name.lower() in PLACEHOLDER_FILENAMES:
                        fname = PurePosixPath(src_val).name
                    else:
                        fname = f"{meta['sha256']}{ext}"
                    target_member = f"images/known_vehicles/{fname}"
                    dest_path = resolve_destination_image(project_path, target_member, PRIVATE_IMAGE_FOLDERS)
                    target_url = f"/static/known_vehicles/{fname}"

                    if candidates:
                        local = candidates[0]
                        expected_biz = business_fields(src_vehicle, "vehicles")
                        expected_biz["vehicle_owner_id"] = local_owner_id
                        if business_fields(local, "vehicles") != expected_biz:
                            record_collision(
                                "vehicle",
                                src_vehicle["vehicle_number_plate"],
                                "Existing vehicle details or owner differ from backup.",
                            )
                            continue
                        loc_val = local.get("vehicle_image_location")
                        try:
                            existing_path = resolve_source_image(project_path, loc_val) if loc_val else None
                        except ToolError:
                            existing_path = None
                        if existing_path:
                            if cached_digest(existing_path) != meta["sha256"]:
                                record_collision(
                                    "vehicle",
                                    src_vehicle["vehicle_number_plate"],
                                    "Existing vehicle image content differs.",
                                )
                                continue
                            summary["skipped"]["vehicles"] += 1
                            continue
                        if not args.repair_missing:
                            record_collision(
                                "vehicle",
                                src_vehicle["vehicle_number_plate"],
                                "Existing vehicle image is missing (use --repair-missing to heal).",
                            )
                            continue
                        if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                            record_collision(
                                "vehicle",
                                src_vehicle["vehicle_number_plate"],
                                f"Target repair image differs at {dest_path}.",
                            )
                            continue
                        if not args.dry_run:
                            created_files = []
                            try:
                                if atomic_copy_from_zip(zf, src_member, dest_path, meta["sha256"]):
                                    created_files.append(dest_path)
                                with conn, conn.cursor() as cur:
                                    cur.execute(
                                        "UPDATE vehicles SET vehicle_image_location=%s WHERE id=%s",
                                        (target_url, local["id"]),
                                    )
                            except Exception:
                                for fpath in created_files:
                                    fpath.unlink(missing_ok=True)
                                raise
                        summary["repaired"]["vehicles"] += 1
                        continue

                    if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                        record_collision(
                            "vehicle",
                            src_vehicle["vehicle_number_plate"],
                            f"Vehicle image destination already exists with different content: {dest_path}",
                        )
                        continue

                    if args.dry_run:
                        local_vehicle = dict(src_vehicle, id=-src_vehicle["id"], vehicle_owner_id=local_owner_id)
                        summary["imported"]["vehicles"] += 1
                    else:
                        created_files = []
                        try:
                            if atomic_copy_from_zip(zf, src_member, dest_path, meta["sha256"]):
                                created_files.append(dest_path)
                            fields_to_insert = [f for f in VEHICLE_FIELDS if f != "id"]
                            row_values = dict(
                                src_vehicle,
                                created_by=actor_id,
                                vehicle_owner_id=local_owner_id,
                                vehicle_image_location=target_url,
                            )
                            stmt = sql.SQL("INSERT INTO vehicles ({}) VALUES ({}) RETURNING id").format(
                                sql.SQL(",").join(map(sql.Identifier, fields_to_insert)),
                                sql.SQL(",").join(sql.Placeholder() for _ in fields_to_insert),
                            )
                            with conn, conn.cursor() as cur:
                                cur.execute(stmt, [row_values[f] for f in fields_to_insert])
                                new_vid = int(cur.fetchone()[0])
                            local_vehicle = dict(row_values, id=new_vid)
                            summary["imported"]["vehicles"] += 1
                        except Exception:
                            for fpath in created_files:
                                fpath.unlink(missing_ok=True)
                            raise
                    local_plates[plate].append(local_vehicle)

                # --- 3. Restore Blacklist one by one (grouped by GUID) ---
                bl_folder = static_root(project_path) / "blacklisted_persons"
                bl_files = (
                    sorted(
                        f
                        for f in os.listdir(bl_folder)
                        if not (bl_folder / f).is_symlink()
                        and (bl_folder / f).is_file()
                        and Path(f).suffix.lower() in BLACKLIST_EXTENSIONS
                    )
                    if bl_folder.is_dir()
                    else []
                )
                incoming_bl_by_guid: dict[str, list[dict]] = defaultdict(list)
                for bl_row in data["blacklist_faces"]:
                    incoming_bl_by_guid[str(bl_row["guid"])].append(bl_row)

                for guid, bl_rows in incoming_bl_by_guid.items():
                    src_member = data["blacklist_map"][guid]
                    meta = files_meta[src_member]
                    dest_path = resolve_destination_image(project_path, src_member, {"blacklisted_persons"})
                    incoming_fps = Counter(blacklist_face_fingerprint(r) for r in bl_rows)

                    existing_bl = local_blacklist_by_guid.get(guid, [])
                    if existing_bl:
                        existing_fps = Counter(blacklist_face_fingerprint(r) for r in existing_bl)
                        if existing_fps - incoming_fps:
                            record_collision(
                                "blacklist",
                                guid,
                                "Existing blacklist face metadata or vector differs from backup.",
                                name=bl_rows[0].get("name"),
                                aadhaar=bl_rows[0].get("aadhaar"),
                            )
                            continue
                        missing_bl_fps = incoming_fps - existing_fps
                        matched_local = match_blacklist_image(bl_files, bl_rows[0])
                        image_missing = matched_local is None
                        if matched_local:
                            local_img = bl_folder / matched_local
                            if cached_digest(local_img) != meta["sha256"]:
                                record_collision(
                                    "blacklist",
                                    guid,
                                    "Existing blacklist image file differs from backup.",
                                    path=str(local_img),
                                )
                                continue
                        if (image_missing or missing_bl_fps) and not args.repair_missing:
                            record_collision(
                                "blacklist",
                                guid,
                                "Existing blacklist entry is missing image or vector(s) (use --repair-missing to heal).",
                            )
                            continue
                        if image_missing and dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                            record_collision("blacklist", guid, f"Blacklist destination exists with different content: {dest_path}")
                            continue
                        if image_missing or missing_bl_fps:
                            if not args.dry_run:
                                created_files = []
                                try:
                                    if image_missing and atomic_copy_from_zip(zf, src_member, dest_path, meta["sha256"]):
                                        created_files.append(dest_path)
                                        bl_files.append(dest_path.name)
                                    if missing_bl_fps:
                                        remaining = Counter(existing_fps)
                                        to_insert = []
                                        for r in bl_rows:
                                            fp = blacklist_face_fingerprint(r)
                                            if remaining[fp]:
                                                remaining[fp] -= 1
                                                continue
                                            to_insert.append(r)
                                        if to_insert:
                                            milvus.insert_rows(BLACKLIST_COLLECTION, to_insert)
                                except Exception:
                                    for fpath in created_files:
                                        fpath.unlink(missing_ok=True)
                                    raise
                            if image_missing:
                                summary["repaired"]["blacklist_images"] += 1
                            if missing_bl_fps:
                                summary["repaired"]["blacklist_faces"] += sum(missing_bl_fps.values())
                        else:
                            summary["skipped"]["blacklist_faces"] += len(bl_rows)
                        continue

                    if dest_path.exists() and cached_digest(dest_path) != meta["sha256"]:
                        record_collision(
                            "blacklist",
                            guid,
                            f"Blacklist image filename collides with existing file: {dest_path.name}",
                        )
                        continue

                    if not args.dry_run:
                        created_files = []
                        try:
                            if atomic_copy_from_zip(zf, src_member, dest_path, meta["sha256"]):
                                created_files.append(dest_path)
                            milvus.insert_rows(BLACKLIST_COLLECTION, bl_rows)
                        except Exception:
                            for fpath in created_files:
                                fpath.unlink(missing_ok=True)
                            raise
                        bl_files.append(dest_path.name)
                    local_blacklist_by_guid[guid].extend(bl_rows)
                    summary["imported"]["blacklist_faces"] += len(bl_rows)

        if not args.dry_run:
            milvus.flush(DEFAULT_COLLECTION)
            milvus.flush(BLACKLIST_COLLECTION)
    finally:
        milvus.close()

    report = {
        "operation": "restore",
        "dry_run": bool(args.dry_run),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "archive": str(archive_path),
        "archive_sha256": digest_file(archive_path),
        **summary,
    }
    write_report(Path(args.report) if args.report else None, report)

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(
        f"{prefix}Restore finished: "
        f"imported={summary['imported']}, "
        f"repaired={summary['repaired']}, "
        f"skipped={summary['skipped']}, "
        f"collisions={len(summary['collisions'])}"
    )
    if summary["collisions"]:
        print("Collisions:")
        for c in summary["collisions"]:
            print(f"  - [{c['entity']}] {c['identity']}: {c['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline backup, reset, and collision-safe restore for enrollment & blacklist data."
    )
    parser.add_argument(
        "--milvus-uri",
        default=os.environ.get("ENROLLMENT_MILVUS_URI", "http://census_counters_facedb:19530"),
        help="Milvus URI (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_save = sub.add_parser("save", help="Export persons, vehicles, images, and default+blacklist vectors to a ZIP.")
    p_save.add_argument("output", help="Output ZIP file path.")
    p_save.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Warn and skip records/vectors with integrity issues instead of aborting.",
    )
    p_save.add_argument("--report", help="Write JSON integrity report to this path.")
    p_save.add_argument("--embedding-model", help="Override ENROLLMENT_EMBEDDING_MODEL recorded in manifest.")

    p_reset = sub.add_parser("reset", help="Reset database, Milvus, Redis, and runtime files to fresh state.")
    p_reset.add_argument("--confirm", required=True, help="Must be exact string RESET.")
    p_reset.add_argument("--yes", action="store_true", help="Skip interactive confirmation prompt.")
    p_reset.add_argument("--wipe-history", action="store_true", help="Also delete trips, passes, and ANPR readings.")
    p_reset.add_argument("--wipe-blacklist", action="store_true", help="Also clear Milvus blacklist & images.")
    p_reset.add_argument("--all", action="store_true", help="Shorthand for --wipe-history --wipe-blacklist.")
    p_reset.add_argument("--backup-first", help="Run `save` to this ZIP path before deleting data.")
    p_reset.add_argument(
        "--backup-skip-invalid",
        action="store_true",
        help="Pass --skip-invalid to the --backup-first export.",
    )
    p_reset.add_argument("--keep-redis", action="store_true", help="Do not flush Redis during reset.")

    p_restore = sub.add_parser("restore", help="Restore a saved ZIP one by one with collision reporting.")
    p_restore.add_argument("archive", help="Input ZIP file path.")
    p_restore.add_argument("--dry-run", action="store_true", help="Validate and report collisions without writing.")
    p_restore.add_argument(
        "--on-conflict",
        choices=("skip", "abort"),
        default="skip",
        help="Behavior when a record collides with existing data (default: skip).",
    )
    p_restore.add_argument(
        "--repair-missing",
        action="store_true",
        help="Fill missing images/vectors on identical existing records without overwriting differing data.",
    )
    p_restore.add_argument(
        "--replace-orphan-faces",
        action="store_true",
        help="Replace an orphaned Milvus default vector if inserting a new person with that GUID.",
    )
    p_restore.add_argument("--actor-id", type=int, help="Local users.id to set as created_by on inserted rows.")
    p_restore.add_argument("--report", help="Write JSON restore & collision report to this path.")
    p_restore.add_argument("--embedding-model", help="Expected ENROLLMENT_EMBEDDING_MODEL.")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        load_runtime_dependencies()
        if args.command == "save":
            return cmd_save(args)
        if args.command == "reset":
            return cmd_reset(args)
        if args.command == "restore":
            return cmd_restore(args)
        parser.error("Unknown command")
        return 2
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
