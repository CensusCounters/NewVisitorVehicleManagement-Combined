from flask import Flask, session, g, url_for
import os, json
from flask_jwt_extended import JWTManager
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, _
import psycopg2, psycopg2.extras
from psycopg2 import pool
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)

@app.before_request
def before_request():
    #print("In before_request.", flush=True)
    if not hasattr(app, 'connection_pool'):
        app.connection_pool = psycopg2.pool.SimpleConnectionPool(
            2,
            20,
            user=app.config["DB_USER_NAME"],
            password=app.config["DB_PASSWORD"],
            host=app.config["POSTGRESQL_URL"],
            port=app.config["DB_PORT"],
            database=app.config["DB_NAME"],
        )
        #print("Connection pool created.", flush=True)

    g.connection_pool = app.connection_pool
    #print("Connection pool added to g variable.", flush=True)

@app.teardown_request
def teardown_request(exception):
    # print("In teardown_request.", flush=True)

    # Optional: Debug what's in g (commented out)
    # custom_attrs = [attr for attr in dir(g) if not attr.startswith('__')]
    # print(f"Attributes in g: {', '.join(custom_attrs)}", flush=True)

    # Show psycopg2 connection pool information
    try:
        if hasattr(g, 'connection_pool'):
            pool = g.connection_pool
            #print(f"psycopg2 Connection Pool Status:", flush=True)
            #print(f"  Max connections: {pool.maxconn}", flush=True)
            #print(f"  Min connections: {pool.minconn}", flush=True)

            # For SimpleConnectionPool, _pool contains AVAILABLE connections
            #if hasattr(pool, '_pool'):
            #    available_connections = len(pool._pool)
                # We can't reliably calculate "used" connections because
                # psycopg2 creates connections on-demand, not pre-allocates them
            #    print(f"  Available connections: {available_connections}", flush=True)
                #print(f"  Note: 'Used' connections can't be calculated reliably", flush=True)
                #print(f"        psycopg2 creates connections on-demand", flush=True)

                # Only warn if NO connections are available
            #    if available_connections == 0:
            #        print(f"  ⚠️  WARNING: No available connections!", flush=True)
            #    else:
            #        print(f"  ✅ Pool status: Normal ({available_connections} available)", flush=True)

            #else:
            #    print(f"  Cannot determine connection usage (internal _pool not accessible)", flush=True)

            # Show pool type
            #print(f"  Pool type: {type(pool).__name__}", flush=True)
        else:
            print("No connection_pool found in g", flush=True)

    except Exception as e:
        print(f"Error getting psycopg2 pool info: {e}", flush=True)


app.config["PROJECT_BASE_PATH"] = os.environ.get("PROJECT_BASE_PATH", "/project/finalfrsproject")
app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] = os.environ.get(
	"REPORT_IMAGE_BASE_PATH", app.config["PROJECT_BASE_PATH"]
)
app.config["IMAGE_PATH_FOR_HTML"] = "/static/images/uploads"
app.config["IMAGE_UPLOADS"] = app.config["PROJECT_BASE_PATH"] + app.config["IMAGE_PATH_FOR_HTML"]

app.config["KNOWN_PERSON_PATH_FOR_HTML"] = "/static/known_persons"
app.config["KNOWN_PERSONS"] = app.config["PROJECT_BASE_PATH"] + app.config["KNOWN_PERSON_PATH_FOR_HTML"]

app.config["KNOWN_VEHICLE_PATH_FOR_HTML"] = "/static/known_vehicles"
app.config["KNOWN_VEHICLES"] = app.config["PROJECT_BASE_PATH"] + app.config["KNOWN_VEHICLE_PATH_FOR_HTML"]

app.config["DRIVERS_LICENSE_PATH_FOR_HTML"] = "/static/drivers_licenses"
app.config["DRIVERS_LICENSES"] = app.config["PROJECT_BASE_PATH"] + app.config["DRIVERS_LICENSE_PATH_FOR_HTML"]

app.config["AADHAR_PATH_FOR_HTML"] = "/static/aadhars"
app.config["VISITOR_AADHARS"] = app.config["PROJECT_BASE_PATH"] + app.config["AADHAR_PATH_FOR_HTML"]

app.config["OTHER_ID_PATH_FOR_HTML"] = "/static/other_ids"
app.config["OTHER_IDS"] = app.config["PROJECT_BASE_PATH"] + app.config["OTHER_ID_PATH_FOR_HTML"]

app.config["PASSES_PATH_FOR_HTML"] = "/static/passes"
app.config["PASSES"] = app.config["PROJECT_BASE_PATH"] + app.config["PASSES_PATH_FOR_HTML"]

app.config["TRIP_PERMIT_PATH_FOR_HTML"] = "/static/permit_images"
app.config["TRIP_PERMIT_IMAGES"] = app.config["PROJECT_BASE_PATH"] + app.config["TRIP_PERMIT_PATH_FOR_HTML"]


