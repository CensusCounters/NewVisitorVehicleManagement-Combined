#!/usr/bin/env python3
"""Regenerate BRANCH_COMPARISON CSV exports."""

from __future__ import annotations

import ast
import csv
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COMBINED_INIT = (
    ROOT
    / "combined/Visitor-Vehicle-Management/src/frontend/finalfrsproject/__init__.py"
)
COMBINED_BASE = COMBINED_INIT.parent

PROFILES = {
    "kupwara": "Kupwara",
    "ncpass": "NCPass",
    "ganganagar": "ganganagar",
    "tangdhar": "tangdhar",
}

# Combined SITE_PROFILES item -> branch __init__.py app.config key (when present)
BRANCH_CONFIG_KEYS = {
    "app_title": "APP_TITLE",
    "logo_path": "APP_LOGO_PATH",
    "visitor_categories": "VISITOR_CATEGORIES",
    "id_lookup_categories": "ID_LOOKUP_CATEGORIES",
    "vehicle_types": "VEHICLE_TYPES",
    "vehicle_categories": "VEHICLE_CATEGORIES",
    "face_match_confidence": "FACE_MATCH_CONFIDENCE",
    "summary_table_by_visitor_type": "SUMMARY_TABLE_BY_VISITOR_TYPE",
    "summary_table_by_men_women": "SUMMARY_TABLE_BY_MEN_WOMEN",
}

# Where branch behavior lives when not a SITE_PROFILES-style key in branch __init__.py
BRANCH_SOURCE_FILES: dict[str, dict[str, str]] = {
    "kupwara": {
        "id_lookup_workflow": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html",
        "allowed_id_types_by_visitor": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html; helpers/unknown_person_helper.py",
        "unknown_person_page_fields": "templates/unknown_person.html; helpers/unknown_person_helper.py",
        "trip_duration_default_hours": "templates/add_trip.html",
        "summary_table_by_visitor_type": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "summary_table_by_men_women": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "trip_closure_mode": "helpers/get_unfinished_trips_helper.py; templates/close_trip.html",
    },
    "ncpass": {
        "id_lookup_workflow": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html",
        "allowed_id_types_by_visitor": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html; helpers/unknown_person_helper.py",
        "unknown_person_page_fields": "templates/unknown_person.html; helpers/unknown_person_helper.py",
        "trip_duration_default_hours": "templates/add_trip.html",
        "summary_table_by_visitor_type": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "summary_table_by_men_women": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "trip_closure_mode": "helpers/get_unfinished_trips_helper.py; templates/close_trip.html",
    },
    "ganganagar": {
        "id_lookup_workflow": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html",
        "allowed_id_types_by_visitor": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html; helpers/unknown_person_helper.py",
        "unknown_person_page_fields": "templates/unknown_person.html; helpers/unknown_person_helper.py",
        "trip_duration_default_hours": "templates/add_trip.html",
        "summary_table_by_visitor_type": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "summary_table_by_men_women": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "trip_closure_mode": "../auto_close/auto_close.py; helpers/get_unfinished_trips_helper.py; templates/close_trip.html",
    },
    "tangdhar": {
        "id_lookup_workflow": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html",
        "allowed_id_types_by_visitor": "helpers/aadhar_lookup_helper.py; templates/aadhar_lookup.html; helpers/unknown_person_helper.py",
        "unknown_person_page_fields": "templates/unknown_person.html; helpers/unknown_person_helper.py",
        "trip_duration_default_hours": "templates/add_trip.html",
        "summary_table_by_visitor_type": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "summary_table_by_men_women": "__init__.py; templates/components/trip_report_summary.html; templates/components/trip_report_summary_script.html",
        "trip_closure_mode": "helpers/get_unfinished_trips_helper.py; templates/close_trip.html",
    },
}

PROFILE_HELPERS = {
    "known_vehicle_helper.py",
    "person_lookup_helper.py",
    "person_report_helper.py",
    "recognize_vehicle_helper.py",
    "report_home_helper.py",
    "trip_registration_helper.py",
    "unknown_vehicle_helper.py",
    "vehicle_report_helper.py",
}

