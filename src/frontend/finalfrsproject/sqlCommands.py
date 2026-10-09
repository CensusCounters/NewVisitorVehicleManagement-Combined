import psycopg2
import psycopg2.extras
#from google.protobuf.internal.test_bad_identifiers_pb2 import message
from psycopg2 import pool
from finalfrsproject import app, g
import os, shutil
from datetime import datetime, timedelta
from collections import defaultdict
import time
import re
from dateutil import parser



def return_connection_to_pool(db_connection):
    """Helper method to safely return database connection to pool"""
    if db_connection:
        try:
            g.connection_pool.putconn(db_connection)
            print("Connection returned to pool", flush=True)
        except Exception as pool_error:
            print(f"Error returning connection to pool: {pool_error}", flush=True)


def _normalize_optional(value):
    """Coerce blank optional form values to NULL for UNIQUE nullable columns."""
    if value is None:
        return None
    normalized = str(value).strip()
    if normalized == '' or normalized.lower() in ('none', 'null'):
        return None
    return normalized

TRIP_VEHICLE_OWNER_JOIN_SQL = """
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) *
            FROM vehicles
            ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC
        ) v ON t.vehicle_number_plate = v.vehicle_number_plate AND t.person_id = v.vehicle_owner_id
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate) *
            FROM vehicles
            WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> ''
            ORDER BY vehicle_number_plate, date_created DESC
        ) vp ON t.vehicle_number_plate = vp.vehicle_number_plate"""

TRIP_VEHICLE_PLATE_EXPR = "COALESCE(v.vehicle_number_plate, t.vehicle_number_plate)"
TRIP_VEHICLE_IMAGE_EXPR = "COALESCE(v.vehicle_image_location, vp.vehicle_image_location)"
TRIP_VEHICLE_SELECT_FIELDS = (
    f"{TRIP_VEHICLE_PLATE_EXPR} AS vehicle_number_plate, "
    f"{TRIP_VEHICLE_IMAGE_EXPR} AS vehicle_image_location"
)


def vehicle_image_html_path(stored_path):
    """Resolve a stored vehicle image path to a browser-served URL."""
    if stored_path is None:
        return None
    stored = str(stored_path).strip()
    if not stored or stored.lower() == "none":
        return None

    filename = os.path.basename(stored.rstrip("/"))
    known_fs = os.path.join(app.config["KNOWN_VEHICLES"], filename)
    anpr_fs = os.path.join(app.config["VEHICLE_IMAGES"], filename)
    if os.path.isfile(known_fs):
        return os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], filename])
    if os.path.isfile(anpr_fs):
        return os.path.sep.join([app.config["SCREENSHOTS_FOLDER"], filename])

    not_available = app.config.get("VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH")
    if not_available and os.path.isfile(not_available):
        return os.path.sep.join([
            app.config["KNOWN_VEHICLE_PATH_FOR_HTML"],
            os.path.basename(not_available),
        ])
    return os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], filename])

def login(user_name, password):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting login", flush=True)
    db_connection = None
    cursor = None
    result = None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''SELECT user_name, user_type, id from Users where user_name = %s and password = crypt(%s,password);'''
        arg = [user_name,password]
        cursor.execute(sql,arg)
        result = cursor.fetchone()
        result = {"Status": "Success", "Details": result}
     
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
 
    finally:
        # closing database connection.
        if cursor:
            cursor.close()
            print("PostgreSQL connection cursor is closed")
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed login | Execution time: {execution_time}ms", flush=True)
    return result

def update_person_record(person_id, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting update_person_record", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        name = _normalize_optional(form.get('name'))
        gender = _normalize_optional(form.get('gender'))
        mobile = _normalize_optional(form.get('mobile_number'))
        guardians_name = _normalize_optional(form.get('guardians_name'))
        address = _normalize_optional(form.get('address'))
        visiting_person_name = _normalize_optional(form.get('visiting_person_name'))
        aadhar_img_file_path = _normalize_optional(form.get('aadhar_img_file_path'))
        allowed_genders = {'Male', 'Female'}

        if not name:
            result = {"Status": "Fail", "Update_Count": 0, "Details": "Name is required."}
        elif gender not in allowed_genders:
            result = {"Status": "Fail", "Update_Count": 0, "Details": "Please select a valid gender."}
        elif mobile and (not mobile.isdigit() or len(mobile) != 10):
            result = {"Status": "Fail", "Update_Count": 0, "Details": "Mobile number must contain exactly 10 digits."}
        else:
            sql = '''UPDATE persons
                     SET person_name = %s,
                         gender = %s,
                         mobile_number = %s,
                         guardians_name = %s,
                         address = %s,
                         visiting_person_name = %s,
                         aadhar_image_location = COALESCE(%s, aadhar_image_location)
                     WHERE id = %s
                     RETURNING *;'''
            arg = (name, gender, mobile, guardians_name, address, visiting_person_name,
                   aadhar_img_file_path, person_id)
            cursor.execute(sql, arg)
            updated_row = cursor.fetchone()
            if updated_row is None:
                db_connection.rollback()
                result = {"Status": "Fail", "Update_Count": 0, "Details": "Person not found."}
            else:
                column_headers = [desc[0] for desc in cursor.description]
                updated_dict = dict(zip(column_headers, updated_row))
                db_connection.commit()
                result = {"Status": "Success", "Update_Count": 1, "Details": updated_dict}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command in update_person_record", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Update_Count": 0, "Details": "Unable to update visitor details."}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in update_person_record", flush=True)
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed update_person_record | Execution time: {execution_time}ms", flush=True)
    return result


def insert_new_person_record(user_id, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting insert_new_person_record", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        name = _normalize_optional(form.get('name'))
        guardians_name = _normalize_optional(form.get('guardians_name'))
        address = _normalize_optional(form.get('address'))
        gender = _normalize_optional(form.get('gender'))
        dob = _normalize_optional(form.get('dob'))
        mobile = _normalize_optional(form.get('mobile_number'))
        enrollment_id = _normalize_optional(form.get("enrollment_id"))
        aadhar_number = _normalize_optional(form.get('aadhar_number'))
        drivers_license = _normalize_optional(form.get('drivers_license'))
        other_id_number = _normalize_optional(form.get('other_id_number'))
        pass_number = _normalize_optional(form.get('pass_number'))
        aadhar_img_file_path = _normalize_optional(form.get('aadhar_img_file_path'))
        drivers_license_img_file_path = _normalize_optional(form.get('drivers_license_img_file_path'))
        other_id_img_file_path = _normalize_optional(form.get('other_id_img_file_path'))
        pass_img_file_path = _normalize_optional(form.get('pass_img_file_path'))
        other_id_type = _normalize_optional(form.get('other_id_type'))
        person_image_destination = _normalize_optional(form.get('person_image_destination'))
        visiting_person_name = _normalize_optional(form.get('visiting_person_name'))
        sql = ''' INSERT INTO persons (created_by, person_name, person_image_location, guardians_name, address, 
            aadhar_number, aadhar_image_location, drivers_license_number, drivers_license_image, 
            other_id_type, other_id_number, other_id_image_location,  
            enrollment_id, gender, dob, mobile_number, visiting_person_name) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *; '''

        arg = [user_id, name, person_image_destination, guardians_name, address,
               aadhar_number, aadhar_img_file_path, drivers_license, drivers_license_img_file_path,
                other_id_type, other_id_number, other_id_img_file_path,
               enrollment_id, gender, dob, mobile, visiting_person_name]

        cursor.execute(sql,(arg))

        # Extract column headers
        inserted_data_person = cursor.fetchone()
        column_headers = [desc[0] for desc in cursor.description]
        # Convert the fetched row into a dictionary
        inserted_data_person_dict = dict(zip(column_headers, inserted_data_person))

        # Prepare response details initially with person data
        response_details = dict(inserted_data_person_dict)

        if pass_number:
            # Extract the generated ID (assuming the first column is 'id')
            person_id = inserted_data_person_dict.get('id')

            # SQL for inserting into another table using the generated ID
            sql = '''INSERT INTO passes (created_by, number, assigned_to, pass_image_location) 
                VALUES (%s, %s, %s, %s) returning *;'''
            arg = [user_id, pass_number, person_id, pass_img_file_path]
            cursor.execute(sql,arg)
            inserted_pass = cursor.fetchone()
            column_headers_pass = [desc[0] for desc in cursor.description]
            inserted_data_pass_dict = dict(zip(column_headers_pass, inserted_pass))
            # Add number and passes_image_location to response
            response_details.update({
                'pass_number': inserted_data_pass_dict.get('number'),
                'pass_image_location': inserted_data_pass_dict.get('pass_image_location')
            })

        db_connection.commit()
        count = cursor.rowcount
        #print("insert count: ", count)
        result = {"Status": "Success", "Insert_Count": count, "Details": response_details}
        
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Insert_Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in insert_new_person_record",flush=True)
        return_connection_to_pool(db_connection)

        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed insert_new_person_record | Execution time: {execution_time}ms", flush=True)
        return result


def delete_person_by_enrollment_id(enrollment_id):
    """Delete a persons row by its enrollment_id.

    Used to roll back a person record when the face could not be enrolled into
    Milvus afterwards, so we never leave an orphan person (Postgres row with no
    face embedding) that would later route recognition to unknown_person and
    collide on re-enrollment.
    """
    start_time = time.time()
    db_connection = None
    cursor = None
    result = None
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = "DELETE FROM persons WHERE enrollment_id = %s;"
        cursor.execute(sql, (enrollment_id,))
        db_connection.commit()
        result = {"Status": "Success", "Deleted": cursor.rowcount}
    except (Exception, psycopg2.Error) as error:
        print("Error deleting person by enrollment_id", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] "
          f"Completed delete_person_by_enrollment_id | Execution time: {execution_time}ms", flush=True)
    return result

def get_pass_details_for_person(person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_pass_details_for_person", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        # Correcting the SQL Query
        sql = '''SELECT number, assigned_to, pass_image_location 
                 FROM passes WHERE assigned_to = %s
                 ORDER BY date_created DESC LIMIT 1;'''

        arg = (person_id,)

        # Debugging: Print the SQL Query

        cursor.execute(sql, arg)
        result = cursor.fetchone()  # Fetch a single row

        if result is None:
            result = {"Status": "Success", "Details": "No records found"}
        else:
            column_headers_pass = [desc[0] for desc in cursor.description]
            result = dict(zip(column_headers_pass, result))
            result = {"Status": "Success", "Details": result}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": str(error)}

    finally:
        # Closing database connection
        if cursor:
            cursor.close()
            print("Cursor closed in insert_new_person_record", flush=True)
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_pass_details_for_person | Execution time: {execution_time}ms", flush=True)
    return result


def get_person_details_with_enrollment_id(enrollment_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_with_enrollment", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select p.created_by, p.date_created, p.person_name, p.person_image_location, p.guardians_name, 
            p.address, p.aadhar_number, p.aadhar_image_location, p.drivers_license_number, p.drivers_license_image, 
            p.id, p.enrollment_id, p.gender, p.vid, p.address, p.dob, p.mobile_number, p.visiting_person_name,
            p.other_id_type, p.other_id_number, p.other_id_image_location, pa.number as pass_number, pa.pass_image_location
            FROM persons p LEFT JOIN passes pa ON p.id = pa.assigned_to
            where p.enrollment_id = %s;'''

        arg = (enrollment_id,)
        cursor.execute(sql,arg)

        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}

        print("enrollment_id lookup details: ", result, flush=True)
        #result = {"Status": "Success", "Details": result}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}


    finally:
        if cursor:
            cursor.close()
            print("cursor closed  in get_person_details_with_enrollment", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_enrollment | Execution time: {execution_time}ms", flush=True)
    return result

def get_person_details_with_other_id(other_id_number, other_id_type):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_pass_details_for_person", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select created_by, date_created, person_name, person_image_location, guardians_name, address, 
                aadhar_number, aadhar_image_location, drivers_license_number,  drivers_license_image, 
                id, enrollment_id, gender, vid, address, dob, mobile_number, visiting_person_name,
                other_id_type, other_id_number, other_id_image_location from persons 
                where other_id_type = %s and other_id_number = %s;'''

        arg = (other_id_type, other_id_number)
        cursor.execute(sql, arg)
        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}


    finally:
        # closing database connection.
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_with_other_id", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_other_id | Execution time: {execution_time}ms", flush=True)

    return result

def get_person_details_with_drivers_license(drivers_license_number):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_with_drivers_license", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select created_by, date_created, person_name, person_image_location, guardians_name, address, 
                aadhar_number, aadhar_image_location, drivers_license_number,  drivers_license_image, 
                id, enrollment_id, gender, vid, address, dob, mobile_number, visiting_person_name,
                other_id_type, other_id_number, other_id_image_location from persons where drivers_license_number = %s;'''

        arg = (drivers_license_number, )
        cursor.execute(sql, arg)
        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}


    finally:
        # closing database connection.
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_with_drivers_license", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_drivers_license | Execution time: {execution_time}ms", flush=True)

    return result


