import os
import psycopg2
import pandas as pd
from sqlalchemy import create_engine

conn = psycopg2.connect(
        host="localhost",
        database="postgres_visitor_vehicle",
        user="postgres",
        password="postgres")

print("connection Done")

cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS anpr_Vehicle_Readings (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP,
        plate VARCHAR(255),
        score FLOAT,
        dscore FLOAT,
        file VARCHAR(255),
        box JSONB,
        make VARCHAR(255),
        model VARCHAR(255),
        color VARCHAR(255),
        vehicle VARCHAR(255),
        region VARCHAR(255),
        orientation VARCHAR(255),
        candidates JSONB,
        source_url VARCHAR(255),
        position_sec FLOAT,
        direction VARCHAR(255),
        status VARCHAR(20),
        plate_fixed BOOLEAN,
        update_time TIMESTAMP
    )
''')
conn.commit()
cursor.close()

print("Database Created!")

db_connection = {
    'host': 'localhost',
    'port': '5432',
    'database': 'postgres_visitor_vehicle',
    'user': 'postgres',
    'password': 'postgres'
}

print("connection Done")
#df = pd.read_csv('./DB_Files/plate_recognition_results.csv')
df = pd.read_csv('../src/ANPR/anpr_data/camera-1_24-08-22.csv')

print(df)

engine = create_engine(f"postgresql://{db_connection['user']}:{db_connection['password']}@{db_connection['host']}:{db_connection['port']}/{db_connection['database']}")
df.to_sql('anpr_vehicle_readings', engine, index=True, if_exists='replace')