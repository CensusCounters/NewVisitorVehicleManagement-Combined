import json, os
from flask import render_template, redirect, url_for, current_app
from finalfrsproject import routeMethods, redisCommands, app
from flask_babel import _
import time
from datetime import datetime


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting unknown_vehicle_helper_get", flush=True)

    user_type = jwt_details.get('logged_in_user_type')
    user_name = jwt_details.get('logged_in_user_name')
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    try:
        result = routeMethods.get_vehicle_details_from_anpr(session_values_json_redis.get('vehicle_plate_number'),session_values_json_redis)
        #print("result from anpr: ", result, flush=True)
        #if there is no information on the match, send it back to unknown_vehicle
        if not result or result.get('Status') == "Fail":
            session_values_json_redis.update({"message": (_("System was unable to retrieve vehicle list from ANPR. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "System was unable to retrieve vehicle list from ANPR. Please try again.")})
            session_values_json_redis.update({"ticket_status": "recognize_vehicle"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            send_to_html_json = {
                'message': (_("System was unable to retrieve vehicle list from ANPR. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "System was unable to retrieve vehicle list from ANPR. Please try again."),
                'page_title': (_("Error") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Error")
            }

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed unknown_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

            return render_template('500.html', details=send_to_html_json), 500
            #return redirect(request.url)

        elif result.get('Count') == 0:

            # vehicle_image_url = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"],os.path.basename(app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"])])
            vehicle_image_url = session_values_json_redis.get("vehicle_image")
            vehicle_owner_name = session_values_json_redis.get("person_name")
            send_to_html_json = {
                'vehicle_number': session_values_json_redis.get('vehicle_plate_number'),
                'vehicle_image_url': vehicle_image_url,
                'vehicle_owner_name': vehicle_owner_name,
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title' : (_('Unregistered Vehicle') if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else 'Unregistered Vehicle'),
                'message': (_('Please fill the vehicle details and click submit.') if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else 'Please fill the vehicle details and click submit.')
            }
            if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.include_vehicle_choices:
                send_to_html_json.update({
                    "vehicle_types": app.config["VEHICLE_TYPES"],
                    "vehicle_categories": app.config["VEHICLE_CATEGORIES"],
                })
            session_values_json_redis.update({"vehicle_image_url": vehicle_image_url})
            session_values_json_redis.update({"ticket_status": "unknown_vehicle"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            #send_to_html_json = redisCommands.create_json_for_unknown_vehicle_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed unknown_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

            return render_template('unknown_vehicle.html', details=send_to_html_json)

        else:
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(result))
            send_to_html_json = redisCommands.create_json_for_unknown_vehicle_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))
            print("send_to_html_json unknown vehicle: ", send_to_html_json, flush=True)
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed unknown_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

            return render_template('unknown_vehicle.html', details=send_to_html_json)

    except Exception as e:
        print(f'Error in unknown_vehicle_helper_get_exception: {str(e)} ')
        session_values_json_redis.update(
            {"message": (_("Unexpected error in Unknown Vehicle get method. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Unexpected error in Unknown Vehicle get method. Please try again.")})
        session_values_json_redis.update({"ticket_status": "recognize_vehicle"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        send_to_html_json = {
            'message': (_("Unexpected error in Unknown Vehicle get method. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Unexpected error in Unknown Vehicle get method. Please try again."),
            'page_title': (_("Error") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Error")
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed unknown_vehicle_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('500.html', details=send_to_html_json), 500


def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting unknown_vehicle_helper_post", flush=True)

    user_type = jwt_details.get('logged_in_user_type')
    user_name = jwt_details.get('logged_in_user_name')

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    try:
        print("insert new vehicle form: " , form, flush=True)

        result = routeMethods.insert_new_vehicle_record(jwt_details.get("logged_in_user_id"), form)

        if not result or result.get('Status') == "Fail" or result.get("Insert_Count") == 0:
            session_values_json_redis.update({"message": (_("System was unable to insert a vehicle record. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "System was unable to insert a vehicle record. Please try again.")})
            session_values_json_redis.update({"ticket_status": "unknown_vehicle"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print("insert a vehicle record failed in unknown_vehicle")
            print("redis in unknown_vehicle on insert new vehicle fail: ", session_values_json_redis)
            send_to_html_json = {
                'message': (_("System was unable to insert a vehicle record. Please try again") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "System was unable to insert a vehicle record. Please try again"),
                'page_title': (_("Error") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Error")
            }

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed unknown_vehicle_helper_post | Execution time: {execution_time}ms", flush=True)

            return render_template('500.html', details=send_to_html_json), 500

        else:
            details = result.get('Details')
            print('unknown_vehicle details: ', details)
            session_values_json_redis.update({"vehicle_make": details.get('vehicle_make')})
            session_values_json_redis.update({"vehicle_model": details.get('vehicle_model')})
            session_values_json_redis.update({"vehicle_color": details.get('vehicle_color')})
            session_values_json_redis.update({"vehicle_type": details.get('vehicle_type')})
            session_values_json_redis.update({"vehicle_owner": details.get(current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.owner_result_key)})
            session_values_json_redis.update({"vehicle_registration_number": details.get('vehicle_registration_number')})
            session_values_json_redis.update({"ticket_status": "trip_registration", "cancel_to": "unknown_vehicle"})
            session_values_json_redis.update({"page_title": "trip_registration"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in unknown_vehicle on insert new vehicle success: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed unknown_vehicle_helper_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('trip_registration'))

    except Exception as e:
        print(f'Error in unknown_vehicle_helper_post: {str(e)} ')
        session_values_json_redis.update({"message": (_("Unexpected error while handling Unknown Vehicle. Please try again.") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Unexpected error while handling Unknown Vehicle. Please try again.")})
        session_values_json_redis.update({"ticket_status": "unknown_vehicle"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        print("redis in unknown_vehicle_helper_post_exception: ", session_values_json_redis)
        send_to_html_json = {
            'message': (_("Unexpected error while handling Unknown Vehicle. Please try again") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Unexpected error while handling Unknown Vehicle. Please try again"),
            'page_title': (_("Error") if current_app.config["SITE_PROFILE_CONFIG"].unknown_vehicle.translate_messages else "Error")
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed unknown_vehicle_helper_post | Execution time: {execution_time}ms",
              flush=True)
        return render_template('500.html', details=send_to_html_json), 500