PROFILE_TEMPLATES = {
    "recognize_vehicle.html",
    "known_vehicle.html",
    "unknown_vehicle.html",
    "trip_summary.html",
    "close_trip.html",
    "unfinished_trips.html",
    "report_home.html",
    "person_report.html",
    "vehicle_report.html",
    "person_lookup.html",
    "person_lookup_result_list.html",
    "static_trip_summary.html",
    "401.html",
    "404.html",
    "500.html",
    "add_trip.html",
}


def load_ast_dict(init_path: Path, name: str) -> dict:
    module = ast.parse(init_path.read_text())
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise KeyError(f"{name} not found in {init_path}")


def extract_branch_config(init_path: Path) -> dict[str, object]:
    """Parse active app.config[...] assignments from branch __init__.py."""
    values: dict[str, object] = {}
    for line in init_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith("app.config["):
            continue
        if stripped.startswith("#"):
            continue
        match = re.match(
            r'app\.config\["([A-Z0-9_]+)"\]\s*=\s*(.+?)\s*(?:#.*)?$',
            stripped,
        )
        if not match:
            continue
        key, raw = match.group(1), match.group(2)
        try:
            values[key] = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            values[key] = raw
    return values


def fmt(value: object) -> str:
    if value is None:
        return "(not set)"
    return repr(value)


def compare_values(branch_val: object, combined_val: object) -> str:
    if branch_val is None:
        return "Combined only"
    if branch_val == combined_val:
        return "Match"
    return "Different"


def priority_for(status: str, item: str) -> str:
    if status == "Match":
        return ""
    if status == "Combined only":
        return "P2"
    if item == "id_lookup_categories" and status == "Different":
        return "P0"
    return "P1"


def write_config_comparison(site_profiles: dict) -> None:
    rows = []
    for profile, folder in PROFILES.items():
        branch_init = (
            ROOT
            / folder
            / "Visitor-Vehicle-Management/src/frontend/finalfrsproject/__init__.py"
        )
        branch_cfg = extract_branch_config(branch_init)
        combined = site_profiles[profile]

        for item, combined_val in combined.items():
            if item in {"trip_report_summary_fields"}:
                continue
            branch_key = BRANCH_CONFIG_KEYS.get(item)
            if branch_key and branch_key in branch_cfg:
                branch_val = branch_cfg[branch_key]
                branch_display = fmt(branch_val)
                status = "Match" if branch_val == combined_val else "Different"
            elif item in BRANCH_SOURCE_FILES.get(profile, {}):
                branch_display = BRANCH_SOURCE_FILES[profile][item]
                status = "Combined only"
            else:
                branch_display = "(not set)"
                status = "Combined only" if combined_val is not None else "Match"

            rows.append(
                {
                    "Site": profile,
                    "Category": "Config",
                    "Item": item,
                    "Branch config key": branch_key or "(combined profile only)",
                    "Branch value": branch_display,
                    "Combined value (SITE_PROFILE)": fmt(combined_val),
                    "Status": status,
                    "Priority": priority_for(status, item),
                    "Notes": "",
                }
            )

    path = OUT / "01_config_comparison.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Site",
                "Category",
                "Item",
                "Branch config key",
                "Branch value",
                "Combined value (SITE_PROFILE)",
                "Status",
                "Priority",
                "Notes",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {path} ({len(rows)} rows)")


