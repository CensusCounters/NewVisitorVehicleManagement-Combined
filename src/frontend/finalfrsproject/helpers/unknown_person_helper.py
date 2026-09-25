import binascii
import json, os, shutil
import re
import requests
from flask import render_template, redirect, url_for
from finalfrsproject import routeMethods, app, redisCommands
from flask_babel import _
import base64
from datetime import datetime
import time

REQUIRED_UNKNOWN_PERSON_FIELDS = (
    "traveler_type",
    "name",
    "gender",
    "mobile_number",
    "guardians_name",
    "address",
    "visiting_person_name",
    "id_type",
    "id_number",
    "id_image",
)


def _safe_filename_part(value):
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return (normalized or "unknown")[:80]


def _decode_image_data(image_data):
    """Validate a browser data URL before writing it to an ID image folder."""
    try:
        header, encoded = image_data.split(',', 1)
    except (AttributeError, ValueError) as error:
        raise ValueError("Invalid ID image data.") from error

    allowed_headers = {
        "data:image/jpeg;base64": b"\xff\xd8\xff",
        "data:image/png;base64": b"\x89PNG\r\n\x1a\n",
    }
    signature = allowed_headers.get(header.lower())
    if signature is None:
        raise ValueError("ID images must be JPEG or PNG files.")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid ID image data.") from error
    if not decoded.startswith(signature):
        raise ValueError("The uploaded ID image content is invalid.")
    if len(decoded) > 10 * 1024 * 1024:
        raise ValueError("Each ID image must be smaller than 10 MB.")
    return decoded


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting unknown_person_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    session_values_json_redis.update({"ticket_status": "unknown_person"})
    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

    send_to_html_json = redisCommands.create_json_for_unknown_person_get_from_redis_object(
        jwt_details.get('logged_in_user_id'), jwt_details.get("logged_in_user_name"),
        jwt_details.get("logged_in_user_type"))
    print("send_to_html_json in unknown person get: ", send_to_html_json, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed unknown_person_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('unknown_person.html', details=send_to_html_json)


def post_handler(jwt_details, redis_conn, request):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting unknown_person_helper_post", flush=True)

    aadhar_image = drivers_license_image = other_id_image = pass_image = primary_id_image = None
    aadhar_number = drivers_license = other_id_number = pass_number = None
    aadhar_img_file_path = drivers_license_img_file_path = other_id_img_file_path = pass_img_file_path = None
    id_image = id_type = id_number = None
    form = None
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    print("about to get to form", flush=True)
    if request.form:
        form = dict(request.form)
        schema = app.config["UNKNOWN_PERSON_PAGE_FIELDS"]
        # print("form from unknown person: ", form, flush=True)
        name = form.get("name")
        id_image = form.get('id_image')
        id_type = form.get('id_type')
        id_number = form.get('id_number')
        missing_fields = [
            field
            for field in REQUIRED_UNKNOWN_PERSON_FIELDS
            if not str(form.get(field) or "").strip()
        ]
        if missing_fields:
            readable_fields = ", ".join(field.replace("_", " ").title() for field in missing_fields)
            session_values_json_redis.update({
                "message": _("Required fields missing: %(fields)s", fields=readable_fields),
                "ticket_status": "unknown_person",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(request.url)

        traveler_type = form.get("traveler_type")
        allowed_id_types = app.config["ALLOWED_ID_TYPES_BY_VISITOR"].get(traveler_type, [])
        if traveler_type not in app.config["VISITOR_CATEGORIES"] or id_type not in allowed_id_types:
            session_values_json_redis.update({
                "message": _("The selected visitor type and ID type are not allowed."),
                "ticket_status": "unknown_person",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(request.url)

        if form.get("gender") not in {"Male", "Female"}:
            session_values_json_redis.update({
                "message": _("Please select a valid gender."),
                "ticket_status": "unknown_person",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(request.url)

        mobile_number = str(form.get("mobile_number") or "").strip()
        if not mobile_number.isdigit() or len(mobile_number) != 10:
            session_values_json_redis.update({
                "message": _("Mobile number must contain exactly 10 digits."),
                "ticket_status": "unknown_person",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(request.url)

        if schema.get("purpose_input") == "select" and form.get("visiting_person_name") not in app.config["VISIT_PURPOSE_CATEGORIES"]:
            session_values_json_redis.update({
                "message": _("Please select a valid visit purpose."),
                "ticket_status": "unknown_person",
            })
            redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
            return redirect(request.url)

        # Get current time
        current_time = datetime.now()
        # Format it
        formatted_time = current_time.strftime("%d-%m-%Y:%H:%M:%S")

        require_dl_for = set(schema.get("require_dl_for", []))
        requires_supplemental_dl = form.get('traveler_type') in require_dl_for and id_type != 'DRIVERS LICENSE'
        if requires_supplemental_dl:
            drivers_license = (form.get('drivers_license') or '').strip()
            drivers_license_image = form.get('drivers_license_image')
            if not drivers_license or not drivers_license_image:
                session_values_json_redis.update({
                    "message": _("Driver's licence number and image are required for this visitor type."),
                    "ticket_status": "unknown_person",
                })
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                return redirect(request.url)

            normalized_license = drivers_license.replace('-', '').replace(' ', '')
            if len(normalized_license) != 15 or not normalized_license.isalnum():
                session_values_json_redis.update({
                    "message": _("Driver's licence number must be exactly 15 alphanumeric characters."),
                    "ticket_status": "unknown_person",
                })
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
                return redirect(request.url)

            new_file_name = _safe_filename_part(name) + "-" + _safe_filename_part(drivers_license) + "-drivers_license-" + formatted_time + '.png'
            image_data = _decode_image_data(drivers_license_image)
            with open(os.path.sep.join([app.config['DRIVERS_LICENSES'], new_file_name]), 'wb') as file:
                file.write(image_data)
            drivers_license_img_file_path = os.path.join(app.config["DRIVERS_LICENSE_PATH_FOR_HTML"], new_file_name)
            form['drivers_license'] = drivers_license
            form['drivers_license_img_file_path'] = drivers_license_img_file_path
        if id_type == 'AADHAR':
            aadhar_number = id_number
            new_file_name = _safe_filename_part(name) + "-" + _safe_filename_part(aadhar_number) + "-aadhar-" + formatted_time + '.png'
            if id_image:
                aadhar_image = id_image
                image_data = _decode_image_data(aadhar_image)
                with open(os.path.sep.join([app.config["VISITOR_AADHARS"], new_file_name]), 'wb') as file:
                    file.write(image_data)
                aadhar_img_file_path = os.path.join(app.config["AADHAR_PATH_FOR_HTML"], new_file_name)

            form['aadhar_number'] = aadhar_number
            form['aadhar_img_file_path'] = aadhar_img_file_path
            primary_id_image = aadhar_img_file_path

        elif id_type == 'DRIVERS LICENSE':
            drivers_license = id_number
            new_file_name = _safe_filename_part(name) + "-" + _safe_filename_part(drivers_license) + "-drivers_license-" + formatted_time + '.png'
            if id_image:
                drivers_license_image = id_image
                image_data = _decode_image_data(drivers_license_image)
                with open(os.path.sep.join([app.config['DRIVERS_LICENSES'], new_file_name]), 'wb') as file:
                    file.write(image_data)
                drivers_license_img_file_path = os.path.join(app.config["DRIVERS_LICENSE_PATH_FOR_HTML"], new_file_name)
            form['drivers_license'] = drivers_license
            form['drivers_license_img_file_path'] = drivers_license_img_file_path
            primary_id_image = drivers_license_img_file_path

        elif id_type == 'OTHER':
            other_id_number = id_number
            new_file_name = _safe_filename_part(name) + "-" + _safe_filename_part(other_id_number) + "-other_id-" + formatted_time + '.png'
            if id_image:
                other_id_image = id_image
                image_data = _decode_image_data(other_id_image)
                with open(os.path.sep.join([app.config['OTHER_IDS'], new_file_name]), 'wb') as file:
                    file.write(image_data)
                other_id_img_file_path = os.path.join(app.config["OTHER_ID_PATH_FOR_HTML"], new_file_name)
            form['other_id_type'] = id_type
            form['other_id_number'] = other_id_number
            form['other_id_img_file_path'] = other_id_img_file_path
            primary_id_image = other_id_img_file_path

        else:
            pass_number = id_number
            new_file_name = _safe_filename_part(name) + "-" + _safe_filename_part(pass_number) + "-pass-" + formatted_time + '.png'

            if id_image:
                # print(f'id_image : {id_image}', flush=True)
                pass_image = id_image
                image_data = _decode_image_data(pass_image)

                print(f"[DEBUG] Does path exist? {os.path.exists(app.config['PASSES'])}", flush=True)
                with open(os.path.sep.join([app.config['PASSES'], new_file_name]), 'wb') as file:
                    file.write(image_data)
                pass_img_file_path = os.path.join(app.config["PASSES_PATH_FOR_HTML"], new_file_name)
            form['pass_number'] = pass_number
            form['pass_img_file_path'] = pass_img_file_path
            primary_id_image = pass_img_file_path

    person_image_actual_path = form.get('person_image_actual_path')
    person_image_destination = os.path.sep.join([app.config["KNOWN_PERSONS"], str(form.get('enrollment_id')) + ".png"])
    form['person_image_destination'] = person_image_destination
    # result = routeMethods.insert_new_person_record(jwt_details.get("logged_in_user_id"), form, aadhar_image, drivers_license_image, person_image_destination)
    result = routeMethods.insert_new_person_record(jwt_details.get("logged_in_user_id"), form)
    # result = {"Status": "Success", "Insert_Count": count, "Details": inserted_data}

    if not result or result.get('Status') == "Fail" or result.get("Insert_Count") == 0:
        if result.get("Status") == "Fail":
            message = "Error - " + str(result.get('Details')) + " Please try again."
        else:
            message = "System was unable to insert a person record. Please try again."
        session_values_json_redis.update({"message": message})
        session_values_json_redis.update({"ticket_status": "unknown_person"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        print("redis in unknown_person when insert new person record failed: ", session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed unknown_person_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return redirect(request.url)

    else:
        result = result.get('Details')
        print('result from insert new person', result, flush=True)

        # 2024-01-18 15:29:53.669541
        # details_entry_date = result[2].strftime('%d %b, %Y %I:%M:%S %p')
        details_entry_date = result.get('date_created').strftime('%d %b, %Y %I:%M:%S %p')
        # if result[13] is not None:
        if result.get('dob') is not None:
            person_dob = result.get('dob').strftime('%d %b, %Y')
        else:
            person_dob = ''

        # Save the person image into known person folder. 
        shutil.move(person_image_actual_path, person_image_destination)
        person_image_actual_path = person_image_destination
        person_image_html_path = os.path.sep.join(
            [app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person_image_actual_path)])

        url = app.config["FACE_RECOGNITION_SERVICE"] + "enroll"
        params = {
            # 'id': str(result[3])#enrollment_id
            'id': str(result.get('enrollment_id'))  # enrollment_id
        }
        files = {
            'file': ('file', open(person_image_actual_path, 'rb'), 'image/jpeg')
        }
        data = {
            # 'name': result[4],
            'name': result.get('person_name'),
            # 'aadhaar': result[6]
            'aadhaar': result.get('id'),
            'collection_name': 'default'
        }

        response = requests.post(url, params=params, files=files, data=data, timeout=30)
        response.raise_for_status()
        flush_response = requests.post(
            app.config["FACE_RECOGNITION_SERVICE"] + "flush",
            data={"collection_name": "default"},
            timeout=30,
        )
        flush_response.raise_for_status()
        aadhar_image_location = result.get('aadhar_image_location')
        print(f'aadhar_image_location: {aadhar_image_location}')
        session_values_json_redis.update({"person_image_html_path": person_image_html_path})
        session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
        session_values_json_redis.update({"enrollment_id": str(result.get('enrollment_id'))})
        session_values_json_redis.update({"details_entered_by": result.get('created_by')})
        session_values_json_redis.update({"details_entered_on": details_entry_date})
        session_values_json_redis.update({"person_name": result.get('person_name')})
        session_values_json_redis.update({"guardians_name": result.get('guardians_name')})
        session_values_json_redis.update({"mobile_number": result.get('mobile_number')})
        session_values_json_redis.update({"address": result.get('address')})
        session_values_json_redis.update({"visiting_person_name": result.get('visiting_person_name')})
        session_values_json_redis.update({"aadhar_number": result.get('aadhar_number')})
        session_values_json_redis.update({"aadhar_image": result.get('aadhar_image_location')})
        session_values_json_redis.update({"drivers_license": result.get('drivers_license_number')})
        session_values_json_redis.update({"drivers_license_image": result.get('drivers_license_image')})
        session_values_json_redis.update({"other_id_type": result.get('other_id_type')})
        session_values_json_redis.update({"other_id_number": result.get('other_id_number')})
        session_values_json_redis.update({"other_id_image_location": result.get('other_id_image_location')})
        session_values_json_redis.update({"person_id": result.get('id')})
        session_values_json_redis.update({"gender": result.get('gender')})
        session_values_json_redis.update({"dob": person_dob})
        session_values_json_redis.update({"person_image": person_image_html_path})
        session_values_json_redis.update({"id_type": id_type})
        session_values_json_redis.update({"pass_number": result.get('pass_number')})
        session_values_json_redis.update({"pass_image": result.get('pass_image_location')})
        session_values_json_redis.update({"primary_id_image": primary_id_image})
        session_values_json_redis.update({"primary_id_number": id_number})
        session_values_json_redis.update({"primary_id_type": id_type})
        session_values_json_redis.update(
            {"message": _("Success! Visitor Information is in the database. Please continue.")})
        session_values_json_redis.update({"ticket_status": "known_person"})
        session_values_json_redis.update({"traveler_type": form.get('traveler_type')})

        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        print("redis in unknown_person after new person record is successfully inserted: ", session_values_json_redis,
              flush=True)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed unknown_person_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return redirect(url_for('known_person'))