def get_person_details_with_aadhar(aadhar_number):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_with_aadhar", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = '''select created_by, date_created, person_name, person_image_location, guardians_name, address, 
                aadhar_number, aadhar_image_location, drivers_license_number,  drivers_license_image, 
                id, enrollment_id, gender, vid, address, dob, mobile_number, visiting_person_name,
                other_id_type, other_id_number, other_id_image_location from persons where aadhar_number = %s;'''

        arg = (aadhar_number, )
        cursor.execute(sql, arg)
        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
    finally:
        # closing database connection.
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_with_aadhar", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_aadhar | Execution time: {execution_time}ms", flush=True)

    return result


def get_person_details_with_pass(id_number):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_with_pass", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = """
        SELECT 
            p.type as pass_type, p.sub_type as pass_sub_type, p.number as pass_number, p.assigned_to, 
            p.pass_start_date, p.pass_end_date, p.pass_issue_date, p.pass_image_location,
            pr.created_by, pr.date_created, pr.person_name, 
            pr.person_image_location, pr.guardians_name, pr.address, 
            pr.aadhar_number, pr.aadhar_image_location, 
            pr.drivers_license_number, pr.drivers_license_image, 
            pr.id, pr.enrollment_id, pr.gender, pr.vid, 
            pr.dob, pr.mobile_number, pr.visiting_person_name,
            pr.other_id_type, pr.other_id_number, pr.other_id_image_location
        FROM passes p
        INNER JOIN persons pr ON p.assigned_to = pr.id
        WHERE p.number = %s;
        """
        arg = (id_number, )
        cursor.execute(sql, arg)
        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_with_aadhar", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_pass | Execution time: {execution_time}ms", flush=True)

    return result

def get_person_details_with_person_id(person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_with_person_id", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = """SELECT 
            p.type as pass_type, p.sub_type as pass_sub_type, p.number as pass_number, p.assigned_to, 
            p.pass_start_date, p.pass_end_date, p.pass_issue_date, p.pass_image_location,
            pr.created_by, pr.date_created, pr.person_name, 
            pr.person_image_location, pr.guardians_name, pr.address, 
            pr.aadhar_number, pr.aadhar_image_location, 
            pr.drivers_license_number, pr.drivers_license_image, 
            pr.id, pr.enrollment_id, pr.gender, pr.vid, 
            pr.dob, pr.mobile_number, pr.visiting_person_name,
            pr.other_id_type, pr.other_id_number, pr.other_id_image_location
        FROM passes p
        INNER JOIN persons pr ON p.assigned_to = pr.id
        WHERE pr.id = %s;
        """
        arg = (person_id, )
        cursor.execute(sql, arg)
        result = cursor.fetchone()
        if result is not None:
            # Fetch column names
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_with_person_id")
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_with_person_id | Execution time: {execution_time}ms", flush=True)
    return result

def get_all_persons_details():
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_persons_details", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = """SELECT 
                pr.created_by, pr.date_created, pr.person_name, 
                pr.person_image_location, pr.aadhar_number, pr.aadhar_image_location, 
                pr.drivers_license_number, pr.drivers_license_image, 
                pr.id, pr.mobile_number, pr.gender, pr.guardians_name, pr.address,
                pr.visiting_person_name, pr.other_id_type, pr.other_id_number, pr.other_id_image_location,
                p.number as pass_number, p.type as pass_type, p.pass_image_location, u.user_name
            FROM persons pr
            LEFT JOIN passes p ON pr.id = p.assigned_to
            INNER JOIN users u ON pr.created_by = u.id 
            """
        arg = ()
        cursor.execute(sql, arg)
        rows = cursor.fetchall()  # Fetch all rows
        column_names = [desc[0] for desc in cursor.description]

        if not rows:  # Check if rows exist
            print("No rows returned in get all person details", flush=True)
            return {"Status": "Success", "Details": []}  # Return an empty list

            # Convert rows into a list of dictionaries
        result = [dict(zip(column_names, row)) for row in rows]
        person_list = []
        if len(result) > 0:
            for person in result:
                if person.get('date_created') is not None:
                    date_created = person.get('date_created').strftime('%d/%m/%Y %H:%M')# entry_time.strftime('%d %b, %Y %I:%M %p')
                    person.update({'date_created':date_created})

                if person.get('person_image_location') is not None:
                    person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"],
                                                     os.path.basename(person.get('person_image_location').strip('/'))])
                    person.update({'person_image_location': person_image})

                if person.get('vehicle_image_location') is not None:
                    vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"],
                                                      os.path.basename(person.get('vehicle_image_location').strip('/'))])
                    person.update({'vehicle_image_location': vehicle_image})

                primary_id_number = next((value for key, value in person.items()
                                          if key in ['aadhar_number', 'drivers_license_number', 'other_id_number',
                                                     'pass_number']
                                          and value is not None), None)
                #print(f'primary id number: {primary_id_number}')

                # Filter valid image locations
                primary_id_image = next((value for key, value in person.items()
                                         if key in ['aadhar_image_location', 'drivers_license_image',
                                                    'other_id_image_location',
                                                    'pass_image_location'] and value is not None), None)

                # Filter valid image locations
                id_type_mapping = {
                    'aadhar_image_location': 'Aadhar',
                    'drivers_license_image': 'Drivers License',
                    'pass_image_location': 'Pass',
                    'other_id_image_location': 'Other ID'
                }

                # Find the first non-None value and return its corresponding label
                primary_id_type = next(
                    (id_type_mapping[key] for key, value in person.items() if
                     key in id_type_mapping and value is not None),
                    None
                )

                if primary_id_image is not None:
                    person.update({'primary_id_image': primary_id_image})

                person.update({'primary_id_number': primary_id_number})
                person.update({'primary_id_type': primary_id_type})
                person_list.append(person)
        result = {"Status": "Success", "Details": person_list}
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_persons_details", flush=True)
        return_connection_to_pool(db_connection)
    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_persons_details | Execution time: {execution_time}ms", flush=True)
    return result


def get_person_details_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_person_details_by_date", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = ''' select p.person_name, p.person_image_location, p.gender, t.vehicle_number_plate, t.traveler_type, p.aadhar_number, p.aadhar_image_location, p.drivers_license_number, 
            p.drivers_license_image, t.entry_time, p.mobile_number, v.vehicle_image_location, t.exit_time, u.user_name, t.visit_duration from trips t
            join persons p on p.id = t.person_id
            left join vehicles v on t.vehicle_number_plate = v.vehicle_number_plate
            left join users u on t.created_by = u.id
            where t.entry_time between %s and %s
            order by t.entry_time desc; '''
                
        arg = [start_date, end_date]
        cursor.execute(sql,arg)
        column_names = [desc[0] for desc in cursor.description]
        result = cursor.fetchall()
        person_list = []
        if "overstay_minutes" not in column_names:
            column_names.append("overstay_minutes")

        if len(result) > 0:
            for person in result: 
                person = list(person)
                #print(person) 
                 
                person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(person[1].rstrip('/'))])
                person[1] = person_image
                entry_time = person[9]

                if person[12] is not None:
                    exit_time = person[12]  # Also a datetime object
                    # Calculate elapsed time in minutes
                    elapsed_time_minutes = (exit_time - entry_time).total_seconds() / 60
                    #person[14] = str(overstay_minutes)
                else:
                    #overstay_minutes = 0
                    current_time = datetime.now()
                    elapsed_time_minutes = (current_time - entry_time).total_seconds() / 60

                expected_visit_duration = person[14].total_seconds() / 60
                overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))

                entry_time = entry_time.strftime('%d-%m-%Y %H:%M:%S')#strftime('%d %b, %Y %I:%M %p')
                person[9] = entry_time
                                
                if person[11] is not None:
                    vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(person[11].rstrip('/'))])
                    person[11] = vehicle_image

                if person[12] is not None:
                    exit_time = exit_time.strftime('%d-%m-%Y %H:%M:%S')#strftime('%d %b, %Y %I:%M %p')
                    person[12] = exit_time 
                else:
                    exit_time = "Not Closed"
                    person[12] = exit_time
                #person[14] = str(person[14])
                person[14] = "{:02d}:{:02d}".format(*divmod(int(person[14].total_seconds() // 60), 60))
                person.append(overstay_minutes)
                person_list.append(dict(zip(column_names, person)))

        else:
            print("No records found")
            person_list.append({
                'gender': 'No records found',
                'vehicle_plate_number': 'No records found',
                'traveler_type': 'No records found',
                'entry_time': 'No records found',
                'exit_time': 'No records found',
                'dob': 'No records found',
                'overstay_minutes': 0,
                'visit_duration': 'No records found'
            })
        
        # print("person_list: ", person_list)
        result = {"Status": "Success", "Details": person_list}

    except (Exception, psycopg2.Error) as error:
        print("error: ", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        # closing database connection.
        if cursor:
            cursor.close()
            print("cursor closed in get_person_details_by_date", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_person_details_by_date | Execution time: {execution_time}ms", flush=True)

    return result


def get_known_person_trips(person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_known_person_trips", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''SELECT entry_time FROM trips WHERE person_id = %s ORDER BY entry_time DESC LIMIT 3;'''

        arg = [person_id, ]
        cursor.execute(sql, arg)
        result = cursor.fetchall()
        print("known person trips: ", result, flush=True)
        if result:
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": "No trips found"}

        # return result

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}


    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_known_person_trips")
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_known_person_trips | Execution time: {execution_time}ms",
          flush=True)

    return result


def insert_manual_vehicle_entry(user_id, vNumber, vMake, vImage, person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting insert_manual_vehicle_entry", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    
    vehicle_number = vNumber
    vehicle_image_actual_location = vImage
    vehicle_make = vMake
    vehicle_model = ''
    vehicle_color = ''
    vehicle_type = 'TempType'
    registered_to = ""
    registration_number = ""
    vehicle_owner = person_id
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()


        sql = '''INSERT INTO vehicles (created_by, vehicle_number_plate, vehicle_image_location, vehicle_make, vehicle_model, vehicle_color, vehicle_type, vehicle_registered_to, vehicle_registration_number, vehicle_owner_id) 
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *; '''

        arg = (user_id, vehicle_number, vehicle_image_actual_location, vehicle_make, vehicle_model, vehicle_color, vehicle_type, registered_to, registration_number, vehicle_owner)

        cursor.execute(sql,arg)
        inserted_data = cursor.fetchone()
        db_connection.commit()
        count = cursor.rowcount

        result = {"Status": "Success", "Insert_Count": count, "Details": inserted_data}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Insert_Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in insert_manual_vehicle_entry", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed insert_manual_vehicle_entry | Execution time: {execution_time}ms",
          flush=True)

    return result


def insert_new_vehicle_record(user_id, form):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting insert_new_vehicle_record", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    print('insert new vehicle record form: ', form)
    
    vehicle_id = form.get('vehicle_id')
    if vehicle_id is not None:
        print('vehicle_id:', vehicle_id)

    person_id = form.get('person_id')
    print('person_id:', person_id)

    vehicle_number = form.get('vehicle_number').strip()
    print('vehicle_number:', vehicle_number)
    
    vehicle_image_actual_location =os.path.sep.join([app.config["KNOWN_VEHICLES"],os.path.basename(form.get('vehicle_image'))])
    print('vehicle_image:', vehicle_image_actual_location)
    
    vehicle_make = form.get('vehicle_make')
    if vehicle_make is not None:
        print('vehicle_make:', vehicle_make)

    vehicle_model = form.get('vehicle_model')
    if vehicle_model is not None:
        print('vehicle_model:', vehicle_model)

    vehicle_color = form.get('vehicle_color')
    if vehicle_color is not None:
        print('vehicle_color:', vehicle_color)

    vehicle_type = form.get('vehicle_type')
    registered_to = form.get('vehicle_owner_name')
    rc_number_raw = form.get('vehicle_registration_number')
    rc_number = rc_number_raw.strip() or None if rc_number_raw is not None else None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        if vehicle_id is not None:

            sql = ''' UPDATE anpr_vehicle_readings set status = 'Processed' where id = %s; '''
            arg = [vehicle_id,]
            cursor.execute(sql,arg)
            db_connection.commit()
            count = cursor.rowcount

        sql = '''INSERT INTO vehicles (created_by, vehicle_number_plate, vehicle_image_location, vehicle_make, vehicle_color, 
                vehicle_registered_to, vehicle_owner_id, vehicle_type, vehicle_registration_number, vehicle_model) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *; '''

        arg = (user_id, vehicle_number, vehicle_image_actual_location, vehicle_make, vehicle_color, registered_to,
               person_id, vehicle_type, rc_number, vehicle_model,)
        print("about to insert new vehicle")
        cursor.execute(sql,arg)
        inserted_data = cursor.fetchone()

        # Get column names and create dictionary
        if inserted_data:
            column_names = [desc[0] for desc in cursor.description]
            inserted_data_dict = dict(zip(column_names, inserted_data))
        else:
            inserted_data_dict = {}

        db_connection.commit()
        count = cursor.rowcount

        result = {"Status": "Success", "Insert_Count": count, "Details": inserted_data_dict}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Insert_Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in insert_new_vehicle_record")
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed insert_new_vehicle_record | Execution time: {execution_time}ms",
          flush=True)

    return result
    

