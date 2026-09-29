import json, os
from flask import render_template, redirect, url_for
from datetime import datetime, timedelta, timezone
from finalfrsproject import routeMethods, app, redisCommands, sqlCommands
from werkzeug.utils import secure_filename
import base64
from flask_babel import _
import time

def _cfg():
    return app.config["TRIP_REGISTRATION_PROFILE"]


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting trip_registration_helper_get", flush=True)

    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        entry_time = datetime.now().strftime('%Y-%m-%dT%H:%M')

        if session_values_json_redis.get('page_title') != 'known_vehicle':
            print('getting primary vehicle for the first time the page loads', flush=True)
            session_values_json_redis = routeMethods.get_primary_vehicle_for_person(session_values_json_redis, session_values_json_redis.get('person_id'))
        else:
            print('new vehicle selected for the trip', flush=True)

        # Preserve whether this person already has a vehicle so recognition can
        # prefer the matching plate-owner association over another owner's row.
        has_vehicle_association = bool(session_values_json_redis.get('vehicle_plate_number'))
        session_values_json_redis.update({"has_vehicle_association": has_vehicle_association})

        session_values_json_redis.update({"ticket_status":"trip_registration"})
        session_values_json_redis.update({"page_title": "trip_registration"})
        if _cfg()["reset_driver_trip_id"]:
            session_values_json_redis.update({"driver_trip_id": ""})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
        IST = timezone(timedelta(hours=5, minutes=30))
        print('*************redis in trip_registration get method: ', session_values_json_redis, flush=True)

        send_to_html_json = redisCommands.create_json_for_trip_registration_get_from_redis_object(
            jwt_details.get('logged_in_user_id'),jwt_details.get("logged_in_user_name"),
                jwt_details.get("logged_in_user_type"),entry_time)
        print('send to html: ', send_to_html_json, flush=True)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed trip_registration_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('add_trip.html', details=send_to_html_json, now=datetime.now(IST).isoformat()[:16])

    except Exception as e:
        print(f"Error occurred: {e}", flush=True)
        send_to_html_json = {
            'message': (_("Unexpected error while generating add trip form. Please try again.") if _cfg()["translate_messages"] else "Unexpected error while generating add trip form. Please try again."),
            'page_title': (_("Error") if _cfg()["translate_messages"] else "Error")
        }
        print(f"No form received in trip_registration_helper send_to_html_json: {send_to_html_json}")

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed trip_registration_helper_get | Execution time: {execution_time}ms",
              flush=True)

        return render_template('500.html', details=send_to_html_json), 500

