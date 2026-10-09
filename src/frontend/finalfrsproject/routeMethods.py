import os, shutil
from finalfrsproject import app, sqlCommands, jwt
from flask import request, render_template
from werkzeug.utils import secure_filename
from datetime import datetime, timezone, timedelta
import base64
from flask_babel import _
from dateutil import parser

def allowed_file(filename, allowed_extensions):
	return '.' in filename and \
		filename.rsplit('.', 1)[1].lower() in allowed_extensions


def _ensure_enrollment_image_on_disk(enrolled_image_full_path, enrolled_image_base_file):
	"""Copy enrollment photo into known_persons when present; never crash if missing."""
	dest_path = os.path.join(app.config["KNOWN_PERSONS"], enrolled_image_base_file)
	if os.path.exists(dest_path):
		return dest_path
	if os.path.isfile(enrolled_image_full_path):
		shutil.copyfile(enrolled_image_full_path, dest_path)
		return dest_path
	print(f"Enrollment image missing on disk: {enrolled_image_full_path}", flush=True)
	return dest_path


def validate_vehicle_fields(form, page_name):
	page_config = app.config["VEHICLE_FIELDS"][page_name]
	missing_fields = [
		field_name for field_name in page_config["required_fields"]
		if not str(form.get(field_name, "")).strip()
	]
	if missing_fields:
		return {
			"Status": "Fail",
			"Insert_Count": 0,
			"Update_Count": 0,
			"Details": f"Required vehicle fields are missing: {', '.join(missing_fields)}",
		}
	return None


def _vehicle_image_html_path(actual_path):
	return os.path.sep.join([
		app.config["KNOWN_VEHICLE_PATH_FOR_HTML"],
		os.path.basename(actual_path),
	])


def _store_vehicle_image_in_session(session_values_json_redis, vehicle_image_url=None, fallback_actual_path=None):
	"""Use known_vehicles file, restore from ANPR capture, or fall back to placeholder."""
	actual_path = None
	basename = None
	if fallback_actual_path:
		basename = os.path.basename(fallback_actual_path)
	elif vehicle_image_url:
		basename = os.path.basename(vehicle_image_url)

	if basename:
		known_path = os.path.sep.join([app.config["KNOWN_VEHICLES"], basename])
		if os.path.isfile(known_path):
			actual_path = known_path
		else:
			capture_path = os.path.sep.join([app.config["VEHICLE_IMAGES"], basename])
			if os.path.isfile(capture_path):
				shutil.copy(capture_path, known_path)
				actual_path = known_path
				print(f"Restored known vehicle image from ANPR: {basename}", flush=True)

	if actual_path is None and vehicle_image_url:
		capture_path = os.path.sep.join([
			app.config["VEHICLE_IMAGES"],
			os.path.basename(vehicle_image_url),
		])
		if os.path.isfile(capture_path):
			destination = os.path.sep.join([
				app.config["KNOWN_VEHICLES"],
				os.path.basename(capture_path),
			])
			shutil.copy(capture_path, destination)
			actual_path = destination

	if actual_path is None and fallback_actual_path and os.path.isfile(fallback_actual_path):
		actual_path = fallback_actual_path

	if actual_path is None or not os.path.isfile(actual_path):
		placeholder = os.path.sep.join([
			app.config["PROJECT_BASE_PATH"],
			"static",
			"images",
			"placeholder.png",
		])
		if os.path.isfile(placeholder):
			actual_path = placeholder
		else:
			actual_path = app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"]

	if actual_path.endswith(os.path.sep.join(["static", "images", "placeholder.png"])):
		html_path = "/static/images/placeholder.png"
	else:
		html_path = _vehicle_image_html_path(actual_path)
	session_values_json_redis.update({
		"vehicle_image_html_path": html_path,
		"vehicle_image_actual_path": actual_path,
		"vehicle_image": html_path,
	})
	return session_values_json_redis


