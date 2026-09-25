import json
from flask import render_template
from datetime import datetime, time as dt_time
from finalfrsproject import app, sqlCommands
from flask_babel import _
import time

def _build_too_many_records_response(user_name, user_type, start_date, end_date, row_count, max_rows):
    return {
        'vehicle_report_list': [],
        'start_date': start_date,
        'end_date': end_date,
        'message': _('Too many records found. Please select a smaller date range.'),
        'alert_title': _('Too many records found'),
        'alert_message': _(
            f'The selected date range contains {row_count} vehicle records. '
            f'Please select a smaller date range. Maximum allowed records: {max_rows}.'
        ),
        'alert_type': 'warning',
        'logged_in_user': user_name,
        'logged_in_user_type': user_type,
        'page_title': 'Vehicle Report'
    }

def get_handler(jwt_details, redis_conn):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting vehicle_report_helper_get", flush=True)

    user_name = jwt_details.get("logged_in_user_name")
    user_type = jwt_details.get("logged_in_user_type")
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))

    try:
        session_values_json_redis.update({"ticket_status":"vehicle_report"})
        start_date = datetime.combine(datetime.now(), dt_time.min)
        #print(start_date) # 2023-02-10 00:00:00
        end_date = datetime.combine(datetime.now(), dt_time.max)
        #print(end_date) # 2023-02-10 00:00:00
        count_result = sqlCommands.count_all_vehicles_from_anpr_by_date(start_date, end_date)
        if not count_result or count_result.get('Status') == "Fail":
            print("count vehicle report failed", flush=True)
            send_to_html_json = {
                'message': "An unexpected error occurred while generating the report. Please try again.",
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': "Error"
            }
            session_values_json_redis.update({"message":"An unexpected error occurred while generating the vehicle report. Please try again."})
            session_values_json_redis.update({"ticket_status":"report_home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            return render_template('report_home.html', details=send_to_html_json)
        else:
            row_count = count_result.get("Details", 0)
            max_rows = app.config["VEHICLE_REPORT_MAX_VIEW_ROWS"]
            if row_count > max_rows:
                send_to_html_json = _build_too_many_records_response(
                    user_name, user_type, start_date, end_date, row_count, max_rows
                )
                session_values_json_redis.update({"ticket_status":"vehicle_report"})
                session_values_json_redis.update({"vehicle_report": []})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed vehicle_report_helper_get | Execution time: {execution_time}ms",
                      flush=True)

                return render_template('vehicle_report.html', details=send_to_html_json)

        result = sqlCommands.get_all_vehicles_from_anpr_by_date(start_date, end_date)
        #result = sqlCommands.get_vehicle_details_from_vehicles_by_date(start_date, end_date)
        print("********************************Vehicle Report: ", result)
        if not result or result.get('Status') == "Fail":
            print("generate vehicle report failed")
            send_to_html_json = {
                'message': "An unexpected error occurred while generating the report. Please try again.",
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': "Error"
            }
            session_values_json_redis.update({"message":"An unexpected error occurred while generating the vehicle report. Please try again."})
            session_values_json_redis.update({"ticket_status":"report_home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in vehicle report on generate report fail: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed vehicle_report_helper_get | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('report_home.html', details=send_to_html_json)
            #return redirect(url_for('report_home'))
        else:
            vehicle_list = result.get("Details")
            #print("vehicle_list : ", vehicle_list, flush=True)
            send_to_html_json = {
                'vehicle_report_list': vehicle_list,
                'start_date': start_date,
                'end_date': end_date,
                'message': _('Following records were found for the selected dates. Please try again with different dates.'),
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': 'Vehicle Report'
            }
            session_values_json_redis.update({"ticket_status":"vehicle_report"})
            session_values_json_redis.update({"vehicle_report": vehicle_list})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            # print('redis in person report on generate report success: ', session_values_json_redis)
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed vehicle_report_helper_get | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('vehicle_report.html', details=send_to_html_json)

    except Exception as e:
        print("Error in vehicle report helper: ", str(e), flush=True)
        send_to_html_json = {
            'message': "An unexpected error occurred while generating the report. Please try again.",
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': "Error"
        }
        session_values_json_redis.update(
            {"message": "An unexpected error occurred while generating the vehicle report. Please try again."})
        session_values_json_redis.update({"ticket_status": "report_home"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        print('redis in vehicle report on generate report fail: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed vehicle_report_helper_get | Execution time: {execution_time}ms",
              flush=True)

        return render_template('report_home.html', details=send_to_html_json)


def post_handler(jwt_details, redis_conn, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting vehicle_report_helper_post", flush=True)

    user_name = jwt_details.get("logged_in_user_name")
    user_type = jwt_details.get("logged_in_user_type")
    start_date = None
    end_date = None
    session_values_json_redis = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    try:
        if form:
            print("form : ", form)
            if form.get('start_date'):
                start_date = form.get('start_date')
                print("form start date: ", start_date)
            if form.get('end_date'):
                end_date = form.get('end_date')
                print("form end date: ", end_date)

        count_result = sqlCommands.count_all_vehicles_from_anpr_by_date(start_date, end_date)
        if not count_result or count_result.get('Status') == "Fail":
            print("count vehicle report failed", flush=True)
            send_to_html_json = {
                'message': "An unexpected error occurred while generating the report. Please try again.",
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': "Error"
            }
            session_values_json_redis.update({"message":"An unexpected error occurred while generating the vehicle report. Please try again."})
            session_values_json_redis.update({"ticket_status":"report_home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            return render_template('report_home.html', details=send_to_html_json)
        else:
            row_count = count_result.get("Details", 0)
            max_rows = app.config["VEHICLE_REPORT_MAX_VIEW_ROWS"]
            if row_count > max_rows:
                send_to_html_json = _build_too_many_records_response(
                    user_name, user_type, start_date, end_date, row_count, max_rows
                )
                session_values_json_redis.update({"ticket_status":"vehicle_report"})
                session_values_json_redis.update({"vehicle_report": []})
                redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))

                end_time = time.time()
                execution_time = round((end_time - start_time) * 1000, 2)
                end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                print(f"[{end_timestamp}] Completed vehicle_report_helper_post | Execution time: {execution_time}ms",
                      flush=True)

                return render_template('vehicle_report.html', details=send_to_html_json)

        result = sqlCommands.get_all_vehicles_from_anpr_by_date(start_date, end_date)
        #result = sqlCommands.get_vehicle_details_from_vehicles_by_date(start_date, end_date)
        #print("********************************: ", result)
        if not result or result.get('Status') == "Fail":
            print("generate vehicle report failed")
            send_to_html_json = {
                'message': "An unexpected error occurred while generating the report. Please try again.",
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': "Error"
            }
            session_values_json_redis.update({"message":"An unexpected error occurred while generating the person report. Please try again."})
            session_values_json_redis.update({"ticket_status":"report_home"})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            print('redis in person report on generate report fail: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed vehicle_report_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('report_home.html', details=send_to_html_json)
        else:
            vehicle_list = result.get("Details")
            send_to_html_json = {
                'vehicle_report_list': vehicle_list,
                'start_date': start_date,
                'end_date': end_date,
                'message': _('Following records were found for the selected dates. Please try again with different dates.'),
                'logged_in_user': user_name,
                'logged_in_user_type': user_type,
                'page_title': 'Vehicle Report'
            }
            session_values_json_redis.update({"ticket_status":"vehicle_report"})
            session_values_json_redis.update({"vehicle_report": vehicle_list})
            redis_conn.set(jwt_details.get('logged_in_user_id'),json.dumps(session_values_json_redis))
            # print('redis in person report on generate report success: ', session_values_json_redis)

            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed vehicle_report_helper_post | Execution time: {execution_time}ms",
                  flush=True)

            return render_template('vehicle_report.html', details=send_to_html_json)

    except Exception as e:
        print("Error in vehicle report helper: ", str(e), flush=True)
        send_to_html_json = {
            'message': "An unexpected error occurred while generating the vehicle report. Please try again..",
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': "Error"
        }
        session_values_json_redis.update(
            {"message": "An unexpected error occurred while generating the vehicle report. Please try again."})
        session_values_json_redis.update({"ticket_status": "report_home"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values_json_redis))
        print('redis in vehicle report on generate report fail: ', session_values_json_redis)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed vehicle_report_helper_post | Execution time: {execution_time}ms",
              flush=True)

        return render_template('report_home.html', details=send_to_html_json)