def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting trip_registration_helper_post", flush=True)

    print("trip registration post handler", flush=True)
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    print("redis in trip_registration post: ", session_values_json_redis, flush=True)
    permit_image = None
    form = None
    permit_img_file_path = None

    if request.form:
        form = request.form
        print("insert trip record form: ", form, flush=True)
        
        #get all vehicles
        if form.get('destination'):
            if form.get('destination') == 'recognize_vehicle':
                print("trip_registration: recognize_vehicle")
                session_values_json_redis.update({"traveler_type": form.get('traveler_type')})
                session_values_json_redis.update({"message": (_(_cfg()["vehicle_selection_message"]) if _cfg()["translate_messages"] else _cfg()["vehicle_selection_message"])})
                session_values_json_redis.update({"ticket_status": "recognize_vehicle"})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
                print("redis in trip_registration before vehicle recognition: ", session_values_json_redis)

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed trip_registration_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return redirect(url_for('recognize_vehicle'))
                    
        #make a trip
        else:
            session_values_json_redis.update({"entry_time": form.get('entry_time')})
            entry_time = datetime.strptime(form.get('entry_time'), "%Y-%m-%dT%H:%M")
            print("entry_time: ", entry_time)
            visit_time_in_hrs = int(form.get('visit_hrs', 0)) if form.get('visit_hrs', '').isdigit() else 0
            if _cfg()["duration_in_days"]:
                visit_time_in_days = int(form.get('visit_days', 0)) if form.get('visit_days', '').isdigit() else 0
                expected_visit_duration = f"{visit_time_in_days} days {visit_time_in_hrs} hours"
            else:
                visit_time_in_min = int(form.get('visit_min', 0)) if form.get('visit_min', '').isdigit() else 0
                expected_visit_duration = f"{visit_time_in_hrs} hours {visit_time_in_min} minutes"
            session_values_json_redis.update({"expected_visit_duration": expected_visit_duration})
            session_values_json_redis.update({"coming_from": form.get('coming_from')})
            session_values_json_redis.update({"going_to": form.get('going_to')})
            session_values_json_redis.update({"trip_reason": form.get('trip_reason')})
            session_values_json_redis.update({"trip_type": form.get('trip_type')})
            session_values_json_redis.update({"traveler_type": form.get('traveler_type')})
            session_values_json_redis.update({"is_passenger_entry": form.get('is_passenger_entry')})
            if form.get('male_passengers') == '':
                session_values_json_redis.update({"male_passengers": 0})
            else:
                session_values_json_redis.update({"male_passengers": form.get('male_passengers')})
            if form.get('female_passengers') == '':
                session_values_json_redis.update({"female_passengers": 0})
            else:    
                session_values_json_redis.update({"female_passengers": form.get('female_passengers')})
            if form.get('child_passengers') == '':
                session_values_json_redis.update({"child_passengers": 0})
            else:
                session_values_json_redis.update({"child_passengers": form.get('child_passengers')})

            session_values_json_redis.update({"token_number": form.get('token_number')})

            # redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            #session_values_json_redis = json.loads(redisCommands.redis_conn.get(jwt_details.get('logged_in_user_id')))
            
            vehicle_plate_number = ''
            vehicle_make = ''
            #if the form has a vehicle_plate_number, compare it with the redis vehicle_plate_number. If it does not match,
            #that means the user has entered a new vehicle number. That needs to be entered like in the clause below.
            #if it matches or if the form.get('vehicle_plate_number') is null then take the redis values and proceed.

            person_id = session_values_json_redis.get('person_id')
            if session_values_json_redis.get('parent_vehicle_number'):
                vehicle_plate_number = session_values_json_redis.get('parent_vehicle_number')
            elif session_values_json_redis.get('vehicle_plate_number'):
                vehicle_plate_number = session_values_json_redis.get('vehicle_plate_number')

            print(f'vehicle plate number from redis: {vehicle_plate_number}', flush=True)

            #elif form.get('vehicle_number'):
            #if form.get('vehicle_number') and form.get('vehicle_number') != vehicle_plate_number:
            if form.get('vehicle_number') != vehicle_plate_number:
                vehicle_plate_number = form.get('vehicle_number')
                vehicle_make = form.get('vehicle_make')
                session_values_json_redis.update({"vehicle_plate_number": vehicle_plate_number})
                session_values_json_redis.update({"vehicle_make": vehicle_make})
                vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"])])
                session_values_json_redis.update({"vehicle_image": vehicle_image})
                # Insert manual vehicle entry.
                sqlCommands.insert_manual_vehicle_entry(jwt_details.get('logged_in_user_id'), vehicle_plate_number, vehicle_make, app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"], person_id)
            else:
                print(f'form vehicle number matches the redis vehicle number or no vehicle no entered in the form')

            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            trip_registration_start_time = datetime.strptime(session_values_json_redis.get('ticket_start_time'), ("%Y-%m-%d %H:%M:%S.%f"))

            permit_image = form.get('permit_image')

            if permit_image: 
                if vehicle_plate_number == None:
                    vehicle_plate_number = 'No Vehicle'
                new_file_name = str(person_id) + "-" + vehicle_plate_number + "-" + str(trip_registration_start_time) +"-permit-" + ".png"
                # permit_image.save(os.path.sep.join([app.config['TRIP_PERMIT_IMAGES'],new_file_name]))

                image_data = base64.b64decode(permit_image.split('base64,')[1])
                with open(os.path.sep.join([app.config['TRIP_PERMIT_IMAGES'],new_file_name]), 'wb') as file:
                    file.write(image_data)

                permit_img_file_path = os.path.sep.join([app.config["TRIP_PERMIT_PATH_FOR_HTML"],new_file_name])
                session_values_json_redis.update({"permit_img_file_path": permit_img_file_path})
                                
            #if request.form:
            print('redis object in trip_registration before new_trip_insert: ', session_values_json_redis)

            #result = routeMethods.insert_new_trip_record(jwt_details.get("logged_in_user_id"), permit_img_file_path, form, person_id,vehicle_plate_number, session_values_json_redis)
            result = routeMethods.insert_new_trip_record(jwt_details.get("logged_in_user_id"), session_values_json_redis)

            if not result or result.get('Status') == "Fail" or result.get("Insert_Count") == 0:
                session_values_json_redis.update({"message": (_("System was unable to insert a trip record. Please try again.") if _cfg()["translate_messages"] else "System was unable to insert a trip record. Please try again.")})
                session_values_json_redis.update({"ticket_status": "trip_registration"})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                print("insert new trip failed in trip registration in routes.py", flush=True)
                print("redis in trip_registration when insert new trip failed: ", session_values_json_redis)
                send_to_html_json = {
                    'message': (_("System was unable to insert a trip record. Please try again") if _cfg()["translate_messages"] else "System was unable to insert a trip record. Please try again"),
                    'page_title': (_("Error") if _cfg()["translate_messages"] else "Error")
                }

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed trip_registration_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return render_template('500.html', details=send_to_html_json), 500

            else:
                session_values_json_redis.update({"message": (_("Trip updated Successfully. Click Continue for trip summary.") if _cfg()["translate_messages"] else "Trip updated Successfully. Click Continue for trip summary.")})
                session_values_json_redis.update({"ticket_status": "make_trip_summary"})
                session_values_json_redis.update({"page_title": "make_trip_summary"})
                session_values_json_redis.update({"message": (_("Trip Successfully Added") if _cfg()["translate_messages"] else "Trip Successfully Added")})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                print("redis in trip_registration when insert new trip succeeded: ", session_values_json_redis)

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed trip_registration_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return redirect(url_for('make_trip_summary'))

    else:
        send_to_html_json = {
            'message': (_("No form received for creating new trip. Please try again.") if _cfg()["translate_messages"] else "No form received for creating new trip. Please try again."),
            'page_title': (_("Error") if _cfg()["translate_messages"] else "Error")
        }
        print(f"No form received in trip_registration_helper send_to_html_json: {send_to_html_json}")

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed trip_registration_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return render_template('500.html', details=send_to_html_json), 500
