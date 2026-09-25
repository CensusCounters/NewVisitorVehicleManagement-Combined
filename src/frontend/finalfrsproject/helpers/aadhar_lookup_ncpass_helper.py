import json
from flask import render_template, redirect, url_for
from finalfrsproject import routeMethods, redisCommands, app
from flask_babel import _
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting aadhar_lookup_get", flush=True)

    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        session_values_json_redis = redisCommands.clean_redis_object_before_aadhar_lookup(session_values_json_redis)
        print('redis in aadhar_lookup before look up: ', session_values_json_redis, flush=True)

        if session_values_json_redis.get('message'):
            message = session_values_json_redis.get('message')
        else:
            message = _('Please select the Visitor type and the ID number to verify identity.')
        session_values_json_redis.update({"ticket_status":"aadhar_lookup"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
        id_categories = app.config["ID_LOOKUP_CATEGORIES"]
        visitor_categories = app.config["VISITOR_CATEGORIES"]
        send_to_html_json = {
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': message,
            'id_categories': id_categories,
            'visitor_categories': visitor_categories,
            'page_title': 'ID Lookup',
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed aadhar_lookup_get | Execution time: {execution_time}ms", flush=True)

        return render_template('aadhar_lookup_ncpass.html', details=send_to_html_json)
    except Exception as e:
        print(f'Error in id look up: {str(e)} ')
        send_to_html_json = {
            'message': "Error in ID look up. Please try again.",
            'page_title': "Error"
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed aadhar_lookup_get | Execution time: {execution_time}ms", flush=True)

        return render_template('home.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting aadhar_lookup_post", flush=True)
    try:
        aadhar_number = drivers_license = other_id_number = pass_number = result = None
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        print('form: ', form, flush=True)
        traveler_type = form.get('traveler_type')
        id_number = form.get('id_number')
        id_type = 'AADHAR'
        print(f' traveler_type: {traveler_type}, id_type: {id_type}, id_number: {id_number}', flush=True)

        if not traveler_type or not id_number:
            session_values_json_redis.update({
                "message": _("Please select a valid visitor type and Aadhar number."),
                "ticket_status": "aadhar_lookup",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(url_for('aadhar_lookup'))

        result = routeMethods.get_known_person_details_with_aadhar(id_number, session_values_json_redis)
        print(f' result from get_known_person_details_with_aadhar: {result.get("Details")}', flush=True)
        pass_number = 'Not Available'
        aadhar_number = id_number
        drivers_license = 'Not Available'
        other_id_number = 'Not Available'

        if result.get("Status") == "Fail":
            print("ID Lookup failed due to a system issue. Please try again")
            session_values_json_redis.update({"message": "The ID lookup failed due to a system issue. Please try again."})
            session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed aadhar_lookup_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('aadhar_lookup'))

        elif result.get("Details") == "No match found":
            print('ID look up did not match any records')
            session_values_json_redis.update({"pass_number": pass_number})
            session_values_json_redis.update({"aadhar_number": aadhar_number})
            session_values_json_redis.update({"drivers_license": drivers_license})
            session_values_json_redis.update({"other_id_number": other_id_number})
            session_values_json_redis.update({"id_type": id_type})
            session_values_json_redis.update({"primary_id_type": id_type})
            session_values_json_redis.update({"primary_id_number": id_number})
            session_values_json_redis.update({"primary_id_image": None})
            session_values_json_redis.update({"traveler_type": traveler_type})
            session_values_json_redis.update({"message": _("The ID Number entered - ") + id_number + _(" - was not found in the system. Please register this person.")})
            session_values_json_redis.update({"ticket_status": "recognize_person"})
            session_values_json_redis.update({"person_details": "Not Available"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in aadhar_lookup on no match: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed aadhar_lookup_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('recognize_person'))

        else:
            session_values_json_redis = result.get("Details")
            primary_id_number = id_number
            primary_id_image = session_values_json_redis.get('aadhar_image')

            print('ID look up successful. Person found in the system: ', session_values_json_redis, flush=True)
            session_values_json_redis.update({"pass_number": pass_number})
            session_values_json_redis.update({"aadhar_number": aadhar_number})
            session_values_json_redis.update({"drivers_license": drivers_license})
            session_values_json_redis.update({"other_id_number": other_id_number})
            session_values_json_redis.update({"id_type": id_type})
            session_values_json_redis.update({"primary_id_number": primary_id_number})
            session_values_json_redis.update({"primary_id_type": id_type})
            session_values_json_redis.update({"primary_id_image": primary_id_image})
            session_values_json_redis.update({"traveler_type": traveler_type})
            session_values_json_redis.update({"message": _("The ID Number entered - ") + id_number + _(" - was found in the system. Please do a face recognition now.")})
            session_values_json_redis.update({"ticket_status": "recognize_person"})
            session_values_json_redis.update({"person_details": "Available"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in aadhar_lookup after update on success: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed aadhar_lookup_post | Execution time: {execution_time}ms", flush=True)

            return redirect(url_for('recognize_person'))
    except Exception as e:
        print(f'Error in id look up: {str(e)} ')
        send_to_html_json = {
            'message': "Error in ID look up. Please try again.",
            'page_title': "Error"
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed aadhar_lookup_post | Execution time: {execution_time}ms", flush=True)

        return render_template('home.html', details=send_to_html_json), 500
