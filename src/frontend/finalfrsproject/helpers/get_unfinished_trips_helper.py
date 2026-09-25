import json
from flask import render_template, redirect, url_for
from datetime import datetime
from finalfrsproject import sqlCommands, routeMethods
from flask_babel import _
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_unfinished_trips_helper_get", flush=True)

    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        open_trip_person_id = session_values_json_redis.get("open_trip_person_id")
        open_trip_message = session_values_json_redis.get("open_trip_message")
        open_trip_flow_next = session_values_json_redis.get("open_trip_flow_next") or "trip_registration"

        result = routeMethods.get_unfinished_trips(
            jwt_details.get("logged_in_user_name"),
            jwt_details.get("logged_in_user_type"),
            person_id=open_trip_person_id,
        )
        #print("result in unfinished_trips_helper: ", result, flush=True)
        session_values_json_redis.update({"ticket_status":"get_unfinished_trips"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

        if not result or result.get('Status') == "Fail":
            send_to_html_json = {
                'logged_in_user': jwt_details.get("logged_in_user_name"),
                'logged_in_user_type': jwt_details.get("logged_in_user_type"),
                'message': 'Error while retrieving open trips. Please try again.',
                'page_title': _('End Trip')
            }
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_get | Execution time: {execution_time}ms", flush=True)

            return render_template('home.html', details=send_to_html_json)

        else:
            send_to_html_json = result.get('Details')
            if open_trip_message:
                send_to_html_json.update({"message": open_trip_message})
            if open_trip_person_id and not send_to_html_json.get("incomplete_trips"):
                session_values_json_redis.pop("open_trip_person_id", None)
                session_values_json_redis.pop("open_trip_message", None)
                session_values_json_redis.pop("open_trip_flow_next", None)
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_get | Execution time: {execution_time}ms", flush=True)

                return redirect(url_for(open_trip_flow_next))
            #print("send_html_to_json at get_unfinished_trips_helper get: ", send_to_html_json, flush=True)
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_get | Execution time: {execution_time}ms", flush=True)

            return render_template('unfinished_trips.html', details=send_to_html_json)

    except Exception as e:
        print(f'Error in get_unfinished_trips: {str(e)} ')
        send_to_html_json = {
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': 'Error while retrieving open trips. Please try again.',
            'page_title': _('End Trip')
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('home.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_unfinished_trips_helper_post", flush=True)
    try:
        form = request.form
        print("form: ", form)
        trip_id = form.get("trip_id")
        trip_close_time = datetime.now().strftime('%Y-%m-%dT%H:%M')
        print("trip id: ", trip_id)
        result = sqlCommands.close_trip(trip_id, trip_close_time)

        if not result or result.get('Status') == "Fail":
            return redirect(request.url)#need to show an error message

        else:

            session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
            open_trip_person_id = session_values_json_redis.get("open_trip_person_id")
            open_trip_message = session_values_json_redis.get("open_trip_message")
            open_trip_flow_next = session_values_json_redis.get("open_trip_flow_next") or "trip_registration"

            result = routeMethods.get_unfinished_trips(
                jwt_details.get("logged_in_user_name"),
                jwt_details.get("logged_in_user_type"),
                person_id=open_trip_person_id,
            )
            print("unfinished_trip handler post method result: ", result)
            if not result or result.get('Status') == "Fail":
                send_to_html_json = {
                    'logged_in_user': jwt_details.get("logged_in_user_name"),
                    'logged_in_user_type': jwt_details.get("logged_in_user_type"),
                    'message': 'Error while retrieving open trips. Please try again.',
                    'page_title': _('End Trip')
                }
                send_to_html_json = result.get('Details')
                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_post | Execution time: {execution_time}ms",
                    flush=True)

                return render_template('home.html', details=send_to_html_json)

            else:
                send_to_html_json = result.get('Details')
                if open_trip_message:
                    send_to_html_json.update({"message": open_trip_message})
                if open_trip_person_id and not send_to_html_json.get("incomplete_trips"):
                    session_values_json_redis.pop("open_trip_person_id", None)
                    session_values_json_redis.pop("open_trip_message", None)
                    session_values_json_redis.pop("open_trip_flow_next", None)
                    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

                    end_time = time.time()
                    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_post | Execution time: {execution_time}ms",
                        flush=True)

                    return redirect(url_for(open_trip_flow_next))
                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_post | Execution time: {execution_time}ms",
                    flush=True)
                return render_template('unfinished_trips.html', details=send_to_html_json)

    except Exception as e:
        print(f'Error in get_unfinished_trips_post: {str(e)} ')
        send_to_html_json = {
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': 'Error while retrieving open trips. Please try again.',
            'page_title': _('End Trip')
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed get_unfinished_trips_helper_post | Execution time: {execution_time}ms", flush=True)
        return render_template('home.html', details=send_to_html_json)
