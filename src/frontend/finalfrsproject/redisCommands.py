import redis
import json
from finalfrsproject import app
from datetime import datetime, time
from flask_babel import _
from flask import url_for
#from pygame.examples.video import driver

# Connect to Redis
redis_conn = redis.from_url(app.config["REDIS_URL"])
# redis_conn = redis.StrictRedis(host='localhost', port=6379, db=0)
#print("redis_conn: ", redis_conn)


def _normalize_redis_value(value):
	"""Convert legacy Redis string sentinels into real empty values."""
	if value is None:
		return None
	normalized = str(value).strip()
	if not normalized or normalized.lower() in ("none", "null", "not available"):
		return None
	return normalized


def _resolve_primary_id_fields(session_values_json_redis):
	"""Resolve ID image/number for trip summary from explicit or legacy session keys."""
	primary_id_image = _normalize_redis_value(session_values_json_redis.get("primary_id_image"))
	primary_id_number = _normalize_redis_value(session_values_json_redis.get("primary_id_number"))

	if primary_id_image is None:
		for key in (
			"aadhar_image",
			"drivers_license_image",
			"other_id_image",
			"other_id_image_location",
			"pass_image_location",
			"pass_image",
		):
			candidate = _normalize_redis_value(session_values_json_redis.get(key))
			if candidate is not None:
				primary_id_image = candidate
				break

	if primary_id_number is None:
		for key in ("aadhar_number", "drivers_license", "other_id_number", "pass_number"):
			candidate = _normalize_redis_value(session_values_json_redis.get(key))
			if candidate is not None:
				primary_id_number = candidate
				break

	return primary_id_number, primary_id_image