def update_existing_vehicle_record(form, new_vehicle_owner, user_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting update_existing_vehicle_record", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    def _normalize_optional(value):
        if value is None:
            return None
        normalized = str(value).strip()
        if normalized == '' or normalized.lower() in ('none', 'null'):
            return None
        return normalized

    vehicle_number = _normalize_optional(form.get('vehicle_number'))
    vehicle_image_url = form.get('vehicle_image_url')
    vehicle_image_actual_location = os.path.sep.join([app.config["KNOWN_VEHICLES"], os.path.basename(vehicle_image_url)]) if vehicle_image_url else app.config["VEHICLE_IMAGE_NOT_AVAILABLE_ACTUAL_PATH"]
    vehicle_make = _normalize_optional(form.get('make'))
    vehicle_model = _normalize_optional(form.get('vehicle_model'))
    vehicle_color = _normalize_optional(form.get('color'))
    vehicle_type = _normalize_optional(form.get('vehicle_type'))
    registered_to = _normalize_optional(form.get('vehicle_owner_name'))
    rc_number_raw = form.get('vehicle_registration_number')
    rc_number = rc_number_raw.strip() or None if rc_number_raw is not None else None
    vehicle_owner_id = new_vehicle_owner

    print("update_existing_vehicle_record normalized inputs: vehicle_number=%s, vehicle_owner_id=%s, vehicle_make=%s, vehicle_model=%s, vehicle_color=%s, vehicle_type=%s, registered_to=%s, rc_number=%s" % (
        vehicle_number,
        vehicle_owner_id,
        vehicle_make,
        vehicle_model,
        vehicle_color,
        vehicle_type,
        registered_to,
        rc_number
    ), flush=True)

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        # Update the most recent row for this plate+owner combination.
        # If no such row exists (new owner), rowcount will be 0 and we INSERT instead.
        sql = '''UPDATE vehicles
                 SET vehicle_image_location = %s,
                     vehicle_make = %s,
                     vehicle_model = %s,
                     vehicle_color = %s,
                     vehicle_type = %s,
                     vehicle_registered_to = %s,
                     vehicle_registration_number = %s
                 WHERE id = (
                     SELECT id FROM vehicles
                     WHERE vehicle_number_plate = %s AND vehicle_owner_id = %s
                     ORDER BY date_created DESC
                     LIMIT 1
                 )
                 RETURNING *;'''
        arg = (vehicle_image_actual_location, vehicle_make, vehicle_model, vehicle_color, vehicle_type,
               registered_to, rc_number, vehicle_number, vehicle_owner_id)
        print("about to update existing owner-vehicle association", flush=True)
        cursor.execute(sql, arg)
        updated_data = cursor.fetchone()
        print("update_existing_vehicle_record update result for plate-owner pair (%s, %s): %s" % (
            vehicle_number,
            vehicle_owner_id,
            updated_data
        ), flush=True)

        if updated_data:
            column_names = [desc[0] for desc in cursor.description]
            updated_data_dict = dict(zip(column_names, updated_data))
            db_connection.commit()
            count = cursor.rowcount
            print("update_existing_vehicle_record completed UPDATE for existing owner association | rowcount=%s" % count, flush=True)
            result = {"Status": "Success", "Insert_Count": 0, "Update_Count": count, "Action": "Updated", "Details": updated_data_dict}
        else:
            # No row for this plate+owner: new owner association, insert to preserve history.
            print("update_existing_vehicle_record did not find an existing plate-owner association; attempting INSERT for a new owner mapping", flush=True)
            sql = '''INSERT INTO vehicles (created_by, vehicle_number_plate, vehicle_image_location, vehicle_make, vehicle_color,
                           vehicle_registered_to, vehicle_owner_id, vehicle_type, vehicle_registration_number, vehicle_model)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *;'''
            arg = (user_id, vehicle_number, vehicle_image_actual_location, vehicle_make, vehicle_color, registered_to,
                   vehicle_owner_id, vehicle_type, rc_number, vehicle_model,)
            print("about to insert new vehicle rider association", flush=True)
            cursor.execute(sql, arg)
            inserted_data = cursor.fetchone()
            print("update_existing_vehicle_record insert result for new plate-owner pair (%s, %s): %s" % (
                vehicle_number,
                vehicle_owner_id,
                inserted_data
            ), flush=True)

            if inserted_data:
                column_names = [desc[0] for desc in cursor.description]
                inserted_data_dict = dict(zip(column_names, inserted_data))
            else:
                inserted_data_dict = {}

            db_connection.commit()
            count = cursor.rowcount
            print("update_existing_vehicle_record completed INSERT for new owner association | rowcount=%s" % count, flush=True)
            result = {"Status": "Success", "Insert_Count": count, "Update_Count": 0, "Action": "Inserted", "Details": inserted_data_dict}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Insert_Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in update_existing_vehicle_record", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed update_existing_vehicle_record | Execution time: {execution_time}ms",
          flush=True)

    return result

def check_if_vehicle_is_in_our_system(vehicle_plate_number, owner_id=None):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting check_if_vehicle_is_in_our_system", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        result = None

        if owner_id is not None:
            sql = '''select * from vehicles
                     where vehicle_number_plate = %s and vehicle_owner_id = %s
                     ORDER BY date_created DESC LIMIT 1;'''
            arg = (vehicle_plate_number, owner_id)
            cursor.execute(sql,arg)
            result = cursor.fetchone()

        if result is None:
            # Fallback to previous behavior when owner-specific mapping is unavailable.
            sql = '''select * from vehicles where vehicle_number_plate = %s ORDER BY date_created DESC LIMIT 1;'''
            arg = (vehicle_plate_number,)
            cursor.execute(sql,arg)
            result = cursor.fetchone()

        print("result: ", result, flush=True)
        if result is not None:
            column_names = [desc[0] for desc in cursor.description]
            result = dict(zip(column_names, result))     
            #print("vehicle_details: ", result)
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": None}
 
    
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in check_if_vehicle_is_in_our_system", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed check_if_vehicle_is_in_our_system | Execution time: {execution_time}ms",
          flush=True)
    return result


def get_vehicle_details_from_anpr(vehicle_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_vehicle_details_from_anpr", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select * from anpr_vehicle_readings where plate = %s;'''
        arg = (vehicle_id,)
        cursor.execute(sql,arg)
        
        result = cursor.fetchone()
        column_names = [desc[0] for desc in cursor.description]
        
        if result is not None:
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": {}, "Count": 0}
        # print("vehicle_details: ", result)
        print("vehicle_details: ", result, flush=True)
        
    
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_vehicle_details_from_anpr", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_vehicle_details_from_anpr | Execution time: {execution_time}ms",
          flush=True)

    return result

def get_vehicle_details_from_anpr_by_id(vehicle_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_vehicle_details_from_anpr_by_id", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        #db_connection = connect_to_db()
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = '''SELECT id, file, plate,timestamp FROM anpr_vehicle_readings WHERE id = %s;'''
        arg = (vehicle_id,)
        cursor.execute(sql,arg)
        result = cursor.fetchone()
        column_names = [desc[0] for desc in cursor.description]
        result = dict(zip(column_names, result))
        #print("vehicle_details: ", result)
        #return result
        result = {"Status": "Success", "Details": result}
 
    
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_vehicle_details_from_anpr_by_id", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_vehicle_details_from_anpr_by_id | Execution time: {execution_time}ms",
          flush=True)
    return result


def get_primary_vehicle_for_person(person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_primary_vehicle_for_person", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select vehicle_number_plate, vehicle_make, vehicle_model, vehicle_color, vehicle_type, vehicle_image_location, vehicle_registered_to, vehicle_registration_number from vehicles 
            where vehicle_owner_id = %s ORDER BY date_created DESC LIMIT 1;'''
        arg = (person_id, )

        cursor.execute(sql, arg)

        result = cursor.fetchone()
        column_names = [desc[0] for desc in cursor.description]
        if result is not None:
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": {}, "Count": 0}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_primary_vehicle_for_person", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_primary_vehicle_for_person | Execution time: {execution_time}ms",
          flush=True)
    return result


def get_vehicle_details_from_vehicles(vehicle_plate_number):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_vehicle_details_from_vehicles", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select vehicle_number_plate, make, model, color, vehicle_type, vehicle_image_location, vehicle_registered_to, vehicle_registration_number from 
                    vehicles where vehicle_number_plate = %s;'''
        arg = (vehicle_plate_number,)
        cursor.execute(sql,arg)

        result = cursor.fetchone()
        column_names = [desc[0] for desc in cursor.description]

        if result is not None:
            result = dict(zip(column_names, result))
            result = {"Status": "Success", "Details": result}
        else:
            result = {"Status": "Success", "Details": {}, "Count": 0}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}


    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_vehicle_details_from_vehicles", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_vehicle_details_from_vehicles | Execution time: {execution_time}ms",
          flush=True)
    return result            

