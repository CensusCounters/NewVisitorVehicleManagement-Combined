import json
from flask import render_template, redirect, url_for
from flask_babel import _
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting manual_face_verification_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    if session_values_json_redis.get('message') is not None:
        message = session_values_json_redis.get('message')
    else: 
        message = _('Please manually check that these pictures are of the same person. If you are sure, press Yes. Else, press No.')
    
    session_values_json_redis.update({"ticket_status":"manual_face_verification"})
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    send_to_html_json = {
        'enrolled_image': session_values_json_redis.get('person_image_html_path'),
        'todays_image': session_values_json_redis.get('todays_image_html_path'),
        'logged_in_user': jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        #'message': 'Please manually check that these pictures are of the same person. If you are sure, press Yes. Else, press No.',
        'message': message,
        'page_title': _('Manual Face Verification')
    }

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed manual_face_verification_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('manual_face_verification.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting manual_face_verification_helper_post", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    print('form: ', form)

    if form.get('Yes'):
        session_values_json_redis.update({"message": _("This person has been manually verified.")})
        session_values_json_redis.update({"ticket_status": "known_person"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
        print('redis in manual_face_verification after user has selected Yes: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed manual_face_verification_helper_post | Execution time: {execution_time}ms", flush=True)

        return redirect(url_for('known_person'))
    
    else:
        if session_values_json_redis.get('number_of_male_passengers_to_add') is not None:
            male_passengers_to_add = session_values_json_redis.get('number_of_male_passengers_to_add')
            if male_passengers_to_add > 0:
                session_values_json_redis.update({"message": _("The Aadhar card provided does not belong to this visitor. Please use the correct aadhar card and try again.")})
                session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
                print('redis in manual_face_verification after user has selected No but a male passenger is being added to an existing trip: ', session_values_json_redis)
                return redirect(url_for('aadhar_lookup'))

        else:    
            session_values_json_redis.update({"message": _("The Aadhar card provided does not belong to this visitor. Please use the correct aadhar card and try again.")})
            session_values_json_redis.update({"ticket_status": "stop_processing"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            print('redis in manual_face_verification after user has selected No: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed manual_face_verification_helper_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('stop_processing'))