def create_json_for_known_person_get_from_redis_object(user_id, user_name, user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	print("redis object in known person get: ", session_values_json_redis, flush=True)
	session_values_json_redis.update({'page_title': _('Known Person')})
	session_values_json_redis.update({'person_details': 'Available'})
	visitor_categories = app.config["VISITOR_CATEGORIES"]
	id_categories = app.config["ID_LOOKUP_CATEGORIES"]
	visit_purpose_categories = app.config["VISIT_PURPOSE_CATEGORIES"]

	send_to_html_json = {
        'details_entered_by': session_values_json_redis.get("details_entered_by"),
        'details_entered_on': session_values_json_redis.get("details_entered_on"),
        'person_name': session_values_json_redis.get("person_name"),
        'original_img' : session_values_json_redis.get("person_image"),
        'guardians_name': session_values_json_redis.get("guardians_name"),
        'address': session_values_json_redis.get("address"),
		'visiting_person_name': session_values_json_redis.get("visiting_person_name"),
		'mobile_number': session_values_json_redis.get("mobile_number"),
        'aadhar_number': session_values_json_redis.get("aadhar_number"),
        'aadhar_image': session_values_json_redis.get("aadhar_image"),
        'drivers_license': session_values_json_redis.get("drivers_license"),
        'drivers_license_image': session_values_json_redis.get("drivers_license_image"),
        'person_id': session_values_json_redis.get("person_id"),
        'person_image': session_values_json_redis.get("person_image"),
        'message': session_values_json_redis.get('message'),
		'gender': session_values_json_redis.get('gender'),
		'dob': session_values_json_redis.get('dob'),
		'traveler_type': session_values_json_redis.get('traveler_type'),
		'pass_number': session_values_json_redis.get('pass_number'),
		'other_id_number': session_values_json_redis.get('other_id_number'),
		'id_type': session_values_json_redis.get('id_type'),
		'primary_id_number': session_values_json_redis.get('primary_id_number'),
		'primary_id_type': session_values_json_redis.get('primary_id_type'),
		'primary_id_image': session_values_json_redis.get('primary_id_image'),
		'visitor_categories': visitor_categories,
		'id_categories': id_categories,
		'visit_purpose_categories': visit_purpose_categories,
		'known_person_schema': app.config["KNOWN_PERSON_SCHEMA"],
        #'message': 'Success! Visitor Information is in the database. Please continue.',
        'logged_in_user': user_name,
        'logged_in_user_type': user_type,
        'page_title': _('Known Visitor')
    }
	return send_to_html_json

def create_json_for_unknown_person_get_from_redis_object(user_id, user_name, user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	#print("redis object in unknown person get: ", session_values_json_redis)
	visitor_categories = app.config["VISITOR_CATEGORIES"]
	id_categories = app.config["ID_LOOKUP_CATEGORIES"]
	visit_purpose_categories = app.config["VISIT_PURPOSE_CATEGORIES"]
	session_values_json_redis.update({'page_title': _('Unknown Person')})
	send_to_html_json = {
		'img': session_values_json_redis.get('person_image_html_path'),
		'person_image_actual_path': session_values_json_redis.get('person_image_actual_path'),
		'enrollment_id': session_values_json_redis.get('enrollment_id'),
		'traveler_type': session_values_json_redis.get('traveler_type'),
		'message': session_values_json_redis.get('message'),
		'pass_number': session_values_json_redis.get('pass_number'),
		'aadhar_number': session_values_json_redis.get('aadhar_number'),
		'drivers_license': session_values_json_redis.get('drivers_license'),
		'other_id_number': session_values_json_redis.get('other_id_number'),
		'id_type': session_values_json_redis.get('id_type'),
		'primary_id_number': session_values_json_redis.get('primary_id_number'),
		'visitor_categories': visitor_categories,
		'id_categories': id_categories,
		'visit_purpose_categories': visit_purpose_categories,
		'unknown_person_page_fields': app.config["UNKNOWN_PERSON_PAGE_FIELDS"],
		'logged_in_user': user_name,
		'logged_in_user_type': user_type,
		'page_title': _("Unknown Person")
	}
	return send_to_html_json

def create_json_for_trip_registration_post_from_redis_object(session_values_json_redis):
	#session_values_json_redis = json.loads(redis_conn.get(user_id))
	print('session_values_json_redis before creating trip traveler details ', session_values_json_redis, flush=True)
	print('entry_time: ', session_values_json_redis.get("entry_time"))
	entry_time = ''
	other_passengers = total_passengers = 0
	if session_values_json_redis.get("entry_time"):
		entry_time = (datetime.strptime(session_values_json_redis.get("entry_time"),'%Y-%m-%dT%H:%M')).strftime('%d %b, %Y %I:%M:%S %p')

	if session_values_json_redis.get("female_passengers") is not None and session_values_json_redis.get("child_passengers") is not None :
		other_passengers = int(session_values_json_redis.get("female_passengers")) + int(session_values_json_redis.get("child_passengers"))
	else:
		other_passengers = 0
	if session_values_json_redis.get("female_passengers") is not None:
		total_passengers = other_passengers + int(session_values_json_redis.get("male_passengers"))
	else:
		total_passengers = other_passengers

	trip_and_traveler_details = []
	if session_values_json_redis.get("trip_and_traveler_details") is not None:
		trip_and_traveler_details = session_values_json_redis.get("trip_and_traveler_details")
		print('trip_and_traveler_details ', trip_and_traveler_details)


	#print("redis object in trip registration post: ", session_values_json_redis)
	primary_id_number, primary_id_image = _resolve_primary_id_fields(session_values_json_redis)
	send_to_html_json = {
        'person_id': session_values_json_redis.get("person_id"),
        'person_image': session_values_json_redis.get("person_image"),
		'vehicle_number': session_values_json_redis.get("vehicle_plate_number"),
		'vehicle_image': session_values_json_redis.get("vehicle_image"),
		'primary_id_number': primary_id_number,
		'primary_id_image': primary_id_image,
        'traveler_name': session_values_json_redis.get("person_name"),
        'traveler_type': session_values_json_redis.get("traveler_type"),
		'visiting_person_name': session_values_json_redis.get("visiting_person_name"),
        'coming_from': session_values_json_redis.get("coming_from"),
        'going_to' : session_values_json_redis.get("going_to"),
        'entry_time': entry_time,
		'expected_visit_duration': session_values_json_redis.get("expected_visit_duration"),
		'mobile_number': session_values_json_redis.get("mobile_number"),
        'male_passengers': session_values_json_redis.get("male_passengers"),
        'female_passengers': session_values_json_redis.get("female_passengers"),
        'child_passengers': session_values_json_redis.get("child_passengers"),
		'other_passengers': other_passengers,
		'total_passengers': total_passengers,
        'trip_reason': session_values_json_redis.get("trip_reason"),
        'trip_type': session_values_json_redis.get("trip_type"),
        'permit_image': session_values_json_redis.get("permit_img_file_path"),
		'token_number': session_values_json_redis.get("token_number")
    }
	trip_and_traveler_details.append(send_to_html_json)
	session_values_json_redis.update({"trip_and_traveler_details": trip_and_traveler_details})
	print("session_values_json_redis before clean up: ", session_values_json_redis)
	session_values_json_redis = clean_redis_object(session_values_json_redis)
	print("session_values_json_redis after clean up: ", session_values_json_redis)
	return session_values_json_redis
	#return send_to_html_json

def create_json_for_trip_registration_get_from_redis_object(user_id, user_name, user_type, entry_time):
	print(f"in create json for trip registration get ********** user_id: {user_id}, user_name: {user_name}, user_type: {user_type},"
		  f"entry_time: {entry_time}", flush=True)
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	print("redis object in trip registration get **********: ", session_values_json_redis, flush=True)
	print("redis object in trip registration get: ", session_values_json_redis.get('vehicle_plate_number'), flush=True)
	visitor_categories = app.config["VISITOR_CATEGORIES"]
	id_categories = app.config["ID_LOOKUP_CATEGORIES"]
	print("redis object in trip registration get************: ", session_values_json_redis, flush=True)
	send_to_html_json = {}
	try:
		person_id = person_name = person_image = traveler_type = None
		vehicle_plate_number = vehicle_make = vehicle_image = None
		vehicle_model = vehicle_color = vehicle_type = vehicle_category = None
		vehicle_registration_number = None
		primary_id_number = address = visiting_person_name = driver_id = None
		print("build send_to_html_json in trip reqistration get*************: ", flush=True)

		if session_values_json_redis.get('person_id'):
			person_id = session_values_json_redis.get('person_id')
		else:
			print(f'person_id not found')

		if session_values_json_redis.get('person_name'):
			person_name = session_values_json_redis.get('person_name')
		else:
			print(f'person name not found')

		if session_values_json_redis.get('person_image'):
			person_image = session_values_json_redis.get('person_image')
		else:
			print(f'person image not found')

		if session_values_json_redis.get('traveler_type'):
			traveler_type = session_values_json_redis.get('traveler_type')
		else:
			print(f'travleer type not found')

		if session_values_json_redis.get('vehicle_plate_number'):
			vehicle_plate_number = session_values_json_redis.get('vehicle_plate_number')
		else:
			print(f'vehicle_plate_number not found')

		if session_values_json_redis.get('vehicle_make'):
			vehicle_make = _normalize_redis_value(session_values_json_redis.get('vehicle_make'))
		else:
			print(f'vehicle_make not found')

		vehicle_model = _normalize_redis_value(session_values_json_redis.get('vehicle_model'))
		vehicle_color = _normalize_redis_value(session_values_json_redis.get('vehicle_color'))
		vehicle_type = _normalize_redis_value(session_values_json_redis.get('vehicle_type'))
		vehicle_category = _normalize_redis_value(session_values_json_redis.get('vehicle_category'))
		vehicle_registration_number = _normalize_redis_value(
			session_values_json_redis.get('vehicle_registration_number')
		)

		if session_values_json_redis.get('vehicle_image'):
			vehicle_image = session_values_json_redis.get('vehicle_image')
		else:
			print(f'vehicle_image not found')

		if session_values_json_redis.get('primary_id_number'):
			primary_id_number = session_values_json_redis.get('primary_id_number')
		else:
			print(f'primary_id_number not found')

		if session_values_json_redis.get('address'):
			address = session_values_json_redis.get('address')
		else:
			print(f' address not found')

		if session_values_json_redis.get('visiting_person_name'):
			visiting_person_name = session_values_json_redis.get('visiting_person_name')
		else:
			print(f'visiting_person_name not found')

		send_to_html_json = {
			'person_id': person_id,
			'person_name': person_name,
			'person_image': person_image,
			'traveler_type': traveler_type,
			'vehicle_plate_number': vehicle_plate_number,
			'vehicle_make': vehicle_make,
			'vehicle_model': vehicle_model,
			'vehicle_color': vehicle_color,
			'vehicle_type': vehicle_type,
			'vehicle_category': vehicle_category,
			'vehicle_registration_number': vehicle_registration_number,
			'vehicle_image': vehicle_image,
			'driver_trip_id': driver_id,
			'entry_time': entry_time,
			'message': _('Please select traveler type and enter trip details.'),
			'logged_in_user': user_name,
			'logged_in_user_type': user_type,
			'page_title': _('Add Trip'),
			"visitor_categories": visitor_categories,
			"id_categories": id_categories,
			'primary_id_number': primary_id_number,
			'address': address,
			'visiting_person_name': visiting_person_name,
			'cancel_url': url_for('home'),
		}
		#print("send_to_html_json in trip reqistration get*************: ", send_to_html_json, flush=True)
	except Exception as e:
		print("ERROR WHILE BUILDING JSON: ", str(e), flush=True)
	return send_to_html_json

def create_json_for_make_trip_summary_get_from_redis_object(user_id, user_name, user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	print("redis object in make trip summary get: ", session_values_json_redis, flush=True)
	send_to_html_json = {
	    'trip_and_traveler_details': session_values_json_redis.get("trip_and_traveler_details"),
	    'message': _('Trip added Successfully. Click Continue to return to the home page.'),
	    # 'message': session_values_json_redis.get("message"),
	    'logged_in_user': user_name,
	    'logged_in_user_type': user_type,
	    'page_title': _('Trip Summary')
	}	
	return send_to_html_json

def create_json_for_recognize_vehicle_get_from_redis_object(user_id, user_name, user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	#print("redis object in recognize vehicle get: ", session_values_json_redis)
	send_to_html_json = {
	    'status': 'Success',
	    'unregistered_vehicles': session_values_json_redis.get('unregistered_vehicles'),
	    'traveler_type': session_values_json_redis.get('traveler_type'),
	    'logged_in_user': user_name,
	    'logged_in_user_type': user_type,
	    'page_title': _('Unknown Vehicle'),
	    'message': session_values_json_redis.get('message')
	}
	return send_to_html_json

def create_json_for_unknown_vehicle_get_from_redis_object(user_id,user_name,user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	vehicle_types = app.config["VEHICLE_TYPES"]
	vehicle_categories = app.config["VEHICLE_CATEGORIES"]
	print("redis object in create_json_for_unknown_vehicle_get: ", session_values_json_redis)
	send_to_html_json = {
		'vehicle_id': session_values_json_redis.get('vehicle_id'),
        'vehicle_number': session_values_json_redis.get('vehicle_plate_number'),
        'vehicle_image_url': session_values_json_redis.get('vehicle_image_html_path'),
		'vehicle_owner_name': session_values_json_redis.get("person_name"),
        'vehicle_make': session_values_json_redis.get("vehicle_make"),
        'vehicle_model': session_values_json_redis.get("vehicle_model"),
        'vehicle_color': session_values_json_redis.get("vehicle_color"),
        'vehicle_entry_time': session_values_json_redis.get("vehicle_entry_time"),
        'vehicle_exit_time': session_values_json_redis.get("pop_time"),
		'person_id': session_values_json_redis.get("person_id"),
		'vehicle_types': vehicle_types,
		'vehicle_categories': vehicle_categories,
		'traveler_type': session_values_json_redis.get('traveler_type'),
        'logged_in_user': user_name,
        'logged_in_user_type': user_type,
        'page_title' : _('Unregistered Vehicle'),
        #'message': 'Please review and click submit to save the vehicle data.'
        'message': session_values_json_redis.get('message')
	}
	return send_to_html_json

def create_json_for_known_vehicle_get_from_redis_object(user_id,user_name,user_type):
	session_values_json_redis = json.loads(redis_conn.get(user_id))
	print("redis object in known vehicle get: ", session_values_json_redis, flush=True)
	session_values_json_redis.update({"vehicle_owner_id": session_values_json_redis.get("person_id")})
	send_to_html_json = {
            'vehicle_number': session_values_json_redis.get("vehicle_plate_number"),
            'vehicle_image': session_values_json_redis.get('vehicle_image'),
			'vehicle_make': _normalize_redis_value(session_values_json_redis.get("vehicle_make")),
			'vehicle_model': _normalize_redis_value(session_values_json_redis.get("vehicle_model")),
			'vehicle_color': _normalize_redis_value(session_values_json_redis.get("vehicle_color")),
			'vehicle_type': _normalize_redis_value(session_values_json_redis.get("vehicle_type")),
			'vehicle_category': _normalize_redis_value(session_values_json_redis.get("vehicle_category")),
			'vehicle_owner': _normalize_redis_value(session_values_json_redis.get("vehicle_owner")),
			'vehicle_registration_number': _normalize_redis_value(session_values_json_redis.get("vehicle_registration_number")),
            'logged_in_user': user_name,
            'logged_in_user_type': user_type,
            'page_title' : _('Known Vehicle'),
            'message': _('Success! Vehicle Information is in the database. Please continue.'),
            'success_font': 'True',
			'vehicle_owner_id': session_values_json_redis.get("vehicle_owner_id"),
			'traveler_type': session_values_json_redis.get('traveler_type'),
        }
	return send_to_html_json

def clean_redis_object(session_values_json_redis):

	#session_values_json_redis = json.loads(redis_conn.get(user_id))
	#print("redis object in trip registration before clean up: ", session_values_json_redis)

	try:
		session_values_json_redis.pop('person_id','Not found')
		session_values_json_redis.pop('enrollment_id','Not found')
		session_values_json_redis.pop('person_image','Not found')
		session_values_json_redis.pop('message','Not found')
		#session_values_json_redis.pop('traveler_type','Not found')
		session_values_json_redis.pop("person_image_html_path", 'Not found')
		session_values_json_redis.pop('person_image_actual_path', 'Not found')
		session_values_json_redis.pop('person_name','Not found')
		session_values_json_redis.pop('guardians_name','Not found')
		session_values_json_redis.pop('address','Not found')
		session_values_json_redis.pop('aadhar_number','Not found')
		session_values_json_redis.pop('aadhar_image','Not found')
		session_values_json_redis.pop('drivers_license','Not found')
		session_values_json_redis.pop('drivers_license_image','Not found')

		#new fields for other IDs
		session_values_json_redis.pop("other_id_type", 'Not found')
		session_values_json_redis.pop("other_id_number", 'Not found')
		session_values_json_redis.pop("other_id_image", 'Not found')
		# new fields from passes
		session_values_json_redis.pop("pass_type", 'Not found')
		session_values_json_redis.pop("pass_type", 'Not found')
		session_values_json_redis.pop("pass_assigned_to", 'Not found')
		session_values_json_redis.pop("pass_start_date", 'Not found')
		session_values_json_redis.pop("pass_end_date", 'Not found')
		session_values_json_redis.pop("pass_issue_date", 'Not found')

		#if session_values_json_redis.get('unregistered_vehicles') is not None:
		session_values_json_redis.pop('unregistered_vehicles','Not found')
		session_values_json_redis.pop('vehicle_image_html_path','Not found')
		session_values_json_redis.pop('vehicle_image_actual_path','Not found')
		session_values_json_redis.pop('vehicle_image','Not found')
		session_values_json_redis.pop('vehicle_id','Not found')
		session_values_json_redis.pop('vehicle_plate_number','Not found')
		session_values_json_redis.pop('vehicle_make','Not found')
		session_values_json_redis.pop('vehicle_model','Not found')
		session_values_json_redis.pop('vehicle_entry_time','Not found')
		session_values_json_redis.pop('vehicle_exit_time','Not found')
		session_values_json_redis.pop('vehicle_color','Not found')
		session_values_json_redis.pop('vehicle_type','Not found')
		session_values_json_redis.pop('vehicle_owner','Not found')
		session_values_json_redis.pop('matched_vehicle_owner_id','Not found')
		session_values_json_redis.pop('vehicle_registration_number','Not found')
		session_values_json_redis.pop('has_vehicle_association','Not found')
		session_values_json_redis.pop('coming_from','Not found')
		session_values_json_redis.pop('going_to','Not found')
		session_values_json_redis.pop('entry_time','Not found')
		#session_values_json_redis.pop('male_passengers')
		session_values_json_redis.pop('female_passengers','Not found')
		session_values_json_redis.pop('child_passengers','Not found')
		session_values_json_redis.pop('trip_reason','Not found')
		session_values_json_redis.pop('trip_type','Not found')
		session_values_json_redis.pop('permit_image','Not found')
		session_values_json_redis.pop('trip_id','Not found')
		session_values_json_redis.pop("person_details",'Not found')


	except Exception as error:
		print("Error while cleanup redis: ", error)

	return session_values_json_redis 
	

def clean_redis_object_before_aadhar_lookup(session_values_json_redis):
    
	session_values_json_redis.pop("person_image_html_path",'Not found') 
	session_values_json_redis.pop("person_image_actual_path", 'Not found')
	session_values_json_redis.pop("details_entered_by",'Not found')
	session_values_json_redis.pop("details_entered_on",'Not found')
	session_values_json_redis.pop("person_name",'Not found')
	session_values_json_redis.pop("guardians_name",'Not found')
	session_values_json_redis.pop("address",'Not found')
	session_values_json_redis.pop("aadhar_number",'Not found')
	session_values_json_redis.pop("aadhar_image",'Not found')
	session_values_json_redis.pop("drivers_license",'Not found')
	session_values_json_redis.pop("drivers_license_image",'Not found')
	session_values_json_redis.pop("person_id",'Not found')
	session_values_json_redis.pop("enrollment_id",'Not found')
	session_values_json_redis.pop("person_image",'Not found')
	session_values_json_redis.pop("person_details",'Not found')
	#missing in the previous list
	session_values_json_redis.pop("traveler_type", 'Not found')
	session_values_json_redis.pop("visiting_person_name", 'Not found')
	session_values_json_redis.pop("mobile_number", 'Not found')
	session_values_json_redis.pop("dob", 'Not found')
	session_values_json_redis.pop("gender", 'Not found')

	#other_ids from persons
	session_values_json_redis.pop("other_id_type", 'Not found')
	session_values_json_redis.pop("other_id_number", 'Not found')
	session_values_json_redis.pop("other_id_image", 'Not found')
	# new fields from passes
	session_values_json_redis.pop("pass_type", 'Not found')
	session_values_json_redis.pop("pass_type", 'Not found')
	session_values_json_redis.pop("pass_assigned_to", 'Not found')
	session_values_json_redis.pop("pass_start_date", 'Not found')
	session_values_json_redis.pop("pass_end_date", 'Not found')
	session_values_json_redis.pop("pass_issue_date", 'Not found')

	session_values_json_redis.pop("id_type", 'Not found')

	
	return session_values_json_redis 
