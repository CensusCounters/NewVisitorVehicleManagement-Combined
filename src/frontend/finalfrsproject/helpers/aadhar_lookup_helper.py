"""Single DRY Aadhaar / ID-lookup handler.

Previously this was a thin dispatcher delegating to three near-identical
per-profile sub-helpers (aadhar_lookup_kupwara/ganganagar/ncpass_helper). The
logic is now in ONE module with ONE get_handler and ONE post_handler.

Every per-profile difference is configured centrally in __init__.py as the
"aadhaar_lookup" block of each SITE_PROFILES entry (kupwara, ncpass, ganganagar
and tangdhar are all explicit). At runtime the active profile's differences are
exposed via app.config["AADHAAR_LOOKUP_PROFILE"] and read through _cfg().
"""

import json
import time
from datetime import datetime

from flask import render_template, redirect, url_for
from flask_babel import _

from finalfrsproject import routeMethods, redisCommands, app


# ---------------------------------------------------------------------------
# Per-profile differences live in __init__.py (SITE_PROFILES[<profile>]["aadhaar_lookup"])
# and are exposed as app.config["AADHAAR_LOOKUP_PROFILE"]. No handler logic is duplicated.
# ---------------------------------------------------------------------------

_DEFAULT_MESSAGES = {
    "id_type": "Please select the ID type and the ID number to verify identity.",
    "visitor_type": "Please select the Visitor type and the ID number to verify identity.",
}


def _cfg():
    return app.config["AADHAAR_LOOKUP_PROFILE"]


def _ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _ids_for(method, id_number):
    ids = {
        "pass_number": "Not Available",
        "aadhar_number": "Not Available",
        "drivers_license": "Not Available",
        "other_id_number": "Not Available",
    }
    if method == "aadhar":
        ids["aadhar_number"] = id_number
    elif method == "dl":
        ids["drivers_license"] = id_number
    elif method == "pass":
        ids["pass_number"] = id_number
    elif method == "other":
        ids["other_id_number"] = id_number
    return ids


def _do_lookup(traveler_type, id_type, id_number, session_values, cfg):
    """Return (result, ids_dict, resolved_id_type) for the active workflow."""
    if cfg["lookup_strategy"] == "aadhar_only":
        result = routeMethods.get_known_person_details_with_aadhar(id_number, session_values)
        return result, _ids_for("aadhar", id_number), id_type

    if traveler_type == "TEACHER":
        result = routeMethods.get_known_person_details_with_pass(id_number, session_values)
        return result, _ids_for("pass", id_number), "PASS"

    if traveler_type == "PASS HOLDER":
        if id_type == "AADHAR":
            result = routeMethods.get_known_person_details_with_aadhar(id_number, session_values)
            method = "aadhar"
        elif id_type == "DRIVERS LICENSE":
            result = routeMethods.get_known_person_details_with_drivers_license(id_number, session_values)
            method = "dl"
        else:
            result = routeMethods.get_known_person_details_with_pass(id_number, session_values)
            method = "pass"
        return result, _ids_for(method, id_number), id_type

    # every other traveler type
    if id_type == "AADHAR":
        result = routeMethods.get_known_person_details_with_aadhar(id_number, session_values)
        method = "aadhar"
    elif id_type == "DRIVERS LICENSE":
        result = routeMethods.get_known_person_details_with_drivers_license(id_number, session_values)
        method = "dl"
    else:
        result = routeMethods.get_known_person_details_with_other_id(id_number, session_values)
        method = "other"
    return result, _ids_for(method, id_number), id_type


def _resolve_primary_image(session_details, traveler_type, id_type, cfg):
    if cfg["pass_holder_teacher_uses_pass_image"] and traveler_type in ("PASS HOLDER", "TEACHER"):
        return session_details.get("pass_image_location")
    if id_type == "AADHAR":
        return session_details.get("aadhar_image")
    if id_type == "DRIVERS LICENSE":
        return session_details.get("drivers_license_image")
    if id_type == "PASS":
        return session_details.get("pass_image_location")
    return session_details.get("other_id_image")