def get_vehicle_details_from_vehicles_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_vehicle_details_from_vehicles_by_date", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = ''' select p.person_name, p.person_image_location, v.vehicle_number_plate, v.vehicle_make, v.vehicle_model, v.vehicle_color, t.entry_time, t.exit_time, 
                    v.vehicle_registered_to, v.vehicle_registration_number, v.vehicle_image_location, u.user_name, t.visit_duration from trips t 
                    join persons p on p.id = t.person_id 
                    join vehicles v on t.vehicle_number_plate = v.vehicle_number_plate
                    left join users u on t.created_by = u.id
                    where t.entry_time between %s and %s
                    and t.traveler_type = 'Driver'
                    order by t.entry_time desc, v.vehicle_number_plate; '''
                
        arg = (start_date, end_date)
        cursor.execute(sql,arg)
        column_names = [desc[0] for desc in cursor.description]
        result = cursor.fetchall()
        if "overstay_minutes" not in column_names:
            column_names.append("overstay_minutes")
        vehicle_list = []

        if len(result) > 0:
            for vehicle in result: 
                vehicle = list(vehicle)
                #print(person) 
                 
                person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(vehicle[1].rstrip('/'))])
                vehicle[1] = person_image
                # Get entry time (Assuming it's a datetime object)
                entry_time = vehicle[6]

                # Initialize Overstay Duration
                #vehicle[12] = "0"

                if vehicle[7] is not None:
                    exit_time = vehicle[7]  # Also a datetime object
                    # Calculate elapsed time in minutes
                    elapsed_time_minutes = (exit_time - entry_time).total_seconds() / 60
                    #expected_visit_duration = vehicle[12].total_seconds() / 60
                    #overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))
                else:
                    current_time = datetime.now()
                    elapsed_time_minutes = (current_time - entry_time).total_seconds() / 60
                    #overstay_minutes = 0
                expected_visit_duration = vehicle[12].total_seconds() / 60
                overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))

                vehicle[6] = entry_time.strftime('%d-%m-%Y %H:%M:%S')#strftime('%d %b, %Y %I:%M %p')#strftime('%d-%m-%Y %H:%M:%S')

                if vehicle[7] is not None:
                    vehicle[7] = exit_time.strftime('%d-%m-%Y %H:%M:%S')#strftime('%d %b, %Y %I:%M %p')

                else:
                    exit_time = "Not Closed"
                    vehicle[7] = exit_time

                if vehicle[10] is not None:
                    vehicle_image = os.path.sep.join([app.config["KNOWN_VEHICLE_PATH_FOR_HTML"], os.path.basename(vehicle[10].rstrip('/'))])
                    vehicle[10] = vehicle_image

                #vehicle[12] = str(vehicle[12])
                vehicle[12] = "{:02d}:{:02d}".format(*divmod(int(vehicle[12].total_seconds() // 60), 60))
                vehicle.append(overstay_minutes)
                #print("vehicle: ", vehicle)
                vehicle_list.append(dict(zip(column_names, vehicle)))
            print("vehicle list in report: ", vehicle_list, flush=True)

        else:
            print("No records found")
            vehicle_list.append({
                'vehicle_driver': 'No records found',
                #'vehicle_plate_number': 'No records found',
                'vehicle_make': 'No records found',
                'vehicle_model': 'No records found',
                'vehicle_color': 'No records found',
                'entry_time': 'No records found',
                'exit_time': 'No records found',
                'vehicle_owner': 'No records found',
                'vehicle_registered_to': 'No records found',
                'vehicle_registration_number': 'No records found',
                'overstay_minutes': 0,
                'visit_duration': 'No records found'
            })

            
        # print("vehicle_list: ", vehicle_list)
        result = {"Status": "Success", "Details": vehicle_list}

    except (Exception, psycopg2.Error) as error:
        print("Error: ", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_vehicle_details_from_vehicles_by_date", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_vehicle_details_from_vehicles_by_date | Execution time: {execution_time}ms",
          flush=True)

    return result

def get_all_vehicles_from_anpr_by_date_paginated(
    start_date,
    end_date,
    start=0,
    length=50,
    search_value="",
    order_col_idx=3,
    order_dir="desc",
):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_vehicles_from_anpr_by_date_paginated", flush=True)

    db_connection = None
    cursor = None
    result = None

    order_map = {
        0: "a.id",
        2: "a.plate",
        3: "a.timestamp",
        4: "a.camera_id",
    }
    order_col = order_map.get(int(order_col_idx), "a.timestamp")
    order_dir = "ASC" if str(order_dir).lower() == "asc" else "DESC"

    base_from = """
        FROM anpr_vehicle_readings a
        WHERE DATE(a.timestamp) BETWEEN %s AND %s
    """
    where_params = [start_date, end_date]

    search_sql = ""
    search_params = []
    if search_value:
        search_sql = """
            AND (
                COALESCE(a.plate, '') ILIKE %s OR
                COALESCE(a.camera_id::text, '') ILIKE %s OR
                COALESCE(a.file, '') ILIKE %s OR
                COALESCE(a.id::text, '') ILIKE %s
            )
        """
        like_term = f"%{search_value}%"
        search_params = [like_term] * 4

    select_sql = """
        SELECT a.id, a.file, a.plate, a.timestamp, a.camera_id
    """

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        total_sql = f"SELECT COUNT(*) AS total {base_from}"
        cursor.execute(total_sql, tuple(where_params))
        records_total = cursor.fetchone()["total"]

        filtered_sql = f"SELECT COUNT(*) AS total {base_from} {search_sql}"
        cursor.execute(filtered_sql, tuple(where_params + search_params))
        records_filtered = cursor.fetchone()["total"]

        data_sql = f"""
            {select_sql}
            {base_from}
            {search_sql}
            ORDER BY {order_col} {order_dir}, a.id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_sql, tuple(where_params + search_params + [int(length), int(start)]))
        rows = cursor.fetchall()

        vehicle_list = []
        for vehicle in rows:
            if vehicle.get("timestamp") is not None:
                timestamp_obj = parser.parse(str(vehicle["timestamp"]))
                vehicle["timestamp"] = timestamp_obj.strftime("%Y-%m-%d %H:%M:%S")

            if vehicle.get("file"):
                vehicle["file"] = os.path.sep.join([
                    app.config["SCREENSHOTS_FOLDER"],
                    os.path.basename(vehicle["file"])
                ])

            vehicle_list.append(vehicle)

        result = {
            "Status": "Success",
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "Details": vehicle_list,
        }

    except (Exception, psycopg2.Error) as error:
        print("Error in get_all_vehicles_from_anpr_by_date_paginated:", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": str(error)}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_vehicles_from_anpr_by_date_paginated | Execution time: {execution_time}ms", flush=True)

    return result


def get_all_vehicles_from_anpr_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_vehicles_from_anpr_by_date", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''SELECT id, file, plate, timestamp, camera_id FROM anpr_vehicle_readings 
                WHERE DATE(timestamp) BETWEEN %s AND %s ORDER BY timestamp desc;'''
        args = (start_date, end_date)
        cursor.execute(sql, args)
        rows = cursor.fetchall()  # Fetch all rows
        column_names = [desc[0] for desc in cursor.description]
        # Convert rows into a list of dictionaries
        result = [dict(zip(column_names, row)) for row in rows]
        print("all_vehicles from anpr: ", result, flush=True)

        if not rows:  # Check if rows exist
            print("No matching records found", flush=True)

            # End logging
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_all_vehicles_from_anpr_by_date | Execution time: {execution_time}ms",
                flush=True)

            return {"Status": "Success", "Details": []}  # Return an empty list

        anpr_list = []
        if len(result) > 0:
            for vehicle in result:
                if vehicle.get('timestamp') is not None:
                    #timestamp_str = vehicle.get('timestamp')
                    #timestamp_obj = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S.%f%z')
                    #formatted_timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')

                    timestamp_str = vehicle.get('timestamp')
                    timestamp_obj = parser.parse(timestamp_str)
                    formatted_timestamp = timestamp_obj.strftime('%Y-%m-%d %H:%M:%S')

                    vehicle.update({'timestamp': formatted_timestamp})
                if vehicle.get('file'):
                    file = os.path.sep.join([app.config["SCREENSHOTS_FOLDER"], os.path.basename(vehicle.get('file'))])
                    vehicle.update({'file': file})
                anpr_list.append(vehicle)

                # Assuming timestamp is a string in the format '2022-12-08 02:49:36.137264+00:00'

            # print("trip_list: ", trip_list, flush=True)
        result = {"Status": "Success", "Details": anpr_list}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_vehicles_from_anpr_by_date", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_vehicles_from_anpr_by_date | Execution time: {execution_time}ms", flush=True)

    return result


def count_all_vehicles_from_anpr_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting count_all_vehicles_from_anpr_by_date", flush=True)
    db_connection = None
    cursor = None
    result = None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''SELECT COUNT(*) FROM anpr_vehicle_readings
                WHERE DATE(timestamp) BETWEEN %s AND %s;'''
        args = (start_date, end_date)
        cursor.execute(sql, args)
        result = {"Status": "Success", "Details": cursor.fetchone()[0]}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in count_all_vehicles_from_anpr_by_date", flush=True)
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed count_all_vehicles_from_anpr_by_date | Execution time: {execution_time}ms", flush=True)

    return result


def get_all_vehicles_from_anpr():
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_vehicles_from_anpr", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''SELECT id, file, plate, timestamp, camera_id FROM anpr_vehicle_readings WHERE "timestamp"::timestamptz >= NOW() - INTERVAL '1 hour' ORDER BY "timestamp"::timestamptz desc;'''
        arg = ()
        cursor.execute(sql,arg)
        result = cursor.fetchall()
        result = {"Status": "Success", "Details": result}
     
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_vehicles_from_anpr", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_vehicles_from_anpr | Execution time: {execution_time}ms", flush=True)

    return result

def get_all_trips_for_autocomplete(term):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_trips_for_autocomplete", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        cursor.execute("SELECT t.id, t.vehicle_number_plate FROM trips t WHERE t.vehicle_number_plate ILIKE %s AND t.is_finished = 'f' and t.traveler_type in ('Driver','Pedestrian') ORDER BY id", ('%' + term + '%',))
        result = cursor.fetchall()
        #print("all_vehicles: ", result)
        result = {"Status": "Success", "Details": result}
     
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_trips_for_autocomplete", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_trips_for_autocomplete | Execution time: {execution_time}ms", flush=True)

    return result

def get_all_vehicles_details_for_autocomplete(term):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_vehicles_details_for_autocomplete", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        cursor.execute("SELECT id, plate FROM anpr_vehicle_readings WHERE plate ILIKE %s AND status = 'new' ORDER BY id", ('%' + term + '%',))
        result = cursor.fetchall()
        #print("all_vehicles: ", result)
        result = {"Status": "Success", "Details": result}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_vehicles_details_for_autocomplete", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_all_vehicles_details_for_autocomplete | Execution time: {execution_time}ms",flush=True)

    return result