def get_known_person_details_with_enrollment_id(enrollment_id, session_values_json_redis):
	result = sqlCommands.get_person_details_with_enrollment_id(enrollment_id)

	if not result or result.get('Status') == "Fail":
		return result #session_values_json_redis

	if result.get('Details') is None:
		print("No match returned")
		result = {"Status": "Success", "Details": "No match found"}
		return result

	else:
		result = result.get("Details")
		print('result ', result, flush=True)
		enrolled_image_full_path = result.get('person_image_location').rstrip('/')
		enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		person_image_actual_path = _ensure_enrollment_image_on_disk(
			enrolled_image_full_path, enrolled_image_base_file
		)
		person_image_html_path = os.path.join(app.config["KNOWN_PERSON_PATH_FOR_HTML"], enrolled_image_base_file)
		# details_entry_date = result[1].strftime('%d %B, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
		details_entry_date = result.get('date_created').strftime(
			'%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		# if result[15] is not None:
		if result.get('dob') is not None:
			dob = result.get('dob').strftime('%d %B, %Y')  # strftime('%d-%m-%Y %H:%M:%S')
		else:
			dob = ''
		session_values_json_redis.update({"person_image_html_path": person_image_html_path})
		session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
		# session_values_json_redis.update({"details_entered_by": result[0]})
		session_values_json_redis.update({"details_entered_by": result.get('created_by')})
		session_values_json_redis.update({"details_entered_on": details_entry_date})  # str(result[1])
		# session_values_json_redis.update({"person_name": result[2]})
		session_values_json_redis.update({"person_name": result.get('person_name')})
		# session_values_json_redis.update({"guardians_name": result[4]})
		session_values_json_redis.update({"guardians_name": result.get('guardian_names')})
		# session_values_json_redis.update({"address": result[5]})
		session_values_json_redis.update({"address": result.get('address')})
		# session_values_json_redis.update({"aadhar_number": result[6]})
		session_values_json_redis.update({"aadhar_number": result.get('aadhar_number')})
		session_values_json_redis.update({"aadhar_image": result.get('aadhar_image_location')})
		session_values_json_redis.update({"drivers_license": result.get('drivers_license_number')})
		session_values_json_redis.update({"drivers_license_image": result.get('drivers_license_image')})
		session_values_json_redis.update({"person_id": result.get('id')})
		session_values_json_redis.update({"enrollment_id": str(result.get('enrollment_id'))})
		session_values_json_redis.update({"gender": result.get('gender')})
		session_values_json_redis.update({"dob": dob})
		session_values_json_redis.update({"mobile_number": result.get('mobile_number')})
		session_values_json_redis.update({"visiting_person_name": result.get('visiting_person_name')})
		session_values_json_redis.update({"person_image": person_image_html_path})
		session_values_json_redis.update({"ticket_status": "recognize_person"})
		# new fields for other IDs
		session_values_json_redis.update({"other_id_type": result.get("other_id_type")})
		session_values_json_redis.update({"other_id_number": result.get("other_id_number")})
		session_values_json_redis.update({"other_id_image": result.get("other_id_image_location")})
		# new fields from passes
		session_values_json_redis.update({"pass_number": result.get("pass_number")})
		session_values_json_redis.update({"pass_type": result.get("pass_type")})
		session_values_json_redis.update({"pass_sub_type": result.get("pass_sub_type")})
		session_values_json_redis.update({"pass_assigned_to": result.get("assigned_to")})
		session_values_json_redis.update({"pass_start_date": result.get("pass_start_date")})
		session_values_json_redis.update({"pass_end_date": result.get("pass_end_date")})
		session_values_json_redis.update({"pass_issue_date": result.get("pass_issue_date")})
		session_values_json_redis.update({"pass_image_location": result.get("pass_image_location")})

		#result = {"Status": "Success", "Details": result}
		result = {"Status": "Success", "Details": session_values_json_redis}
		return result

def get_known_person_details_with_other_id(other_id_number, session_values_json_redis):
	result = sqlCommands.get_person_details_with_other_id(other_id_number)
	if not result or result.get('Status') == "Fail":
		# print("before returning:" , session_values_json_redis)
		return result
	if result.get('Details') is None:
		result = {"Status": "Success", "Details": "No match found"}
		return result
	else:
		result = result.get("Details")
		#print('result ', result)
		# enrolled_image_full_path = result[3].rstrip('/')
		enrolled_image_full_path = result.get('person_image_location').rstrip('/')
		enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		person_image_actual_path = _ensure_enrollment_image_on_disk(
			enrolled_image_full_path, enrolled_image_base_file
		)
		person_image_html_path = os.path.join(app.config["KNOWN_PERSON_PATH_FOR_HTML"], enrolled_image_base_file)
		# details_entry_date = result[1].strftime('%d %B, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
		details_entry_date = result.get('date_created').strftime(
			'%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		# if result[15] is not None:
		if result.get('dob') is not None:
			dob = result.get('dob').strftime('%d %B, %Y')  # strftime('%d-%m-%Y %H:%M:%S')
		else:
			dob = ''
		session_values_json_redis.update({"person_image_html_path": person_image_html_path})
		session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
		# session_values_json_redis.update({"details_entered_by": result[0]})
		session_values_json_redis.update({"details_entered_by": result.get('created_by')})
		session_values_json_redis.update({"details_entered_on": details_entry_date})  # str(result[1])
		# session_values_json_redis.update({"person_name": result[2]})
		session_values_json_redis.update({"person_name": result.get('person_name')})
		# session_values_json_redis.update({"guardians_name": result[4]})
		session_values_json_redis.update({"guardians_name": result.get('guardian_names')})
		# session_values_json_redis.update({"address": result[5]})
		session_values_json_redis.update({"address": result.get('address')})
		# session_values_json_redis.update({"aadhar_number": result[6]})
		session_values_json_redis.update({"aadhar_number": result.get('aadhar_number')})
		session_values_json_redis.update({"aadhar_image": result.get('aadhar_image_location')})
		session_values_json_redis.update({"drivers_license": result.get('drivers_license_number')})
		session_values_json_redis.update({"drivers_license_image": result.get('drivers_license_image')})
		session_values_json_redis.update({"person_id": result.get('id')})
		session_values_json_redis.update({"enrollment_id": str(result.get('enrollment_id'))})
		session_values_json_redis.update({"gender": result.get('gender')})
		session_values_json_redis.update({"dob": dob})
		session_values_json_redis.update({"mobile_number": result.get('mobile_number')})
		session_values_json_redis.update({"visiting_person_name": result.get('visiting_person_name')})
		session_values_json_redis.update({"person_image": person_image_html_path})
		session_values_json_redis.update({"ticket_status": "recognize_person"})
		# new fields for other IDs
		session_values_json_redis.update({"other_id_type": result.get("other_id_type")})
		session_values_json_redis.update({"other_id_number": result.get("other_id_number")})
		session_values_json_redis.update({"other_id_image": result.get("other_id_image_location")})
		# new fields from passes
		session_values_json_redis.update({"pass_number": None})
		session_values_json_redis.update({"pass_type": None})
		session_values_json_redis.update({"pass_sub_type": None})
		session_values_json_redis.update({"pass_assigned_to": None})
		session_values_json_redis.update({"pass_start_date": None})
		session_values_json_redis.update({"pass_end_date": None})
		session_values_json_redis.update({"pass_issue_date": None})
		session_values_json_redis.update({"pass_image_location": None})
		# print("redis: ", session_values_json_redis)
		result = {"Status": "Success", "Details": session_values_json_redis}
		return result

def get_known_person_details_with_drivers_license(drivers_license_number, session_values_json_redis):
	result = sqlCommands.get_person_details_with_drivers_license(drivers_license_number)
	if not result or result.get('Status') == "Fail":
		# print("before returning:" , session_values_json_redis)
		return result
	if result.get('Details') is None:
		result = {"Status": "Success", "Details": "No match found"}
		return result
	else:
		result = result.get("Details")
		#print('result ', result)
		# enrolled_image_full_path = result[3].rstrip('/')
		enrolled_image_full_path = result.get('person_image_location').rstrip('/')
		enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		person_image_actual_path = _ensure_enrollment_image_on_disk(
			enrolled_image_full_path, enrolled_image_base_file
		)
		person_image_html_path = os.path.join(app.config["KNOWN_PERSON_PATH_FOR_HTML"], enrolled_image_base_file)
		# details_entry_date = result[1].strftime('%d %B, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
		details_entry_date = result.get('date_created').strftime(
			'%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		# if result[15] is not None:
		if result.get('dob') is not None:
			dob = result.get('dob').strftime('%d %B, %Y')  # strftime('%d-%m-%Y %H:%M:%S')
		else:
			dob = ''
		session_values_json_redis.update({"person_image_html_path": person_image_html_path})
		session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
		# session_values_json_redis.update({"details_entered_by": result[0]})
		session_values_json_redis.update({"details_entered_by": result.get('created_by')})
		session_values_json_redis.update({"details_entered_on": details_entry_date})  # str(result[1])
		# session_values_json_redis.update({"person_name": result[2]})
		session_values_json_redis.update({"person_name": result.get('person_name')})
		# session_values_json_redis.update({"guardians_name": result[4]})
		session_values_json_redis.update({"guardians_name": result.get('guardians_name')})
		# session_values_json_redis.update({"address": result[5]})
		session_values_json_redis.update({"address": result.get('address')})
		# session_values_json_redis.update({"aadhar_number": result[6]})
		session_values_json_redis.update({"aadhar_number": result.get('aadhar_number')})
		session_values_json_redis.update({"aadhar_image": result.get('aadhar_image_location')})
		session_values_json_redis.update({"drivers_license": result.get('drivers_license_number')})
		session_values_json_redis.update({"drivers_license_image": result.get('drivers_license_image')})
		session_values_json_redis.update({"person_id": result.get('id')})
		session_values_json_redis.update({"enrollment_id": str(result.get('enrollment_id'))})
		session_values_json_redis.update({"gender": result.get('gender')})
		session_values_json_redis.update({"dob": dob})
		session_values_json_redis.update({"mobile_number": result.get('mobile_number')})
		session_values_json_redis.update({"visiting_person_name": result.get('visiting_person_name')})

		session_values_json_redis.update({"person_image": person_image_html_path})
		session_values_json_redis.update({"ticket_status": "recognize_person"})

		# new fields for other IDs
		session_values_json_redis.update({"other_id_type": result.get("other_id_type")})
		session_values_json_redis.update({"other_id_number": result.get("other_id_number")})
		session_values_json_redis.update({"other_id_image": result.get("other_id_image_location")})
		# new fields from passes
		session_values_json_redis.update({"pass_number": None})
		session_values_json_redis.update({"pass_type": None})
		session_values_json_redis.update({"pass_sub_type": None})
		session_values_json_redis.update({"pass_assigned_to": None})
		session_values_json_redis.update({"pass_start_date": None})
		session_values_json_redis.update({"pass_end_date": None})
		session_values_json_redis.update({"pass_issue_date": None})
		session_values_json_redis.update({"pass_image_location": None})

		# print("redis: ", session_values_json_redis)
		result = {"Status": "Success", "Details": session_values_json_redis}
		return result


def get_known_person_details_with_aadhar(aadhar_number, session_values_json_redis):

	result = sqlCommands.get_person_details_with_aadhar(aadhar_number)
	if not result or result.get('Status') == "Fail":
		#print("before returning:" , session_values_json_redis)
		return result
	if result.get('Details') is None:
		result = {"Status": "Success", "Details": "No match found"}
		return result
	else:
		result = result.get("Details")
		#print('result ', result)
		#enrolled_image_full_path = result[3].rstrip('/')
		enrolled_image_full_path = result.get('person_image_location').rstrip('/')
		enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		person_image_actual_path = _ensure_enrollment_image_on_disk(
			enrolled_image_full_path, enrolled_image_base_file
		)
		person_image_html_path = os.path.join(app.config["KNOWN_PERSON_PATH_FOR_HTML"],enrolled_image_base_file)
		#details_entry_date = result[1].strftime('%d %B, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
		details_entry_date = result.get('date_created').strftime('%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		#if result[15] is not None:
		if result.get('dob') is not None:
			dob = result.get('dob').strftime('%d %B, %Y')#strftime('%d-%m-%Y %H:%M:%S')
		else:
			dob = ''
		session_values_json_redis.update({"person_image_html_path": person_image_html_path})
		session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
		#session_values_json_redis.update({"details_entered_by": result[0]})
		session_values_json_redis.update({"details_entered_by": result.get('created_by')})
		session_values_json_redis.update({"details_entered_on": details_entry_date})#str(result[1])
		#session_values_json_redis.update({"person_name": result[2]})
		session_values_json_redis.update({"person_name": result.get('person_name')})
		#session_values_json_redis.update({"guardians_name": result[4]})
		session_values_json_redis.update({"guardians_name": result.get('guardians_name')})
		#session_values_json_redis.update({"address": result[5]})
		session_values_json_redis.update({"address": result.get('address')})
		#session_values_json_redis.update({"aadhar_number": result[6]})
		session_values_json_redis.update({"aadhar_number": result.get('aadhar_number')})
		session_values_json_redis.update({"aadhar_image": result.get('aadhar_image_location')})
		session_values_json_redis.update({"drivers_license": result.get('drivers_license_number')})
		session_values_json_redis.update({"drivers_license_image": result.get('drivers_license_image')})
		session_values_json_redis.update({"person_id": result.get('id')})
		session_values_json_redis.update({"enrollment_id": str(result.get('enrollment_id'))})
		session_values_json_redis.update({"gender": result.get('gender')})
		session_values_json_redis.update({"dob": dob})
		session_values_json_redis.update({"mobile_number": result.get('mobile_number')})
		session_values_json_redis.update({"visiting_person_name": result.get('visiting_person_name')})
		session_values_json_redis.update({"person_image": person_image_html_path})
		session_values_json_redis.update({"ticket_status": "recognize_person"})
		#new fields for other IDs
		session_values_json_redis.update({"other_id_type": result.get("other_id_type")})
		session_values_json_redis.update({"other_id_number": result.get("other_id_number")})
		session_values_json_redis.update({"other_id_image": result.get("other_id_image_location")})
		# new fields from passes
		session_values_json_redis.update({"pass_number": None})
		session_values_json_redis.update({"pass_type": None})
		session_values_json_redis.update({"pass_sub_type": None})
		session_values_json_redis.update({"pass_assigned_to": None})
		session_values_json_redis.update({"pass_start_date": None})
		session_values_json_redis.update({"pass_end_date": None})
		session_values_json_redis.update({"pass_issue_date": None})
		session_values_json_redis.update({"pass_image_location": None})
		#print("redis: ", session_values_json_redis)
		result = {"Status": "Success", "Details": session_values_json_redis}
		return result

def get_known_person_details_with_pass(id_number, session_values_json_redis):
	result = sqlCommands.get_person_details_with_pass(id_number)
	if not result or result.get('Status') == "Fail":
		# print("before returning:" , session_values_json_redis)
		return result
	if result.get('Details') is None:
		result = {"Status": "Success", "Details": "No match found"}
		return result
	else:
		result = result.get("Details")
		print('result ', result)
		result.get("aadhar_number")
		# print('rows returned: ', len(result))
			#enrolled_image_full_path = result[3].rstrip('/')
			#enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		enrolled_image_full_path = result.get("person_image_location").rstrip('/')
		enrolled_image_base_file = os.path.basename(enrolled_image_full_path)
		person_image_actual_path = _ensure_enrollment_image_on_disk(
			enrolled_image_full_path, enrolled_image_base_file
		)
		person_image_html_path = os.path.join(app.config["KNOWN_PERSON_PATH_FOR_HTML"], enrolled_image_base_file)
		#details_entry_date = result[1].strftime('%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		details_entry_date = result.get("date_created").strftime('%d %B, %Y %I:%M:%S %p')  # strftime('%d-%m-%Y %H:%M:%S')
		#if result[15] is not None:
		#	dob = result[15].strftime('%d %B, %Y')  # strftime('%d-%m-%Y %H:%M:%S')
		#else:
		#	dob = ''
		if result.get("dob") is not None:
			dob = result.get("dob").strftime('%d %B, %Y')  # strftime('%d-%m-%Y %H:%M:%S')
		else:
			dob = ''
		session_values_json_redis.update({"details_entered_by": result.get("created_by")})
		session_values_json_redis.update({"details_entered_on": details_entry_date})  # str(result[1])
		session_values_json_redis.update({"person_name": result.get("person_name")})
		session_values_json_redis.update({"person_image_html_path": person_image_html_path})
		session_values_json_redis.update({"person_image_actual_path": person_image_actual_path})
		session_values_json_redis.update({"guardians_name": result.get("guardians_name")})
		session_values_json_redis.update({"address": result.get('address')})
		session_values_json_redis.update({"aadhar_number": result.get("aadhar_number")})
		session_values_json_redis.update({"aadhar_image": result.get("aadhar_image_location")})
		session_values_json_redis.update({"drivers_license": result.get("drivers_license_number")})
		session_values_json_redis.update({"drivers_license_image": result.get("drivers_license_image")})
		session_values_json_redis.update({"person_id": result.get("id")})
		session_values_json_redis.update({"enrollment_id": str(result.get("enrollment_id"))})
		session_values_json_redis.update({"gender": result.get("gender")})
		session_values_json_redis.update({"dob": dob})
		session_values_json_redis.update({"mobile_number": result.get("mobile_number")})
		session_values_json_redis.update({"visiting_person_name": result.get("visiting_person_name")})
		#new fields for other IDs
		session_values_json_redis.update({"other_id_type": result.get("other_id_type")})
		session_values_json_redis.update({"other_id_number": result.get("other_id_number")})
		session_values_json_redis.update({"other_id_image": result.get("other_id_image_location")})
		# new fields from passes
		session_values_json_redis.update({"pass_number": result.get("pass_number")})
		session_values_json_redis.update({"pass_type": result.get("pass_type")})
		session_values_json_redis.update({"pass_sub_type": result.get("pass_sub_type")})
		session_values_json_redis.update({"pass_assigned_to": result.get("assigned_to")})
		session_values_json_redis.update({"pass_start_date": result.get("pass_start_date")})
		session_values_json_redis.update({"pass_end_date": result.get("pass_end_date")})
		session_values_json_redis.update({"pass_issue_date": result.get("pass_issue_date")})
		session_values_json_redis.update({"pass_image_location": result.get("pass_image_location")})
		session_values_json_redis.update({"person_image": person_image_html_path})
		session_values_json_redis.update({"ticket_status": "recognize_person"})
		# print("redis: ", session_values_json_redis)
		result = {"Status": "Success", "Details": session_values_json_redis}
		return result

#def insert_new_person_record(user_id, form, aadhar_image, drivers_license_image, person_image_destination):
def insert_new_person_record(user_id, form):
	#enrollment_id = form.get('enrollment_id')
	#print("enrollment_id: ", enrollment_id)
	#person_image_html_path = form.get('person_image_relative_path')
	#person_image_actual_path = form.get('person_image_actual_path')
	#print('person_image_actual_path', person_image_actual_path)
	#print('person_image_relative_path', person_image_html_path)
	result = sqlCommands.insert_new_person_record(user_id, form)
	print("result in insert_new_person_record: ", result)
	return result

def update_person_record(person_id, form):
	result = sqlCommands.update_person_record(person_id, form)
	print("result in update_person_record: ", result)
	return result


def delete_person_by_enrollment_id(enrollment_id):
	result = sqlCommands.delete_person_by_enrollment_id(enrollment_id)
	print("result in delete_person_by_enrollment_id: ", result)
	return result


def insert_new_trip_record(user_id, session_values_json_redis):
	
	#result = sqlCommands.insert_new_trip_record(user_id,permit_img_file_path, form, person_id,vehicle_plate_number)
	result = sqlCommands.insert_new_trip_record(user_id, session_values_json_redis)
	return result

	#if not result or result.get('Status') == "Fail":
	#	return result

	#else:
	#return result


def get_primary_vehicle_for_person(session_values_json_redis,person_id):
	result = sqlCommands.get_primary_vehicle_for_person(person_id)
	if not result or result.get('Status') == "Fail" or result.get('Count') == 0: #len(result) == 0:
		return session_values_json_redis
	else:
		result = result.get('Details')
		print("result get primary vehicle for person: ", result, flush=True)
		session_values_json_redis = _store_vehicle_image_in_session(
			session_values_json_redis,
			fallback_actual_path=result.get("vehicle_image_location"),
		)
		session_values_json_redis.update({"vehicle_plate_number": result.get("vehicle_number_plate")})
		session_values_json_redis.update({"vehicle_make": result.get("vehicle_make")})
		# NCPass uses the extended vehicle fields; retaining them for every profile
		# is harmless and prevents them from disappearing before trip registration.
		session_values_json_redis.update({"vehicle_model": result.get("vehicle_model")})
		session_values_json_redis.update({"vehicle_color": result.get("vehicle_color")})
		session_values_json_redis.update({"vehicle_type": result.get("vehicle_type")})
		session_values_json_redis.update({"vehicle_owner": result.get("vehicle_registered_to")})
		session_values_json_redis.update({
			"vehicle_registration_number": result.get("vehicle_registration_number")
		})

		return session_values_json_redis


def insert_new_vehicle_record(user_id, form):
	validation_error = validate_vehicle_fields(form, "unknown_vehicle")
	if validation_error:
		return validation_error
	result = sqlCommands.insert_new_vehicle_record(user_id, form)
	return result

def update_existing_vehicle_record(form, new_vehicle_owner, user_id, session_values_json_redis=None):
	validation_error = validate_vehicle_fields(form, "known_vehicle")
	if validation_error:
		return validation_error

	def _normalize(value):
		if value is None:
			return None
		normalized = str(value).strip()
		if normalized == '' or normalized.lower() in ('none', 'null'):
			return None
		return normalized

	# Avoid a database write when neither the vehicle fields nor its owner changed.
	if session_values_json_redis is not None:
		form_make = _normalize(form.get('make'))
		form_model = _normalize(form.get('vehicle_model'))
		form_color = _normalize(form.get('color'))
		form_type = _normalize(form.get('vehicle_type'))
		form_owner = _normalize(form.get('vehicle_owner_name'))
		form_rc = _normalize(form.get('vehicle_registration_number'))
		form_image_basename = os.path.basename(form.get('vehicle_image_url', '') or '')

		redis_make = _normalize(session_values_json_redis.get('vehicle_make'))
		redis_model = _normalize(session_values_json_redis.get('vehicle_model'))
		redis_color = _normalize(session_values_json_redis.get('vehicle_color'))
		redis_type = _normalize(session_values_json_redis.get('vehicle_type'))
		redis_owner = _normalize(session_values_json_redis.get('vehicle_owner'))
		redis_rc = _normalize(session_values_json_redis.get('vehicle_registration_number'))
		redis_image_basename = os.path.basename(session_values_json_redis.get('vehicle_image', '') or '')
		matched_vehicle_owner_id = session_values_json_redis.get('matched_vehicle_owner_id')
		owner_changed = (
			matched_vehicle_owner_id is not None
			and str(matched_vehicle_owner_id) != str(new_vehicle_owner)
		)

		has_change = any([
			form_make != redis_make,
			form_model != redis_model,
			form_color != redis_color,
			form_type != redis_type,
			form_owner != redis_owner,
			form_rc != redis_rc,
			form_image_basename != redis_image_basename,
			owner_changed,
		])

		if not has_change:
			print('update_existing_vehicle_record: no change detected via Redis, skipping DB call', flush=True)
			return {"Status": "Success", "Insert_Count": 0, "Update_Count": 0, "Action": "NoChange", "Details": {}}

	result = sqlCommands.update_existing_vehicle_record(form, new_vehicle_owner, user_id)
	#print('result: ', result)
	if not result or result.get('Status') == 'Fail':
		return result
	else:
		return result


def get_all_vehicles_from_anpr(session_values_json_redis):
	#print("redis in get all vehicles from anpr 1: ", session_values_json_redis)
	result = sqlCommands.get_all_vehicles_from_anpr()
	formatted_vehicles = []

	if not result or result.get('Status') == "Fail" or result.get('Details') is None or len(result.get('Details')) == 0:
		session_values_json_redis.update({"unregistered_vehicles": formatted_vehicles})
		#print("redis in get all vehicles from anpr 2: ", session_values_json_redis)
		return session_values_json_redis 
	else:
		#print('rows returned: ', result)
		result = result.get('Details')
		print(f'**************result in get_all vehicles from anpr: {result}', flush=True)
		for vehicle in result:
			#Assuming timestamp is different from the format '2022-12-08 02:49:36.137264+00:00'
			timestamp_str = vehicle[3]
			timestamp_obj = parser.parse(timestamp_str)
			formatted_timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
			#Assuming timestamp is a string in the format '2022-12-08 02:49:36.137264+00:00'
			#timestamp_str = vehicle[3]
			#timestamp_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f%z')
			#formatted_timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')
			formatted_vehicles.append({
				"id": vehicle[0],
				'image_url': os.path.sep.join([app.config["SCREENSHOTS_FOLDER"],os.path.basename(vehicle[1])]),
				'plate_number': vehicle[2],
				'timestamp': formatted_timestamp,
				'camera_id' : vehicle[4]
			})
		
		session_values_json_redis.update({"unregistered_vehicles": formatted_vehicles})
		#print("redis in get all vehicles from anpr: ", session_values_json_redis)
		return session_values_json_redis


def get_vehicle_details_from_anpr(vehicle_plate_number, session_values_json_redis):

	print("get vehicle details from anpr", flush=True)
	result = sqlCommands.get_vehicle_details_from_anpr(vehicle_plate_number)
	print("result: ", result)

	if not result or result.get('Details') is None or result.get('Count') == 0 or result.get('Status') == "Fail":
		return result 
	else:
		result = result.get('Details')
		if len(result) > 0:
			#print('rows returned: ', len(result))
			vehicle_entry_time = result.get("timestamp").split()[0] + " : " + result.get("timestamp").split()[1].split('.')[0]
			session_values_json_redis.update({"vehicle_id": result.get("id")})
			session_values_json_redis.update({'vehicle_make': result.get("make")})
			session_values_json_redis.update({'vehicle_model': result.get("model")})
			session_values_json_redis.update({'vehicle_entry_time': vehicle_entry_time})
			session_values_json_redis.update({'vehicle_exit_time': result.get("update_time")})
		
		print("redis: ", session_values_json_redis, flush=True)
		return session_values_json_redis

'''
def get_all_open_trips(session_values_json_redis):

	result = sqlCommands.get_all_open_trips()

	if not result or len(result.get('Details')) == 0 or result.get('Status') == "Fail":
		return result 
	else:

		result = result.get("Details")
		#print('result ', result)
		formatted_trips = []
		#print('rows returned: ', len(result))
		for trip in result:
			formatted_trips.append({
				"id": trip[0],
				"date_created": trip[1].strftime("%m/%d/%Y, %H:%M:%S"),
				"driver_name":trip[2],
				'image_url': os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"],os.path.basename(trip[3])]),
				'traveler_type': trip[4],
				'vehicle_plate_number': trip[5]
			})

		session_values_json_redis.update({"open_trips": formatted_trips})
		#print("redis: ", session_values_json_redis)
		return session_values_json_redis
'''
def check_if_vehicle_is_in_our_system(vehicle_plate_number, vehicle_image_url, vehicle_id, session_values_json_redis):
	print('Check_if_vehicle_is_in_our_system: ', vehicle_plate_number, flush=True)
	has_vehicle_association = session_values_json_redis.get('has_vehicle_association')
	owner_id = session_values_json_redis.get('person_id') if has_vehicle_association else None
	result = sqlCommands.check_if_vehicle_is_in_our_system(vehicle_plate_number, owner_id)
	print('result from check_if_vehicle_is_in_our_system: ', result, flush=True)

	if not result or result.get('Status') == "Fail":        
		return result
	else:
		result = result.get('Details')
		if result is None or len(result) == 0:
			print('vehicle not found in database', flush=True)
			_store_vehicle_image_in_session(
				session_values_json_redis,
				vehicle_image_url=vehicle_image_url,
			)

			if vehicle_id is not None:
				print('vehicle id is Not None', flush=True)
				session_values_json_redis.update({"vehicle_id": vehicle_id})	
	
			session_values_json_redis.update({"vehicle_plate_number": vehicle_plate_number})
			session_values_json_redis.pop('matched_vehicle_owner_id', None)
			return session_values_json_redis, 'unknown_vehicle'

		else:
			print('vehicle found in database', flush=True)
			_store_vehicle_image_in_session(
				session_values_json_redis,
				fallback_actual_path=result.get('vehicle_image_location'),
			)
			session_values_json_redis.update({"vehicle_plate_number": result.get("vehicle_number_plate")})
			session_values_json_redis.update({"vehicle_make": result.get("vehicle_make")})
			session_values_json_redis.update({"vehicle_model": result.get("vehicle_model")})
			session_values_json_redis.update({"vehicle_color": result.get("vehicle_color")})
			session_values_json_redis.update({"vehicle_type": result.get("vehicle_type")})
			session_values_json_redis.update({"vehicle_owner": result.get("vehicle_registered_to")})
			session_values_json_redis.update({"vehicle_registration_number": result.get("vehicle_registration_number")})
			session_values_json_redis.update({"matched_vehicle_owner_id": result.get("vehicle_owner_id")})
			#session_values_json_redis.update({"vehicle_expiry_date": vehicle_expiry_date})
			return session_values_json_redis, 'known_vehicle'

def get_unfinished_trips(user_name, user_type, person_id=None):
	result = sqlCommands.get_unfinished_trips(person_id)
	#print(f'generate_trip_report result: {result}', flush=True)
	send_to_html_json = {}
	open_trips_list = []
	#return result
	#print(result, flush=True)
	if not result or result.get('Status') == "Fail":
		return result

	elif result.get('Details') is None:
		print("No records found in unfinished_trips", flush=True)
		send_to_html_json = {
			'incomplete_trips': open_trips_list,
			'logged_in_user': user_name,
			'logged_in_user_type': user_type,
			'message': _('No records found. Please try again with different dates.'),
			'page_title': _('End Trip')
		}
		print("send_to_html_json: ", send_to_html_json)

	else:
		result = result.get('Details')
		print('rows returned: ', len(result))
		send_to_html_json = {
		   'incomplete_trips': result,
		   'logged_in_user': user_name,
		   'logged_in_user_type': user_type,
		   'message': _('Please select a trip from the list below. It will be closed with the current time.'),
		   'page_title': _('End Trip')
		}

	result = {"Status": "Success", "Details": send_to_html_json}
	return result


def generate_vehicle_report(start_date, end_date, user_name, user_type):

	result = sqlCommands.get_vehicle_details_from_vehicles_by_date(start_date, end_date)
	send_to_html_json = {}
	vehicle_report_list = []

	if not result or result.get('Status') == "Fail" or result.get('Count') == 0:
		return result
 
	else:
		result = result.get('Details')

		if len(result) > 0:

			for vehicle in result:
				vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(vehicle[9])])
				entry_time = vehicle[5].strftime('%d %b, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
				#registration_date = vehicle[7].strftime('%d-%m-%Y')
				#expiry_date = vehicle[8].strftime('%d %b, %Y %I:%M:%S %p')#strftime('%d-%m-%Y')

				vehicle_report_list.append({
					'vehicle_driver': vehicle[0],
					'vehicle_plate_number': vehicle[1],
					'vehicle_make': vehicle[2],
					'vehicle_model': vehicle[3],
					'vehicle_color': vehicle[4],
					'entry_time': entry_time,
					'vehicle_owner': vehicle[6],
					#'vehicle_registration_date': registration_date,
					'vehicle_registration_number':vehicle[7],
					#'vehicle_expiry_date': expiry_date,
					'vehicle_image': vehicle_image
				})
			send_to_html_json = {
				'vehicle_report_list': vehicle_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': _('Following records were found for the selected dates. Please try again with different dates.'),
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': _('Vehicle Report')
			}


		else:
			#print("No records found")
			vehicle_report_list.append({
				'vehicle_driver': _('No records found'),
				#'vehicle_plate_number': 'No records found',
				'vehicle_make': _('No records found'),
				'vehicle_model': _('No records found'),
				'vehicle_color': _('No records found'),
				'entry_time': _('No records found'),
				'vehicle_owner': _('No records found'),
				#'vehicle_registration_date': 'No records found',
				'vehicle_registration_number': _('No records found'),
				#'vehicle_expiry_date': 'No records found'
				#'vehicle_image': None
			})

			send_to_html_json = {
				'vehicle_report_list': vehicle_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': _('No records found for the selected dates. Please try again with different dates.'),
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': _('Vehicle Report')
			}

		result = {"Status": "Success", "Details": send_to_html_json}    
		return result

def generate_person_report(start_date, end_date, user_name, user_type):

	result = sqlCommands.get_person_details_by_date(start_date, end_date)
	send_to_html_json = {}
	person_report_list = []

	if not result or result.get('Status') == "Fail":        
		return result
 
	else:
		result = result.get('Details')

		if len(result) > 0:
			for person in result:

				person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person[1].rstrip('/'))])
				entry_time = person[9].strftime('%d %b, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')

				#entry_time = datetime.strptime(person[9],'%d %b, %Y %I:%M:%S %p')#strftime('%d-%m-%Y %H:%M:%S')
				#entry_time = entry_time.strftime('%d %b, %Y %I:%M:%S %p')


				person_report_list.append({
					'person_name': person[0],
					'person_image': person_image,
					'guardians_name': person[2],
					'vehicle_plate_number': person[3],
					'traveler_type': person[4],
					'aadhar_number': person[5],
					'aadhar_image': person[6],
					'drivers_license': person[7],
					'drivers_license_image': person[8],
					'entry_time': entry_time,
					'address': person[10]
				})
			send_to_html_json = {
				'person_report_list': person_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': _('Following records were found for the selected dates. Please try again with different dates.'),
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': _('Person Report')
			}


		else:
			#print("No records found")
			person_report_list.append({
				#'person_name': 'No records found',
				#'person_image': 'No records found',
				'guardians_name': _('No records found'),
				'vehicle_plate_number': _('No records found'),
				'traveler_type': _('No records found'),
				#'aadhar_number': 'No records found',
				#'aadhar_image': 'No records found',
				#'drivers_license': 'No records found',
				#'drivers_license_image': 'No records found',
				'entry_time': _('No records found'),
				'address': _('No records found')
			})

			send_to_html_json = {
				'person_report_list': person_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': _('No records found for the selected dates. Please try again with different dates.'),
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': _('Person Report')
			}

		result = {"Status": "Success", "Details": send_to_html_json}    
		return result