def _write_session(session, ids, id_type, id_number, traveler_type, message, ticket_status, person_details, primary_id_image=None):
    session.update({"pass_number": ids["pass_number"]})
    session.update({"aadhar_number": ids["aadhar_number"]})
    session.update({"drivers_license": ids["drivers_license"]})
    session.update({"other_id_number": ids["other_id_number"]})
    session.update({"id_type": id_type})
    session.update({"primary_id_type": id_type})
    session.update({"primary_id_number": id_number})
    session.update({"primary_id_image": primary_id_image})
    session.update({"traveler_type": traveler_type})
    session.update({"message": message})
    session.update({"ticket_status": ticket_status})
    session.update({"person_details": person_details})


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    print(f"[{_ts()}] Starting aadhar_lookup_get", flush=True)
    cfg = _cfg()
    template = "aadhar_lookup.html"
    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get("logged_in_user_id")))
        session_values_json_redis = redisCommands.clean_redis_object_before_aadhar_lookup(session_values_json_redis)
        print("redis in aadhar_lookup before look up: ", session_values_json_redis, flush=True)

        if cfg["support_male_passenger_skip"] and session_values_json_redis.get("number_of_male_passengers_to_add"):
            number_of_male_passengers_to_add = int(session_values_json_redis.get("number_of_male_passengers_to_add"))
            if number_of_male_passengers_to_add > 0:
                if session_values_json_redis.get("message") is not None and session_values_json_redis.get("ticket_status"):
                    message = session_values_json_redis.get("message")
                else:
                    message = _("Add member passenger details. Please enter the aadhar number")
                send_to_html_json = {
                    "message": message,
                    "logged_in_user": jwt_details.get("logged_in_user_name"),
                    "logged_in_user_type": jwt_details.get("logged_in_user_type"),
                    "number_of_male_passengers_to_add": number_of_male_passengers_to_add,
                    "page_title": _("ID Lookup"),
                }
                session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
                return render_template(template, details=send_to_html_json,
                                       custom_dropdown=cfg["custom_dropdown"],
                                       show_id_type_first=cfg["show_id_type_first"],
                                       show_id_number_only=cfg["show_id_number_only"])

        if session_values_json_redis.get("message"):
            message = session_values_json_redis.get("message")
        else:
            message = _(_DEFAULT_MESSAGES[cfg["default_message_key"]])
        session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
        redis_conn.set(jwt_details.get("logged_in_user_id"), json.dumps(session_values_json_redis))
        send_to_html_json = {
            "logged_in_user": jwt_details.get("logged_in_user_name"),
            "logged_in_user_type": jwt_details.get("logged_in_user_type"),
            "message": message,
            "id_categories": app.config["ID_LOOKUP_CATEGORIES"],
            "visitor_categories": app.config["VISITOR_CATEGORIES"],
            "page_title": _("ID Lookup"),
        }
        if cfg["support_male_passenger_skip"]:
            send_to_html_json["number_of_male_passengers_to_add"] = 0
        print(f"[{_ts()}] Completed aadhar_lookup_get | Execution time: {round((time.time() - start_time) * 1000, 2)}ms", flush=True)
        return render_template(template, details=send_to_html_json,
                               custom_dropdown=cfg["custom_dropdown"],
                               show_id_type_first=cfg["show_id_type_first"],
                               show_id_number_only=cfg["show_id_number_only"])
    except Exception as e:
        print(f"Error in id look up: {str(e)} ")
        send_to_html_json = {"message": _("Error in ID look up. Please try again."), "page_title": _("Error")}
        return render_template("home.html", details=send_to_html_json)


def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    print(f"[{_ts()}] Starting aadhar_lookup_post", flush=True)
    try:
        cfg = _cfg()
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get("logged_in_user_id")))
        print("form: ", form, flush=True)
        traveler_type = form.get("traveler_type")
        id_number = form.get("id_number")
        id_type = form.get("id_type")
        if cfg["force_id_type"]:
            id_type = cfg["force_id_type"]
        print(f" traveler_type: {traveler_type}, id_type: {id_type}, id_number: {id_number}", flush=True)

        if cfg["require_input_validation"]:
            if not traveler_type or not id_number:
                session_values_json_redis.update({
                    "message": _("Please select a valid visitor type and Aadhar number."),
                    "ticket_status": "aadhar_lookup",
                })
                redis_conn.set(jwt_details.get("logged_in_user_id"), json.dumps(session_values_json_redis))
                return redirect(url_for("aadhar_lookup"))

        result, ids, id_type = _do_lookup(traveler_type, id_type, id_number, session_values_json_redis, cfg)

        if result.get("Status") == "Fail":
            print("ID Lookup failed due to a system issue. Please try again")
            session_values_json_redis.update({"message": _("The ID lookup failed due to a system issue. Please try again.")})
            session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
            redis_conn.set(jwt_details.get("logged_in_user_id"), json.dumps(session_values_json_redis))
            return redirect(url_for("aadhar_lookup"))

        if result.get("Details") == "No match found":
            print("ID look up did not match any records")
            _write_session(
                session_values_json_redis, ids, id_type, id_number, traveler_type,
                _("The ID Number entered - %(id_number)s - was not found in the system. Please register this person.") % {"id_number": id_number},
                "recognize_person", "Not Available",
            )
            redis_conn.set(jwt_details.get("logged_in_user_id"), json.dumps(session_values_json_redis))
            print(f"[{_ts()}] Completed aadhar_lookup_post | Execution time: {round((time.time() - start_time) * 1000, 2)}ms", flush=True)
            return redirect(url_for("recognize_person"))

        # success
        session_values_json_redis = result.get("Details")
        primary_id_image = _resolve_primary_image(session_values_json_redis, traveler_type, id_type, cfg)
        _write_session(
            session_values_json_redis, ids, id_type, id_number, traveler_type,
            _("The ID Number entered - %(id_number)s - was found in the system. Please do a face recognition now.") % {"id_number": id_number},
            "recognize_person", "Available", primary_id_image=primary_id_image,
        )
        redis_conn.set(jwt_details.get("logged_in_user_id"), json.dumps(session_values_json_redis))
        print(f"[{_ts()}] Completed aadhar_lookup_post | Execution time: {round((time.time() - start_time) * 1000, 2)}ms", flush=True)
        return redirect(url_for("recognize_person"))
    except Exception as e:
        print(f"Error in id look up: {str(e)} ")
        send_to_html_json = {"message": _("Error in ID look up. Please try again."), "page_title": _("Error")}
        return render_template(cfg["exception_template_post"], details=send_to_html_json), 500
