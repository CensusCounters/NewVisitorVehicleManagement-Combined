import json, os, base64
from flask import render_template
from finalfrsproject import routeMethods, app, redisCommands, sqlCommands, ALLOWED_PHOTO_EXTENSIONS
import requests
from flask_babel import _
from datetime import datetime
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting person_lookup_helper_get", flush=True)
    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        session_values_json_redis.update({"ticket_status":"person_lookup"})
        session_values_json_redis.update({"page_title": "person_lookup"})
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
        print('*************redis in person_lookup get method: ', session_values_json_redis, flush=True)

        send_to_html_json = {
            'message': _('Please upload a picture and click submit. Only use pictures with the face of a single person.'),
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': _('Person Lookup'),
        }
        print('send to html: ', send_to_html_json, flush=True)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed person_lookup_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('person_lookup.html', details=send_to_html_json)
    except Exception as e:
        print(f"Error occurred: {e}", flush=True)
        send_to_html_json = {
            'message': "Error in person look up. Please try again.",
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': _('Person Lookup')
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed person_lookup_helper_get | Execution time: {execution_time}ms", flush=True)

        return render_template('person_lookup.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting person_lookup_helper_post", flush=True)

    print("person_lookup post handler", flush=True)
    print("request:", request, flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    print("redis in person lookup post: ", session_values_json_redis, flush=True)
    try:
        print("request in person lookup post: ", request, flush=True)
        # Check if 'image' file is present and valid
        lookup_image = request.files.get('image')
        if (not lookup_image or lookup_image.filename == '' or
                    not routeMethods.allowed_file(lookup_image.filename, ALLOWED_PHOTO_EXTENSIONS)):
            send_to_html_json = {
                'message': "Please upload a valid image file for person lookup.",
                'page_title': "Person Look Up",
                'logged_in_user': jwt_details.get("logged_in_user_name"),
                'logged_in_user_type': jwt_details.get("logged_in_user_type")
            }
            print(f"Invalid or missing image in person_lookup: {send_to_html_json}")
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed person_lookup_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('person_lookup.html', details=send_to_html_json)
        else:
            # Send the uploaded file directly to the face recognition service
            files = {
                'file': (lookup_image.filename, lookup_image.stream, lookup_image.mimetype)
            }

            recognition_result_raw = requests.post(app.config["FACE_RECOGNITION_SERVICE"] + "recognize", files=files)
            #print("recognition result: ", recognition_result_raw, flush=True)
            if recognition_result_raw:
                recognition_result = recognition_result_raw.json()
                if recognition_result['matches'] == []:
                    # Then call it before each render_template:
                    image_base64, image_mime_type = prepare_image_for_display(lookup_image)
                    send_to_html_json = {
                        'message': "No matches found for the uploaded picture.",
                        'page_title': "Person Look Up Result",
                        'lookup_image_base64': image_base64,
                        'lookup_image_mime_type': image_mime_type,
                        'logged_in_user': jwt_details.get("logged_in_user_name"),
                        'logged_in_user_type': jwt_details.get("logged_in_user_type")
                    }
                    end_time = time.time()
                    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{end_timestamp}] Completed person_lookup_helper_post | Execution time: {execution_time}ms",
                          flush=True)

                    return render_template('person_lookup_result_list.html', details=send_to_html_json)
                else:
                    matches = recognition_result['matches']
                    #matches = recognition_result['matches'][3]
                    print(f'face recognition matches: {matches}')
                    valid_matches = []

                    for match in matches:
                        similarity = match.get('similarity')  # or whatever the key name is

                        # Only process if similarity is above confidence threshold
                        if similarity > app.config["FACE_MATCH_CONFIDENCE"]:
                            enrollment_id = match.get('guid')  # or whatever the key name is

                            # Create actual file path on hard drive
                            person_image_on_hard_drive_actual_path = os.path.sep.join([app.config["KNOWN_PERSONS"],str(enrollment_id) + ".png"])

                            # Check if the file actually exists
                            if os.path.exists(person_image_on_hard_drive_actual_path):
                                # Create HTML path only if file exists
                                person_image_on_hard_drive_html_path = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"],
                                    os.path.basename(person_image_on_hard_drive_actual_path)
                                ])

                                # Add paths to the existing match dictionary
                                match['image_actual_path'] = person_image_on_hard_drive_actual_path
                                match['image_html_path'] = person_image_on_hard_drive_html_path

                                # Add to valid matches list
                                valid_matches.append(match)

                                print(f"Enrollment ID: {enrollment_id}, Similarity: {similarity}")
                                print(f"image_file_on_hard_drive_path: {person_image_on_hard_drive_actual_path}")
                                print("picture found for the enrollment id on the hard drive", flush=True)
                            else:
                                print(
                                    f"Discarding match - Image file not found for enrollment ID {enrollment_id}: {person_image_on_hard_drive_actual_path}",
                                    flush=True)
                                # Skip this match (don't add to valid_matches)
                        else:
                            print(
                                f"Discarding match - Similarity {similarity} below threshold {app.config['FACE_MATCH_CONFIDENCE']}",
                                flush=True)
                            # Skip this match (don't add to valid_matches)

                    # Replace the original matches list with only valid ones
                    matches = valid_matches
                    print("valid matches: ", matches, flush=True)
                    # Then call it before each render_template:
                    image_base64, image_mime_type = prepare_image_for_display(lookup_image)

                    end_time = time.time()
                    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    print(f"[{end_timestamp}] Completed person_lookup_helper_post | Execution time: {execution_time}ms",
                          flush=True)

                    return render_template('person_lookup_result_list.html', details={
                        'message': "Following matches were found for the upload picture.",
                        'matches': matches,
                        'page_title': "Person Look Up Result",
                        'lookup_image_base64': image_base64,
                        'lookup_image_mime_type': image_mime_type,
                        'logged_in_user': jwt_details.get("logged_in_user_name"),
                        'logged_in_user_type': jwt_details.get("logged_in_user_type")
                    })
            else:

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed person_lookup_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return render_template('person_lookup.html', details={
                    'message': "Error in person look up. Please try again",
                    'page_title': "Person Look Up",
                    'logged_in_user': jwt_details.get("logged_in_user_name"),
                    'logged_in_user_type': jwt_details.get("logged_in_user_type")
                })

    except Exception as e:
        print("Error in person look up: ", e, flush=True)
        send_to_html_json = {
            'message': "Error in person look up. Please try again",
            'page_title': "Person Look Up",
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type")
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed person_lookup_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('person_lookup.html', details=send_to_html_json)

def prepare_image_for_display(image_file):
    image_file.seek(0)
    image_data = image_file.read()
    image_base64 = base64.b64encode(image_data).decode('utf-8')
    return image_base64, image_file.mimetype