def get_all_open_trips_for_autocomplete(term):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_all_open_trips_for_autocomplete", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = '''Select t.id, t.date_created, p.person_name, p.person_image_location, t.traveler_type, t.vehicle_number_plate from trips t, persons p 
            where t.is_finished = 'f' and t.traveler_type = 'Driver' and t.person_id = p.id ORDER BY t.date_created; '''
        arg = ()
        cursor.execute(sql,arg)
        result = cursor.fetchall()
        #print("all_vehicles: ", result)
        result = {"Status": "Success", "Details": result}
     
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
 
        #result = error

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_all_open_trips_for_autocomplete", flush=True)
            return_connection_to_pool(db_connection)

        # End logging
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed get_all_open_trips_for_autocomplete | Execution time: {execution_time}ms", flush=True)

    return result                        


def insert_new_trip_record(user_id, session_values_json_redis):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting insert_new_trip_record", flush=True)
    db_connection = None
    cursor = None
    result = None
    driver_trip_id = None
    
    person_id =  session_values_json_redis.get('person_id')
    vehicle_plate_number = session_values_json_redis.get('vehicle_plate_number')   
    entry_time = session_values_json_redis.get('entry_time')
    expected_visit_duration = session_values_json_redis.get('expected_visit_duration')
    coming_from = session_values_json_redis.get('coming_from')
    going_to = session_values_json_redis.get('going_to')
    trip_reason = session_values_json_redis.get('trip_reason')
    trip_type = session_values_json_redis.get('trip_type')

    #permit_image = session_values_json_redis.get("permit_img_file_path")
    permit_image = session_values_json_redis.get("permit_img_file_path")
    permit_type = session_values_json_redis.get("primary_id_type")
    print(f'permit_type: {permit_type}', flush=True)

    traveler_type = session_values_json_redis.get('traveler_type')

    
    if session_values_json_redis.get('male_passengers'):
        number_of_male_passengers = session_values_json_redis.get('male_passengers')
    else:
        number_of_male_passengers = None
    if session_values_json_redis.get('female_passengers'):
        number_of_female_passengers = session_values_json_redis.get('female_passengers')
    else:
        number_of_female_passengers = None
    if session_values_json_redis.get('child_passengers'):
        number_of_child_passengers = session_values_json_redis.get('child_passengers')
    else:
        number_of_child_passengers = None
    token_number = session_values_json_redis.get('token_number')
    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        
        if permit_image:
            sql = ''' INSERT INTO trips (created_by, person_id, vehicle_number_plate, entry_time, coming_from, going_to, traveler_type, number_of_male_passengers, number_of_female_passengers, number_of_child_passengers, trip_reason,
                trip_permit_type, trip_permit_image_location, driver_trip_id, visit_duration, token_number) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *; '''

            arg = [user_id, person_id, vehicle_plate_number, entry_time, coming_from, going_to, traveler_type, number_of_male_passengers, number_of_female_passengers, number_of_child_passengers, trip_reason, 
                permit_type, permit_image, driver_trip_id, expected_visit_duration, token_number]
        else:
            sql = ''' INSERT INTO trips (created_by, person_id, vehicle_number_plate, entry_time, coming_from, going_to, traveler_type, number_of_male_passengers, number_of_female_passengers, number_of_child_passengers, trip_reason,
                trip_permit_type, driver_trip_id, visit_duration, token_number) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning *; '''

            arg = [user_id, person_id, vehicle_plate_number, entry_time, coming_from, going_to, traveler_type, number_of_male_passengers, number_of_female_passengers, number_of_child_passengers, trip_reason, 
                permit_type, driver_trip_id, expected_visit_duration, token_number]

        cursor.execute(sql,arg)
        inserted_data = cursor.fetchone()
        count = cursor.rowcount
        print ("insert new trip record: ", inserted_data, flush=True)
        new_trip_id = inserted_data[0]
        print("new_trip_id: ", new_trip_id)

        db_connection.commit()
        result = {"Status": "Success", "Insert_Count": count, "Details": inserted_data}
        
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error)
        if str(error).split("DETAIL:")[1] is not None:
            error = str(error).split("DETAIL:")[1]
            print("error in sql: ", error)

        if db_connection:
            db_connection.rollback()

        result = {"Status": "Fail", "Insert_Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in insert_new_trip_record", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed insert_new_trip_record | Execution time: {execution_time}ms", flush=True)

    return result          


DATE_PRESET_VALUES = frozenset({
    'today', 'yesterday', 'last_7_days', 'last_30_days', 'this_month', 'last_month', 'not_closed',
})

UNFINISHED_TRIPS_DATE_FILTER_COLS = {6: 't.entry_time', 7: 't.exit_time'}
TRIP_REPORT_DATE_FILTER_COLS = {10: 't.entry_time', 11: 't.exit_time'}


def _date_preset_sql(column_expr, preset):
    preset = (preset or '').strip().lower()
    if preset not in DATE_PRESET_VALUES:
        return None
    if preset == 'not_closed':
        return "t.exit_time IS NULL", []
    if preset == 'today':
        return (
            f"({column_expr} >= CURRENT_DATE AND {column_expr} < CURRENT_DATE + INTERVAL '1 day')",
            [],
        )
    if preset == 'yesterday':
        return (
            f"({column_expr} >= CURRENT_DATE - INTERVAL '1 day' AND {column_expr} < CURRENT_DATE)",
            [],
        )
    if preset == 'last_7_days':
        return f"({column_expr} >= CURRENT_DATE - INTERVAL '6 days')", []
    if preset == 'last_30_days':
        return f"({column_expr} >= CURRENT_DATE - INTERVAL '29 days')", []
    if preset == 'this_month':
        return (
            f"({column_expr} >= DATE_TRUNC('month', CURRENT_DATE) "
            f"AND {column_expr} < DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')",
            [],
        )
    if preset == 'last_month':
        return (
            f"({column_expr} >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '1 month' "
            f"AND {column_expr} < DATE_TRUNC('month', CURRENT_DATE))",
            [],
        )
    return None


# Expected-stay duration expressed as whole minutes (used by duration filters).
VISIT_DURATION_MINUTES_EXPR = "FLOOR(EXTRACT(EPOCH FROM COALESCE(t.visit_duration, interval '0')) / 60)"

def _build_duration_clause(minutes_expr, token):
    """Translate a duration filter token into SQL.

    Token grammar (built by the frontend stepper):
      D<days>        -> days component equals <days> (any hours)
      H<hours>       -> hours component equals <hours> (any days)
      D<days>H<hours>-> exact total duration

    The hours component is the "remainder hours" shown in the displayed
    "D days H hours" breakdown, so the filter matches what the user sees.
    """
    if not token:
        return None, None
    m = re.match(r'^D(\d+)H(\d+)$', token)
    if m:
        return f"({minutes_expr} = %s)", [int(m.group(1)) * 1440 + int(m.group(2)) * 60]
    m = re.match(r'^D(\d+)$', token)
    if m:
        return f"(FLOOR({minutes_expr} / 1440) = %s)", [int(m.group(1))]
    m = re.match(r'^H(\d+)$', token)
    if m:
        # Use MOD() instead of the % operator: psycopg2 treats a bare %
        # in the SQL string as a parameter placeholder and raises an error.
        return f"(FLOOR(MOD({minutes_expr}, 1440) / 60) = %s)", [int(m.group(1))]
    return None, None


def _append_column_filter_sql(column_filters, column_filter_sql, date_filter_cols, search_sql, search_params, duration_minutes_map=None):
    for col_idx, val in (column_filters or {}).items():
        col_idx = int(col_idx)
        val = (val or '').strip()
        if not val:
            continue

        if col_idx in date_filter_cols:
            preset_clause = _date_preset_sql(date_filter_cols[col_idx], val)
            if preset_clause:
                clause, extra_params = preset_clause
                search_sql += f" AND {clause}"
                search_params.extend(extra_params)
                continue
            # Date preset tokens must never fall through to ILIKE on formatted dates.
            if val.lower() in DATE_PRESET_VALUES:
                continue

        if duration_minutes_map and col_idx in duration_minutes_map:
            clause, params = _build_duration_clause(duration_minutes_map[col_idx], val)
            if clause:
                search_sql += f" AND {clause}"
                search_params.extend(params)
            continue

        clause = column_filter_sql.get(col_idx)
        if clause and val:
            search_sql += f" AND {clause}"
            search_params.append(f"%{val}%")
    return search_sql, search_params


def get_unfinished_trips_paginated(
    person_id=None,
    start=0,
    length=50,
    search_value="",
    order_col_idx=6,
    order_dir="desc",
    column_filters=None,
):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_unfinished_trips_paginated", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    column_filters = column_filters or {}

    overstay_expr = """
        GREATEST(
            0,
            EXTRACT(EPOCH FROM (COALESCE(t.exit_time, NOW()) - t.entry_time)) / 60
            - EXTRACT(EPOCH FROM COALESCE(t.visit_duration, interval '0')) / 60
        )
    """

    total_passengers_expr = """
        (COALESCE(t.number_of_male_passengers, 0)
         + COALESCE(t.number_of_female_passengers, 0)
         + COALESCE(t.number_of_child_passengers, 0))
    """

    primary_id_expr = "COALESCE(p.aadhar_number, p.drivers_license_number, p.other_id_number, pa.number)"

    permit_expr = "CASE WHEN t.trip_permit_image_location IS NOT NULL THEN 'Yes' ELSE 'No' END"

    # DataTables column index -> SQL sort expression
    order_map = {
        1: "p.person_name",
        2: TRIP_VEHICLE_PLATE_EXPR,
        3: "t.traveler_type",
        4: primary_id_expr,
        5: permit_expr,
        6: "t.entry_time",
        7: "t.exit_time",
        8: "t.visit_duration",
        9: overstay_expr,
        10: "p.visiting_person_name",
        11: "t.going_to",
        12: total_passengers_expr,
        13: "p.mobile_number",
        14: "u.user_name",
    }

    # DataTables column index -> SQL filter expression
    column_filter_sql = {
        1: "COALESCE(p.person_name, '') ILIKE %s",
        2: f"COALESCE({TRIP_VEHICLE_PLATE_EXPR}, '') ILIKE %s",
        3: "COALESCE(t.traveler_type, '') ILIKE %s",
        4: f"COALESCE({primary_id_expr}, '') ILIKE %s",
        5: f"{permit_expr} ILIKE %s",
        10: "COALESCE(p.visiting_person_name, '') ILIKE %s",
        11: "COALESCE(t.going_to, '') ILIKE %s",
        12: f"CAST({total_passengers_expr} AS TEXT) ILIKE %s",
        13: "COALESCE(p.mobile_number, '') ILIKE %s",
        14: "COALESCE(u.user_name, '') ILIKE %s",
    }

    # Duration columns (Expected Stay / Overstay) filter by component, not raw text.
    duration_minutes_map = {
        8: VISIT_DURATION_MINUTES_EXPR,
        9: f"FLOOR({overstay_expr})",
    }

    order_col = order_map.get(int(order_col_idx), "t.entry_time")
    order_dir = "ASC" if str(order_dir).lower() == "asc" else "DESC"

    base_from = """
        FROM trips t
        JOIN persons p ON p.id = t.person_id
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) *
            FROM vehicles
            ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC
        ) v ON t.vehicle_number_plate = v.vehicle_number_plate AND t.person_id = v.vehicle_owner_id
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate) *
            FROM vehicles
            WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> ''
            ORDER BY vehicle_number_plate, date_created DESC
        ) vp ON t.vehicle_number_plate = vp.vehicle_number_plate
        LEFT JOIN (
            SELECT DISTINCT ON (assigned_to) *
            FROM passes
            ORDER BY assigned_to, create_date DESC
        ) pa ON p.id = pa.assigned_to
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.is_finished = FALSE
    """

    where_params = []
    if person_id is not None:
        base_from += " AND t.person_id = %s"
        where_params.append(person_id)

    search_sql = ""
    search_params = []

    # global search box
    if search_value:
        search_sql += f"""
            AND (
                COALESCE(p.person_name, '') ILIKE %s OR
                COALESCE({TRIP_VEHICLE_PLATE_EXPR}, '') ILIKE %s OR
                COALESCE(t.traveler_type, '') ILIKE %s OR
                COALESCE(p.mobile_number, '') ILIKE %s OR
                COALESCE(t.going_to, '') ILIKE %s OR
                COALESCE(p.visiting_person_name, '') ILIKE %s OR
                COALESCE(u.user_name, '') ILIKE %s OR
                COALESCE(CAST(t.id AS TEXT), '') ILIKE %s OR
                COALESCE(""" + primary_id_expr + """, '') ILIKE %s
            )
        """
        like_term = f"%{search_value}%"
        search_params.extend([like_term] * 9)

    # per-column filters
    search_sql, search_params = _append_column_filter_sql(
        column_filters, column_filter_sql, UNFINISHED_TRIPS_DATE_FILTER_COLS, search_sql, search_params,
        duration_minutes_map=duration_minutes_map
    )

    select_sql = (
        """
        SELECT
            p.person_name, p.person_image_location, p.aadhar_number, p.aadhar_image_location,
            p.drivers_license_number, p.drivers_license_image, p.other_id_type, p.other_id_number,
            p.other_id_image_location, p.visiting_person_name AS purpose, p.mobile_number,
            pa.number AS pass_number, pa.pass_image_location,
            """
        + TRIP_VEHICLE_SELECT_FIELDS
        + f""",
            t.traveler_type, t.entry_time, t.exit_time, t.coming_from, t.going_to,
            t.number_of_male_passengers, t.number_of_female_passengers, t.number_of_child_passengers,
            t.id, t.visit_duration, t.token_number, t.driver_trip_id, t.trip_permit_type,
            t.trip_permit_image_location, t.created_by, u.user_name,
            CAST({overstay_expr} AS BIGINT) AS overstay_minutes
    """
    )

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        total_sql = f"SELECT COUNT(*) AS total {base_from}"
        cursor.execute(total_sql, tuple(where_params))
        records_total = cursor.fetchone()["total"]

        filtered_sql = f"SELECT COUNT(*) AS total {base_from} {search_sql}"
        cursor.execute(filtered_sql, tuple(where_params + search_params))
        records_filtered = cursor.fetchone()["total"]

        data_sql = f"""
            {select_sql}
            {base_from}
            {search_sql}
            ORDER BY {order_col} {order_dir}, t.id DESC
            LIMIT %s OFFSET %s
        """
        data_params = where_params + search_params + [int(length), int(start)]
        cursor.execute(data_sql, tuple(data_params))
        rows = cursor.fetchall()

        trip_list = []
        for trip in rows:
            if trip.get("person_image_location"):
                trip["person_image_location"] = os.path.sep.join([
                    app.config["KNOWN_PERSON_PATH_FOR_HTML"],
                    os.path.basename(trip["person_image_location"].rstrip("/"))
                ])
            if trip.get("vehicle_image_location"):
                trip["vehicle_image_location"] = vehicle_image_html_path(trip["vehicle_image_location"])

            entry_time = trip.get("entry_time")
            exit_time = trip.get("exit_time")
            now_time = datetime.now()
            elapsed_minutes = ((exit_time or now_time) - entry_time).total_seconds() / 60 if entry_time else 0

            visit_duration = trip.get("visit_duration")
            if isinstance(visit_duration, timedelta):
                expected_minutes = visit_duration.total_seconds() / 60
            elif isinstance(visit_duration, (int, float)):
                expected_minutes = float(visit_duration)
            else:
                expected_minutes = 0.0

            trip["visit_duration"] = expected_minutes
            # Overstay is computed once in SQL (CAST({overstay_expr} AS BIGINT)) so the
            # displayed value matches the Overstay filter exactly, regardless of timezone skew
            # between Python's datetime.now() and the server's NOW().
            trip["overstay_minutes"] = int(trip.get("overstay_minutes") or 0)

            trip["entry_time"] = entry_time.strftime("%d/%m/%Y %H:%M") if entry_time else "Not Available"
            trip["exit_time"] = exit_time.strftime("%d/%m/%Y %H:%M") if exit_time else "Not Closed"

            female = int(trip.get("number_of_female_passengers") or 0)
            child = int(trip.get("number_of_child_passengers") or 0)
            male = int(trip.get("number_of_male_passengers") or 0)
            trip["other_passengers"] = female + child
            trip["total_passengers"] = male + female + child

            trip["primary_id_number"] = (
                trip.get("aadhar_number")
                or trip.get("drivers_license_number")
                or trip.get("other_id_number")
                or trip.get("pass_number")
            )
            trip["primary_id_image"] = (
                trip.get("aadhar_image_location")
                or trip.get("drivers_license_image")
                or trip.get("other_id_image_location")
                or trip.get("pass_image_location")
            )

            trip_list.append(trip)

        result = {
            "Status": "Success",
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "Details": trip_list,
        }

    except (Exception, psycopg2.Error) as error:
        print("Error in get_unfinished_trips_paginated:", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": str(error)}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_unfinished_trips_paginated | Execution time: {execution_time}ms", flush=True)

    return result



def get_unfinished_trips(person_id=None):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_unfinished_trips", flush=True)
    other_passengers = total_passengers = 0
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()
        sql = ''' select p.person_name, p.person_image_location, p.aadhar_number, p.aadhar_image_location,
        p.drivers_license_number, p.drivers_license_image, p.other_id_type, p.other_id_number, p.other_id_image_location, 
        p.visiting_person_name as purpose, p.mobile_number,
        pa.number as pass_number, pa.pass_image_location,
        ''' + TRIP_VEHICLE_SELECT_FIELDS + ''', t.traveler_type, t.entry_time, t.exit_time, t.coming_from, t.going_to, t.number_of_male_passengers,
        t.number_of_female_passengers, t.number_of_child_passengers, t.id, t.visit_duration, t.token_number, t.driver_trip_id, t.trip_permit_type, 
        t.trip_permit_image_location, t.created_by, u.user_name
        from trips t 
        join persons p on p.id = t.person_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) * FROM vehicles ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC)
        v on t.vehicle_number_plate = v.vehicle_number_plate and t.person_id = v.vehicle_owner_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate) * FROM vehicles WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> '' ORDER BY vehicle_number_plate, date_created DESC)
        vp on t.vehicle_number_plate = vp.vehicle_number_plate
        LEFT JOIN(SELECT DISTINCT ON(assigned_to) * FROM passes ORDER BY assigned_to, create_date DESC ) pa ON p.id = pa.assigned_to
        left jOIN users u ON t.created_by = u.id
        where t.is_finished = 'False' AND t.entry_time >= NOW() - INTERVAL '1 hour' '''

        if person_id is not None:
            sql += " and t.person_id = %s"
            arg = (person_id,)
        else:
            arg = ()

        sql += " order by t.entry_time desc;"
        cursor.execute(sql,arg)
        rows = cursor.fetchall()  # Fetch all rows
        column_names = [desc[0] for desc in cursor.description]

        if not rows:  # Check if rows exist
            print("No matching records found", flush=True)

            # End logging
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_unfinished_trips | Execution time: {execution_time}ms", flush=True)

            return {"Status": "Success", "Details": []}  # Return an empty list

        # Convert rows into a list of dictionaries
        result = [dict(zip(column_names, row)) for row in rows]
        trip_list = []
        if len(result) > 0:
            for trip in result:
                if trip.get('person_image_location') is not None:
                    person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(trip.get('person_image_location').rstrip('/'))])
                    trip.update({'person_image_location': person_image})

                if trip.get('vehicle_image_location') is not None:
                    vehicle_image = vehicle_image_html_path(trip.get('vehicle_image_location'))
                    trip.update({'vehicle_image_location': vehicle_image})

                entry_time = trip.get('entry_time')
                exit_time = trip.get('exit_time')

                if entry_time and exit_time:  # Ensure both values are datetime objects
                    elapsed_time_minutes = (exit_time - entry_time).total_seconds() / 60
                else:
                    current_time = datetime.now()
                    elapsed_time_minutes = (current_time - trip.get('entry_time')).total_seconds() / 60

                visit_duration = trip.get('visit_duration')
                if isinstance(visit_duration, timedelta):
                    expected_visit_duration = visit_duration.total_seconds() / 60
                elif isinstance(visit_duration, (int, float)):
                    expected_visit_duration = float(visit_duration)
                else:
                    expected_visit_duration = 0
                
                overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))
                trip.update({'visit_duration': expected_visit_duration})

                if trip.get('entry_time') is not None:
                    entry_time = trip.get('entry_time').strftime('%d/%m/%Y %H:%M')# entry_time.strftime('%d %b, %Y %I:%M %p')
                    trip.update({'entry_time':entry_time})

                if trip.get('exit_time') is not None:
                    exit_time = trip.get('exit_time').strftime('%d/%m/%Y %H:%M')#strftime('%d %b, %Y %I:%M %p')
                    trip.update({'exit_time': exit_time})
                else:
                    exit_time = "Not Closed"
                    trip.update({'exit_time': exit_time})

                if trip.get('number_of_female_passengers') is not None and trip.get('number_of_child_passengers') is not None:
                    other_passengers = int(trip.get('number_of_female_passengers')) + int(trip.get('number_of_child_passengers'))
                else:
                    other_passengers = 0

                if trip.get('number_of_male_passengers') is not None:
                    total_passengers = int(trip.get('number_of_male_passengers')) + other_passengers
                else:
                    total_passengers = 0

                primary_id_number = next((value for key, value in trip.items()
                                                if key in ['aadhar_number', 'drivers_license_number', 'other_id_number',
                                                           'pass_number']
                                                and value is not None), None)

                # Filter valid image locations
                primary_id_image = next((value for key, value in trip.items()
                                           if key in ['aadhar_image_location', 'drivers_license_image',
                                                      'other_id_image_location',
                                                      'pass_image_location'] and value is not None), None)
                # Filter valid image locations
                id_type_mapping = {
                    'aadhar_image_location': 'Aadhar',
                    'drivers_license_image': 'Drivers License',
                    'pass_image_location': 'Pass',
                    'other_id_image_location': 'Other ID'
                }

                # Find the first non-None value and return its corresponding label
                primary_id_image_type = next(
                    (id_type_mapping[key] for key, value in trip.items() if
                     key in id_type_mapping and value is not None),
                    None
                )

                if primary_id_image is not None:
                    trip.update({'primary_id_image': primary_id_image})

                trip.update({'other_passengers': other_passengers})
                trip.update({'total_passengers': total_passengers})
                trip.update({'overstay_minutes': overstay_minutes})
                trip.update({'primary_id_number': primary_id_number})
                trip.update({'primary_id_image': primary_id_image})
                trip_list.append(trip)

            #print("trip_list: ", trip_list, flush=True)
        result = {"Status": "Success", "Details": trip_list}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}
 
    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_unfinished_trips", flush=True)
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_unfinished_trips | Execution time: {execution_time}ms", flush=True)

    return result


def get_unfinished_trips_for_autocomplete(trip_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_unfinished_trips", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''Select t.id, t.driver_trip_id, p.person_name, t.traveler_type, t.vehicle_number_plate, t.entry_time, t.is_finished, t.coming_from, t.going_to, t.number_of_male_passengers, 
            t.number_of_female_passengers, t.number_of_child_passengers, p.person_image_location, v.vehicle_image_location, t.visit_duration, t.token_number 
            from persons p, trips t, vehicles v where t.id = %s and t.person_id = p.id 
            and v.vehicle_number_plate = t.vehicle_number_plate;''' 
        arg = (trip_id,)
        cursor.execute(sql,arg)
        result = cursor.fetchall()
        result = {"Status": "Success", "Details": result}
     
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in get_unfinished_trips_for_autocomplete", flush=True)
        return_connection_to_pool(db_connection)

        # End logging
        end_time = time.time()
        execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        print(f"[{end_timestamp}] Completed get_unfinished_trips_for_autocomplete | Execution time: {execution_time}ms", flush=True)

    return result


