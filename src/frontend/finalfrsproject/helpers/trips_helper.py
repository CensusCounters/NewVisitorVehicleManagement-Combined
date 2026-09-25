import os
from flask import render_template, redirect, url_for
from finalfrsproject import sqlCommands, app
from flask_babel import _

def get_handler(jwt_details, trip_id):
    result = sqlCommands.get_unfinished_trips_for_autocomplete(trip_id)
    if not result or result.get('Status') == 'Fail':
        print("fail")
        return redirect(url_for('get_unfinished_trips'))

    result = result.get("Details")
    print("result in get trips: ", result, flush=True)
    if len(result) > 0:
        print('rows returned: ', len(result))
        formatted_trips = []
        for trip in result:
            entry_time = trip[5].strftime('%d %b, %Y %I:%M:%S %p')
            vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(trip[13].rstrip('/'))])
            if trip[6] == False:
                is_vehicle_in_the_base = 'Yes'
            formatted_trips.append({
                "trip_id": trip[0],
                "driver_trip_id": trip[1],
                "person_name": trip[2],
                'traveler_type': trip[3],
                'vehicle_plate_number': trip[4],
                'entry_time': entry_time, #trip[5],
                'trip_status': is_vehicle_in_the_base,#trip[6],
                'coming_from': trip[7],
                'going_to': trip[8],
                'male_passengers': trip[9],
                'female_passengers': trip[10],
                'child_passengers': trip[11],
                'person_image': trip[12],
                'vehicle_image': vehicle_image #trip[13]
            })
        send_to_html_json = {
            'incomplete_trips': formatted_trips,
            'logged_in_user':  jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': _('Please select a trip from the list below. It will be closed with the current time.'),
            'page_title': _('End Trip')
        }
        print("detials in get_trip_details_by_id: ", send_to_html_json)
        return render_template('unfinished_trips.html', details=send_to_html_json)  
