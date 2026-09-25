import json
from flask import render_template, redirect, url_for
from finalfrsproject import redisCommands
from flask_babel import _
import traceback
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting make_trip_summary_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    is_passenger_entry = session_values_json_redis.get('is_passenger_entry')
    #trip_and_traveler_details = []
    traveler_type = session_values_json_redis.get('traveler_type')
    print("traveler_type: ", traveler_type)

    print('trip registration: All Others')
    session_values_json_redis = redisCommands.create_json_for_trip_registration_post_from_redis_object(session_values_json_redis)
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    send_to_html_json = redisCommands.create_json_for_make_trip_summary_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))
    print('redis in make_trip_summary before showing the trip summary page: ', session_values_json_redis, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed make_trip_summary_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('trip_summary.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting make_trip_summary_helper_get", flush=True)
    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        print("form: ", form)

        if form.get('end_trip_registration'):
            session_values_json_redis.update({"message": "Trip registration completed"})
            session_values_json_redis.update({"ticket_status": "home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in make_trip_summary after trip has ended: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed make_trip_summary_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('home'))

    except Exception as e:
        # Log the error and return an error page or message
        stack_trace = traceback.format_exc()  # Get full stack trace
        print(f"Stack Trace:\n{stack_trace}", flush=True)
        print(f"[ERROR] post_handler failed: {e}")
        send_to_html_json = {
            'message': _("Error in the trip summary page. Please go to the home page."),
            'page_title': 'Error'
        }
        print("404 error details: ", send_to_html_json)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed make_trip_summary_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return render_template('401.html', details=send_to_html_json), 401