#def close_trip(trip_id, driver_trip_id, traveler_type, exit_time):
def close_trip(trip_id, exit_time):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting close_trip", flush=True)

    db_connection = None
    cursor = None
    result = None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''UPDATE trips set is_finished = TRUE, exit_time = %s where id = %s RETURNING id; '''
        arg = (exit_time, trip_id)
        cursor.execute(sql,arg)
        result = cursor.fetchall()
        updated_id = result[0]
        count = cursor.rowcount
        print("update trip count: ", count)
        db_connection.commit()
        result = {"Status": "Success", "Update Count": count, "Details": 'Updated trip id ' + str(updated_id) }
    
    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Update Count": 0, "Details": error}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed close_trip | Execution time: {execution_time}ms", flush=True)
    return result

def get_trip_details_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_trip_details_by_date", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    other_passengers = total_passengers = 0
    person_image_path_for_download = vehicle_image_path_for_download \
        = primary_id_image_path_for_download =  permit_image_path_for_download = None
    traveler_type_counts = {}
    report_summary = None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select p.person_name, p.person_image_location, p.aadhar_number, p.aadhar_image_location,
        p.drivers_license_number, p.drivers_license_image, p.other_id_type, p.other_id_number, p.other_id_image_location,
        p.visiting_person_name as purpose, p.mobile_number,
        pa.number as pass_number, pa.pass_image_location,
        ''' + TRIP_VEHICLE_SELECT_FIELDS + ''', t.traveler_type, t.entry_time, t.exit_time, t.coming_from, t.going_to, t.number_of_male_passengers,
        t.number_of_female_passengers, t.number_of_child_passengers, t.id, t.visit_duration, t.token_number, t.driver_trip_id, t.trip_permit_type, t.trip_permit_image_location,
        t.created_by, u.user_name
        from trips t 
        join persons  p on p.id = t.person_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) * FROM vehicles ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC)
        v on t.vehicle_number_plate = v.vehicle_number_plate and t.person_id = v.vehicle_owner_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate) * FROM vehicles WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> '' ORDER BY vehicle_number_plate, date_created DESC)
        vp on t.vehicle_number_plate = vp.vehicle_number_plate
        LEFT JOIN(SELECT DISTINCT ON(assigned_to) * FROM passes ORDER BY assigned_to, create_date DESC ) pa ON p.id = pa.assigned_to 
        left jOIN users u ON t.created_by = u.id 
        where t.entry_time between %s and %s order by t.entry_time desc, t.id desc;
        '''
        arg = (start_date, end_date)
        cursor.execute(sql,arg)
        rows = cursor.fetchall()  # Fetch all rows
        column_names = [desc[0] for desc in cursor.description]

        if not rows:  # Check if rows exist
            print("No matching records found", flush=True)
            report_summary = "No records were found the current filters."

            # End logging
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_trip_details_by_date | Execution time: {execution_time}ms",
                  flush=True)

            return {"Status": "Success", "Details": [], "Message": report_summary}  # Return an empty list

        # Convert rows into a list of dictionaries
        result = [dict(zip(column_names, row)) for row in rows]
        trip_list = []
        if len(result) > 0:
            traveler_type_counts = defaultdict(int)
            for trip in result:
                traveler_type = trip.get('traveler_type')
                if traveler_type:
                    traveler_type_counts[traveler_type] += 1

                if trip.get('person_image_location') is not None:
                    person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"], os.path.basename(trip.get('person_image_location').strip('/'))])
                    trip.update({'person_image_location': person_image})
                    person_image_path_for_download = app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + person_image

                if trip.get('vehicle_image_location') is not None:
                    vehicle_image = vehicle_image_html_path(trip.get('vehicle_image_location'))
                    trip.update({'vehicle_image_location': vehicle_image})
                    if vehicle_image:
                        vehicle_image_path_for_download = app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + vehicle_image

                entry_time = trip.get('entry_time')
                exit_time = trip.get('exit_time')

                if entry_time and exit_time:  # Ensure both values are datetime objects
                    elapsed_time_minutes = (exit_time - entry_time).total_seconds() / 60

                else:
                    current_time = datetime.now()
                    elapsed_time_minutes = (current_time - trip.get('entry_time')).total_seconds() / 60

                visit_duration = trip.get('visit_duration')
                #expected_visit_duration = 0
                if isinstance(visit_duration, timedelta):
                    #print("time delta", flush=True)
                    expected_visit_duration = visit_duration.total_seconds() / 60  # Convert timedelta to minutes
                elif isinstance(visit_duration, (int, float)):  # Ensure it's numeric before converting
                    expected_visit_duration = float(visit_duration)  # If already a float or int, keep it as is
                else:
                    expected_visit_duration = 0  # Default if visit_duration is None or an unexpected type
                overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))
                trip.update({"visit_duration": expected_visit_duration})

                if trip.get('entry_time') is not None:
                    entry_time = trip.get('entry_time').strftime('%d/%m/%Y %H:%M')# entry_time.strftime('%d %b, %Y %I:%M %p')
                    trip.update({'entry_time':entry_time})
                    #print("entry_time: ", entry_time, flush=True)

                if trip.get('exit_time') is not None:
                    exit_time = trip.get('exit_time').strftime('%d/%m/%Y %H:%M')#strftime('%d %b, %Y %I:%M %p')
                    trip.update({'exit_time': exit_time})
                else:
                    exit_time = "Not Closed"
                    trip.update({'exit_time': exit_time})
                    #print("exit_time: ", exit_time, flush=True)

                if trip.get('number_of_female_passengers') is not None and trip.get('number_of_child_passengers') is not None:
                    other_passengers = int(trip.get('number_of_female_passengers')) + int(trip.get('number_of_child_passengers'))
                else:
                    other_passengers = 0
                #if trip[9] is not None:
                if trip.get('number_of_male_passengers') is not None:
                    total_passengers = int(trip.get('number_of_male_passengers')) + other_passengers
                    #print('total_passengers: ', total_passengers,flush=True)
                else:
                    total_passengers = 0

                primary_id_number = next((value for key, value in trip.items()
                                                if key in ['aadhar_number', 'drivers_license_number', 'other_id_number',
                                                           'pass_number']
                                                and value is not None), None)

                # Filter valid image locations
                primary_id_image = next((value for key, value in trip.items()
                                           if key in ['aadhar_image_location', 'drivers_license_image',
                                                      'other_id_image_location',
                                                      'pass_image_location'] and value is not None), None)
                # Filter valid image locations
                primary_id_image_type = next((key for key, value in trip.items()
                                         if key in ['aadhar_image_location', 'drivers_license_image',
                                                    'other_id_image_location',
                                                    'pass_image_location'] and value is not None), None)

                if primary_id_image is not None:
                    trip.update({'primary_id_image': primary_id_image})
                    primary_id_image_path_for_download = os.path.sep.join([app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],primary_id_image])

                if trip.get('trip_permit_image_location') is not None:
                    permit_image_path_for_download = os.path.sep.join([app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],
                                                        trip.get('trip_permit_image_location').strip('/')])

                trip.update({'other_passengers': other_passengers})
                trip.update({'total_passengers': total_passengers})
                trip.update({'overstay_minutes': overstay_minutes})
                trip.update({'primary_id_number': primary_id_number})
                trip.update({'primary_id_image': primary_id_image})
                trip.update({'primary_id_image_type': primary_id_image_type})
                trip.update({'person_image_path_for_download': person_image_path_for_download})
                trip.update({'vehicle_image_path_for_download': vehicle_image_path_for_download})
                trip.update({'id_image_path_for_download': primary_id_image_path_for_download})
                trip.update({'permit_image_path_for_download': permit_image_path_for_download})

                for key, value in trip.items():
                    if isinstance(value, timedelta):
                        print(f"DEBUG: {key} is a timedelta -> {value}", flush=True)
                trip_list.append(trip)
                #print("trip_list: ", trip_list, flush=True)

        data = defaultdict(int, traveler_type_counts)
        # Add total sum of values
        data["Total"] = sum(data.values())
        # Function to pluralize words (basic logic)
        def pluralize(word, count):
            if count == 1:
                return word  # Singular case
            elif word == 'Total':
                return 'TOTAL'  # Singular case
            elif word.endswith("Y"):  # Handle words ending in 'Y' (e.g., "CITY" → "CITIES")
                return word[:-1] + "IES"
            elif word == 'OTHERS':
                return word
            else:
                return word + "S"  # Default pluralization

        # Generate the report summary with a newline after the first sentence
        #report_summary = ""
        report_summary = ", ".join(f"{pluralize(key, value)}: {value}" for key, value in data.items())
        #report_summary = str([f"{pluralize(key, value)}: {value}" for key, value in data.items()])
        print(f"message: {report_summary}", flush=True)
        result = {"Status": "Success", "Details": trip_list, "Message": report_summary}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_trip_details_by_date | Execution time: {execution_time}ms", flush=True)

    return result

