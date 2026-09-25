import json
import os
import re
from datetime import datetime

from flask import redirect, render_template, url_for
from flask_babel import _

from finalfrsproject import app
import time


def _sanitize_filename(value: str, max_length: int = 80) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "")
    value = value.strip("._")
    if not value:
        value = "unknown"
    return value[:max_length]


def _find_blacklist_image_html_path(blacklist_info):
    blacklist_folder = app.config["BLACKLISTED_PERSONS"]
    blacklist_static_path = app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"]

    if not os.path.isdir(blacklist_folder):
        return None

    files = [
        f for f in os.listdir(blacklist_folder)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    guid = str(blacklist_info.get("guid") or "").strip()
    aadhaar = str(blacklist_info.get("aadhaar") or "").strip()
    safe_name = _sanitize_filename(str(blacklist_info.get("name") or ""))

    if guid:
        for filename in files:
            if filename.startswith(f"{guid}_"):
                return f"{blacklist_static_path}/{filename}"

    if aadhaar:
        for filename in files:
            root, _ = os.path.splitext(filename)
            if root.endswith(f"_{aadhaar}"):
                return f"{blacklist_static_path}/{filename}"

    if safe_name:
        for filename in files:
            if f"_{safe_name}_" in filename:
                return f"{blacklist_static_path}/{filename}"

    return None


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting blacklist_alert_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    blacklist = session_values_json_redis.get("blacklist") or {}

    if not blacklist.get("blacklist_route"):
        return redirect(url_for('recognize_person'))

    blacklist_info = blacklist.get("blacklist_info") or {}
    todays_image = (
        session_values_json_redis.get('todays_image_html_path')
        or session_values_json_redis.get('person_image_html_path')
    )
    blacklist_image = _find_blacklist_image_html_path(blacklist_info)

    session_values_json_redis.update({"ticket_status": "blacklist_alert"})
    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

    send_to_html_json = {
        'logged_in_user': jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': _("Possible blacklist match detected. Please confirm if these faces are the same person."),
        'page_title': _("Blacklist Alert"),
        'todays_image': todays_image,
        'blacklist_image': blacklist_image,
        'blacklist_name': blacklist_info.get("name"),
        'blacklist_aadhaar': blacklist_info.get("aadhaar"),
        'blacklist_similarity': blacklist_info.get("similarity"),
    }

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed blacklist_alert_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('blacklist_alert.html', details=send_to_html_json)


def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting blacklist_alert_helper_post", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    if form.get('Yes'):
        session_values_json_redis.pop("blacklist_pending", None)
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

        send_to_html_json = {
            'message': _("Processing stopped due to a blacklist alert. Click Continue to proceed."),
            'page_title': _("Blacklist Alert")
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed blacklist_alert_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('401.html', details=send_to_html_json), 401

    resume_route = session_values_json_redis.get("blacklist_resume_route") or "unknown_person"
    if resume_route not in ["reregister_face", "unknown_person"]:
        resume_route = "unknown_person"

    session_values_json_redis.pop("blacklist", None)
    session_values_json_redis.pop("blacklist_pending", None)
    session_values_json_redis.pop("blacklist_resume_route", None)
    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed blacklist_alert_helper_post | Execution time: {execution_time}ms", flush=True)

    return redirect(url_for(resume_route))

