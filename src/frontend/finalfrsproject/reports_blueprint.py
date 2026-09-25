from finalfrsproject import app, jwt
from flask_jwt_extended import get_jwt_identity, get_jwt, jwt_required
from flask import render_template, jsonify, Blueprint

reports_blueprint = Blueprint('reports_blueprint',__name__)


'''
#@app.route('/reports', methods=['GET','POST'])
@jwt_required()
def reports():
    print("In reports: ", request.method)
    jwt_details=get_jwt_identity()
    print("token: ", jwt_details)
    if request.method == 'POST':
        send_to_html_json = {
            'logged_in_user':  jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': 'Please click on a report from the list below.'
        }
        return render_template('report.html', details=send_to_html_json)    

    else: 
        send_to_html_json = {
            'logged_in_user':  jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': 'Please click on a report from the list below.',
            'page_title': 'Report Home'
        }
        return render_template('report_home.html', details=send_to_html_json)    
'''
@reports_blueprint.route("/report_home", methods=['GET','POST'])
#app.route("/report_home", methods=['GET','POST'])
@jwt_required()
def report_home():
    print("In report_home: ", request.method)
    jwt_details=get_jwt_identity()
    print("token: ", jwt_details)
    
    if request.method == 'POST':
        if request.form:
            form = request.form
            #print("calling vehicle_report.html")
            #return render_template('vehicle_report.html', details=send_to_html_json)
            print('form: ', form)    
            if form.get('vehicle_report'):
                return redirect(url_for('vehicle_report'))
            
            elif form.get('person_report'):
                return redirect(url_for('person_report')) #need to make a new route for this

            elif form.get('trip_report'):
                return redirect(url_for('trip_report')) #need to make a new route for this
        
        
    #GET
    else:
        send_to_html_json = {
            'logged_in_user':  jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'message': 'Please click on a report from the list below.',
            'page_title': 'Report Home'
        }
        return render_template('report_home.html', details=send_to_html_json)

@reports.route("/vehicle_report", methods=['GET','POST'])
#@app.route("/vehicle_report", methods=['GET','POST'])
@jwt_required()
def vehicle_report():
    print("In vehicle_report: ", request.method)
    jwt_details=get_jwt_identity()
    print("token: ", jwt_details)
    start_date = None
    end_date = None
    if request.method == 'POST':
        if request.form:
            form = request.form
            print("form : ", form)
            if form.get('start_date'):
                start_date = form.get('start_date')
                print("form start date: ", start_date)
            if form.get('end_date'):
                end_date = form.get('end_date')
                print("form end date: ", end_date)

        result = sqlCommands.get_vehicle_details_from_vehicles_by_date(start_date, end_date)
        if not result or result.get('Status') == 'Fail':
            print("fail")
            return redirect(url_for('get_unfinished_trips'))
        else:
            vehicle_report_list = []
            result = result.get('Details')
            print("result: ", result)
            print("type: ", type(result))

            if len(result) > 0:

                for vehicle in result:
                    vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(vehicle[9])])
                    entry_time = vehicle[5].strftime('%d-%m-%Y %H:%M:%S')
                    #registration_date = vehicle[7].strftime('%d-%m-%Y')
                    #expiry_date = vehicle[8].strftime('%d-%m-%Y')
                    
                    vehicle_report_list.append({
                        'vehicle_driver': vehicle[0],
                        'vehicle_plate_number': vehicle[1],
                        'vehicle_make': vehicle[2],
                        'vehicle_model': vehicle[3],
                        'vehicle_color': vehicle[4],
                        'entry_time': entry_time,
                        'vehicle_owner': vehicle[6],
                        'vehicle_registration_number': vehicle[9],
                        #'vehicle_expiry_date': expiry_date,
                        'vehicle_image': vehicle_image
                    })
                send_to_html_json = {
                    'vehicle_report_list': vehicle_report_list,
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'No records found for the selected dates. Please try again with different dates.',
                    'logged_in_user': jwt_details.get("logged_in_user_name"),
                    'logged_in_user_type': jwt_details.get("logged_in_user_type"),
                    'page_title': 'Vehicle Report'
                }

            
            else:
                print("No records found")
                vehicle_report_list.append({
                    'vehicle_driver': 'No records found',
                    'vehicle_plate_number': 'No records found',
                    'vehicle_make': 'No records found',
                    'vehicle_model': 'No records found',
                    'vehicle_color': 'No records found',
                    'entry_time': 'No records found',
                    'vehicle_owner': 'No records found',
                    #'vehicle_registration_date': 'No records found',
                    #'vehicle_expiry_date': 'No records found',
                    'vehicle_image': ''
                })

                send_to_html_json = {
                    'vehicle_report_list': vehicle_report_list,
                    'start_date': start_date,
                    'end_date': end_date,
                    'message': 'No records found for the selected dates. Please try again with different dates.',
                    'logged_in_user': jwt_details.get("logged_in_user_name"),
                    'logged_in_user_type': jwt_details.get("logged_in_user_type"),
                    'page_title': 'Vehicle Report'
                }
            print("calling vehicle_report.html")
            return render_template('vehicle_report.html', details=send_to_html_json)


        
    #GET
    else:
        queried_vehicles = []
        #for vehicle in result.get('Details'):
        queried_vehicles.append({
            'vehicle_plate_number': "vehicle",
            'vehicle_driver': "vehicle",
            'vehicle_entry_time': "vehicle",
            'vehicle_owner' : "vehicle",
            #'vehicle_registration_date': "vehicle",
            'vehicle_registration_number': "vehicle",
            #'vehicle_expiry_date': "vehicle"
        })

        send_to_html_json = {
            'queried_vehicles': queried_vehicles,
            'message': 'Please change the dates from the calendar and presss submit.',
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': 'Vehicle Report'
        }

        return render_template('vehicle_report.html', details=send_to_html_json)

