import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from jinja2 import Environment


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "frontend" / "finalfrsproject"
WORKSPACE = ROOT.parent.parent
PROFILES = ("kupwara", "ncpass", "ganganagar", "tangdhar")

PROFILE_SOURCE_DIRS = {
    "kupwara": WORKSPACE / "Kupwara" / "Visitor-Vehicle-Management",
    "ncpass": WORKSPACE / "NCPass" / "Visitor-Vehicle-Management",
    "ganganagar": WORKSPACE / "ganganagar" / "Visitor-Vehicle-Management",
    "tangdhar": WORKSPACE / "tangdhar" / "Visitor-Vehicle-Management",
}

PROFILE_TEMPLATE_NAMES = {
    "recognize_vehicle.html", "known_vehicle.html", "unknown_vehicle.html",
    "trip_summary.html",
    "close_trip.html", "unfinished_trips.html", "report_home.html",
    "person_report.html", "vehicle_report.html",
    "person_lookup.html", "person_lookup_result_list.html",
    "static_trip_summary.html", "401.html",
    "404.html", "500.html",
}

PROFILE_HELPERS = {
    "known_vehicle_helper.py",
    "person_lookup_helper.py", "person_report_helper.py",
    "recognize_vehicle_helper.py", "report_home_helper.py",
    "trip_registration_helper.py", "unknown_vehicle_helper.py",
    "vehicle_report_helper.py",
}