def get_trip_details_by_date_paginated(
    start_date,
    end_date,
    start=0,
    length=50,
    search_value="",
    order_col_idx=10,
    order_dir="desc",
    column_filters=None,
):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_trip_details_by_date_paginated", flush=True)

    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    column_filters = column_filters or {}

    overstay_expr = """
        GREATEST(
            0,
            EXTRACT(EPOCH FROM (COALESCE(t.exit_time, NOW()) - t.entry_time)) / 60
            - EXTRACT(EPOCH FROM COALESCE(t.visit_duration, interval '0')) / 60
        )
    """

    total_passengers_expr = """
        (COALESCE(t.number_of_male_passengers, 0)
        + COALESCE(t.number_of_female_passengers, 0)
        + COALESCE(t.number_of_child_passengers, 0))
    """

    primary_id_expr = "COALESCE(p.aadhar_number, p.drivers_license_number, p.other_id_number, pa.number)"

    permit_expr = "CASE WHEN t.trip_permit_image_location IS NOT NULL THEN 'Yes' ELSE 'No' END"

    # DataTables column index -> SQL sort expression
    order_map = {
        0: "t.id",
        1: "p.person_name",
        3: TRIP_VEHICLE_PLATE_EXPR,
        5: "t.traveler_type",
        6: primary_id_expr,
        8: permit_expr,
        10: "t.entry_time",
        11: "t.exit_time",
        12: "t.visit_duration",
        13: overstay_expr,
        14: "p.visiting_person_name",
        15: "t.going_to",
        16: total_passengers_expr,
        17: "p.mobile_number",
        18: "u.user_name",
    }

    # DataTables column index -> SQL filter expression
    column_filter_sql = {
        1: "COALESCE(p.person_name, '') ILIKE %s",
        3: f"COALESCE({TRIP_VEHICLE_PLATE_EXPR}, '') ILIKE %s",
        5: "COALESCE(t.traveler_type, '') ILIKE %s",
        6: f"COALESCE({primary_id_expr}, '') ILIKE %s",
        8: f"{permit_expr} ILIKE %s",
        14: "COALESCE(p.visiting_person_name, '') ILIKE %s",
        15: "COALESCE(t.going_to, '') ILIKE %s",
        16: f"CAST({total_passengers_expr} AS TEXT) ILIKE %s",
        17: "COALESCE(p.mobile_number, '') ILIKE %s",
        18: "COALESCE(u.user_name, '') ILIKE %s",
    }

    # Duration columns (Expected Stay / Overstay) filter by component, not raw text.
    duration_minutes_map = {
        12: VISIT_DURATION_MINUTES_EXPR,
        13: f"FLOOR({overstay_expr})",
    }



    order_col = order_map.get(int(order_col_idx), "t.entry_time")
    order_dir = "ASC" if str(order_dir).lower() == "asc" else "DESC"

    base_from = """
        FROM trips t
        JOIN persons p ON p.id = t.person_id
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) *
            FROM vehicles
            ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC
        ) v ON t.vehicle_number_plate = v.vehicle_number_plate AND t.person_id = v.vehicle_owner_id
        LEFT JOIN (
            SELECT DISTINCT ON (vehicle_number_plate) *
            FROM vehicles
            WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> ''
            ORDER BY vehicle_number_plate, date_created DESC
        ) vp ON t.vehicle_number_plate = vp.vehicle_number_plate
        LEFT JOIN (
            SELECT DISTINCT ON (assigned_to) *
            FROM passes
            ORDER BY assigned_to, create_date DESC
        ) pa ON p.id = pa.assigned_to
        LEFT JOIN users u ON t.created_by = u.id
        WHERE t.entry_time BETWEEN %s AND %s
    """
    where_params = [start_date, end_date]

    search_sql = ""
    search_params = []
    if search_value:
        search_sql = f"""
            AND (
                COALESCE(p.person_name, '') ILIKE %s OR
                COALESCE({TRIP_VEHICLE_PLATE_EXPR}, '') ILIKE %s OR
                COALESCE(t.traveler_type, '') ILIKE %s OR
                COALESCE(p.mobile_number, '') ILIKE %s OR
                COALESCE(t.going_to, '') ILIKE %s OR
                COALESCE(p.visiting_person_name, '') ILIKE %s OR
                COALESCE(u.user_name, '') ILIKE %s OR
                COALESCE(t.token_number, '') ILIKE %s
            )
        """
        like_term = f"%{search_value}%"
        search_params = [like_term] * 8
    # per-column filters
    search_sql, search_params = _append_column_filter_sql(
        column_filters, column_filter_sql, TRIP_REPORT_DATE_FILTER_COLS, search_sql, search_params,
        duration_minutes_map=duration_minutes_map
    )
    select_sql = (
        """
        SELECT
            p.person_name, p.person_image_location, p.aadhar_number, p.aadhar_image_location,
            p.drivers_license_number, p.drivers_license_image, p.other_id_type, p.other_id_number,
            p.other_id_image_location, p.visiting_person_name AS purpose, p.mobile_number,
            pa.number AS pass_number, pa.pass_image_location,
            """
        + TRIP_VEHICLE_SELECT_FIELDS
        + f""",
            t.traveler_type, t.entry_time, t.exit_time, t.coming_from, t.going_to,
            t.number_of_male_passengers, t.number_of_female_passengers, t.number_of_child_passengers,
            t.id, t.visit_duration, t.token_number, t.driver_trip_id, t.trip_permit_type,
            t.trip_permit_image_location, t.created_by, u.user_name,
            CAST({overstay_expr} AS BIGINT) AS overstay_minutes
    """
    )

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        total_sql = f"SELECT COUNT(*) AS total {base_from}"
        cursor.execute(total_sql, tuple(where_params))
        records_total = cursor.fetchone()["total"]

        filtered_sql = f"SELECT COUNT(*) AS total {base_from} {search_sql}"
        cursor.execute(filtered_sql, tuple(where_params + search_params))
        records_filtered = cursor.fetchone()["total"]

        # People / destination summary for the filtered set (not just current page)
        summary_totals_sql = f"""
            SELECT
                COUNT(*) AS total_trips,
                COALESCE(SUM(COALESCE(t.number_of_male_passengers, 0)), 0) AS total_males,
                COALESCE(SUM(COALESCE(t.number_of_female_passengers, 0)), 0) AS total_females,
                COALESCE(SUM(COALESCE(t.number_of_child_passengers, 0)), 0) AS total_children
            {base_from}
            {search_sql}
        """
        cursor.execute(summary_totals_sql, tuple(where_params + search_params))
        totals_row = cursor.fetchone() or {}
        total_males = int(totals_row.get("total_males") or 0)
        total_females = int(totals_row.get("total_females") or 0)
        total_children = int(totals_row.get("total_children") or 0)
        total_trips = int(totals_row.get("total_trips") or 0)

        traveler_type_sql = f"""
            SELECT
                COALESCE(NULLIF(TRIM(t.traveler_type), ''), 'Unknown') AS traveler_type,
                COUNT(*) AS trip_count
            {base_from}
            {search_sql}
            GROUP BY COALESCE(NULLIF(TRIM(t.traveler_type), ''), 'Unknown')
            ORDER BY trip_count DESC, traveler_type ASC
        """
        cursor.execute(traveler_type_sql, tuple(where_params + search_params))
        traveler_types = [
            {"type": row["traveler_type"], "trips": int(row["trip_count"] or 0)}
            for row in cursor.fetchall()
        ]

        going_to_sql = f"""
            SELECT
                COALESCE(NULLIF(TRIM(t.going_to), ''), 'Not Available') AS going_to,
                COUNT(*) AS trip_count,
                COALESCE(SUM(COALESCE(t.number_of_male_passengers, 0)), 0) AS males,
                COALESCE(SUM(COALESCE(t.number_of_female_passengers, 0)), 0) AS females,
                COALESCE(SUM(COALESCE(t.number_of_child_passengers, 0)), 0) AS children
            {base_from}
            {search_sql}
            GROUP BY COALESCE(NULLIF(TRIM(t.going_to), ''), 'Not Available')
            ORDER BY trip_count DESC, going_to ASC
        """
        cursor.execute(going_to_sql, tuple(where_params + search_params))
        going_to_breakdown = []
        for row in cursor.fetchall():
            males = int(row["males"] or 0)
            females = int(row["females"] or 0)
            children = int(row["children"] or 0)
            going_to_breakdown.append({
                "going_to": row["going_to"],
                "trips": int(row["trip_count"] or 0),
                "males": males,
                "females": females,
                "children": children,
                "total_persons": males + females + children,
            })

        summary = {
            "total_trips": total_trips,
            "total_males": total_males,
            "total_females": total_females,
            "total_children": total_children,
            "total_persons": total_males + total_females + total_children,
            "traveler_types": traveler_types,
            "going_to": going_to_breakdown,
        }

        data_sql = f"""
            {select_sql}
            {base_from}
            {search_sql}
            ORDER BY {order_col} {order_dir}, t.id DESC
            LIMIT %s OFFSET %s
        """
        data_params = where_params + search_params + [int(length), int(start)]
        cursor.execute(data_sql, tuple(data_params))
        rows = cursor.fetchall()

        trip_list = []
        for trip in rows:
            person_image_path_for_download = vehicle_image_path_for_download = None
            primary_id_image_path_for_download = permit_image_path_for_download = None

            if trip.get("person_image_location"):
                person_image = os.path.sep.join([
                    app.config["KNOWN_PERSON_PATH_FOR_HTML"],
                    os.path.basename(trip["person_image_location"].strip("/"))
                ])
                trip["person_image_location"] = person_image
                person_image_path_for_download = app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + person_image

            if trip.get("vehicle_image_location"):
                vehicle_image = vehicle_image_html_path(trip["vehicle_image_location"])
                trip["vehicle_image_location"] = vehicle_image
                if vehicle_image:
                    vehicle_image_path_for_download = app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + vehicle_image

            entry_time = trip.get("entry_time")
            exit_time = trip.get("exit_time")
            elapsed_time_minutes = ((exit_time or datetime.now()) - entry_time).total_seconds() / 60 if entry_time else 0

            visit_duration = trip.get("visit_duration")
            if isinstance(visit_duration, timedelta):
                expected_visit_duration = visit_duration.total_seconds() / 60
            elif isinstance(visit_duration, (int, float)):
                expected_visit_duration = float(visit_duration)
            else:
                expected_visit_duration = 0.0

            trip["visit_duration"] = expected_visit_duration
            # Overstay is computed once in SQL (CAST({overstay_expr} AS BIGINT)) so the
            # displayed value matches the Overstay filter exactly, regardless of timezone skew
            # between Python's datetime.now() and the server's NOW().
            trip["overstay_minutes"] = int(trip.get("overstay_minutes") or 0)

            trip["entry_time"] = entry_time.strftime("%d/%m/%Y %H:%M") if entry_time else "Not Available"
            trip["exit_time"] = exit_time.strftime("%d/%m/%Y %H:%M") if exit_time else "Not Closed"

            female = int(trip.get("number_of_female_passengers") or 0)
            child = int(trip.get("number_of_child_passengers") or 0)
            male = int(trip.get("number_of_male_passengers") or 0)
            trip["other_passengers"] = female + child
            trip["total_passengers"] = male + female + child

            trip["primary_id_number"] = (
                trip.get("aadhar_number")
                or trip.get("drivers_license_number")
                or trip.get("other_id_number")
                or trip.get("pass_number")
            )
            trip["primary_id_image"] = (
                trip.get("aadhar_image_location")
                or trip.get("drivers_license_image")
                or trip.get("other_id_image_location")
                or trip.get("pass_image_location")
            )

            if trip.get("primary_id_image"):
                primary_id_image_path_for_download = os.path.sep.join([
                    app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],
                    trip["primary_id_image"]
                ])

            if trip.get("trip_permit_image_location"):
                permit_image_path_for_download = os.path.sep.join([
                    app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],
                    trip["trip_permit_image_location"].strip("/")
                ])

            trip["person_image_path_for_download"] = person_image_path_for_download
            trip["vehicle_image_path_for_download"] = vehicle_image_path_for_download
            trip["id_image_path_for_download"] = primary_id_image_path_for_download
            trip["permit_image_path_for_download"] = permit_image_path_for_download

            trip_list.append(trip)

        result = {
            "Status": "Success",
            "recordsTotal": records_total,
            "recordsFiltered": records_filtered,
            "Details": trip_list,
            "Summary": summary,
        }

    except (Exception, psycopg2.Error) as error:
        print("Error in get_trip_details_by_date_paginated:", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": str(error)}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_trip_details_by_date_paginated | Execution time: {execution_time}ms", flush=True)

    return result


