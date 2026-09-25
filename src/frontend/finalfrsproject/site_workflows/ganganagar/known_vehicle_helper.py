import json
from flask import render_template, redirect, url_for
from finalfrsproject import routeMethods, redisCommands
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_vehicle_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id'))) 
    routeMethods._store_vehicle_image_in_session(
        session_values_json_redis,
        fallback_actual_path=session_values_json_redis.get('vehicle_image_actual_path'),
    )
    session_values_json_redis.update({"ticket_status":"known_vehicle"})
    session_values_json_redis.update({"page_title": "known_vehicle"})
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    send_to_html_json = redisCommands.create_json_for_known_vehicle_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed known_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('known_vehicle.html', details=send_to_html_json)
  

def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_vehicle_helper_post", flush=True)

    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        new_vehicle_owner = session_values_json_redis.get('person_id')
        print("new_vehicle_owner: ", new_vehicle_owner, flush=True)
        print("known_vehicle_helper_post owner-association context: has_vehicle_association=%s, existing_vehicle_plate=%s, existing_vehicle_owner=%s" % (
            session_values_json_redis.get('has_vehicle_association'),
            session_values_json_redis.get('vehicle_plate_number'),
            session_values_json_redis.get('vehicle_owner')
        ), flush=True)
        form = request.form
        print("form: ", form, flush=True)
        result = routeMethods.update_existing_vehicle_record(
            form,
            new_vehicle_owner,
            jwt_details.get('logged_in_user_id'),
            session_values_json_redis,
        )
        print("result: ", result, flush=True)
        if not result or result.get('Status') == 'Fail':
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed known_vehicle_helper_post | Execution time: {execution_time}ms", flush=True)
            return redirect(request.url)

        else:
            session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
            # Keep Add Trip in sync with the submitted known-vehicle edits.
            updated_make = form.get('make')
            updated_model = form.get('vehicle_model')
            updated_color = form.get('color')

            if updated_make is not None:
                session_values_json_redis.update({"vehicle_make": updated_make})
            if updated_model is not None:
                session_values_json_redis.update({"vehicle_model": updated_model})
            if updated_color is not None:
                session_values_json_redis.update({"vehicle_color": updated_color})

            session_values_json_redis.update({"ticket_status": "trip_registration", "cancel_to": "known_vehicle"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in known_vehicle before redirecting to trip registration: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed known_vehicle_helper_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('trip_registration'))

    except Exception as e:
        print(f'Error in known_vehicle_helper_post: {str(e)} ')
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed aadhar_lookup_get | Execution time: {execution_time}ms", flush=True)
        return redirect(request.url)
