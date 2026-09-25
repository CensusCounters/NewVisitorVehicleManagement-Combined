import json
from flask import render_template, redirect, url_for
from flask_babel import _

def get_handler(jwt_details, redis_conn):
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    message = session_values_json_redis.get('message')
    session_values_json_redis.update({"ticket_status":"stop_processing"})
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

    send_to_html_json = {
        'logged_in_user': jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': message,
        'page_title': _('Error')
    }
    return render_template('stop_processing.html', details=send_to_html_json)

def post_handler(jwt_details, redis_conn, form):
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    message = session_values_json_redis.get('message')
    session_values_json_redis.update({"ticket_status": "home"})
    redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis)) 
    print('redis in stop_processing before redirecting to home: ', session_values_json_redis)
    return redirect(url_for('home'))  