def count_trip_details_by_date(start_date, end_date):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting count_trip_details_by_date", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = '''select COUNT(*)
        from trips t
        join persons  p on p.id = t.person_id
        where t.entry_time between %s and %s;
        '''
        arg = (start_date, end_date)
        cursor.execute(sql, arg)
        result = {"Status": "Success", "Details": cursor.fetchone()[0]}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
            print("cursor closed in count_trip_details_by_date", flush=True)
        return_connection_to_pool(db_connection)

    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed count_trip_details_by_date | Execution time: {execution_time}ms", flush=True)

    return result


def get_trip_details_by_person_id(person_id):
    start_time = time.time()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{start_timestamp}] Starting get_trip_details_by_person_id", flush=True)
    db_connection = None
    cursor = None
    result = None
    psycopg2.extras.register_uuid()
    person_image_path_for_download = vehicle_image_path_for_download \
        = primary_id_image_path_for_download =  permit_image_path_for_download = None

    try:
        db_connection = g.connection_pool.getconn()
        cursor = db_connection.cursor()

        sql = ''' select p.person_name, p.person_image_location, p.aadhar_number, p.aadhar_image_location,
        p.drivers_license_number, p.drivers_license_image, p.other_id_type, p.other_id_number, p.other_id_image_location, 
        p.visiting_person_name as purpose, p.mobile_number,
        pa.number as pass_number, pa.pass_image_location,
        ''' + TRIP_VEHICLE_SELECT_FIELDS + ''', t.traveler_type, t.entry_time, t.exit_time, t.coming_from, t.going_to, t.number_of_male_passengers,
        t.number_of_female_passengers, t.number_of_child_passengers, t.id, t.visit_duration, t.token_number, t.driver_trip_id, t.trip_permit_type, 
        t.trip_permit_image_location, t.created_by, u.user_name
        from trips t 
        join persons p on p.id = t.person_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate, vehicle_owner_id) * FROM vehicles ORDER BY vehicle_number_plate, vehicle_owner_id, date_created DESC)
        v on t.vehicle_number_plate = v.vehicle_number_plate and t.person_id = v.vehicle_owner_id
        LEFT JOIN ( SELECT DISTINCT ON (vehicle_number_plate) * FROM vehicles WHERE vehicle_image_location IS NOT NULL AND TRIM(vehicle_image_location) <> '' ORDER BY vehicle_number_plate, date_created DESC)
        vp on t.vehicle_number_plate = vp.vehicle_number_plate
        LEFT JOIN(SELECT DISTINCT ON(assigned_to) * FROM passes ORDER BY assigned_to, create_date DESC ) pa ON p.id = pa.assigned_to
        left jOIN users u ON t.created_by = u.id
        where t.person_id = %s 
        order by t.entry_time desc;'''

        arg = (person_id,)
        cursor.execute(sql, arg)
        rows = cursor.fetchall()  # Fetch all rows
        column_names = [desc[0] for desc in cursor.description]

        if not rows:  # Check if rows exist
            print("No matching records found", flush=True)

            # End logging
            end_time = time.time()
            execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
            end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            print(f"[{end_timestamp}] Completed get_trip_details_by_person_id | Execution time: {execution_time}ms", flush=True)

            return {"Status": "Success", "Details": []}  # Return an empty list

        # Convert rows into a list of dictionaries
        result = [dict(zip(column_names, row)) for row in rows]
        trip_list = []
        if len(result) > 0:
            for trip in result:
                if trip.get('person_image_location') is not None:
                    person_image = os.path.sep.join([app.config["KNOWN_PERSON_PATH_FOR_HTML"],
                                                     os.path.basename(trip.get('person_image_location').rstrip('/'))])
                    trip.update({'person_image_location': person_image})
                    person_image_path_for_download = app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + person_image

                if trip.get('vehicle_image_location') is not None:
                    vehicle_image = vehicle_image_html_path(trip.get('vehicle_image_location'))
                    trip.update({'vehicle_image_location': vehicle_image})
                    if vehicle_image:
                        vehicle_image_path_for_download = app.config[
                                                              "COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"] + vehicle_image

                entry_time = trip.get('entry_time')
                exit_time = trip.get('exit_time')

                if entry_time and exit_time:  # Ensure both values are datetime objects
                    elapsed_time_minutes = (exit_time - entry_time).total_seconds() / 60
                else:
                    current_time = datetime.now()
                    elapsed_time_minutes = (current_time - trip.get('entry_time')).total_seconds() / 60

                visit_duration = trip.get('visit_duration')
                if isinstance(visit_duration, timedelta):
                    expected_visit_duration = visit_duration.total_seconds() / 60
                elif isinstance(visit_duration, (int, float)):
                    expected_visit_duration = float(visit_duration)
                else:
                    expected_visit_duration = 0
                
                overstay_minutes = int(max(0, elapsed_time_minutes - expected_visit_duration))
                trip.update({'visit_duration': expected_visit_duration})

                if trip.get('entry_time') is not None:
                    entry_time = trip.get('entry_time').strftime(
                        '%d/%m/%Y %H:%M')  # entry_time.strftime('%d %b, %Y %I:%M %p')
                    trip.update({'entry_time': entry_time})

                if trip.get('exit_time') is not None:
                    exit_time = trip.get('exit_time').strftime('%d/%m/%Y %H:%M')  # strftime('%d %b, %Y %I:%M %p')
                    trip.update({'exit_time': exit_time})
                else:
                    exit_time = "Not Closed"
                    trip.update({'exit_time': exit_time})

                if trip.get('female_passengers') is not None and trip.get('male_passengers') is not None:
                    other_passengers = int(trip.get('female_passengers')) + int(trip.get('male_passengers'))
                else:
                    other_passengers = 0

                if trip.get('male_passengers') is not None:
                    total_passengers = int(trip.get('male_passengers')) + other_passengers
                else:
                    total_passengers = 0

                primary_id_number = next((value for key, value in trip.items()
                                          if key in ['aadhar_number', 'drivers_license_number', 'other_id_number',
                                                     'pass_number']
                                          and value is not None), None)

                # Filter valid image locations
                primary_id_image = next((value for key, value in trip.items()
                                         if key in ['aadhar_image_location', 'drivers_license_image',
                                                    'other_id_image_location',
                                                    'pass_image_location'] and value is not None), None)
                # Filter valid image locations
                id_type_mapping = {
                    'aadhar_image_location': 'Aadhar',
                    'drivers_license_image': 'Drivers License',
                    'pass_image_location': 'Pass',
                    'other_id_image_location': 'Other ID'
                }

                # Find the first non-None value and return its corresponding label
                primary_id_image_type = next(
                    (id_type_mapping[key] for key, value in trip.items() if
                     key in id_type_mapping and value is not None),
                    None
                )

                if primary_id_image is not None:
                    trip.update({'primary_id_image': primary_id_image})
                    primary_id_image_path_for_download = os.path.sep.join([app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],primary_id_image])

                if trip.get('trip_permit_image_location') is not None:
                    permit_image_path_for_download = os.path.sep.join([app.config["COMPLETE_FOLDER_PATH_FOR_REPORT_IMAGES"],
                                                        trip.get('trip_permit_image_location').strip('/')])

                trip.update({'other_passengers': other_passengers})
                trip.update({'total_passengers': total_passengers})
                trip.update({'overstay_minutes': overstay_minutes})
                trip.update({'primary_id_number': primary_id_number})
                trip.update({'primary_id_image': primary_id_image})
                trip.update({'primary_id_image_type': primary_id_image_type})
                trip.update({'person_image_path_for_download': person_image_path_for_download})
                trip.update({'vehicle_image_path_for_download': vehicle_image_path_for_download})
                trip.update({'id_image_path_for_download': primary_id_image_path_for_download})
                trip.update({'permit_image_path_for_download': permit_image_path_for_download})
                trip_list.append(trip)

            # print("trip_list: ", trip_list, flush=True)
        result = {"Status": "Success", "Details": trip_list}

    except (Exception, psycopg2.Error) as error:
        print("Error while executing PostgreSQL command", error, flush=True)
        if db_connection:
            db_connection.rollback()
        result = {"Status": "Fail", "Details": error}

    finally:
        if cursor:
            cursor.close()
        return_connection_to_pool(db_connection)

    # End logging
    end_time = time.time()
    execution_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
    end_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{end_timestamp}] Completed get_trip_details_by_person_id | Execution time: {execution_time}ms", flush=True)

    return result
