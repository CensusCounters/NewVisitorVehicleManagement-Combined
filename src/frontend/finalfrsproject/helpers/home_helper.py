import json
from flask import render_template, redirect, url_for
from datetime import datetime
import uuid
from flask_babel import _
import time

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting home_helper_get", flush=True)

    #remove any objects in redis
    if redis_conn.get(jwt_details.get('logged_in_user_id')) is not None:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        session_values_json_redis.update({"ticket_status":"home"})
        redis_conn.delete(str(jwt_details.get('logged_in_user_id')))
        print('redis in home before get form: ', session_values_json_redis)

    else:
        print('no redis in home: ')
    send_to_html_json = {
        'logged_in_user': jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': _('Please click on one of the options below to continue. This will start a new thread.'),
        'page_title': _('Home Page')
    }
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed home_helper_get | Execution time: {execution_time}ms", flush=True)
    return render_template('home.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting home_helper_post", flush=True)

    ticket_id = uuid.uuid4()
    ticket_type = "Start_Trip"
    ticket_start_time = datetime.now() 

    if redis_conn.get(jwt_details.get('logged_in_user_id')) is not None:
        session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
        redis_conn.delete(str(jwt_details.get('logged_in_user_id')))

    #print('form: ', form)    
    if form.get('new_trip'):
        ticket_status = "aadhar_lookup"
        session_values_json_redis = {"ticket_id": str(ticket_id), "ticket_start_time": str(ticket_start_time), "ticket_status": ticket_status}
        redis_conn.set(str(jwt_details.get('logged_in_user_id')),json.dumps(session_values_json_redis)) 
        print('redis in home when new trip is selected: ', session_values_json_redis)
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed home_helper_post | Execution time: {execution_time}ms", flush=True)

        return redirect(url_for('aadhar_lookup'))

    elif form.get('end_trip'):
        ticket_status = "get_unfinished_trips"
        session_values_json_redis = {"ticket_id": str(ticket_id), "ticket_start_time": str(ticket_start_time), "ticket_status": ticket_status}
        print('redis in home when end trip is selected: ', session_values_json_redis)
        redis_conn.set(str(jwt_details.get('logged_in_user_id')),json.dumps(session_values_json_redis))
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed home_helper_post | Execution time: {execution_time}ms", flush=True)

        return redirect(url_for('get_unfinished_trips')) #need to make a new route for this

    elif form.get('view_reports'):
        ticket_status = "report_home"
        session_values_json_redis = {"ticket_id": str(ticket_id), "ticket_start_time": str(ticket_start_time),
                                     "ticket_status": ticket_status}
        print('redis in home when report is selected: ', session_values_json_redis)
        redis_conn.set(str(jwt_details.get('logged_in_user_id')),json.dumps(session_values_json_redis))
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed home_helper_post | Execution time: {execution_time}ms", flush=True)

        return redirect(url_for('report_home'))  # need to make a new route for this

    else:
        send_to_html_json = {
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': _('Error while processing your request. Please click on one of the options below to continue.'),
            'page_title': _('Home Page')
        }
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed home_helper_post | Execution time: {execution_time}ms", flush=True)

        return render_template('home.html', details=send_to_html_json)
