import json, os, shutil, uuid
import requests
from flask import render_template, redirect, url_for
from datetime import datetime
from finalfrsproject import routeMethods, app, ALLOWED_PHOTO_EXTENSIONS
from flask_babel import _
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting recognize_person_helper_get", flush=True)

    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        if session_values_json_redis.get("message") is not None:
            message = session_values_json_redis.get("message")
        else:
            message = 'Please check if the person is already in our system. Click on Take a Picture button and then Submit for Recognition.'

        session_values_json_redis.update({"ticket_status":"recognize_person"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

        send_to_html_json = {
            'logged_in_user':  jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': message,
            'page_title': _("Recognize Person")
        }

        if session_values_json_redis.get("person_details") == "Available":
            send_to_html_json.update({'success_font': 'True'})

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed recognize_person_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('recognize_person.html', details=send_to_html_json)
    except Exception as e:
        print(f'Error in get_recognize_person: {str(e)} ')
        send_to_html_json = {
            'message': "Error while creating page for face recognition. Please try again.",
            'page_title': "Error"
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed recognize_person_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('500.html', details=send_to_html_json), 500


def post_handler(jwt_details, redis_conn, files):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting recognize_person_helper_post", flush=True)

    try:
        person_image_actual_path = None
        person_image_html_path = None
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        enrollment_id = None
        match_status = None
        match_confidence = None
        file = None

        def redirect_with_blacklist_intercept(target_route):
            blacklist_data = session_values_json_redis.get("blacklist") or {}
            if blacklist_data.get("blacklist_route"):
                session_values_json_redis.update({"blacklist_pending": True})
                session_values_json_redis.update({"blacklist_resume_route": target_route})
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                return redirect(url_for('blacklist_alert'))

            session_values_json_redis.pop("blacklist_pending", None)
            session_values_json_redis.pop("blacklist_resume_route", None)
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(url_for(target_route))

        #reads file sent in the request
        if 'file' not in files:
            print('No image file received in recognize person')
            session_values_json_redis.update({"ticket_status": "recognize_person"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            send_to_html_json = {
                'message': "There was no file sent in the recognize person form. Please try again",
                'page_title': "Error"
            }

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('500.html', details=send_to_html_json), 500

        else:
            print('Image file received in recognize person', flush=True)
            file = files['file']

            if file and routeMethods.allowed_file(file.filename, ALLOWED_PHOTO_EXTENSIONS):
                image_time_stamp = datetime.now()
                # Today's image stored as person_image_actual_path.
                person_image_actual_path = os.path.sep.join([app.config['IMAGE_UPLOADS'], "upload_{}.png".format(str(image_time_stamp).replace(" ", "-").replace(":","-"))])
                file.save(person_image_actual_path)
                session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

            # Do a facial recognition and get the similarity level
            files = {
                'file': ('file', open(person_image_actual_path, 'rb'), 'image/jpeg')
            }
            best_match = None
            match_status = None
            try:
                recognition_result_raw = requests.post(
                    app.config["FACE_RECOGNITION_SERVICE"] + "recognize",
                    files=files,
                    timeout=30,
                )
            except requests.RequestException as req_error:
                print("Face recognition service request failed:", req_error, flush=True)
                session_values_json_redis.update({"ticket_status": "recognize_person"})
                session_values_json_redis.update({
                    "message": _("Face recognition service is unavailable. Please try again.")
                })
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                return redirect(url_for('recognize_person'))

            print("recognition result: ", recognition_result_raw, flush=True)
            blacklist_route = False
            blacklist_info = {}
            if recognition_result_raw.ok:
                recognition_result = recognition_result_raw.json()
                if recognition_result['matches'] == []:
                    best_match = None
                    match_status = False  # unknown_person
                else:
                    best_match = recognition_result['matches'][0]
                #check if this person exists in the black listed database
                if recognition_result['matches_blacklist'] == []:
                    print("no black list match", flush=True)
                    pass
                else:
                    blacklist_route = None
                    blacklist_info = recognition_result['matches_blacklist'][0]
                    print(f'found black list match {str(blacklist_info)}', flush=True)
                    if blacklist_info:
                        blacklist_match_confidence = blacklist_info.get('similarity')
                        if blacklist_match_confidence > app.config["FACE_MATCH_CONFIDENCE"]:
                            print(f'black list match confidence {str(blacklist_match_confidence)}', flush=True)
                            blacklist_route = True
                            session_values_json_redis.update(
                                {"blacklist": {"blacklist_route": blacklist_route, "blacklist_info": blacklist_info}})
                            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

            else:
                best_match = None
                match_status = False
                print(
                    "Face recognition service returned HTTP",
                    recognition_result_raw.status_code,
                    flush=True,
                )
                session_values_json_redis.update({"ticket_status": "recognize_person"})
                session_values_json_redis.update({
                    "message": _("Face recognition failed. Please try again.")
                })
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                return redirect(url_for('recognize_person'))

            #result : {'result': [{'box': {'probability': 1.0, 'x_max': 326, 'y_max': 303, 'x_min': 181, 'y_min': 147}, 'subjects': []}]}

            if best_match:
                print("recognition result match found: ", best_match, flush=True)
                match_confidence = best_match['similarity']
                best_match_guid = best_match['guid']
                print(f"recognition result best match guid: ", best_match_guid, flush=True)
                print(f"recognition result match confidence: ", match_confidence, flush=True)

                print("Check if this person_details are available in the system: ", session_values_json_redis, flush=True)
                if session_values_json_redis.get("person_details") == "Available":
                    print("ID exists!!!. Pull the image from know_person folder", flush=True)
                    person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"],str(session_values_json_redis.get('enrollment_id')) + ".png"])
                    print("image_file_on_hard_drive_path: ", person_image_on_hard_drive_actual_path)
                    print("picture found for the enrollment id on the hard drive", flush=True)
                    person_image_on_hard_drive_html_path = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"],os.path.basename(person_image_on_hard_drive_actual_path)])
                    person_image_html_path = os.path.sep.join([app.config["IMAGE_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])
                    session_values_json_redis.update({"todays_image_html_path": person_image_html_path})
                    session_values_json_redis.update({"person_image_on_hard_drive_html_path": person_image_on_hard_drive_html_path})
                    session_values_json_redis.update({"ticket_status": "reregister_face"})
                    #session_values_json_redis.update({"temp_aadhar_number": session_values_json_redis.get('aadhar_number')})
                    # List of keys to check
                    keys_to_check = ["aadhar_number", "drivers_license", "pass_number", "other_id_number"]
                    # Find the first valid key and its corresponding value
                    id_number_in_database, id_type_in_database = None, None
                    for key in keys_to_check:
                        value = session_values_json_redis.get(key)
                        print(f"Checking key: {key}, value: {value}")  # Your debug print
                        if value not in [None, "Not Available"]:
                            id_number_in_database = value
                            id_type_in_database = key
                            break
                    print(f'id_number_in_database: {id_number_in_database}, id_type_in_database: {id_type_in_database}')
                    # Update the dictionary with both values
                    session_values_json_redis.update({"id_number_in_database": id_number_in_database})
                    if id_type_in_database == 'pass_number':
                        id_type_in_database = 'PASS'
                    session_values_json_redis.update({"id_type_in_database": id_type_in_database})
                    session_values_json_redis.update({"message": _("Picture found for this enrollment id. Please confirm this is the same person.")})
                    session_values_json_redis.update({"page_title": "Face Verification "})

                    if session_values_json_redis.get('enrollment_id') == best_match_guid:
                        session_values_json_redis.update({"enrollment_id_match_status": "Pass"})
                        if match_confidence < app.config["FACE_MATCH_CONFIDENCE"]:
                            print("match confidence low", flush=True)
                            session_values_json_redis.update({"face_recognition_match_confidence": "Low"})
                            session_values_json_redis.update({"face_recognition_match_status": _("Fail")})
                        else:
                            print("match confidence high", flush=True)
                            session_values_json_redis.update({"face_recognition_match_confidence": "High"})
                            session_values_json_redis.update({"face_recognition_match_status": _("Pass")})
                    else:
                        session_values_json_redis.update({"enrollment_id_match_status": "Fail"})
                        session_values_json_redis.update(
                            {"message": _("Different person found for the ID provided. Please confirm below.")})
                        session_values_json_redis.update({"page_title": "Error"})
                        print("person does not match with the face associated with ID provided", flush=True)
                        session_values_json_redis.update({"face_recognition_match_status": _("Fail")})

                    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                    print('redis in recognize_person when a picture is found for the enrollment_id: ', session_values_json_redis, flush=True)

                    end_time = time.time()
                    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                        flush=True)

                    return redirect_with_blacklist_intercept('reregister_face')

                else:
                    print("Face was recognized found but person_details are not available from the ID look up", flush=True)

                    #if the user says No, then go to unknown person.
                    #if the user says Yes, then go where?
                    if match_confidence is None or match_confidence < app.config["FACE_MATCH_CONFIDENCE"]:
                        match_status = False #unknown_person
                        session_values_json_redis.update({"face_recognition_match_status": _("Fail")})
                        session_values_json_redis.update({"face_recognition_match_confidence": "Low"})
                        print(f"recognition result match confidence is below threshold or none")
                    else:
                        session_values_json_redis.update({"face_recognition_match_status": _("Pass")})
                        session_values_json_redis.update({"face_recognition_match_confidence": "High"})
                        print(f"recognition result match confidence is above threshold", flush=True)

                        #Important assignment. Future logic depends on whether this matches or not
                        enrollment_id = best_match['guid']

                        print("recognition result match enrollment_id: ", enrollment_id, flush=True)

                        # is this picture in our database assigned to a different aadhar number
                        print("Check 1 - Is there any other person in the database for the same picture.",flush=True)

                        result = routeMethods.get_known_person_details_with_enrollment_id(enrollment_id, session_values_json_redis)

                        if result.get("Status") != "Fail" and result.get("Details") != "No match found":
                            print("Yes there is another person matched this face.", flush=True)
                            person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"], str(enrollment_id) + ".png"])
                            print("image_file_on_hard_drive_path: ", person_image_on_hard_drive_actual_path)
                            if os.path.isfile(person_image_on_hard_drive_actual_path) is True:
                                print("picture found for the enrollment id on the hard drive")
                                person_image_on_hard_drive_html_path = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person_image_on_hard_drive_actual_path)])
                                person_image_html_path = os.path.sep.join([app.config["IMAGE_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])
                                print("person_image_html_path: ", person_image_html_path)
                                session_values_json_redis.update({"enrollment_id": str(enrollment_id)})
                                session_values_json_redis.update({"todays_image_html_path": person_image_html_path})
                                session_values_json_redis.update({"person_image_on_hard_drive_html_path": person_image_on_hard_drive_html_path})
                                session_values_json_redis.update({"ticket_status": "reregister_face"})
                                # List of keys to check
                                keys_to_check = ["aadhar_number", "drivers_license", "other_id_number", "pass_number"]
                                # Fetch values from the "Details" sub-dictionary
                                details = result.get("Details")
                                print(f'result from get_person_details_with_enrollment_id: ',details)
                                id_number_in_database, id_type_in_database = None, None
                                for key in keys_to_check:
                                    #value = session_values_json_redis.get(key)
                                    value = details.get(key)
                                    print(f"Checking key: {key}, value: {value}")  # Your debug print
                                    if value not in [None, "Not Available"]:
                                        id_number_in_database = value
                                        id_type_in_database = key
                                        break
                                print(f'id_number_in_database: {id_number_in_database}, id_type_in_database: {id_type_in_database}')
                                session_values_json_redis.update({"id_number_in_database": id_number_in_database})
                                if id_type_in_database == 'pass_number':
                                    id_type_in_database = 'PASS'
                                session_values_json_redis.update({"id_type_in_database": id_type_in_database})
                                # Update session dictionary
                                #session_values_json_redis.update({"temp_aadhar_number": id_number, "temp_id_type": id_type})
                                session_values_json_redis.update({"message": _("This picture matched another ID. Please confirm below.")})

                                session_values_json_redis.update({"picture_matched_another_ID_status": "Pass"})

                                session_values_json_redis.update({"page_title": "Error"})
                                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                                print('redis in recognize_person when a picture is found for the enrollment_id: ', session_values_json_redis)

                                end_time = time.time()
                                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                                print(
                                    f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                                    flush=True)

                                return redirect_with_blacklist_intercept('reregister_face')
                            else:
                                print(
                                    "Matched person in database but enrollment photo is missing; "
                                    "continuing as new registration",
                                    flush=True,
                                )
                                match_status = False

                        elif result.get("Details") == "No match found":
                            print("No matching person details found for this enrollment_id in the facial database")
                            # do we have a picture in the local drive
                            # if session_values_json_redis.get("person_details") == "Available":
                            #      person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"],str(session_values_json_redis.get('enrollment_id')) + ".png"])
                            # else:

                            person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"], str(enrollment_id) + ".png"])

                            # image_file_on_hard_drive_path = os.path.sep.join([app.config["KNOWN_PERSONS"], image_file_on_hard_drive])
                            print("image_file_on_hard_drive_path: ", person_image_on_hard_drive_actual_path)
                            if os.path.isfile(person_image_on_hard_drive_actual_path) is True:
                                print("picture found for the enrollment id on the hard drive")
                                person_image_on_hard_drive_html_path = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person_image_on_hard_drive_actual_path)])
                                person_image_html_path = os.path.sep.join([app.config["IMAGE_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])
                                session_values_json_redis.update({"enrollment_id": str(enrollment_id)})
                                session_values_json_redis.update({"todays_image_html_path": person_image_html_path})
                                session_values_json_redis.update({"person_image_on_hard_drive_html_path": person_image_on_hard_drive_html_path})
                                session_values_json_redis.update({"ticket_status": "reregister_face"})
                                # List of keys to check
                                keys_to_check = ["aadhar_number", "drivers_license", "pass_number", "other_id_number"]
                                # Find the first valid key and its corresponding value
                                id_number_in_database, id_type_in_database = None, None
                                for key in keys_to_check:
                                    value = session_values_json_redis.get(key)
                                    print(f"Checking key: {key}, value: {value}")  # Your debug print
                                    if value not in [None, "Not Available"]:
                                        id_number_in_database = value
                                        id_type_in_database = key
                                        break
                                print(
                                    f'id_number_in_database: {id_number_in_database}, id_type_in_database: {id_type_in_database}')
                                # Update the dictionary with both values
                                session_values_json_redis.update({"id_number_in_database": id_number_in_database})
                                if id_type_in_database == 'pass_number':
                                    id_type_in_database = 'PASS'
                                session_values_json_redis.update({"id_type_in_database": id_type_in_database})
                                session_values_json_redis.update({"temp_aadhar_number": session_values_json_redis.get('aadhar_number')})
                                session_values_json_redis.update({"message": "Picture found for this enrollment id. Please reregister this is the same person."})
                                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                                print('redis in recognize_person when a picture is found for the enrollment_id: ',
                                      session_values_json_redis)
                                '''
                                print("No other person was found in the database matching this face", flush=True)
                                print(
                                    "Person face matched in the Facial database, but no entry in the database or the directory. "
                                    "Need to delete face from facial database")
        
                                url = app.config["FACE_RECOGNITION_SERVICE"] + "delete"
                                params = {'id': str(enrollment_id)}
                                response = requests.post(url, params=params)
                                person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"], str(enrollment_id) + ".png"])
                                print("image_file_on_hard_drive_path: ", person_image_on_hard_drive_actual_path)
                                if os.path.isfile(person_image_on_hard_drive_actual_path) is True:
                                    os.remove(person_image_on_hard_drive_actual_path)
                                    print("File deleted successfully.")
                                else:
                                    print("File not found.")
                                match_status = False
                                '''

                                end_time = time.time()
                                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                                print(
                                    f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                                    flush=True)

                                return redirect_with_blacklist_intercept('reregister_face')

                        elif result.get("Status") == "Fail":
                            print("Enrollment_ID Lookup failed due to a system issue. Please try again")
                            session_values_json_redis.update({"message": "The enrollment id lookup failed due to a system issue. Please try again."})
                            session_values_json_redis.update({"ticket_status": "recognize_person"})
                            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

                            end_time = time.time()
                            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                            print(
                                f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                                flush=True)

                            return redirect(url_for('recognize_person'))

            if match_status == False:
                print("no match in the person table", flush=True)
                enrollment_id = uuid.uuid4()
                person_image_html_path = os.path.sep.join([app.config["IMAGE_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])
                session_values_json_redis.update({"person_image_html_path": person_image_html_path})
                session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
                session_values_json_redis.update({"enrollment_id": str(enrollment_id)})
                session_values_json_redis.update({"message": _("This person is not in the system. Please enter details and submit.")}),
                session_values_json_redis.update({"ticket_status": "unknown_person"})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                print('redis in recognize_person: ', session_values_json_redis, flush=True)

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return redirect_with_blacklist_intercept('unknown_person')

    except Exception as e:
        print(f'Error in post_recognize_person: {str(e)} ', flush=True)
        send_to_html_json = {
            'message': "Error while recognizing person. Please try again.",
            'page_title': "Error"
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed recognize_person_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return render_template('500.html', details=send_to_html_json), 500
