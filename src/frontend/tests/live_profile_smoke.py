"""Non-destructive smoke checks intended to run inside the web container."""

import json
import uuid

from flask_jwt_extended import create_access_token

from finalfrsproject import app, redisCommands


SAFE_GET_ROUTES = (
    "/home",
    "/aadhar_lookup",
    "/recognize_person",
    "/manual_face_verification",
    "/reregister_face",
    "/unknown_person",
    "/enroll_blacklisted_person",
    "/blacklisted_persons_list",
    "/report_home",
    "/person_lookup",
    "/recognize_vehicle",
    "/known_vehicle",
    "/trip_registration",
    "/make_trip_summary",
    "/get_unfinished_trips",
    "/vehicle_report",
    "/person_report",
    "/trip_report",
)


def main():
    audit_id = f"profile-smoke-{uuid.uuid4()}"
    identity = {
        "logged_in_user_id": audit_id,
        "logged_in_user_name": "profile-smoke",
        "logged_in_user_type": "audit",
    }
    session_data = {
        "ticket_status": "home",
        "message": "",
        "traveler_type": app.config["VISITOR_CATEGORIES"][0],
        "id_type": app.config["ID_LOOKUP_CATEGORIES"][0],
        "primary_id_type": app.config["ID_LOOKUP_CATEGORIES"][0],
        "primary_id_number": "AUDIT-ONLY",
        "person_details": "Not Available",
        "trip_and_traveler_details": [],
    }

    try:
        with app.app_context():
            token = create_access_token(identity=identity)
        client = app.test_client()
        client.set_cookie("access_token_cookie", token)

        failures = []
        for path in SAFE_GET_ROUTES:
            # `/home` intentionally deletes the current workflow. Seed a fresh,
            # isolated workflow before every independent route check.
            redisCommands.redis_conn.set(audit_id, json.dumps(session_data), ex=120)
            response = client.get(path, follow_redirects=False)
            print(path, response.status_code, response.headers.get("Location", ""))
            if response.status_code >= 500:
                failures.append((path, response.status_code))
        if failures:
            raise SystemExit(f"Smoke failures: {failures}")
    finally:
        redisCommands.redis_conn.delete(audit_id)


if __name__ == "__main__":
    main()