app.config["UNKNOWN_PERSONS"] = app.config["PROJECT_BASE_PATH"] + "/static/unknown_persons"

app.config["UNKNOWN_VEHICLES"] = app.config["PROJECT_BASE_PATH"] + "/static/unknown_vehicles"

app.config["SCREENSHOTS_FOLDER"] = "/static/anpr_vehicles"
app.config["VEHICLE_IMAGES"] = app.config["PROJECT_BASE_PATH"] + app.config["SCREENSHOTS_FOLDER"]

app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"] = app.config["KNOWN_VEHICLES"] + "/No-Image-Available.jpg" 

app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"] = "/static/blacklisted_persons"
app.config["BLACKLISTED_PERSONS"] = app.config["PROJECT_BASE_PATH"] + app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"]

ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}

# This schema is intentionally common.  It should only move into an individual
# site profile if a site introduces genuinely different fields or validation.
COMMON_KNOWN_PERSON_SCHEMA = {
	"editable_fields": [
		"name", "gender", "mobile_number", "guardians_name", "address",
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
            "key": "traveler_types", "label": "Traveler Types",
            "name_key": "type", "value_key": "trips",
        },
        "grouped_table": {
            "key": "going_to", "title": "Summary by Destination",
            "table_id": "trip-summary-going-to",
            "view_more_btn_id": "going-to-view-more-btn",
            "grand_total_note_id": "going-to-grand-total-note",
            "row_class": "going-to-row",
            "hidden_row_class": "going-to-row-hidden",
            "preview_limit": 5,
            "empty_message": "No destination data for current filters.",
            "total_row_label": "Total",
            "columns": [
                {"key": "going_to", "label": "Destination", "empty_value": "Not Available"},
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

SINGLE_ACTIVE_LOGIN = True

# All site differences are explicit data; helpers and templates remain shared.
SITE_PROFILES = {'kupwara': {'id_lookup_workflow': 'kupwara',
             'app_title': 'Vajr Entry Management System',
             'logo_path': 'images/vajr-28-div-logo.jpeg',
             'visitor_categories': ['PASS HOLDER', 'PERMISSION', 'CIVILIAN', 'GUEST', 'OTHERS'],
             'id_lookup_categories': ['AADHAR', 'DRIVERS LICENSE', 'PASS'],
             'allowed_id_types_by_visitor': {'PASS HOLDER': ['AADHAR', 'DRIVERS LICENSE', 'PASS'],
                                             'PERMISSION': ['AADHAR', 'DRIVERS LICENSE'],
                                             'CIVILIAN': ['AADHAR', 'DRIVERS LICENSE'],
                                             'GUEST': ['AADHAR', 'DRIVERS LICENSE'],
                                             'OTHERS': ['AADHAR', 'DRIVERS LICENSE']},
             'unknown_person_page_fields': {'purpose_input': 'text', 'require_dl_for': []},
             'trip_duration_default_hours': 1,
             'face_match_confidence': 0.7,
             'summary_table_by_visitor_type': True,
             'summary_table_by_men_women': True,
             'trip_closure_mode': 'manual',
             'vehicle_types': [],
             'vehicle_categories': [],
             'vehicle_fields': {'known_vehicle': {'fields': ['vehicle_number',
                                                             'vehicle_owner_name',
                                                             'make',
                                                             'color'],
                                                  'required_fields': ['vehicle_number',
                                                                      'vehicle_owner_name',
                                                                      'make',
                                                                      'color']},
                                'unknown_vehicle': {'fields': ['vehicle_number',
                                                               'vehicle_owner_name',
                                                               'vehicle_make',
                                                               'vehicle_color'],
                                                    'required_fields': ['vehicle_number',
                                                                        'vehicle_owner_name']}},
             'aadhaar_lookup': {'custom_dropdown': False,
                                'support_male_passenger_skip': True,
                                'default_message_key': 'id_type',
                                'lookup_strategy': 'multi',
                                'force_id_type': None,
                                'require_input_validation': False,
                                'pass_holder_teacher_uses_pass_image': False,
                                'exception_template_post': '500.html',
                                'show_id_type_first': ['PASS HOLDER',
                                                       'PERMISSION',
                                                       'CIVILIAN',
                                                       'GUEST',
                                                       'OTHERS'],
                                'show_id_number_only': ['TEACHER']},
             'known_vehicle': {'person_log_label': 'new_vehicle_owner: '},
             'unknown_vehicle': {'translate_messages': True,
                                 'include_vehicle_choices': False,
                                 'owner_result_key': 'vehicle_registered_to'},
             'person_lookup': {'translate_messages': True},
             'person_report': {'translate_messages': True},
             'make_trip_summary': {'passenger_registration_loop': True, 'translate_messages': True},
             'trip_registration': {'translate_messages': True,
                                   'reset_driver_trip_id': False,
                                   'duration_in_days': False,
                                   'vehicle_selection_message': "'Please identify the vehicle from "
                                                                "the list below.'"},
             'recognize_vehicle': {'translate_messages': True,
                                   'manual_plate_search': True,
                                   'strict_lookup_result': False,
                                   'require_vehicle_url': True,
                                   'require_cached_vehicle_list': False,
                                   'post_log_name': 'recognize_vehicle_helper_post'},
             'report_home': {'redirect_missing_session': False, 'string_session_key': False},
             'vehicle_report': {'load_initial_records': False,
                                'post_exception_message': 'An unexpected error occurred while '
                                                          'generating the report. Please try '
                                                          'again.',
                                'post_query_failure_session_message': 'An unexpected error '
                                                                      'occurred while generating '
                                                                      'the vehicle report. Please '
                                                                      'try again.',
                                'log_traceback': True},
             'templates': {'401': {'translate_labels': True},
                           '404': {'translate_labels': True},
                           '500': {'translate_labels': True},
                           'add_trip': {'translate_labels': True,
                                        'address_max_length': 30,
                                        'extended_vehicle_details': False},
                           'close_trip': {'translate_labels': True},
                           'trip_report_details_styles': {'compact_link_styles': False},
                           'trip_report_summary_script': {'separate_other_column': False},
                           'known_vehicle': {'translate_labels': True,
                                             'extended_vehicle_details': False},
                           'person_lookup': {'translate_labels': True},
                           'person_lookup_result_list': {'translate_labels': True},
                           'person_report': {'translate_labels': True,
                                             'destination_gate_columns': False,
                                             'extended_vehicle_details': False},
                           'static_recognize_vehicle': {'translate_labels': True},
                           'static_recognize': {'translate_labels': True},
                           'static_trip_summary': {'translate_labels': True},
                           'trip_summary': {'translate_labels': True,
                                            'show_missing_value_labels': False,
                                            'enhanced_image_preview': False},
                           'unknown_vehicle': {'translate_labels': True,
                                               'extended_vehicle_details': False}}},
 'ncpass': {'id_lookup_workflow': 'ncpass',
            'app_title': 'SM Hill Visitor Management System',
            'logo_path': 'images/7RR-Logo.jpeg',
            'visitor_categories': ['DRIVER', 'PASSENGER'],
            'id_lookup_categories': ['AADHAR'],
            'allowed_id_types_by_visitor': {'DRIVER': ['AADHAR'], 'PASSENGER': ['AADHAR']},
            'unknown_person_page_fields': {'purpose_input': 'select', 'require_dl_for': ['DRIVER']},
            'trip_duration_default_hours': 12,
            'face_match_confidence': 0.7,
            'summary_table_by_visitor_type': True,
            'summary_table_by_men_women': True,
            'trip_closure_mode': 'manual',
            'vehicle_types': ['LOCAL', 'TOURIST'],
            'vehicle_categories': ['LIGHT VEHICLE', 'HEAVY VEHICLE', 'AMBULANCE', 'LD CARRIER'],
            'vehicle_fields': {'known_vehicle': {'fields': ['vehicle_number',
                                                            'vehicle_type',
                                                            'vehicle_model',
                                                            'vehicle_owner_name',
                                                            'vehicle_registration_number',
                                                            'make',
                                                            'color'],
                                                 'required_fields': ['vehicle_number',
                                                                     'vehicle_type',
                                                                     'vehicle_model',
                                                                     'vehicle_owner_name',
                                                                     'make',
                                                                     'color']},
                               'unknown_vehicle': {'fields': ['vehicle_number',
                                                              'vehicle_type',
                                                              'vehicle_model',
                                                              'vehicle_owner_name',
                                                              'vehicle_registration_number',
                                                              'vehicle_make',
                                                              'vehicle_color'],
                                                   'required_fields': ['vehicle_number',
                                                                       'vehicle_owner_name']}},
            'aadhaar_lookup': {'custom_dropdown': True,
                               'support_male_passenger_skip': False,
                               'default_message_key': 'visitor_type',
                               'lookup_strategy': 'aadhar_only',
                               'force_id_type': 'AADHAR',
                               'require_input_validation': True,
                               'pass_holder_teacher_uses_pass_image': False,
                               'exception_template_post': 'home.html',
                               'show_id_type_first': [],
                               'show_id_number_only': []},
            'known_vehicle': {'person_log_label': 'new_vehicle_rider: '},
            'unknown_vehicle': {'translate_messages': False,
                                'include_vehicle_choices': True,
                                'owner_result_key': 'vehicle_owner'},
            'person_lookup': {'translate_messages': False},
            'person_report': {'translate_messages': False},
            'make_trip_summary': {'passenger_registration_loop': False,
                                  'translate_messages': False},
            'trip_registration': {'translate_messages': False,
                                  'reset_driver_trip_id': True,
                                  'duration_in_days': True,
                                  'vehicle_selection_message': 'Please identify the vehicle from '
                                                               'the list below.'},
            'recognize_vehicle': {'translate_messages': False,
                                  'manual_plate_search': False,
                                  'strict_lookup_result': True,
                                  'require_vehicle_url': False,
                                  'require_cached_vehicle_list': True,
                                  'post_log_name': 'known_vehicle_helper_post'},
            'report_home': {'redirect_missing_session': True, 'string_session_key': True},
            'vehicle_report': {'load_initial_records': True,
                               'post_exception_message': 'An unexpected error occurred while '
                                                         'generating the vehicle report. Please '
                                                         'try again..',
                               'post_query_failure_session_message': 'An unexpected error occurred '
                                                                     'while generating the person '
                                                                     'report. Please try again.',
                               'log_traceback': False},
            'templates': {'401': {'translate_labels': False},
                          '404': {'translate_labels': False},
                          '500': {'translate_labels': False},
                          'add_trip': {'translate_labels': False,
                                       'address_max_length': 30,
                                       'extended_vehicle_details': True},
                          'close_trip': {'translate_labels': False},
                          'trip_report_details_styles': {'compact_link_styles': True},
                          'trip_report_summary_script': {'separate_other_column': True},
                          'known_vehicle': {'translate_labels': False,
                                            'extended_vehicle_details': True},
                          'person_lookup': {'translate_labels': False},
                          'person_lookup_result_list': {'translate_labels': False},
                          'person_report': {'translate_labels': False,
                                            'destination_gate_columns': False,
                                            'extended_vehicle_details': True},
                          'static_recognize_vehicle': {'translate_labels': False},
                          'static_recognize': {'translate_labels': False},
                          'static_trip_summary': {'translate_labels': False},
                          'trip_summary': {'translate_labels': False,
                                           'show_missing_value_labels': False,
                                           'enhanced_image_preview': True},
                          'unknown_vehicle': {'translate_labels': False,
                                              'extended_vehicle_details': True}}},
 'ganganagar': {'id_lookup_workflow': 'ganganagar',
                'app_title': 'Amogh Entry Management System',
                'logo_path': 'images/amogh-ganganagar-logo.png',
                'visitor_categories': ['PASS HOLDER',
                                       'TEACHER',
                                       'PERMISSION',
                                       'CIVILIAN',
                                       'GUEST',
                                       'MES',
                                       'LABOUR',
                                       'OTHERS'],
                'id_lookup_categories': ['AADHAR', 'DRIVERS LICENSE', 'PASS'],
                'allowed_id_types_by_visitor': {'PASS HOLDER': ['AADHAR',
                                                                'DRIVERS LICENSE',
                                                                'PASS'],
                                                'TEACHER': ['PASS'],
                                                'PERMISSION': ['AADHAR', 'DRIVERS LICENSE'],
                                                'CIVILIAN': ['AADHAR', 'DRIVERS LICENSE'],
                                                'GUEST': ['AADHAR', 'DRIVERS LICENSE'],
                                                'MES': ['AADHAR', 'DRIVERS LICENSE'],
                                                'LABOUR': ['AADHAR', 'DRIVERS LICENSE'],
                                                'OTHERS': ['AADHAR', 'DRIVERS LICENSE']},
                'unknown_person_page_fields': {'purpose_input': 'text', 'require_dl_for': []},
                'trip_duration_default_hours': 1,
                'face_match_confidence': 0.7,
                'summary_table_by_visitor_type': True,
                'summary_table_by_men_women': True,
                'trip_closure_mode': 'manual_and_anpr',
                'vehicle_types': [],
                'vehicle_categories': [],
                'vehicle_fields': {'known_vehicle': {'fields': ['vehicle_number',
                                                                'vehicle_owner_name',
                                                                'make',
                                                                'color'],
                                                     'required_fields': ['vehicle_number',
                                                                         'vehicle_owner_name',
                                                                         'make',
                                                                         'color']},
                                   'unknown_vehicle': {'fields': ['vehicle_number',
                                                                  'vehicle_owner_name',
                                                                  'vehicle_make',
                                                                  'vehicle_color'],
                                                       'required_fields': ['vehicle_number',
                                                                           'vehicle_owner_name']}},
                'aadhaar_lookup': {'custom_dropdown': False,
                                   'support_male_passenger_skip': True,
                                   'default_message_key': 'id_type',
                                   'lookup_strategy': 'multi',
                                   'force_id_type': None,
                                   'require_input_validation': False,
                                   'pass_holder_teacher_uses_pass_image': True,
                                   'exception_template_post': '500.html',
                                   'show_id_type_first': ['PASS HOLDER',
                                                          'PERMISSION',
                                                          'CIVILIAN',
                                                          'GUEST',
                                                          'OTHERS',
                                                          'MES',
                                                          'LABOUR'],
                                   'show_id_number_only': ['TEACHER']},
                'known_vehicle': {'person_log_label': 'new_vehicle_owner: '},
                'unknown_vehicle': {'translate_messages': True,
                                    'include_vehicle_choices': False,
                                    'owner_result_key': 'vehicle_registered_to'},
                'person_lookup': {'translate_messages': False},
                'person_report': {'translate_messages': False},
                'make_trip_summary': {'passenger_registration_loop': True,
                                      'translate_messages': False},
                'trip_registration': {'translate_messages': False,
                                      'reset_driver_trip_id': True,
                                      'duration_in_days': False,
                                      'vehicle_selection_message': "'Please identify the vehicle "
                                                                   "from the list below.'"},
                'recognize_vehicle': {'translate_messages': True,
                                      'manual_plate_search': True,
                                      'strict_lookup_result': False,
                                      'require_vehicle_url': True,
                                      'require_cached_vehicle_list': False,
                                      'post_log_name': 'recognize_vehicle_helper_post'},
                'report_home': {'redirect_missing_session': False, 'string_session_key': False},
                'vehicle_report': {'load_initial_records': False,
                                   'post_exception_message': 'An unexpected error occurred while '
                                                             'generating the report. Please try '
                                                             'again.',
                                   'post_query_failure_session_message': 'An unexpected error '
                                                                         'occurred while '
                                                                         'generating the vehicle '
                                                                         'report. Please try '
                                                                         'again.',
                                   'log_traceback': True},
                'templates': {'401': {'translate_labels': False},
                              '404': {'translate_labels': False},
                              '500': {'translate_labels': False},
                              'add_trip': {'translate_labels': True,
                                           'address_max_length': 100,
                                           'extended_vehicle_details': False},
                              'close_trip': {'translate_labels': False},
                              'trip_report_details_styles': {'compact_link_styles': False},
                              'trip_report_summary_script': {'separate_other_column': False},
                              'known_vehicle': {'translate_labels': False,
                                                'extended_vehicle_details': False},
                              'person_lookup': {'translate_labels': False},
                              'person_lookup_result_list': {'translate_labels': False},
                              'person_report': {'translate_labels': False,
                                                'destination_gate_columns': True,
                                                'extended_vehicle_details': False},
                              'static_recognize_vehicle': {'translate_labels': False},
                              'static_recognize': {'translate_labels': False},
                              'static_trip_summary': {'translate_labels': False},
                              'trip_summary': {'translate_labels': False,
                                               'show_missing_value_labels': False,
                                               'enhanced_image_preview': False},
                              'unknown_vehicle': {'translate_labels': False,
                                                  'extended_vehicle_details': False}}},
 'tangdhar': {'id_lookup_workflow': 'kupwara',
              'app_title': 'Shakti Vijay Entry Management System',
              'logo_path': 'images/shakti-vijay-logo.jpeg',
              'visitor_categories': ['PASS HOLDER', 'PERMISSION', 'CIVILIAN', 'GUEST', 'OTHERS'],
              'id_lookup_categories': ['AADHAR', 'DRIVERS LICENSE', 'PASS'],
              'allowed_id_types_by_visitor': {'PASS HOLDER': ['AADHAR', 'DRIVERS LICENSE', 'PASS'],
                                              'PERMISSION': ['AADHAR', 'DRIVERS LICENSE'],
                                              'CIVILIAN': ['AADHAR', 'DRIVERS LICENSE'],
                                              'GUEST': ['AADHAR', 'DRIVERS LICENSE'],
                                              'OTHERS': ['AADHAR', 'DRIVERS LICENSE']},
              'unknown_person_page_fields': {'purpose_input': 'text', 'require_dl_for': []},
              'trip_duration_default_hours': 1,
              'face_match_confidence': 0.7,
              'summary_table_by_visitor_type': True,
              'summary_table_by_men_women': True,
              'trip_closure_mode': 'manual',
              'vehicle_types': [],
              'vehicle_categories': [],
              'vehicle_fields': {'known_vehicle': {'fields': ['vehicle_number',
                                                              'vehicle_owner_name',
                                                              'make',
                                                              'color'],
                                                   'required_fields': ['vehicle_number',
                                                                       'vehicle_owner_name',
                                                                       'make',
                                                                       'color']},
                                 'unknown_vehicle': {'fields': ['vehicle_number',
                                                                'vehicle_owner_name',
                                                                'vehicle_make',
                                                                'vehicle_color'],
                                                     'required_fields': ['vehicle_number',
                                                                         'vehicle_owner_name']}},
              'aadhaar_lookup': {'custom_dropdown': False,
                                 'support_male_passenger_skip': True,
                                 'default_message_key': 'id_type',
                                 'lookup_strategy': 'multi',
                                 'force_id_type': None,
                                 'require_input_validation': False,
                                 'pass_holder_teacher_uses_pass_image': False,
                                 'exception_template_post': '500.html',
                                 'show_id_type_first': ['PASS HOLDER',
                                                        'PERMISSION',
                                                        'CIVILIAN',
                                                        'GUEST',
                                                        'OTHERS'],
                                 'show_id_number_only': ['TEACHER']},
              'known_vehicle': {'person_log_label': 'new_vehicle_owner: '},
              'unknown_vehicle': {'translate_messages': True,
                                  'include_vehicle_choices': False,
                                  'owner_result_key': 'vehicle_registered_to'},
              'person_lookup': {'translate_messages': True},
              'person_report': {'translate_messages': True},
              'make_trip_summary': {'passenger_registration_loop': True,
                                    'translate_messages': True},
              'trip_registration': {'translate_messages': True,
                                    'reset_driver_trip_id': False,
                                    'duration_in_days': False,
                                    'vehicle_selection_message': "'Please identify the vehicle "
                                                                 "from the list below.'"},
              'recognize_vehicle': {'translate_messages': True,
                                    'manual_plate_search': True,
                                    'strict_lookup_result': False,
                                    'require_vehicle_url': True,
                                    'require_cached_vehicle_list': False,
                                    'post_log_name': 'recognize_vehicle_helper_post'},
              'report_home': {'redirect_missing_session': False, 'string_session_key': False},
              'vehicle_report': {'load_initial_records': False,
                                 'post_exception_message': 'An unexpected error occurred while '
                                                           'generating the report. Please try '
                                                           'again.',
                                 'post_query_failure_session_message': 'An unexpected error '
                                                                       'occurred while generating '
                                                                       'the vehicle report. Please '
                                                                       'try again.',
                                 'log_traceback': True},
              'templates': {'401': {'translate_labels': True},
                            '404': {'translate_labels': True},
                            '500': {'translate_labels': True},
                            'add_trip': {'translate_labels': True,
                                         'address_max_length': 30,
                                         'extended_vehicle_details': False},
                            'close_trip': {'translate_labels': True},
                            'trip_report_details_styles': {'compact_link_styles': False},
                            'trip_report_summary_script': {'separate_other_column': False},
                            'known_vehicle': {'translate_labels': True,
                                              'extended_vehicle_details': False},
                            'person_lookup': {'translate_labels': True},
                            'person_lookup_result_list': {'translate_labels': True},
                            'person_report': {'translate_labels': True,
                                              'destination_gate_columns': False,
                                              'extended_vehicle_details': False},
                            'static_recognize_vehicle': {'translate_labels': True},
                            'static_recognize': {'translate_labels': True},
                            'static_trip_summary': {'translate_labels': True},
                            'trip_summary': {'translate_labels': True,
                                             'show_missing_value_labels': True,
                                             'enhanced_image_preview': False},
                            'unknown_vehicle': {'translate_labels': True,
                                                'extended_vehicle_details': False}}}}


def _validate_trip_report_summary(summary_settings, label):
    supported_trip_totals = {
        "total_trips", "total_males", "total_females",
        "total_children", "total_persons",
    }
    supported_grouped_columns = {
        "going_to", "trips", "males", "females", "children", "total_persons",
    }
    if set(summary_settings.keys()) != {"trip_report_summary_fields"}:
        raise RuntimeError(f"{label} must only define trip_report_summary_fields")

    summary_fields = summary_settings["trip_report_summary_fields"]
    if set(summary_fields) != {
        "title", "totals", "traveler_types", "grouped_table", "visitor_type_table",
    }:
        raise RuntimeError(f"{label} has an invalid trip report summary structure")
    unsupported_totals = {
        field["key"] for field in summary_fields["totals"]
    } - supported_trip_totals
    grouped_table = summary_fields["grouped_table"]
    unsupported_columns = (
        {field["key"] for field in grouped_table["columns"]}
    ) - supported_grouped_columns
    if unsupported_totals or unsupported_columns:
        raise RuntimeError(
            f"{label} trip report summary contains unsupported fields: "
            f"{sorted(unsupported_totals | unsupported_columns)}"
        )
    if summary_fields["traveler_types"]["key"] != "traveler_types":
        raise RuntimeError(f"{label} has an unsupported traveler summary source")
    if grouped_table["key"] != "going_to" or grouped_table["preview_limit"] < 1:
        raise RuntimeError(f"{label} has invalid grouped trip summary settings")
    visitor_type_table = summary_fields["visitor_type_table"]
    if visitor_type_table["key"] != "traveler_types":
        raise RuntimeError(f"{label} has an invalid traveler type summary table")


def _validate_vehicle_fields(vehicle_fields, label):
    for page_name in ("known_vehicle", "unknown_vehicle"):
        page_fields = vehicle_fields.get(page_name, {})
        fields = set(page_fields.get("fields", []))
        required_fields = set(page_fields.get("required_fields", []))
        if not fields or not required_fields.issubset(fields):
            raise RuntimeError(f"{label}/{page_name} has invalid vehicle field requirements")


def _resolve_site_profile(profile_name):
    return {
        **SITE_PROFILES[profile_name],
        **COMMON_TRIP_REPORT_SUMMARY,
    }


def _validate_site_profiles(profiles, common_summary):
    _validate_trip_report_summary(common_summary, "COMMON_TRIP_REPORT_SUMMARY")
    shared_keys = set(common_summary.keys())
    required_profile_keys = {
        "id_lookup_workflow", "app_title", "logo_path",
        "visitor_categories", "id_lookup_categories",
        "allowed_id_types_by_visitor",
        "unknown_person_page_fields", "vehicle_types", "vehicle_fields",
        "vehicle_categories",
        "trip_duration_default_hours", "face_match_confidence",
        "trip_closure_mode",
        "summary_table_by_visitor_type", "summary_table_by_men_women",
    }
    for profile_name, profile in profiles.items():
        duplicated = shared_keys & profile.keys()
        if duplicated:
            raise RuntimeError(
                f"{profile_name} profile must not override shared config: "
                f"{sorted(duplicated)}"
            )
        missing = required_profile_keys - profile.keys()
        if missing:
            raise RuntimeError(f"{profile_name} profile is missing: {sorted(missing)}")
        _validate_vehicle_fields(profile["vehicle_fields"], profile_name)
        categories = set(profile["visitor_categories"])
        configured_categories = set(profile["allowed_id_types_by_visitor"])
        if categories != configured_categories:
            raise RuntimeError(
                f"{profile_name} ID rules must cover every visitor category exactly"
            )
        known_id_types = set(profile["id_lookup_categories"])
        for visitor_type, id_types in profile["allowed_id_types_by_visitor"].items():
            unsupported = set(id_types) - known_id_types
            if unsupported:
                raise RuntimeError(
                    f"{profile_name}/{visitor_type} contains unsupported IDs: {sorted(unsupported)}"
                )
        if profile["trip_duration_default_hours"] < 1:
            raise RuntimeError(f"{profile_name} trip duration must be at least one hour")
        confidence = profile["face_match_confidence"]
        if not isinstance(confidence, (int, float)) or not (0 < confidence <= 1):
            raise RuntimeError(
                f"{profile_name} face_match_confidence must be a number between 0 and 1"
            )
        if profile["trip_closure_mode"] not in {"manual", "manual_and_anpr"}:
            raise RuntimeError(f"{profile_name} has an invalid trip closure mode")
        if not isinstance(profile["summary_table_by_visitor_type"], bool):
            raise RuntimeError(f"{profile_name} summary_table_by_visitor_type must be true or false")
        if not isinstance(profile["summary_table_by_men_women"], bool):
            raise RuntimeError(f"{profile_name} summary_table_by_men_women must be true or false")


_validate_site_profiles(SITE_PROFILES, COMMON_TRIP_REPORT_SUMMARY)

site_profile_name = os.environ.get("SITE_PROFILE", "kupwara").strip().lower()
if site_profile_name not in SITE_PROFILES:
    valid_profiles = ", ".join(sorted(SITE_PROFILES))
    raise RuntimeError(
        f"Unsupported SITE_PROFILE={site_profile_name!r}. Expected one of: {valid_profiles}."
    )
site_profile = _resolve_site_profile(site_profile_name)

if site_profile_name == "ncpass":
    # NCPass is normally deployed behind the TLS reverse proxy.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config["SITE_PROFILE"] = site_profile_name
# Bind-mounted frontend dev: reload HTML/CSS template edits without restarting Gunicorn.
app.config["TEMPLATES_AUTO_RELOAD"] = os.environ.get(
    "TEMPLATE_AUTO_RELOAD", "1"
).strip().lower() in ("1", "true", "yes", "on")
app.config["POSTGRESQL_URL"] = os.environ.get("POSTGRESQL_URL", "census_counters_postgres_db")
app.config["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://census_counters_redis:6379/0")
app.config["DB_NAME"] = os.environ.get("DB_NAME", "postgres_visitor_vehicle")
app.config["DB_USER_NAME"] = os.environ.get("DB_USER_NAME", "postgres")
app.config["DB_PASSWORD"] = os.environ.get("DB_PASSWORD", "postgres")
app.config["DB_PORT"] = os.environ.get("DB_PORT", "5432")
app.config["FACE_RECOGNITION_SERVICE"] = os.environ.get(
    "FACE_RECOGNITION_SERVICE", "http://172.17.0.1:18081/"
)
#app.config["FACE_DELETE_SERVICE"] = "http://172.17.0.1:18081/"

# Every deployment uses the NCPass authentication policy.
app.config["JWT_COOKIE_SECURE"] = True
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=30)
app.config["TEMPLATE_PROFILES"] = site_profile["templates"]
app.config["APP_TITLE"] = site_profile["app_title"]
app.config["ID_LOOKUP_WORKFLOW"] = site_profile["id_lookup_workflow"]
app.config["AADHAAR_LOOKUP_PROFILE"] = site_profile["aadhaar_lookup"]
app.config["KNOWN_VEHICLE_PROFILE"] = site_profile["known_vehicle"]
app.config["UNKNOWN_VEHICLE_PROFILE"] = site_profile["unknown_vehicle"]
app.config["PERSON_LOOKUP_PROFILE"] = site_profile["person_lookup"]
app.config["PERSON_REPORT_PROFILE"] = site_profile["person_report"]
app.config["MAKE_TRIP_SUMMARY_PROFILE"] = site_profile["make_trip_summary"]
app.config["TRIP_REGISTRATION_PROFILE"] = site_profile["trip_registration"]
app.config["RECOGNIZE_VEHICLE_PROFILE"] = site_profile["recognize_vehicle"]
app.config["REPORT_HOME_PROFILE"] = site_profile["report_home"]
app.config["VEHICLE_REPORT_PROFILE"] = site_profile["vehicle_report"]
app.config["APP_LOGO_PATH"] = site_profile["logo_path"]
app.config["ASSET_URL_VERSION"] = os.environ.get("ASSET_URL_VERSION", site_profile_name + "-1")
app.config['SECRET_KEY'] = os.environ.get(
    'SECRET_KEY', 'development-only-change-this-secret'
)
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['WTF_CSRF_ENABLED'] = True
app.config["TRIP_REPORT_MAX_VIEW_ROWS"] = int(os.environ.get("TRIP_REPORT_MAX_VIEW_ROWS", "1000"))
app.config["VEHICLE_REPORT_MAX_VIEW_ROWS"] = int(os.environ.get("VEHICLE_REPORT_MAX_VIEW_ROWS", "1000"))

#app.config["VISITOR_CATEGORIES"] = ['PASS HOLDER', 'PERMIT HOLDERS', 'TEACHER', 'CIVILIAN', 'GUEST', 'OTHERS']
#app.config["VISITOR_CATEGORIES"] = ['PASS HOLDER', 'TEACHER', 'PERMISSION', 'CIVILIAN' ,'GUEST', 'OTHERS']
app.config["VISITOR_CATEGORIES"] = site_profile["visitor_categories"]
app.config["VISIT_PURPOSE_CATEGORIES"] = ['OFFICIAL', 'LOCAL', 'TOURIST']
app.config["ID_LOOKUP_CATEGORIES"] = site_profile["id_lookup_categories"]
app.config["ALLOWED_ID_TYPES_BY_VISITOR"] = site_profile["allowed_id_types_by_visitor"]
app.config["KNOWN_PERSON_SCHEMA"] = COMMON_KNOWN_PERSON_SCHEMA
app.config["UNKNOWN_PERSON_PAGE_FIELDS"] = site_profile["unknown_person_page_fields"]
app.config["TRIP_REPORT_SUMMARY_FIELDS"] = site_profile["trip_report_summary_fields"]
app.config["SUMMARY_TABLE_BY_VISITOR_TYPE"] = site_profile["summary_table_by_visitor_type"]
app.config["SUMMARY_TABLE_BY_MEN_WOMEN"] = site_profile["summary_table_by_men_women"]
app.config["TRIP_DURATION_DEFAULT_HOURS"] = site_profile["trip_duration_default_hours"]
app.config["FACE_MATCH_CONFIDENCE"] = float(
    os.environ.get("FACE_MATCH_CONFIDENCE", site_profile["face_match_confidence"])
)
app.config["VEHICLE_FIELDS"] = site_profile["vehicle_fields"]
app.config["TRIP_CLOSURE_MODE"] = site_profile["trip_closure_mode"]
app.config["SINGLE_ACTIVE_LOGIN"] = SINGLE_ACTIVE_LOGIN
app.config["VEHICLE_TYPES"] = site_profile["vehicle_types"]
app.config["VEHICLE_CATEGORIES"] = site_profile["vehicle_categories"]

# Disable CSRF token expiration
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.config['MAX_CONTENT_LENGTH'] = 2*1024*1024*1024 #2GB
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
    return session.get('lang', 'en')

app.config['BABEL_SUPPORTED_LOCALES'] = ['en', 'hi']
babel = Babel(app, locale_selector=get_locale)


from finalfrsproject import routes, errors
