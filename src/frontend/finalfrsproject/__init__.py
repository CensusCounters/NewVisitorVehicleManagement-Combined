from flask import Flask, session, g, url_for
import os, json
from flask_jwt_extended import JWTManager
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, _
import psycopg2, psycopg2.extras
from psycopg2 import pool
from werkzeug.middleware.proxy_fix import ProxyFix

from finalfrsproject.config import get_active_profile

app = Flask(__name__)


@app.before_request
def before_request():
    # print("In before_request.", flush=True)
    if not hasattr(app, "connection_pool"):
        app.connection_pool = psycopg2.pool.SimpleConnectionPool(
            2,
            20,
            user=app.config["DB_USER_NAME"],
            password=app.config["DB_PASSWORD"],
            host=app.config["POSTGRESQL_URL"],
            port=app.config["DB_PORT"],
            database=app.config["DB_NAME"],
        )
        # print("Connection pool created.", flush=True)

    g.connection_pool = app.connection_pool
    # print("Connection pool added to g variable.", flush=True)


@app.teardown_request
def teardown_request(exception):
    # print("In teardown_request.", flush=True)

    # Optional: Debug what's in g (commented out)
    # custom_attrs = [attr for attr in dir(g) if not attr.startswith('__')]
    # print(f"Attributes in g: {', '.join(custom_attrs)}", flush=True)

    # Show psycopg2 connection pool information
    try:
        if hasattr(g, "connection_pool"):
            pool = g.connection_pool
            # print(f"psycopg2 Connection Pool Status:", flush=True)
            # print(f"  Max connections: {pool.maxconn}", flush=True)
            # print(f"  Min connections: {pool.minconn}", flush=True)

            # For SimpleConnectionPool, _pool contains AVAILABLE connections
            # if hasattr(pool, '_pool'):
            #    available_connections = len(pool._pool)
            # We can't reliably calculate "used" connections because
            # psycopg2 creates connections on-demand, not pre-allocates them
            #    print(f"  Available connections: {available_connections}", flush=True)
            # print(f"  Note: 'Used' connections can't be calculated reliably", flush=True)
            # print(f"        psycopg2 creates connections on-demand", flush=True)

            # Only warn if NO connections are available
            #    if available_connections == 0:
            #        print(f"  ⚠️  WARNING: No available connections!", flush=True)
            #    else:
            #        print(f"  ✅ Pool status: Normal ({available_connections} available)", flush=True)

            # else:
            #    print(f"  Cannot determine connection usage (internal _pool not accessible)", flush=True)

            # Show pool type
            # print(f"  Pool type: {type(pool).__name__}", flush=True)
        else:
            print("No connection_pool found in g", flush=True)

    except Exception as e:
        print(f"Error getting psycopg2 pool info: {e}", flush=True)


app.config["PROJECT_BASE_PATH"] = os.environ.get(
    "PROJECT_BASE_PATH", "/project/finalfrsproject"
)
app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] = os.environ.get(
    "REPORT_IMAGE_BASE_PATH", app.config["PROJECT_BASE_PATH"]
)
app.config["IMAGE_PATH_FOR_HTML"] = "/static/images/uploads"
app.config["IMAGE_UPLOADS"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["IMAGE_PATH_FOR_HTML"]
)

app.config["KNOWN_PERSON_PATH_FOR_HTML"] = "/static/known_persons"
app.config["KNOWN_PERSONS"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["KNOWN_PERSON_PATH_FOR_HTML"]
)

app.config["KNOWN_VEHICLE_PATH_FOR_HTML"] = "/static/known_vehicles"
app.config["KNOWN_VEHICLES"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["KNOWN_VEHICLE_PATH_FOR_HTML"]
)

app.config["DRIVERS_LICENSE_PATH_FOR_HTML"] = "/static/drivers_licenses"
app.config["DRIVERS_LICENSES"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["DRIVERS_LICENSE_PATH_FOR_HTML"]
)

