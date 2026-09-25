import json
from flask import render_template, url_for, redirect
from flask_babel import _
from datetime import datetime
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting report_home_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    session_values_json_redis.update({"ticket_status":"report_home"})

    send_to_html_json = {
        'logged_in_user':  jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': _('Please click on a report from the list below.'),
        'page_title': 'Report Home'
    }
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed report_home_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('report_home.html', details=send_to_html_json)
    
def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting report_home_helper_post", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    if form:
        print('form: ', form)    
        if form.get('report') == 'vehicle_report':
            session_values_json_redis.update({"ticket_status":"vehicle_report"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in report home before redirecting to vehicle_report : ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed report_home_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('vehicle_report'))
        
        elif form.get('report') == 'person_report':
            session_values_json_redis.update({"ticket_status":"person_report"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            print('redis in report_home before redirecting to person_report: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed report_home_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            #return redirect(url_for('person_report'))
            return redirect(url_for('person_lookup'))

        elif form.get('report') == 'trip_report':
            session_values_json_redis.update({"ticket_status":"trip_report"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            print('redis in report_home before redirecting to trip_report: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed report_home_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('trip_report'))

        elif form.get('report') == 'blacklist_enroll':
            session_values_json_redis.update({"ticket_status":"blacklist_enroll"})
            session_values_json_redis.update({"page_title": "blacklist_enroll"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in report_home before redirecting to enroll_blacklisted_person: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed report_home_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('enroll_blacklisted_person'))