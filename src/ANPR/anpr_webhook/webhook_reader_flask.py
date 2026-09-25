import errno
import json
import os
import re
import datetime
import sys
from datetime import date
import threading
import random

import pickle
import numpy as np

from flask import Flask, request
import psycopg2

# import firebase_admin
# from firebase_admin import credentials
# from firebase_admin import db, storage

app = Flask(__name__)

#regexp = re.compile(r'^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$')
#regexp_bharat = re.compile(r'^\d{2}[A-Z]{2}\d{4}[A-Z]{2}$')
regexp = re.compile(r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}$')
regexp_bharat = re.compile(r'^\d{2}[A-Z]{2}\d{4}[A-Z]{1,2}$')
regexp_digits = re.compile(r'.*\d{4}$')

POSTGRESQL_URL = 'census_counters_postgres_db'
# POSTGRESQL_URL = 'database-1.cyzmx3rjxh6p.ap-south-1.rds.amazonaws.com'
postgres_conn = None
def connect_to_db():
    global postgres_conn
    postgres_conn = psycopg2.connect(dbname='postgres_visitor_vehicle', user='postgres',
                            password='postgres', host=POSTGRESQL_URL)
    postgres_conn.autocommit = True


ApplyMask=False
if ApplyMask:
    masks = {}
    for i in range(1,4):
        masks[f'camera-{i}'] = {}
        with open(f'./masks/camera-{i}-mask.pkl', 'rb') as f:
            masks[f'camera-{i}']['mask'] = pickle.load(f)
            mask_shape = masks[f'camera-{i}']['mask'].shape[:2]
            masks[f'camera-{i}']['mask_img'] = np.zeros((mask_shape[0], mask_shape[1], 3), np.uint8)
            mask_image = masks[f'camera-{i}']['mask'] == 'R'
            masks[f'camera-{i}']['mask_img'][mask_image] = (255, 0, 0)

#pos_val = masks['camera-1']['mask'][500, 888]
#print(pos_val)
#a=1/0


running = True
drawing_instructions = {}
cap = None
im = None
current_plate_number = None
current_car_type = None
plate_issue = None
out = None
plate_dict = {}

def get_highest_confidence_plate(instructions):
    """
    Extract the plate number with the highest confidence score.
    """
    highest_score = 0
    best_plate = None
    if 'results' in instructions:
        for result in instructions['results']:
            if 'candidates' in result:
                for candidate in result['candidates']:
                    if candidate['score'] > highest_score:
                        highest_score = candidate['score']
                        best_plate = candidate['plate']
    return best_plate




# Fetch the service account key JSON file contents
# cred = credentials.Certificate('./censusparkingsolution-firebase-adminsdk-ik5c2-47685d7f7f.json')

# Initialize the app with a service account, granting admin privileges
# firebase_admin.initialize_app(cred, {
#     'databaseURL': 'https://censusparkingsolution-default-rtdb.asia-southeast1.firebasedatabase.app',
#     'storageBucket': 'censusparkingsolution.appspot.com'
# })

# As an admin, the app has access to read and write all data, regradless of Security Rules
# ref = db.reference('/Vehicles')
# bucket = storage.bucket()