def file_hash(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def combined_compare_path(profile: str, rel: str) -> str:
    rel_path = Path(rel)
    name = rel_path.name
    if name in PROFILE_HELPERS:
        return f"site_workflows/{profile}/{name}"
    if name in PROFILE_TEMPLATES:
        site_override = COMBINED_BASE / "templates" / "sites" / profile / name
        if site_override.is_file():
            return f"templates/sites/{profile}/{name}"
        return f"templates/{name}"
    return rel


def write_file_comparisons() -> None:
    all_rows = []
    summary: dict[tuple[str, str], int] = {}

    for profile, folder in PROFILES.items():
        branch_root = (
            ROOT
            / folder
            / "Visitor-Vehicle-Management/src/frontend/finalfrsproject"
        )
        branch_files = sorted(
            p.relative_to(branch_root).as_posix()
            for p in branch_root.rglob("*")
            if p.is_file()
            and ".pyc" not in p.parts
            and "__pycache__" not in p.parts
        )
        per_site_rows = []

        for rel in branch_files:
            branch_path = branch_root / rel
            combined_rel = combined_compare_path(profile, rel)
            combined_path = COMBINED_BASE / combined_rel

            if not combined_path.is_file():
                status = "Missing in combined"
                priority = "P1"
            elif file_hash(branch_path) == file_hash(combined_path):
                status = "Match"
                priority = ""
            else:
                status = "Different"
                priority = "P0" if rel.endswith((".html", "_helper.py", "__init__.py")) else "P1"

            row = {
                "Site": profile,
                "Category": _category_for(rel),
                "Relative path (branch)": rel,
                "Combined compare path": combined_rel if combined_path.is_file() else "(no combined file)",
                "Status": status,
                "Priority": priority,
                "Notes": "",
            }
            per_site_rows.append(row)
            all_rows.append(row)
            summary[(profile, status)] = summary.get((profile, status), 0) + 1

        # 02_* tabs: all diffs + non-media matches (exclude matching images/assets only).
        site_tab_rows = [row for row in per_site_rows if _include_in_site_diff_tab(row)]
        excluded_matches = len(per_site_rows) - len(site_tab_rows)

        site_path = OUT / f"02_files_{profile}.csv"
        with site_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "Site",
                    "Category",
                    "Relative path (branch)",
                    "Combined compare path",
                    "Status",
                    "Priority",
                    "Notes",
                ],
            )
            writer.writeheader()
            writer.writerows(site_tab_rows)
        print(
            f"Wrote {site_path} ({len(site_tab_rows)} rows, "
            f"excluded {excluded_matches} matching media/assets)"
        )

    all_path = OUT / "03_all_files_comparison.csv"
    with all_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "Site",
                "Category",
                "Relative path (branch)",
                "Combined compare path",
                "Status",
                "Priority",
                "Notes",
            ],
        )
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Wrote {all_path} ({len(all_rows)} rows)")

    summary_path = OUT / "04_summary_counts.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Site", "Status", "Count"],
        )
        writer.writeheader()
        for (site, status), count in sorted(summary.items()):
            writer.writerow({"Site": site, "Status": status, "Count": count})
    print(f"Wrote {summary_path}")


MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svg",
    ".mp4", ".webm", ".mp3", ".wav",
}

MEDIA_PATH_MARKERS = (
    "static/images/",
    "static/uploads/",
    "static/known_persons/",
    "static/known_vehicles/",
    "static/aadhars/",
    "static/drivers_licenses/",
    "static/unknown_persons/",
    "static/blacklisted_persons/",
    "static/vehicle_images/",
    "static/screenshots/",
)


def _is_media_asset(rel: str) -> bool:
    rel_lower = rel.lower().replace("\\", "/")
    if Path(rel_lower).suffix in MEDIA_EXTENSIONS:
        return True
    return any(marker in rel_lower for marker in MEDIA_PATH_MARKERS)


def _include_in_site_diff_tab(row: dict) -> bool:
    """Keep all diffs; for Match rows, drop media/assets only."""
    if row["Status"] != "Match":
        return True
    return not _is_media_asset(row["Relative path (branch)"])


def _category_for(rel: str) -> str:
    if rel.endswith(".html"):
        return "Template"
    if rel.endswith(".py"):
        return "Python"
    if rel.endswith((".css", ".js")):
        return "Static"
    return "Other"


def main() -> None:
    site_profiles = load_ast_dict(COMBINED_INIT, "SITE_PROFILES")
    write_config_comparison(site_profiles)
    write_file_comparisons()


if __name__ == "__main__":
    main()
