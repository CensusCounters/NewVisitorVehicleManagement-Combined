import json
import traceback
from datetime import datetime, time as dt_time
from flask import render_template, current_app
from flask_babel import _
from finalfrsproject import app, sqlCommands


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

def _report_error(jwt_details, redis_conn, session_values, message, session_message):
    session_values.update({"message": session_message, "ticket_status": "report_home"})
    redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values))
    return render_template('report_home.html', details={
        'message': message,
        'logged_in_user': jwt_details.get('logged_in_user_name'),
        'logged_in_user_type': jwt_details.get('logged_in_user_type'),
        'page_title': 'Error',
    })


def _render_report(jwt_details, redis_conn, form=None, *, submitted=False):
    session_values = json.loads(redis_conn.get(jwt_details.get('logged_in_user_id')))
    user_name = jwt_details.get('logged_in_user_name')
    user_type = jwt_details.get('logged_in_user_type')
    error_message = "An unexpected error occurred while generating the report. Please try again."
    session_error = "An unexpected error occurred while generating the vehicle report. Please try again."
    try:
        if submitted:
            start_date = form.get('start_date') if form else None
            end_date = form.get('end_date') if form else None
            if current_app.config["SITE_PROFILE_CONFIG"].vehicle_report.load_initial_records:
                start_date = start_date or None
                end_date = end_date or None
        else:
            session_values.update({"ticket_status": "vehicle_report"})
            start_date = datetime.combine(datetime.now(), dt_time.min)
            end_date = datetime.combine(datetime.now(), dt_time.max)
        records = []
        message = _('Report for the selected dates.')
        if current_app.config["SITE_PROFILE_CONFIG"].vehicle_report.load_initial_records:
            count_result = sqlCommands.count_all_vehicles_from_anpr_by_date(start_date, end_date)
            if not count_result or count_result.get('Status') == 'Fail':
                return _report_error(jwt_details, redis_conn, session_values, error_message, session_error)
            row_count = count_result.get('Details', 0)
            max_rows = app.config['VEHICLE_REPORT_MAX_VIEW_ROWS']
            if row_count > max_rows:
                details = _build_too_many_records_response(
                    user_name, user_type, start_date, end_date, row_count, max_rows
                )
                session_values.update({"ticket_status": "vehicle_report", "vehicle_report": []})
                redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values))
                return render_template('vehicle_report.html', details=details)
            result = sqlCommands.get_all_vehicles_from_anpr_by_date(start_date, end_date)
            if not result or result.get('Status') == 'Fail':
                query_error = current_app.config["SITE_PROFILE_CONFIG"].vehicle_report.post_query_failure_session_message if submitted else session_error
                return _report_error(jwt_details, redis_conn, session_values, error_message, query_error)
            records = result.get('Details')
            message = _('Following records were found for the selected dates. Please try again with different dates.')
            session_values.update({"vehicle_report": records})
        details = {
            'vehicle_report_list': records,
            'start_date': start_date,
            'end_date': end_date,
            'message': message,
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title': 'Vehicle Report',
        }
        session_values.update({"ticket_status": "vehicle_report"})
        redis_conn.set(jwt_details.get('logged_in_user_id'), json.dumps(session_values))
        return render_template('vehicle_report.html', details=details)
    except Exception as error:
        print("Error in vehicle report helper: ", str(error), flush=True)
        if current_app.config["SITE_PROFILE_CONFIG"].vehicle_report.log_traceback:
            print(f"Stack Trace:\n{traceback.format_exc()}", flush=True)
        message = current_app.config["SITE_PROFILE_CONFIG"].vehicle_report.post_exception_message if submitted else error_message
        return _report_error(jwt_details, redis_conn, session_values, message, session_error)


def get_handler(jwt_details, redis_conn):
    return _render_report(jwt_details, redis_conn)


def post_handler(jwt_details, redis_conn, form):
    return _render_report(jwt_details, redis_conn, form, submitted=True)