@app.route("/", methods=["GET", "POST"])
def process_request():
    global ref, postgres_conn
    global current_car_type, current_plate_number, plate_issue
    global plate_dict

    if request.method == "GET":
        return "Send a POST request instead."
    else:
        try:
            if not postgres_conn:
                connect_to_db()
                app.logger.debug('Just connected to Postgres DB')
            # Files exist for multipart/form-data
            files = request.files
            app.logger.debug(f"files: {files}")
            if files:
                form = request.form
                json_data = form["json"]

            else:
                print("inside request - ", request)

                if request.content_type == 'application/json':
                    json_data = request.get_json()
                elif request.content_type == 'application/x-www-form-urlencoded':
                    json_data = request.form.get('json')
                    # if json_data:
                    #     json_data = json.loads(json_data)
                else:
                    return 'Unsupported Media Type', 415
                # app.logger.debug(f"Request contains json, request={request}")
                # json_data = request.json

            app.logger.debug(f"JSON={json_data}")
            json_data = json.loads(json_data)["data"]

            current_json = json_data

            License_Plate_Number=str(json_data["results"][0]["plate"]).upper()
            Bbox=json_data["results"][0]["box"]

            #License_Plate_Number=json_data["results"][0]["plate"]
            Make=''#json_data["results"][0][]
            Model=''#json_data["camera_id"]
            Color=''#json_data["camera_id"]
            Vehicle_Type=json_data["results"][0]["vehicle"]["type"]
            Vehicle_Chargeable_Type="" #TODO
            Candidates=json_data["results"][0]["candidates"]
            Camera_ID = json_data["camera_id"]
            Time_Local = json_data["timestamp_local"]
            # if Camera_ID in ['camera-1', 'camera-3']:
            #     direction='Entry'
            #     Entry_Camera_ID=json_data["camera_id"]
            #     Entry_Time=json_data["timestamp_local"]
            #     Parking_Status="True"#"New"
            #     Parking_Rate_Per_Min=0
            # else:
            #     direction='Exit'
            #     Exit_Camera_ID=json_data["camera_id"]
            #     Exit_Time=json_data["timestamp_local"]
            #     Parking_Status="True"#"DetectedAtExit"
            #     Total_Time_Parked_In_Mins=1 #TODO
            #     timestamp = datetime.datetime.utcnow()
            is_pattern_matched = bool(regexp.search(License_Plate_Number)) or bool(regexp_bharat.search(License_Plate_Number))
            processing_status = 'new'

            current_plate_number = License_Plate_Number
            current_car_type = Vehicle_Type
            #plate_issue = random.choice(
             #   ['stolen', 'expired', 'number_mismatch', 'belt_not_fastened', 'using_phone_driving', 'NO ISSUE', 'NO ISSUE', 'NO ISSUE', 'NO ISSUE', 'NO ISSUE'])
            if License_Plate_Number in plate_dict.keys():
                plate_dict[License_Plate_Number] += 1
            else:
                plate_dict[License_Plate_Number] = 1

            if not is_pattern_matched:
                #try to find out better candidate from Candidates
                found_better_plate = False
                if len(Candidates) > 1:
                    for x in Candidates[1:]:
                        #print(x)
                        better_plate = x['plate'].upper()
                        if bool(regexp.search(better_plate)) or bool(regexp_bharat.search(better_plate)):
                            found_better_plate=True
                            break
                    if found_better_plate:
                        app.logger.debug(f'   ! {better_plate} prediction is used instead of {License_Plate_Number}')
                        License_Plate_Number = better_plate
                        is_pattern_matched = True

            original_link = vehicle_link = plate_img_link = ''
            if files:
                app.logger.debug("Request contains image")
                # upload_to = f"{date.today()}/"
                upload_to = f"images/"
                if not os.path.exists(upload_to):
                    try:
                        os.makedirs(upload_to)
                    except OSError as exc:  # Guard against race condition
                        if exc.errno != errno.EEXIST:
                            raise
                for key in files.keys():  # The file doesn't exist under upload
                    app.logger.debug(f"key: {key}")
                    f = files[key]
                    new_filename = f'{os.path.splitext(f.filename)[0]}_{Camera_ID}_{License_Plate_Number}.jpg'
                    # filename = f"{upload_to}/{new_filename}"
                    filename = os.path.join(upload_to, new_filename)
                    f.save(filename)
                    print("Saving the files!!!!! - ", filename)
                    # filename_abs = os.path.abspath(filename)
                    print("new_filename path!!!!! - ", new_filename)

                    original_link = new_filename

                    # blob = bucket.blob(f'images/{filename}')
                    # blob.upload_from_filename(filename)
                    # blob.make_public()
                    # print(blob.public_url)
                    # if key=='original':
                    #     original_link = blob.public_url
                    # elif key=='vehicle':
                    #     vehicle_link = blob.public_url
                    # elif key=='plate_img':
                    #     plate_img_link = blob.public_url

                    #break


            center_y = int((Bbox['ymax']+Bbox['ymin'])/2)
            center_x = int((Bbox['xmax']+Bbox['xmin'])/2)
            if ApplyMask:
                pos_val = masks[Camera_ID]['mask'][center_y, center_x]
                if pos_val == 'R':
                    processing_status = 'masked'
                    print(f'Position center_x={center_x}, center_y={center_y} was rejected')
                    masked = True
                else:
                    #processing_status = 'created'
                    masked = False
            else:
                masked = False

            with postgres_conn.cursor() as cursor:
                '''cursor.execute(
                    'INSERT INTO anpr_vehicle_readings (camera_id, plate, make, model, color, timestamp, vehicle_type, '
                    'vehicle_chargeable_type, file, vehicle_image_link, plate_image_link, comments, is_pattern_matched, status) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id',
                    (Camera_ID, License_Plate_Number, Make, Model, Color, Time_Local, Vehicle_Type,
                     Vehicle_Chargeable_Type, original_link, vehicle_link, plate_img_link, json.dumps(Candidates), is_pattern_matched, processing_status))'''

                sql = '''INSERT INTO anpr_vehicle_readings (camera_id, plate, make, model, color, timestamp, vehicle_type,
                    vehicle_chargeable_type, file, vehicle_image_link, plate_image_link, comments, is_pattern_matched, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;'''

                arg = [Camera_ID, License_Plate_Number, Make, Model, Color, Time_Local, Vehicle_Type,
                     Vehicle_Chargeable_Type, original_link, vehicle_link, plate_img_link, json.dumps(Candidates),
                       is_pattern_matched, processing_status]

                result = cursor.execute(sql, (arg))
                print("result: ", result)
                print("sql insert stmt: ", (cursor.mogrify(sql, (arg)).decode('utf=8')))
                #print("sql insert stmt returning id: ", )
                #inserted_data = cursor.fetchone()
                #postgres_conn.commit()
                count = cursor.rowcount
                print("insert count: ", count)
                #app.logger.debug(f'Record loaded: {Candidates}')
            app.logger.debug(f"json_data: {json_data}")

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            app.logger.debug(f'{exc_type}, {exc_obj}, {exc_tb}')
            app.logger.debug(f'[{e.__class__.__name__}] {e}')

            print("Error")
            print(f'{exc_type}, {exc_obj}, {exc_tb}')
            print(f'[{e.__class__.__name__}] {e}')
            if 'connection already closed' in str(e):
                app.logger.debug('Connection to Postgres DB corrupted')
                connect_to_db()
                app.logger.debug('Just connected to Postgres DB')
            return 'Record saving failed', 500
        return "OK"


def run_flask():
    app.run(host='0.0.0.0', threaded=True, port=6068, debug=True, use_reloader=True)


if __name__ == '__main__':
    run_flask()