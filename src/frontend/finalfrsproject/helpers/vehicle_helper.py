import os
from flask import render_template, redirect
from datetime import datetime
from finalfrsproject import sqlCommands, app
from flask_babel import _

def get_handler(jwt_details, request, vehicle_id):
    result = sqlCommands.get_vehicle_details_from_anpr_by_id(vehicle_id)
    print("vehicle_details: ", result)

    if not result or result.get('Status') == "Fail":        
        return redirect(request.url)
    
    vehicle_details = result.get("Details")
    #print(type(vehicle_details))

    timestamp_str = vehicle_details.get('timestamp')
    timestamp_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f%z')
    formatted_timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
    print(os.path.basename(vehicle_details.get('file')))
    print(app.config["VEHICLE_IMAGES"])
    formatted_vehicles = []
    formatted_vehicles.append({
        "id": vehicle_details.get('id'),
        'image_url': os.path.sep.join([app.config["SCREENSHOTS_FOLDER"],os.path.basename(vehicle_details.get('file'))]),
        'plate_number': vehicle_details.get('plate'),
        'timestamp': formatted_timestamp
    })

    send_to_html_json = {
        'unregistered_vehicles': formatted_vehicles,
        'logged_in_user':  jwt_details.get("logged_in_user_name"),
        'logged_in_user_type': jwt_details.get("logged_in_user_type"),
        'message': _('Please identify the vehicle from the list below.'),
        'page_title' : _('Unregistered Vehicle')
    }
    return render_template('recognize_vehicle.html', details=send_to_html_json) 
