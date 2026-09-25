import json, os, uuid, shutil
from flask import render_template, redirect, url_for
from finalfrsproject import app
from datetime import datetime
from flask_babel import _
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting reregister_face_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    if session_values_json_redis.get('message') is not None:
        message = session_values_json_redis.get('message')
    else: 
        message = 'Please manually check that these pictures are of the same person. If you are sure, press Yes. Else, press No.'

    #if session_values_json_redis.get('page_title') is not None:
    #    page_title = session_values_json_redis.get('page_title')
    #else:
    page_title = _('Reregister Face')
    '''
    if session_values_json_redis.get("enrollment_id") in ['08eba432-b2ed-4f29-a96b-3909a49b0e00', '3cdb9891-f874-4413-930f-49e8210d9082']:
        message = 'Alert!! This person is blacklisted.'
    '''
    blacklist = session_values_json_redis.get("blacklist")
    if blacklist:
        route = blacklist.get("blacklist_route")
        #info = blacklist.get("blacklist_info")
        name = session_values_json_redis.get("blacklist", {}).get("blacklist_info")["name"]
        id_value = session_values_json_redis.get("blacklist", {}).get("blacklist_info")["aadhaar"]
        message = 'Alert!! This person is blacklisted. Name: ' + name + ', Aadhar: ' + str(id_value)
    else:
        route = None


    session_values_json_redis.update({"page_title": page_title})
    session_values_json_redis.update({"ticket_status":"reregister_face"})
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    # List of keys to check
    #keys_to_check = ["aadhar_number", "drivers_license", "pass_number", "other_id_number"]
    # Find the first valid key that is not "Not Available"
    #provided_aadhar_number = next((session_values_json_redis[key] for key in keys_to_check if
    #    session_values_json_redis.get(key) != "Not Available"), None # Default value if no valid key is found
    #)
    provided_id_number = session_values_json_redis.get("primary_id_number")
    provided_id_type = session_values_json_redis.get("id_type")
    if session_values_json_redis.get('id_type_in_database') == 'aadhar_number':
        database_id_type = 'AADHAR'
    else:
        database_id_type = session_values_json_redis.get('id_type_in_database')


    print("redis in reregister face: ", session_values_json_redis, flush=True)

    send_to_html_json = {
        'enrolled_image': session_values_json_redis.get('person_image_on_hard_drive_html_path'),
        'todays_image': session_values_json_redis.get('todays_image_html_path'),
        'logged_in_user': jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': message,
        'database_id_number': session_values_json_redis.get('id_number_in_database'),
        #'database_id_type': session_values_json_redis.get('id_type_in_database'),
        'database_id_type': database_id_type,
        'provided_id_number': provided_id_number,
        'provided_id_type': provided_id_type,
        'face_recognition_result': session_values_json_redis.get('face_recognition_match_status'),
        'page_title': page_title,
        'enrollment_id': session_values_json_redis.get("enrollment_id")
    }
    print("send_to_html: ", send_to_html_json, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed reregister_face_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('reregister_face.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting reregister_face_helper_post", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    if form.get('Yes'):
        print("face matches the visitor in reregister_face", flush=True)
        print('redis session id: ', session_values_json_redis, flush=True)
        #This block handles these following cases:
        # This is the case where enrollment_id matches the face_id in the person database and the match confidence is high
        # This is the case where enrollment_id matches the face_id in the person database but the match confidence is low \
        #    but the soldier is saying Yes the face matches, we should send the user to Known Person
        # This is the case where enrollment id does not match the enrollment id associated with the ID look up
        #   but the soldier is saying Yes the face matches
        if session_values_json_redis.get("person_details") == "Available":
            session_values_json_redis.update({"message": _("Success! Visitor Information is in the database. Please continue.")})
            session_values_json_redis.update({"ticket_status": "known_person"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in recognize_person when enrollment_id matched: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('known_person'))

        # This is the case where this face enrollment already exists with another ID different from the ID with the person
        # Soldier is saying Yes that the faces match, so we should send the user to Known Person
        if session_values_json_redis.get("picture_matched_another_ID_status") == "Pass":
            session_values_json_redis.update({"message": _("Success! Visitor Information is in the database. Please continue.")})
            session_values_json_redis.update({"ticket_status": "known_person"})
            session_values_json_redis.update({"primary_id_number": session_values_json_redis.get("id_number_in_database")})
            session_values_json_redis.update({"primary_id_type": session_values_json_redis.get("id_type_in_database")})
            id_type_in_database = session_values_json_redis.get('id_type_in_database')
            print(f'id_type: {id_type_in_database}', flush=True)
            id_mapping = {
                'aadhar_number': session_values_json_redis.get('aadhar_image'),
                'drivers_license': session_values_json_redis.get('drivers_license_image'),
                'other_id_number': session_values_json_redis.get('other_id_image')
                or session_values_json_redis.get('other_id_image_location'),
                'OTHER': session_values_json_redis.get('other_id_image')
                or session_values_json_redis.get('other_id_image_location'),
                'pass_number': session_values_json_redis.get('pass_image_location')
                or session_values_json_redis.get('pass_image'),
                'PASS': session_values_json_redis.get('pass_image_location')
                or session_values_json_redis.get('pass_image'),
            }
            print(f'id_type: {id_mapping}', flush=True)
            primary_id_image = id_mapping.get(id_type_in_database)
            session_values_json_redis.update({"primary_id_image": primary_id_image})

            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            print('picture_matched_another_ID_status: ', session_values_json_redis, flush=True)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('known_person'))

        if (session_values_json_redis.get("id_type") == session_values_json_redis.get("id_type_in_database") and
                session_values_json_redis.get("primary_id_number") == session_values_json_redis.get(
                    "id_number_in_database")):
        #if session_values_json_redis.get('temp_aadhar_number') and session_values_json_redis.get('aadhar_number') != session_values_json_redis.get('temp_aadhar_number'):
            send_to_html_json = {
                'message': _("This person's image is already used with another ID. Please use the correct ID and try again."),
                'page_title': 'Error'
            }
            print("404 error details: ", send_to_html_json)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('401.html', details=send_to_html_json), 401


        #values for enrollment id and aadhar number have been set previously
        person_image_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"],os.path.basename(session_values_json_redis.get("person_image_on_hard_drive_html_path"))])
        #person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"],os.path.basename(person_image_on_hard_drive_html_path)])
        person_image_html_path = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])
        print('actual path: ', person_image_actual_path)
        print('html path: ', person_image_html_path)
        session_values_json_redis.update({"person_image_html_path": person_image_html_path}) 
        session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
        session_values_json_redis.update({"message": _("This person is not in the system. Please enter details and submit.")}),
        session_values_json_redis.update({"ticket_status": "unknown_person"})
        session_values_json_redis.update({"person_details": "Not Available"})

        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
        print('redis in reregister_face after user has selected Yes to reregister: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return redirect(url_for('unknown_person'))
        #return redirect(url_for('aadhar_lookup'))
    
    else: #user selects No
        #insert code to delete file from compreface
        print("User clicked No - face does not match the visitor in reregister_face", flush=True)
        # This is the case where face enrollment id does not match the enrollment id associated with the Aadhar
        # AND the soldier has selected No to the face match. So 2 faces are claiming the same ID.
        '''
        if session_values_json_redis.get("enrollment_id_match_status") == "Fail":
            session_values_json_redis.update(
                {"message": "Different person found for the ID provided. Please use the correct Aadhar and try again."})
            session_values_json_redis.update({"ticket_status": "reregister_face"})

            send_to_html_json = {
                'message': _(
                    "Different person found for the ID provided. Please use the correct Aadhar and try again."),
                'page_title': 'Fraud Alert'
            }
            print("404 error details: ", send_to_html_json)
            return render_template('401.html', details=send_to_html_json), 401
        '''

        if session_values_json_redis.get("person_details") == "Available":
            send_to_html_json = {
                'message': _("Different person found for the ID provided. Please use the correct ID and try again."),
                'page_title': 'Fraud Alert'
            }
            print("404 error details: ", send_to_html_json)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('401.html', details=send_to_html_json), 401


        #send to unknown person handles many conditions. The exceptions should be called out above for a different treatement
        # 1. This is the case where this face enrollment already exists with another ID different from the ID with the person
        # Soldier is saying Yes that the faces match, so we should send the user to Known Person
        #if session_values_json_redis.get("picture_matched_another_ID_status") == "Pass":
        print("default block. send to unknown person", flush=True)

        enrollment_id = uuid.uuid4()
        person_image_html_path = session_values_json_redis.get("todays_image_html_path")
        print('person_image_html_path: ', person_image_html_path, flush=True)
        person_image_actual_path = '/project/finalfrsproject/'+ person_image_html_path
        print('person_image_actual_path: ', person_image_html_path, flush=True)
        session_values_json_redis.update({"person_image_html_path": person_image_html_path})
        session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
        #compreface.face_collection.add(image_path=person_image_actual_path, subject=str(enrollment_id))
        session_values_json_redis.update({"enrollment_id": str(enrollment_id)})
        session_values_json_redis.update({"message": _("This person is not in the system. Please enter details and submit.")}),
        session_values_json_redis.update({"ticket_status": "unknown_person"})
        session_values_json_redis.update({"person_details": "Not Available"})

        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
        print('redis in reregister_face after user has selected No to reregister: ', session_values_json_redis, flush=True)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed reregister_face_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return redirect(url_for('unknown_person'))
