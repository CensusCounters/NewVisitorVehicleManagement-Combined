import json
from flask import render_template
from datetime import datetime
import time
from finalfrsproject import sqlCommands
from flask_babel import _
import traceback

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting person_report_helper_post", flush=True)
    try:
        user_name = jwt_details.get("logged_in_user_name")
        user_type = jwt_details.get("logged_in_user_type")
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        session_values_json_redis.update({"ticket_status":"person_report"})
        person_trip_list = []
        send_to_html_json = {}
        person_id = form.get('person_id')
        print(f'person_id: {person_id}', flush=True)
        result = sqlCommands.get_trip_details_by_person_id(person_id)

        if not result or result.get('Status') == "Fail":
            send_to_html_json = {
                'logged_in_user': jwt_details.get("logged_in_user_name"),
                'logged_in_user_type': jwt_details.get("logged_in_user_type"),
                'message': _('Error while retrieving trips for uploaded picture. Please try again.'),
                'page_title': _('Person Lookup')
            }
            session_values_json_redis.update(
                {"message": _("Error while retrieving trips for uploaded picture. Please try again.")})
            session_values_json_redis.update({"ticket_status": "person_lookup"})
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed person_report_helper_post | Execution time: {execution_time}ms",
                  flush=True)
            return render_template('person_lookup.html', details=send_to_html_json)

        elif result.get('Details') is None:
            print("No records found in unfinished_trips", flush=True)
            send_to_html_json = {
                'person_report_list': person_trip_list,
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'message': _('No records found for the selected person.'),
                'page_title': _('Person Trip Report')
            }

        else:
            person_trip_list = result.get('Details')
            print('person_trip_list returned: ', person_trip_list, flush=True)
            send_to_html_json = {
                'person_trip_list': person_trip_list,
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'message': _('Following records were found for the selected person.'),
                'page_title': _('Person Trip Report')
            }

        session_values_json_redis.update({"person_report": person_trip_list})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        # print('redis in person report on generate report success: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed person_report_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('person_report.html', details=send_to_html_json)

    except Exception as e:
        # Log the error and return an error page or message
        stack_trace = traceback.format_exc()  # Get full stack trace
        print(f"Stack Trace:\n{stack_trace}", flush=True)
        print(f"[ERROR] post_handler failed: {e}")
        send_to_html_json = {
            'message': _("Error in the person trip report page. Please try again."),
            'page_title': _('Person Lookup')
        }
        print("404 error details: ", send_to_html_json)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed person_report_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('person_lookup.html', details=send_to_html_json)

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting person_report_helper_get", flush=True)
    send_to_html_json = {
        'message': _("Error in the person trip report page. Please try again."),
        'page_title': _('Person Lookup')
    }
    print("person report helper get: ", send_to_html_json)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed person_report_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('person_lookup.html', details=send_to_html_json)
