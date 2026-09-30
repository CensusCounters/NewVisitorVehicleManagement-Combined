from finalfrsproject import app
import json
from flask import render_template, redirect, url_for, current_app
from finalfrsproject import redisCommands
from flask_babel import _
import traceback
import time
from datetime import datetime


def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting make_trip_summary_helper_get", flush=True)

    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    is_passenger_entry = session_values_json_redis.get('is_passenger_entry')
    #trip_and_traveler_details = []
    traveler_type = session_values_json_redis.get('traveler_type')
    print("traveler_type: ", traveler_type)

    if current_app.config["SITE_PROFILE_CONFIG"].make_trip_summary.passenger_registration_loop and traveler_type == 'Pedestrian':
        print('trip registration: Pedestrian')
        session_values_json_redis = redisCommands.create_json_for_trip_registration_post_from_redis_object(session_values_json_redis)
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    elif current_app.config["SITE_PROFILE_CONFIG"].make_trip_summary.passenger_registration_loop and traveler_type == 'Driver':
        print('trip registration: Driver')
        if session_values_json_redis.get("trip_and_traveler_details") is None:
            session_values_json_redis = redisCommands.create_json_for_trip_registration_post_from_redis_object(session_values_json_redis)
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
        male_passengers = int(session_values_json_redis.get('male_passengers'))
        parent_vehicle_number = session_values_json_redis.get("trip_and_traveler_details")[0].get("vehicle_number")
        print("parent_vehicle_number: ", parent_vehicle_number)
        if male_passengers is not None and male_passengers > 0:
            session_values_json_redis.update({"traveler_type": 'Male_Passenger'})
            session_values_json_redis.update({"parent_traveler_type": 'Driver'})
            session_values_json_redis.update({"parent_vehicle_number": parent_vehicle_number})
            session_values_json_redis.update({"number_of_male_passengers_to_add": male_passengers})
            session_values_json_redis.update({"message": "Please add " + str(male_passengers) + " male passenger(s) to complete registration"})
            session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
            print("redis object in make_trip_summary after new trip for Driver with male passengers: ", session_values_json_redis)
            if(is_passenger_entry == 'yes'):
                return redirect(url_for('aadhar_lookup'))

    elif current_app.config["SITE_PROFILE_CONFIG"].make_trip_summary.passenger_registration_loop and traveler_type == 'Male_Passenger':
        print('trip registration: Male Passenger', flush=True)
        if session_values_json_redis.get('person_id'):
            session_values_json_redis = redisCommands.create_json_for_trip_registration_post_from_redis_object(session_values_json_redis)
            print('trip registration: Male Passenger back from redisCommands', flush=True)
            
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            if session_values_json_redis.get('number_of_male_passengers_to_add'):
                number_of_male_passengers_to_add = int(session_values_json_redis.get('number_of_male_passengers_to_add')) - 1
                print(number_of_male_passengers_to_add)
                if number_of_male_passengers_to_add > 0:
                    session_values_json_redis.update({"traveler_type": 'Male_Passenger'})
                    session_values_json_redis.update({"number_of_male_passengers_to_add": number_of_male_passengers_to_add})
                    session_values_json_redis.update({"message": "Please add " + str(number_of_male_passengers_to_add) + " male passenger(s) to complete registration"})
                    session_values_json_redis.update({"ticket_status": "aadhar_lookup"})
                    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
                    print('redis object in make_trip_summary after adding one of the male passengers to the trip: ', session_values_json_redis)
                    return redirect(url_for('aadhar_lookup'))
        else:
            session_values_json_redis.update({"number_of_male_passengers_to_add": 0})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    else:
        print('trip registration: All Others')
        session_values_json_redis = redisCommands.create_json_for_trip_registration_post_from_redis_object(session_values_json_redis)
        redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    send_to_html_json = redisCommands.create_json_for_make_trip_summary_get_from_redis_object(jwt_details.get('logged_in_user_id'),jwt_details.get('logged_in_user_name'),jwt_details.get('logged_in_user_type'))
    print('redis in make_trip_summary before showing the trip summary page: ', session_values_json_redis, flush=True)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed make_trip_summary_helper_get | Execution time: {execution_time}ms", flush=True)

    return render_template('trip_summary.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting make_trip_summary_helper_get", flush=True)
    try:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        print("form: ", form)

        if form.get('end_trip_registration'):
            session_values_json_redis.update({"message": (_("Trip registration completed") if current_app.config["SITE_PROFILE_CONFIG"].make_trip_summary.translate_messages else "Trip registration completed")})
            session_values_json_redis.update({"ticket_status": "home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in make_trip_summary after trip has ended: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed make_trip_summary_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return redirect(url_for('home'))

    except Exception as e:
        # Log the error and return an error page or message
        stack_trace = traceback.format_exc()  # Get full stack trace
        print(f"Stack Trace:\n{stack_trace}", flush=True)
        print(f"[ERROR] post_handler failed: {e}")
        send_to_html_json = {
            'message': _("Error in the trip summary page. Please go to the home page."),
            'page_title': (_('Error') if current_app.config["SITE_PROFILE_CONFIG"].make_trip_summary.translate_messages else 'Error')
        }
        print("404 error details: ", send_to_html_json)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed make_trip_summary_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return render_template('401.html', details=send_to_html_json), 401
