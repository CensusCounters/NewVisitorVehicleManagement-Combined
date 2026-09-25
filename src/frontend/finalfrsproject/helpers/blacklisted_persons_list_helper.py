import os
import time
from datetime import datetime
from flask import render_template
from flask_babel import _
from finalfrsproject import app

BLACKLIST_LIST_COLUMNS = ("name", "id")


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting blacklisted_persons_list_get", flush=True)

    try:
        blacklist_folder = app.config["BLACKLISTED_PERSONS"]
        blacklist_static_path = app.config["BLACKLISTED_PERSON_PATH_FOR_HTML"]

        persons = []

        if os.path.exists(blacklist_folder):
            for file in sorted(os.listdir(blacklist_folder), key=str.lower):
                if file.lower().endswith((".jpg", ".jpeg", ".png")):
                    parts = os.path.splitext(file)[0].split("_")
                    name = " ".join(parts[1:-1]).replace("-", " ") if len(parts) > 2 else ""
                    person_id = parts[-1] if len(parts) > 2 else ""
                    persons.append({
                        "filename": file,
                        "image_url": f"{blacklist_static_path}/{file}",
                        "name": name,
                        "id": person_id,
                    })

        send_to_html_json = {
            "message": "Blacklisted Persons",
            "logged_in_user": jwt_details.get("logged_in_user_name"),
            "logged_in_user_type": jwt_details.get("logged_in_user_type"),
            "page_title": _("Blacklisted Persons"),
            "persons": persons,
            "columns": BLACKLIST_LIST_COLUMNS,
        }

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed blacklisted_persons_list_get | Execution time: {execution_time}ms", flush=True)

        return render_template("blacklisted_persons_list.html", details=send_to_html_json)

    except Exception as e:
        print("Error in blacklisted_persons_list:", e, flush=True)

        send_to_html_json = {
            "message": "Error loading blacklisted persons.",
            "logged_in_user": jwt_details.get("logged_in_user_name"),
            "logged_in_user_type": jwt_details.get("logged_in_user_type"),
            "page_title": _("Blacklisted Persons"),
            "persons": [],
            "columns": BLACKLIST_LIST_COLUMNS,
        }

        return render_template("blacklisted_persons_list.html", details=send_to_html_json)