app.config["AADHAR_PATH_FOR_HTML"] = "/static/aadhars"
app.config["VISITOR_AADHARS"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["AADHAR_PATH_FOR_HTML"]
)

app.config["OTHER_ID_PATH_FOR_HTML"] = "/static/other_ids"
app.config["OTHER_IDS"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["OTHER_ID_PATH_FOR_HTML"]
)

app.config["PASSES_PATH_FOR_HTML"] = "/static/passes"
app.config["PASSES"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["PASSES_PATH_FOR_HTML"]
)

app.config["TRIP_PERMIT_PATH_FOR_HTML"] = "/static/permit_images"
app.config["TRIP_PERMIT_IMAGES"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["TRIP_PERMIT_PATH_FOR_HTML"]
)


app.config["UNKNOWN_PERSONS"] = (
    app.config["PROJECT_BASE_PATH"] + "/static/unknown_persons"
)

app.config["UNKNOWN_VEHICLES"] = (
    app.config["PROJECT_BASE_PATH"] + "/static/unknown_vehicles"
)

app.config["SCREENSHOTS_FOLDER"] = "/static/anpr_vehicles"
app.config["VEHICLE_IMAGES"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["SCREENSHOTS_FOLDER"]
)

app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"] = (
    app.config["KNOWN_VEHICLES"] + "/No-Image-Available.jpg"
)

app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"] = "/static/blacklisted_persons"
app.config["BLACKLISTED_PERSONS"] = (
    app.config["PROJECT_BASE_PATH"] + app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"]
)

ALLOWED_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}

# This schema is intentionally common.  It should only move into an individual
# site profile if a site introduces genuinely different fields or validation.
COMMON_KNOWN_PERSON_SCHEMA = {
    "editable_fields": [
        "name",
        "gender",
        "mobile_number",
        "guardians_name",
        "address",
        "visiting_person_name",
    ],
    "required_fields": ["name", "gender", "mobile_number"],
    "id_number_label": "ID Number",
    "id_image_label": "ID Image",
}

COMMON_TRIP_REPORT_SUMMARY = {
    "trip_report_summary_fields": {
        "title": "Summary Report",
        "totals": [
            {"key": "total_trips", "label": "Trips"},
            {"key": "total_males", "label": "Males"},
            {"key": "total_females", "label": "Females"},
            {"key": "total_children", "label": "Children"},
            {"key": "total_persons", "label": "Total Persons"},
        ],
        "traveler_types": {
            "key": "traveler_types",
            "label": "Traveler Types",
            "name_key": "type",
            "value_key": "trips",
        },
        "grouped_table": {
            "key": "going_to",
            "title": "Summary by Destination",
            "table_id": "trip-summary-going-to",
            "view_more_btn_id": "going-to-view-more-btn",
            "grand_total_note_id": "going-to-grand-total-note",
            "row_class": "going-to-row",
            "hidden_row_class": "going-to-row-hidden",
            "preview_limit": 5,
            "empty_message": "No destination data for current filters.",
            "total_row_label": "Total",
            "columns": [
                {
                    "key": "going_to",
                    "label": "Destination",
                    "empty_value": "Not Available",
                },
                {"key": "trips", "label": "Trips", "empty_value": 0},
                {"key": "males", "label": "Male", "empty_value": 0},
                {"key": "females", "label": "Female", "empty_value": 0},
                {"key": "children", "label": "Children", "empty_value": 0},
                {"key": "total_persons", "label": "Total", "empty_value": 0},
            ],
        },
        "visitor_type_table": {
            "key": "traveler_types",
            "title": "Summary by Visitor Type",
            "table_id": "trip-summary-traveler-type",
            "row_label": "Trips",
            "total_column_label": "Total",
            "empty_message": "No visitor type data for current filters.",
        },
    },
}

COMMON_VEHICLE_SELECTION_MESSAGE = "Please identify the vehicle from the list below."

SINGLE_ACTIVE_LOGIN = True

