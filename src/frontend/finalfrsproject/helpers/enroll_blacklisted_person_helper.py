import json, os, base64, uuid
import shutil

from flask import render_template
from finalfrsproject import routeMethods, app, redisCommands, sqlCommands, ALLOWED_PHOTO_EXTENSIONS
import requests
from flask_babel import _
from datetime import datetime
import time
import re


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting enroll_blacklisted_person_helper_get", flush=True)

    try:
        #session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        #print('*************redis in enroll_blacklisted_person get method: ', session_values_json_redis, flush=True)

        send_to_html_json = {
            'message': _('Please upload a picture and click submit. Only use pictures with the face of a single person.'),
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': _('Enroll Blacklisted Person'),
        }
        print('send to html: ', send_to_html_json, flush=True)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed enroll_blacklisted_person_get | Execution time: {execution_time}ms", flush=True)

        return render_template('enroll_blacklisted_person.html', details=send_to_html_json)

    except Exception as e:
        print(f"Error occurred: {e}", flush=True)
        send_to_html_json = {
            'message': "Error in person look up. Please try again.",
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': _('Enroll Blacklisted Person')
        }


def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting enroll_blacklisted_person_helper_post", flush=True)

    name = request.form.get('name')  # Mandatory field
    id = request.form.get('id')  # Optional field (can be empty string)
    collection_name = 'blacklist'

    print(f'name: {name}, id: {id}, collection: {collection_name}', flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    print("redis in enroll_blacklisted_post: ", session_values_json_redis, flush=True)
    try:

        # Check if 'image' file is present and valid
        lookup_image = request.files.get('image')
        if (not lookup_image or lookup_image.filename == '' or
                not routeMethods.allowed_file(lookup_image.filename, ALLOWED_PHOTO_EXTENSIONS)):
            send_to_html_json = {
                'message': "Please upload a valid image file for person lookup.",
                'page_title': _('Enroll Blacklisted Person'),
                'logged_in_user': jwt_details.get("logged_in_user_name"),
                'logged_in_user_type': jwt_details.get("logged_in_user_type")
            }
            print(f"Invalid or missing image in enroll_blacklisted_person: {send_to_html_json}")
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed enroll_blacklisted_person_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('enroll_blacklisted_person.html', details=send_to_html_json)
        else:

            files = {
                'file': (lookup_image.filename, lookup_image.stream, lookup_image.mimetype)
            }

            # validate if the image before enrollment

            validation_result = validate_enrollment_image(files)

            if validation_result["status"] != "accept":
                lookup_image.stream.seek(0)
                image_bytes = lookup_image.read()
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")
                image_mime = lookup_image.mimetype

                send_to_html_json = {
                    'message': validation_result["reason"],
                    'page_title': _('Enroll Blacklisted Person'),
                    'logged_in_user': jwt_details.get("logged_in_user_name"),
                    'logged_in_user_type': jwt_details.get("logged_in_user_type"),

                    # form values
                    'name': name,
                    'id': id,
                    'collection_name': collection_name,

                    # image preview
                    'image_b64': image_b64,
                    'image_mime': image_mime,
                    'image_name': lookup_image.filename
                }
                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(
                    f"[{end_timestamp}] Completed enroll_blacklisted_person_post | Execution time: {execution_time}ms",
                    flush=True)

                return render_template('enroll_blacklisted_person.html', details=send_to_html_json)

            # Validation passed. send the uploaded file directly to enroll
            # IMPORTANT: reset stream before reusing
            lookup_image.stream.seek(0)
            url = app.config["FACE_RECOGNITION_SERVICE"] + "enroll"
            enrollment_id = uuid.uuid4()
            params = {
                'id':  enrollment_id # enrollment_id
            }
            data = {
                'name': name,
                'aadhaar': id,
                'collection_name': collection_name
            }

            response = requests.post(url, params=params, files=files, data=data, timeout=30)
            print(f'response from enrollment call: {response.json()}')
            response.raise_for_status()

            resp_json = response.json()
            if resp_json.get("status") != "success":
                raise Exception(resp_json.get("message", "Enrollment failed"))

            flush_response = requests.post(
                app.config["FACE_RECOGNITION_SERVICE"] + "flush",
                data={"collection_name": "blacklist"},
                timeout=30,
            )
            flush_response.raise_for_status()

            blacklist_folder = app.config["BLACKLISTED_PERSONS"]
            os.makedirs(blacklist_folder, exist_ok=True)

            safe_name = sanitize_filename(name)

            filename = f"{enrollment_id}_{safe_name}_{id}.jpg"
            save_path = os.path.join(blacklist_folder, filename)

            lookup_image.stream.seek(0)
            with open(save_path, "wb") as f:
                shutil.copyfileobj(lookup_image.stream, f)

            send_to_html_json = {
                'message': "Blacklisted Person successfully enrolled.",
                'page_title': _('Enroll Blacklisted Person'),
                'logged_in_user': jwt_details.get("logged_in_user_name"),
                'logged_in_user_type': jwt_details.get("logged_in_user_type")
            }

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed enroll_blacklisted_person_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('enroll_blacklisted_person.html', details=send_to_html_json)


    except Exception as e:
        print("Error in enroll_blacklisted_person: ", e, flush=True)
        send_to_html_json = {
            'message': "Error while enrolling blacklisted person. Please try again",
            'page_title': _('Enroll Blacklisted Person'),
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type")
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed enroll_blacklisted_person_post | Execution time: {execution_time}ms", flush=True)

        return render_template('enroll_blacklisted_person.html', details=send_to_html_json)

# -----------------------------
# Validate Enrolled Image before enrollment
# -----------------------------
def validate_enrollment_image(files):
    """
    Runs all face validation checks required before enrollment.

    Returns:
        {
            "status": "accept" | "reject",
            "reason": "human readable message"
        }

    Current checks:
    1. Exactly one face must be detected
    2. Image should not be blurry
    """
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting validate_enrollment_image", flush=True)

    try:
        service = app.config.get("FACE_RECOGNITION_SERVICE")
        if not service:
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] validate_enrollment_image service not available| Execution time: {execution_time}ms",
                  flush=True)
            return {
                "status": "reject",
                "reason": "Validation service not configured"
            }

        # 1. Face check
        files["file"][1].seek(0)
        url = service + "validate/image_quality_check"
        response = requests.post(url, files=files, timeout=30)
        if response.status_code != 200:
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(
                f"[{end_timestamp}] validate_enrollment_image service returned "
                f"{response.status_code} | Execution time: {execution_time}ms",
                flush=True
            )
            return {
                "status": "reject",
                "reason": "Image validation service error"
            }
        result = response.json()

        if result.get("status") != "accept":
            print(f'Image quality check failed ', result)
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed validate_enrollment_image | Execution time: {execution_time}ms",
                  flush=True)

            return {
                "status": "reject",
                "reason": result.get("reason", "Image quality check failed")
            }

        # SUCCESS PATH
        print(f'Image quality check successful: ', result)
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed validate_enrollment_image | Execution time: {execution_time}ms",
              flush=True)

        return {
            "status": "accept",
            "reason": "Image validation passed"
        }

    except Exception as e:
        print("Validation service error:", e, flush=True)
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed validate_enrollment_image | Execution time: {execution_time}ms",
              flush=True)

        return {
            "status": "reject",
            "reason": "Image validation service unavailable"
        }


def sanitize_filename(value: str, max_length: int = 80) -> str:
    # Keep only ASCII letters, numbers, underscore, dash, and dot
    value = re.sub(r'[^A-Za-z0-9._-]+', '_', value)

    # Remove leading/trailing underscores or dots
    value = value.strip("._")

    # Prevent empty filename
    if not value:
        value = "unknown"

    return value[:max_length]