def generate_trip_report(start_date, end_date, user_name, user_type):

	result = sqlCommands.get_trip_details_by_date(start_date, end_date)
	print(f'generate_trip_report result: {result}', flush=True)
	send_to_html_json = {}
	trip_report_list = []
	'''
	if not result or result.get('Status') == "Fail":        
		return result
 
	else:
		result = result.get('Details')
		if len(result) > 0:
			for trip in result:
				person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(trip[1].rstrip('/'))])
				vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(trip[3].rstrip('/'))])
				#entry_time = trip[5].strftime('%d-%m-%Y %H:%M:%S')
				entry_time = trip[5].strftime('%d %b, %Y %I:%M:%S %p')
				if trip[6] is not None:
					#exit_time = trip[6].strftime('%d-%m-%Y %H:%M:%S')
					exit_time = trip[6].strftime('%d %b, %Y %I:%M:%S %p')
				else:
					exit_time = "Not Closed"
				
				trip_report_list.append({
					'person_name': trip[0],
					'person_image':person_image,#trip[1]
					'vehicle_plate_number': trip[2],
					'vehicle_image': vehicle_image,#trip[3],
					'traveler_type': trip[4],
					'entry_time': entry_time,
					'exit_time': exit_time,
					'coming_from': trip[7],
					'going_to': trip[8],
					'male_passengers': trip[9],
					'female_passengers': trip[10],
					'child_passengers': trip[11],
					'trip_id': trip[12]
				})
			
			send_to_html_json = {
				'trip_report_list': trip_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': 'Following records were found for the selected dates. Please try again with different dates.',
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': 'Vehicle Report'
			}


		else:
			#print("No records found")
			trip_report_list.append({
					#'person_name': 'No records found',
					'person_image': 'No records found',
					#'vehicle_plate_number': 'No records found',
					'vehicle_image': 'No records found',
					'traveler_type': 'No records found',
					'entry_time': 'No records found',
					'exit_time': 'No records found',
					'coming_from': 'No records found',
					'going_to': 'No records found',
					'male_passengers': 'No records found',
					'female_passengers': 'No records found',
					'child_passengers': 'No records found',
					'trip_id': 'No records found'
			})

			send_to_html_json = {
				'trip_report_list': trip_report_list,
				'start_date': start_date,
				'end_date': end_date,
				'message': 'No records found for the selected dates. Please try again with different dates.',
				'logged_in_user': user_name,
				'logged_in_user_type': user_type,
				'page_title': 'Trip Report'
			}

		result = {"Status": "Success", "Details": send_to_html_json}    
		return result	
	'''
	return result

def get_known_person_trips(person_id):

	result = sqlCommands.get_known_person_trips(person_id)
	print("result :", result, flush=True)
	'''
	if not result or result.get('Status') == "Fail":
		# print("before returning:" , session_values_json_redis)
		return result

	if result.get('Details') is None:
		print('Why: ', result.get('Details'), flush=True)
		result = {"Status": "Success", "Details": "No trips found"}
		return result

	else:
		result = result.get("Details")
		#print('number of trips ', result, flush=True)

		result = {"Status": "Success", "Details": result}
		return result
	'''
	return result