# All site differences are explicit, validated data in config.py; helpers and
# templates remain shared. The active profile is a typed object (see
# finalfrsproject.config.get_active_profile).
site_profile_name = os.environ.get("SITE_PROFILE", "kupwara").strip().lower()
active_profile = get_active_profile(site_profile_name)
app.config["SITE_PROFILE_CONFIG"] = active_profile

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config["SITE_PROFILE"] = site_profile_name
# Bind-mounted frontend dev: reload HTML/CSS template edits without restarting Gunicorn.
app.config["TEMPLATES_AUTO_RELOAD"] = os.environ.get(
    "TEMPLATE_AUTO_RELOAD", "1"
).strip().lower() in ("1", "true", "yes", "on")
app.config["POSTGRESQL_URL"] = os.environ.get(
    "POSTGRESQL_URL", "census_counters_postgres_db"
)
app.config["REDIS_URL"] = os.environ.get(
    "REDIS_URL", "redis://census_counters_redis:6379/0"
)
app.config["DB_NAME"] = os.environ.get("DB_NAME", "postgres_visitor_vehicle")
app.config["DB_USER_NAME"] = os.environ.get("DB_USER_NAME", "postgres")
app.config["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "postgres")
app.config["DB_PORT"] = os.environ.get("DB_PORT", "5432")
app.config["FACE_RECOGNITION_SERVICE"] = os.environ.get(
    "FACE_RECOGNITION_SERVICE", "http://172.17.0.1:18081/"
)
# app.config["FACE_DELETE_SERVICE"] = "http://172.17.0.1:18081/"

# Every deployment uses the NCPass authentication policy.
app.config["JWT_COOKIE_SECURE"] = True
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
app.config["TEMPLATE_PROFILES"] = active_profile.templates
app.config["APP_TITLE"] = active_profile.app_title

app.config["APP_LOGO_PATH"] = active_profile.logo_path
app.config["ASSET_URL_VERSION"] = os.environ.get(
    "ASSET_URL_VERSION", site_profile_name + "-1"
)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "development-only-change-this-secret"
)
app.config["JWT_COOKIE_CSRF_PROTECT"] = False
app.config["WTF_CSRF_ENABLED"] = True
app.config["TRIP_REPORT_MAX_VIEW_ROWS"] = int(
    os.environ.get("TRIP_REPORT_MAX_VIEW_ROWS", "1000")
)
app.config["VEHICLE_REPORT_MAX_VIEW_ROWS"] = int(
    os.environ.get("VEHICLE_REPORT_MAX_VIEW_ROWS", "1000")
)

# app.config["VISITOR_CATEGORIES"] = ['PASS HOLDER', 'PERMIT HOLDERS', 'TEACHER', 'CIVILIAN', 'GUEST', 'OTHERS']
# app.config["VISITOR_CATEGORIES"] = ['PASS HOLDER', 'TEACHER', 'PERMISSION', 'CIVILIAN' ,'GUEST', 'OTHERS']
app.config["VISITOR_CATEGORIES"] = active_profile.visitor_categories
app.config["VISIT_PURPOSE_CATEGORIES"] = ["OFFICIAL", "LOCAL", "TOURIST"]
app.config["ID_LOOKUP_CATEGORIES"] = active_profile.id_lookup_categories
app.config["ALLOWED_ID_TYPES_BY_VISITOR"] = active_profile.allowed_id_types_by_visitor
app.config["KNOWN_PERSON_SCHEMA"] = COMMON_KNOWN_PERSON_SCHEMA
app.config["UNKNOWN_PERSON_PAGE_FIELDS"] = active_profile.unknown_person_page_fields.model_dump()
app.config["TRIP_REPORT_SUMMARY_FIELDS"] = COMMON_TRIP_REPORT_SUMMARY["trip_report_summary_fields"]
if site_profile_name == "kupwara":
    import copy
    _summary = copy.deepcopy(app.config["TRIP_REPORT_SUMMARY_FIELDS"])
    _gt = _summary.get("grouped_table") or {}
    _gt["title"] = "Summary by To Meet"
    _gt["empty_message"] = "No to meet data for current filters."
    for _col in _gt.get("columns", []):
        if _col.get("key") == "going_to":
            _col["label"] = "To Meet"
    app.config["TRIP_REPORT_SUMMARY_FIELDS"] = _summary
