import json
from flask import render_template, redirect, url_for, current_app
from finalfrsproject import routeMethods, redisCommands,  app, sqlCommands, jwt
import os, shutil
from flask_babel import _
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
    print(f"[{start_timestamp}] Starting {current_app.config['SITE_PROFILE_CONFIG'].recognize_vehicle.post_log_name}", flush=True)

    user_type = jwt_details.get('logged_in_user_type')
    user_name = jwt_details.get('logged_in_user_name')
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    vehicle_plate_number = form.get('vehicle_plate_number')
    vehicle_image_url = form.get('vehicle_image_url')
    vehicle_id = form.get('vehicle_id')

    # A manually entered search value is also a valid plate selection.
    if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.manual_plate_search and not vehicle_plate_number and form.get('searchText'):
        vehicle_plate_number = form.get('searchText').replace(" ", "")
        vehicle_image_url = None
        vehicle_id = None

    if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.strict_lookup_result and not vehicle_plate_number:
        raise UnboundLocalError("local variable 'result' referenced before assignment")
    result = None
    url = None
    if vehicle_plate_number:
        lookup_result = routeMethods.check_if_vehicle_is_in_our_system(
            vehicle_plate_number,
            vehicle_image_url,
            vehicle_id,
            session_values_json_redis,
        )
        if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.strict_lookup_result or isinstance(lookup_result, tuple):
            result, url = lookup_result
        else:
            result = lookup_result

    if not result or result.get('Status') == "Fail" or (current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.require_vehicle_url and url is None):
        send_to_html_json = {
            'status': 'Success',
            'unregistered_vehicles': session_values_json_redis.get('unregistered_vehicles'),
            'traveler_type': session_values_json_redis.get('traveler_type'),
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': (_("Recognize Vehicle") if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.translate_messages else "Recognize Vehicle"),
            'message': (_("Error while checking if the vehicle is in the system. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.translate_messages else "Error while checking if the vehicle is in the system. Please try again.")
        }
        return render_template('recognize_vehicle.html', details=send_to_html_json)

    if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.require_cached_vehicle_list:
        session_values_json_redis.pop("unregistered_vehicles")
    else:
        session_values_json_redis.pop("unregistered_vehicles", None)
    if url == 'unknown_vehicle':
        print("URL is Unknown Vehicle", flush=True)
        session_values_json_redis.update({"message": (_("Please review and click submit to save the vehicle data.") if current_app.config["SITE_PROFILE_CONFIG"].recognize_vehicle.translate_messages else "Please review and click submit to save the vehicle data.")})
        session_values_json_redis.update({"ticket_status": "unknown_vehicle"})
    else:
        print("URL is known Vehicle", flush=True)
        session_values_json_redis.update({"ticket_status": "known_vehicle"})

    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
    print('redis object in recognize vehicles POST: ', session_values_json_redis)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed recognize_vehicle_helper_post | Execution time: {execution_time}ms", flush=True)

    return redirect(url_for(url))