class ConsolidationAuditTests(unittest.TestCase):
    def test_ocr_feature_is_completely_absent(self):
        forbidden_names = {"ocr.html", "ocr-google-api.html", "ocr_helper.py", "tesseract.min.js"}
        for path in ROOT.rglob("*"):
            if path.is_file():
                self.assertNotIn(path.name, forbidden_names, path)

        routes = (PACKAGE / "routes.py").read_text()
        self.assertNotIn('route("/ocr"', routes)
        self.assertNotIn("route('/recognize_image'", routes)
        self.assertNotIn("route('/recognize_qr'", routes)

    def test_frontend_and_optional_worker_python_syntax(self):
        roots = (
            ROOT / "src" / "frontend",
            ROOT / "src" / "auto_close",
            ROOT / "src" / "topreport",
            ROOT / "src" / "cleanup",
        )
        for source_root in roots:
            for path in source_root.rglob("*.py"):
                with self.subTest(path=path):
                    ast.parse(path.read_text())

    def test_all_templates_have_valid_jinja_syntax(self):
        environment = Environment(extensions=["jinja2.ext.i18n"])
        for path in (PACKAGE / "templates").rglob("*.html"):
            with self.subTest(path=path):
                environment.parse(path.read_text(errors="strict"))

    def test_profile_overrides_match_the_audited_branch_snapshots(self):
        override_root = PACKAGE / "templates" / "sites"
        for profile, source_project in PROFILE_SOURCE_DIRS.items():
            source_root = source_project / "src" / "frontend" / "finalfrsproject" / "templates"
            for name in PROFILE_TEMPLATE_NAMES:
                source = source_root / name
                override = override_root / profile / name
                with self.subTest(profile=profile, template=name):
                    self.assertEqual(source.exists(), override.exists())
                    if source.exists():
                        self.assertEqual(source.read_bytes(), override.read_bytes())

    def test_profile_workflows_match_the_audited_branch_snapshots(self):
        workflow_root = PACKAGE / "site_workflows"
        for profile, source_project in PROFILE_SOURCE_DIRS.items():
            source_root = source_project / "src" / "frontend" / "finalfrsproject" / "helpers"
            for name in PROFILE_HELPERS:
                with self.subTest(profile=profile, helper=name):
                    self.assertEqual(
                        (source_root / name).read_bytes(),
                        (workflow_root / profile / name).read_bytes(),
                    )

    def test_ncpass_trip_registration_form_matches_branch_source(self):
        source = (
            PROFILE_SOURCE_DIRS["ncpass"]
            / "src" / "frontend" / "finalfrsproject" / "templates" / "add_trip.html"
        )
        override = (
            PACKAGE / "templates" / "sites" / "ncpass" / "add_trip.html"
        )
        self.assertEqual(source.read_bytes(), override.read_bytes())

    def test_every_profile_imports_compiles_templates_and_registers_routes(self):
        script = r'''
import importlib
from finalfrsproject import app
from finalfrsproject import routeMethods

workflow_modules = (
    "known_vehicle_helper", "make_trip_summary_helper",
    "person_lookup_helper", "person_report_helper", "recognize_vehicle_helper",
    "report_home_helper", "trip_registration_helper", "unknown_vehicle_helper",
    "vehicle_report_helper",
)
for module in workflow_modules:
    importlib.import_module(
        f"finalfrsproject.site_workflows.{app.config['SITE_PROFILE']}.{module}"
    )
for template in app.jinja_loader.list_templates():
    app.jinja_env.get_template(template)

required_endpoints = {
    "login", "home", "aadhar_lookup", "recognize_person",
    "manual_face_verification", "reregister_face", "known_person",
    "unknown_person", "blacklist_alert", "enroll_blacklisted_person",
    "blacklisted_persons_list", "recognize_vehicle", "known_vehicle",
    "unknown_vehicle", "trip_registration", "make_trip_summary",
    "get_unfinished_trips", "report_home", "person_report",
    "trip_report", "vehicle_report", "person_lookup",
}
registered = {rule.endpoint for rule in app.url_map.iter_rules()}
missing = required_endpoints - registered
if missing:
    raise AssertionError(f"missing endpoints: {sorted(missing)}")

assert app.config["KNOWN_PERSON_SCHEMA"]["required_fields"] == [
    "name", "gender", "mobile_number"
]
assert set(app.config["ALLOWED_ID_TYPES_BY_VISITOR"]) == set(
    app.config["VISITOR_CATEGORIES"]
)
assert app.config["JWT_COOKIE_SECURE"] is True
assert app.config["SINGLE_ACTIVE_LOGIN"] is True
assert "APP_LOGO_WIDTH" not in app.config
assert "APP_LOGO_FALLBACK_PATH" not in app.config
assert "PASSENGER_LOOP_ENABLED" not in app.config
assert "UNKNOWN_PERSON_SCHEMA" not in app.config
assert "SITE_FEATURES" not in app.config
assert "UNKNOWN_PERSON_PAGE_FIELDS" in app.config
assert "TRIP_REPORT_SUMMARY_FIELDS" in app.config
assert isinstance(app.config["FACE_MATCH_CONFIDENCE"], float)
assert 0 < app.config["FACE_MATCH_CONFIDENCE"] <= 1
assert app.config["TRIP_DURATION_DEFAULT_HOURS"] == (
    12 if app.config["SITE_PROFILE"] == "ncpass" else 1
)
assert "VEHICLE_FIELDS" in app.config
assert app.config["TRIP_CLOSURE_MODE"] == (
    "manual_and_anpr" if app.config["SITE_PROFILE"] == "ganganagar" else "manual"
)
expected_known_vehicle_fields = (
    [
        "vehicle_number", "vehicle_type", "vehicle_model",
        "vehicle_owner_name", "make", "color",
    ]
    if app.config["SITE_PROFILE"] == "ncpass"
    else ["vehicle_number", "vehicle_owner_name", "make", "color"]
)
assert app.config["VEHICLE_FIELDS"]["known_vehicle"]["required_fields"] == (
    expected_known_vehicle_fields
)
valid_known_vehicle = {field: "test" for field in expected_known_vehicle_fields}
assert routeMethods.validate_vehicle_fields(valid_known_vehicle, "known_vehicle") is None
invalid_known_vehicle = dict(valid_known_vehicle)
invalid_known_vehicle[expected_known_vehicle_fields[0]] = ""
assert routeMethods.validate_vehicle_fields(invalid_known_vehicle, "known_vehicle")["Status"] == "Fail"
required_unknown_vehicle_fields = app.config["VEHICLE_FIELDS"]["unknown_vehicle"]["required_fields"]
valid_unknown_vehicle = {field: "test" for field in required_unknown_vehicle_fields}
assert routeMethods.validate_vehicle_fields(valid_unknown_vehicle, "unknown_vehicle") is None
invalid_unknown_vehicle = dict(valid_unknown_vehicle)
invalid_unknown_vehicle[required_unknown_vehicle_fields[0]] = ""
assert routeMethods.validate_vehicle_fields(invalid_unknown_vehicle, "unknown_vehicle")["Status"] == "Fail"
assert "VEHICLE_TRIP_AND_DEPLOYMENT_SETTINGS" not in app.config
'''
        for profile in PROFILES:
            env = os.environ.copy()
            env.update({
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(ROOT / "src" / "frontend"),
                "SITE_PROFILE": profile,
                "PROJECT_BASE_PATH": str(PACKAGE),
                "REPORT_IMAGE_BASE_PATH": str(PACKAGE),
            })
            with self.subTest(profile=profile):
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shared_header_and_auth_are_not_profile_options(self):
        init_tree = ast.parse((PACKAGE / "__init__.py").read_text())
        profiles_node = next(
            node.value for node in init_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SITE_PROFILES" for target in node.targets)
        )
        profiles = ast.literal_eval(profiles_node)
        common_summary_node = next(
            node.value for node in init_tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "COMMON_TRIP_REPORT_SUMMARY"
                for target in node.targets
            )
        )
        common_summary = ast.literal_eval(common_summary_node)
        removed_profile_keys = {
            "logo_fallback_path", "logo_width", "logo_column_class",
            "user_column_class", "logo_style", "jwt_cookie_secure",
            "passenger_loop_enabled",
            "trip_report_summary_fields", "single_active_login",
        }
        for profile_name, profile in profiles.items():
            with self.subTest(profile=profile_name):
                self.assertTrue(removed_profile_keys.isdisjoint(profile))
                self.assertIn("unknown_person_page_fields", profile)
                self.assertIn("face_match_confidence", profile)
                self.assertIsInstance(profile["face_match_confidence"], (int, float))
                self.assertIn("summary_table_by_visitor_type", profile)
                self.assertIn("summary_table_by_men_women", profile)
                self.assertIn("vehicle_fields", profile)
                self.assertIsInstance(profile["summary_table_by_visitor_type"], bool)
                self.assertIsInstance(profile["summary_table_by_men_women"], bool)
                self.assertTrue(profile["summary_table_by_visitor_type"])
                self.assertTrue(profile["summary_table_by_men_women"])
                self.assertEqual(
                    profile["trip_duration_default_hours"],
                    12 if profile_name == "ncpass" else 1,
                )
                self.assertEqual(
                    profile["trip_closure_mode"],
                    "manual_and_anpr" if profile_name == "ganganagar" else "manual",
                )
                self.assertNotIn("required_fields", profile["unknown_person_page_fields"])
                self.assertNotIn("blacklist_list_columns", profile)
                self.assertNotIn("unknown_person_schema", profile)
                self.assertNotIn("features", profile)
                self.assertNotIn("vehicle_trip_and_deployment_settings", profile)

                known_vehicle = profile["vehicle_fields"]["known_vehicle"]
                unknown_vehicle = profile["vehicle_fields"]["unknown_vehicle"]
                if profile_name == "ncpass":
                    self.assertEqual(
                        known_vehicle["required_fields"],
                        [
                            "vehicle_number", "vehicle_type", "vehicle_model",
                            "vehicle_owner_name", "make", "color",
                        ],
                    )
                    self.assertIn("vehicle_registration_number", known_vehicle["fields"])
                    self.assertIn("vehicle_type", unknown_vehicle["fields"])
                    self.assertIn("vehicle_model", unknown_vehicle["fields"])
                    self.assertIn("vehicle_registration_number", unknown_vehicle["fields"])
                else:
                    self.assertEqual(
                        known_vehicle["fields"],
                        ["vehicle_number", "vehicle_owner_name", "make", "color"],
                    )
                    self.assertEqual(known_vehicle["required_fields"], known_vehicle["fields"])
                    self.assertEqual(
                        unknown_vehicle["fields"],
                        ["vehicle_number", "vehicle_owner_name", "vehicle_make", "vehicle_color"],
                    )
                self.assertEqual(
                    unknown_vehicle["required_fields"],
                    ["vehicle_number", "vehicle_owner_name"],
                )

        self.assertEqual(
            [field["key"] for field in common_summary["trip_report_summary_fields"]["totals"]],
            ["total_trips", "total_males", "total_females", "total_children", "total_persons"],
        )
        self.assertEqual(set(common_summary.keys()), {"trip_report_summary_fields"})

        layout = (PACKAGE / "templates" / "layout.html").read_text()
        self.assertIn('class="col-md-3" style="text-align: center; padding-top: 20px;"', layout)
        self.assertIn("asset_url('images/census-logo.png')", layout)
        self.assertIn('width="200"', layout)

        summary_script = (
            PACKAGE / "templates" / "components" / "trip_report_summary_script.html"
        ).read_text()
        self.assertIn("configuredCategoryKeys", summary_script)
        self.assertIn("catchAllKey", summary_script)
        self.assertNotIn("trip-summary-other-col", summary_script)

    def test_optional_features_are_profile_scoped(self):
        init_tree = ast.parse((PACKAGE / "__init__.py").read_text())
        profiles_node = next(
            node.value for node in init_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "SITE_PROFILES" for target in node.targets)
        )
        profiles = ast.literal_eval(profiles_node)
        self.assertTrue((ROOT / "src" / "auto_close" / "auto_close.py").exists())
        self.assertTrue((ROOT / "src" / "topreport" / "top_report_service.py").exists())
        self.assertTrue((ROOT / "Dockerfile_topreport").exists())

    def test_compose_configuration_is_valid(self):
        result = subprocess.run(
            [
                "docker", "compose", "-f",
                "docker-compose-census-counters-visitor-vehicle.yml", "config", "--quiet",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