app.config["SUMMARY_TABLE_BY_VISITOR_TYPE"] = active_profile.summary_table_by_visitor_type
app.config["SUMMARY_TABLE_BY_MEN_WOMEN"] = active_profile.summary_table_by_men_women
app.config["TRIP_DURATION_DEFAULT_HOURS"] = active_profile.trip_duration_default_hours
app.config["FACE_MATCH_CONFIDENCE"] = float(
    os.environ.get("FACE_MATCH_CONFIDENCE", active_profile.face_match_confidence)
)
app.config["VEHICLE_FIELDS"] = active_profile.vehicle_fields.model_dump()
app.config["TRIP_CLOSURE_MODE"] = active_profile.trip_closure_mode
app.config["SINGLE_ACTIVE_LOGIN"] = SINGLE_ACTIVE_LOGIN
app.config["VEHICLE_TYPES"] = active_profile.vehicle_types
app.config["VEHICLE_CATEGORIES"] = active_profile.vehicle_categories
app.config["VEHICLE_SELECTION_MESSAGE"] = COMMON_VEHICLE_SELECTION_MESSAGE

# Disable CSRF token expiration
app.config["WTF_CSRF_TIME_LIMIT"] = None
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB
jwt = JWTManager(app)

csrf = CSRFProtect()
csrf.init_app(app)


@app.context_processor
def inject_asset_helpers():
    def asset_url(filename):
        return url_for("static", filename=filename, v=app.config["ASSET_URL_VERSION"])

    return {
        "asset_url": asset_url,
        "template_profiles": app.config["TEMPLATE_PROFILES"],
        "app_title": app.config["APP_TITLE"],
        "app_logo_path": app.config["APP_LOGO_PATH"],
        "site_profile": app.config["SITE_PROFILE"],
        "trip_report_summary_fields": app.config["TRIP_REPORT_SUMMARY_FIELDS"],
        "summary_table_by_visitor_type": app.config["SUMMARY_TABLE_BY_VISITOR_TYPE"],
        "summary_table_by_men_women": app.config["SUMMARY_TABLE_BY_MEN_WOMEN"],
        "visitor_categories": app.config["VISITOR_CATEGORIES"],
        "trip_duration_default_hours": app.config["TRIP_DURATION_DEFAULT_HOURS"],
        "vehicle_fields": app.config["VEHICLE_FIELDS"],
        "trip_closure_mode": app.config["TRIP_CLOSURE_MODE"],
    }


_RUNTIME_DIRECTORIES = (
    "IMAGE_UPLOADS",
    "KNOWN_PERSONS",
    "UNKNOWN_PERSONS",
    "KNOWN_VEHICLES",
    "UNKNOWN_VEHICLES",
    "VISITOR_AADHARS",
    "DRIVERS_LICENSES",
    "OTHER_IDS",
    "PASSES",
    "TRIP_PERMIT_IMAGES",
    "VEHICLE_IMAGES",
    "BLACKLISTED_PERSONS",
)
for config_key in _RUNTIME_DIRECTORIES:
    try:
        os.makedirs(app.config[config_key], exist_ok=True)
    except OSError as error:
        app.logger.error(
            "Unable to create runtime directory %s=%s: %s",
            config_key,
            app.config[config_key],
            error,
        )


def get_locale():
    return session.get("lang", "en")


app.config["BABEL_SUPPORTED_LOCALES"] = ["en", "hi"]
babel = Babel(app, locale_selector=get_locale)


from finalfrsproject import routes, errors