@reports.route("/person_report", methods=['GET','POST'])
#@app.route("/person_report", methods=['GET','POST'])
@jwt_required()
def person_report():
    print("In person report: ", request.method)
    jwt_details=get_jwt_identity()
    print("token: ", jwt_details)
    
    if request.method == 'POST':
        print("calling vehicle_report.html")
        return render_template('vehicle_report.html', details=send_to_html_json)

        
    #GET
    else:
        queried_vehicles = []
        for vehicle in result.get('Details'):
            queried_vehicles.append({
                'vehicle_plate_number': "vehicle",
                'vehicle_driver': "vehicle",
                'vehicle_entry_time': "vehicle",
                'vehicle_owner' : "vehicle",
                #'vehicle_registration_date': "vehicle",
                'vehicle_registration_number': "vehicle",
                #'vehicle_expiry_date': "vehicle"
            })

        send_to_html_json = {
            'queried_vehicles': queried_vehicles,
            'message': 'Please change the dates from the calendar and presss submit.',
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': 'Person Report'
        }

        return render_template('vehicle_report.html', details=send_to_html_json)

@reports.route("/trip_report", methods=['GET','POST'])
#@app.route("/trip_report", methods=['GET','POST'])
@jwt_required()
def trip_report():
    print("In trip report: ", request.method)
    jwt_details=get_jwt_identity()
    print("token: ", jwt_details)
    
    if request.method == 'POST':
        print("calling vehicle_report.html")
        return render_template('vehicle_report.html', details=send_to_html_json)

        
    #GET
    else:
        queried_vehicles = []
        for vehicle in result.get('Details'):
            queried_vehicles.append({
                'vehicle_plate_number': "vehicle",
                'vehicle_driver': "vehicle",
                'vehicle_entry_time': "vehicle",
                'vehicle_owner' : "vehicle",
                #'vehicle_registration_date': "vehicle",
                'vehicle_registration_number': "vehicle",
                #'vehicle_expiry_date': "vehicle"
            })

        send_to_html_json = {
            'queried_vehicles': queried_vehicles,
            'message': 'Please change the dates from the calendar and presss submit.',
            'logged_in_user': jwt_details.get("logged_in_user_name"),
            'logged_in_user_type': jwt_details.get("logged_in_user_type"),
            'page_title': 'Trip Report'
        }

        return render_template('vehicle_report.html', details=send_to_html_json)
