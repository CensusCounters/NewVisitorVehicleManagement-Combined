import json
from flask import render_template
from datetime import datetime, time as dt_time
from flask_babel import _
import traceback
import time


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting trip_report_helper_get", flush=True)

    user_name = jwt_details.get("logged_in_user_name")
    user_type = jwt_details.get("logged_in_user_type")
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    try:
        session_values_json_redis.update({"ticket_status": "trip_report"})

        start_date = datetime.combine(datetime.now(), dt_time.min)
        end_date = datetime.combine(datetime.now(), dt_time.max)

        send_to_html_json = {
            'trip_report_list': [],
            'start_date': start_date,
            'end_date': end_date,
            'message': _('Report for the selected dates.'),
            'message1': '',
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': 'Trip Report'
        }
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed trip_report_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('trip_report.html', details=send_to_html_json)

    except Exception as e:
        print("Error in trip report helper: ", str(e), flush=True)
        stack_trace = traceback.format_exc()
        print(f"Stack Trace:\n{stack_trace}", flush=True)
        send_to_html_json = {
            'message': "An unexpected error occurred while generating the trip report. Please try again..",
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': "Error"
        }
        session_values_json_redis.update(
            {"message": "An unexpected error occurred while generating the trip report. Please try again."})
        session_values_json_redis.update({"ticket_status": "report_home"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        return render_template('report_home.html', details=send_to_html_json)


def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting trip_report_helper_post", flush=True)

    user_name = jwt_details.get("logged_in_user_name")
    user_type = jwt_details.get("logged_in_user_type")
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    try:
        start_date = form.get('start_date')
        end_date = form.get('end_date')

        send_to_html_json = {
            'trip_report_list': [],
            'start_date': start_date,
            'end_date': end_date,
            'message': _('Report for the selected dates.'),
            'message1': '',
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': 'Trip Report'
        }
        session_values_json_redis.update({"ticket_status": "trip_report"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed trip_report_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('trip_report.html', details=send_to_html_json)

    except Exception as e:
        print(f'Error in trip report post request: {str(e)}', flush=True)
        stack_trace = traceback.format_exc()
        print(f"Stack Trace:\n{stack_trace}", flush=True)
        send_to_html_json = {
            'message': "An unexpected error occurred while generating the trip report. Please try again.",
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': "Error"
        }
        session_values_json_redis.update(
            {"message": "An unexpected error occurred while generating the trip report. Please try again."})
        session_values_json_redis.update({"ticket_status": "report_home"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        return render_template('report_home.html', details=send_to_html_json)
