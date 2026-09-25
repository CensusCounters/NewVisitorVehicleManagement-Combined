import json
from flask import render_template, redirect, url_for
from finalfrsproject import routeMethods, redisCommands,  app, sqlCommands, jwt
import os, shutil
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting recognize_vehicle_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    session_values_json_redis.update({"ticket_status":"recognize_vehicle"})

    result = routeMethods.get_all_vehicles_from_anpr(session_values_json_redis)
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(result)) 
    send_to_html_json = redisCommands.create_json_for_recognize_vehicle_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))
    #print('redis in recognize_vehicle before showing recognize vehicle page: ', session_values_json_redis, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed recognize_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('recognize_vehicle.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_vehicle_helper_post", flush=True)

    user_type = jwt_details.get('logged_in_user_type')
    user_name = jwt_details.get('logged_in_user_name')
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    if form.get('vehicle_plate_number'):
        #is this vehicle in our system
        result, url = routeMethods.check_if_vehicle_is_in_our_system(form.get('vehicle_plate_number'),form.get('vehicle_image_url'),
                                                                     form.get('vehicle_id'), session_values_json_redis)

    if not result or result.get('Status') == "Fail":
        send_to_html_json = {
            'status': 'Success',
            'unregistered_vehicles': session_values_json_redis.get('unregistered_vehicles'),
            'traveler_type': session_values_json_redis.get('traveler_type'),
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': "Recognize Vehicle",
            'message': "Error while checking if the vehicle is in the system. Please try again."
        }
        return render_template('recognize_vehicle.html', details=send_to_html_json)
    else:
        session_values_json_redis.pop("unregistered_vehicles")
        if url == 'unknown_vehicle':
            print("URL is Unknown Vehicle", flush=True)
            session_values_json_redis.update({"message": "Please review and click submit to save the vehicle data."})
            session_values_json_redis.update({"ticket_status": "unknown_vehicle"})
        else:
            print("URL is known Vehicle", flush=True)
            session_values_json_redis.update({"ticket_status": "known_vehicle"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
        print('redis object in recognize vehicles POST: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed recognize_vehicle_helper_post | Execution time: {execution_time}ms",
              flush=True)
        return redirect(url_for(url))
