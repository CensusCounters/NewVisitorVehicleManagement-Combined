import base64
import binascii
import json
import os
from flask import render_template, redirect, url_for, jsonify
from finalfrsproject import app, redisCommands, routeMethods
from flask_babel import _
import time
from datetime import datetime

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_person_helper_get", flush=True)

    user_id_key = str(jwt_details.get('logged_in_user_id'))
    raw_session = redis_conn.get(user_id_key)
    if raw_session is None:
        return redirect(url_for('home'))
    session_values_json_redis = json.loads(raw_session)
    trip_and_traveler_details = session_values_json_redis.get("trip_and_traveler_details")
    print('current travelers in this trip: ', trip_and_traveler_details)
    if trip_and_traveler_details is not None:
        for traveler in trip_and_traveler_details:
            if traveler.get("person_id") == session_values_json_redis.get("person_id"):
                print("same person being added twice - Person 1: ", traveler.get("person_id"), " Person 2: ", session_values_json_redis.get("person_id"), flush=True)
                #if session_values_json_redis.get("message") is not None:
                #message = session_values_json_redis.get("message")
                message = _("You cannot add the same person again to the trip. Please start with a new ID to continue.")
                session_values_json_redis.update({"message": message})
                session_values_json_redis.update({"ticket_status": "known_person"})
                redis_conn.set(user_id_key, json.dumps(session_values_json_redis))
                print("redis in known_person after the same person was being added more than once: ", session_values_json_redis)
                return redirect(url_for('aadhar_lookup'))

    result = routeMethods.get_known_person_trips(session_values_json_redis.get("person_id"))
    #print("result: ", result, flush=True)
    if result.get("Status") == "Fail":
        message = f"Success! Visitor Information is in the database. Unable to get previous visits."
        print("Known Person Trips Lookup failed", flush=True)

    elif result.get("Details") == "No trips found":
        message = f"Success! Visitor Information is in the database. No last recorded visit found."
        print('No Known Person Trips found', flush=True)

    else:
        known_person_trips = result.get("Details")
        formatted_dates = [dt[0].strftime("%H:%M %b %d, %Y") for dt in known_person_trips]
        message = f"Last recorded visit(s): {', '.join(formatted_dates)}."
        print('Known Person Trips found', message, flush=True)

    session_values_json_redis.update({"message": message})
    session_values_json_redis.update({"ticket_status": "known_person"})
    redis_conn.set(user_id_key, json.dumps(session_values_json_redis))
    send_to_html_json = redisCommands.create_json_for_known_person_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get("logged_in_user_name"),jwt_details.get("logged_in_user_type"))
    print("redis in known_person before redirecting to known_person.html: ", session_values_json_redis, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed known_person_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('known_person.html', details=send_to_html_json)

def _sync_person_fields_to_redis(session_values_json_redis, form, updated_details=None):
    """Keep Redis session in sync after person detail edits."""
    source = updated_details or form
    session_values_json_redis.update({
        "person_name": source.get("person_name") if updated_details else source.get("name"),
        "gender": source.get("gender"),
        "mobile_number": source.get("mobile_number"),
        "guardians_name": source.get("guardians_name"),
        "address": source.get("address"),
        "visiting_person_name": source.get("visiting_person_name"),
    })
    return session_values_json_redis

def _save_aadhar_retake(person_id, image_data):
    """Validate and save a replacement Aadhar image submitted as a data URL."""
    if not image_data:
        return None

    try:
        header, encoded = image_data.split(',', 1)
    except ValueError as error:
        raise ValueError("Invalid ID image data.") from error

    allowed_headers = {
        'data:image/jpeg;base64': '.jpg',
        'data:image/png;base64': '.png',
    }
    extension = allowed_headers.get(header.lower())
    if not extension:
        raise ValueError("ID image must be a JPEG or PNG file.")

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Invalid ID image data.") from error

    if not image_bytes:
        raise ValueError("The captured ID image is empty.")
    if len(image_bytes) > 10 * 1024 * 1024:
        raise ValueError("The captured ID image must be smaller than 10 MB.")
    if extension == '.jpg' and not image_bytes.startswith(b'\xff\xd8\xff'):
        raise ValueError("The captured ID image is not a valid JPEG file.")
    if extension == '.png' and not image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError("The captured ID image is not a valid PNG file.")

    filename = f"{person_id}-aadhar-{datetime.now().strftime('%Y%m%d%H%M%S%f')}{extension}"
    actual_path = os.path.join(app.config["VISITOR_AADHARS"], filename)
    with open(actual_path, 'wb') as image_file:
        image_file.write(image_bytes)

    return {
        "actual_path": actual_path,
        "html_path": os.path.join(app.config["AADHAR_PATH_FOR_HTML"], filename),
    }

def update_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_person_helper_update", flush=True)

    user_id_key = str(jwt_details.get('logged_in_user_id'))
    raw_session = redis_conn.get(user_id_key)
    if raw_session is None:
        return jsonify({"Status": "Fail", "Details": "Session expired. Please sign in again."}), 401

    session_values_json_redis = json.loads(raw_session)
    person_id = session_values_json_redis.get("person_id")
    if not person_id:
        return jsonify({"Status": "Fail", "Details": "No person selected in session."}), 400

    form_data = form.to_dict() if hasattr(form, 'to_dict') else dict(form)
    required_fields = app.config.get("KNOWN_PERSON_SCHEMA", {}).get("required_fields", [])
    missing_fields = [field for field in required_fields if not str(form_data.get(field) or "").strip()]
    if missing_fields:
        readable_fields = ", ".join(field.replace("_", " ").title() for field in missing_fields)
        return jsonify({"Status": "Fail", "Details": f"Required fields missing: {readable_fields}."}), 400

    purpose = (form_data.get("visiting_person_name") or "").strip()
    allowed_purposes = set(app.config.get("VISIT_PURPOSE_CATEGORIES", []))
    current_purpose = session_values_json_redis.get("visiting_person_name")
    if allowed_purposes and purpose not in allowed_purposes and purpose != current_purpose:
        return jsonify({"Status": "Fail", "Details": "Please select a valid purpose."}), 400

    saved_image = None
    image_data = form_data.get("id_image_data")
    if image_data:
        primary_id_type = str(session_values_json_redis.get("primary_id_type") or "").upper()
        if primary_id_type not in {"AADHAR", "AADHAR_NUMBER"}:
            return jsonify({"Status": "Fail", "Details": "ID image retake is supported only for Aadhar."}), 400
        try:
            saved_image = _save_aadhar_retake(person_id, image_data)
            form_data["aadhar_img_file_path"] = saved_image["html_path"]
        except (OSError, ValueError) as error:
            return jsonify({"Status": "Fail", "Details": str(error)}), 400

    result = routeMethods.update_person_record(person_id, form_data)
    if not result or result.get("Status") == "Fail":
        if saved_image:
            try:
                os.remove(saved_image["actual_path"])
            except OSError:
                pass
        details = result.get("Details") if result else "Update failed."
        return jsonify({"Status": "Fail", "Details": str(details)}), 400

    updated_details = result.get("Details") or {}
    _sync_person_fields_to_redis(session_values_json_redis, form_data, updated_details)
    if saved_image:
        session_values_json_redis.update({
            "aadhar_image": saved_image["html_path"],
            "primary_id_image": saved_image["html_path"],
        })
    redis_conn.set(user_id_key, json.dumps(session_values_json_redis))

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed known_person_helper_update | Execution time: {execution_time}ms", flush=True)

    return jsonify({
        "Status": "Success",
        "Details": {
            "person_name": updated_details.get("person_name"),
            "gender": updated_details.get("gender"),
            "mobile_number": updated_details.get("mobile_number"),
            "guardians_name": updated_details.get("guardians_name"),
            "address": updated_details.get("address"),
            "visiting_person_name": updated_details.get("visiting_person_name"),
            "primary_id_image": saved_image["html_path"] if saved_image else session_values_json_redis.get("primary_id_image"),
        },
        "message": "Visitor details updated successfully.",
    })

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting known_person_helper_post", flush=True)

    user_id_key = str(jwt_details.get('logged_in_user_id'))
    raw_session = redis_conn.get(user_id_key)
    if raw_session is None:
        return redirect(url_for('home'))
    session_values_json_redis = json.loads(raw_session)
    session_values_json_redis.update({"ticket_status": "trip_registration", "cancel_to": "known_person"})
    redis_conn.set(user_id_key, json.dumps(session_values_json_redis))
    print("redis in known_person when user says Continue on the known person page: ", session_values_json_redis)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed known_person_helper_post | Execution time: {execution_time}ms", flush=True)

    return redirect(url_for('trip_registration'))
