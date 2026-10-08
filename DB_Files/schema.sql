-- Visitor Vehicle Management database schema (PostgreSQL 15).
--
-- Load once into an empty database:
--   psql -v ON_ERROR_STOP=1 -U postgres -d postgres_visitor_vehicle -f schema.sql
--
-- Runs in a single transaction: if any statement fails, nothing is created.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


CREATE TABLE users (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_by character varying(50) NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_name character varying(100) NOT NULL,
    email character varying(50) NOT NULL,
    password character varying(100) NOT NULL,
    user_type character varying(20) NOT NULL,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_email_key UNIQUE (email)
);


CREATE TABLE persons (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_by bigint NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    enrollment_id uuid NOT NULL,
    person_name character varying(100) NOT NULL,
    person_image_location character varying(200) NOT NULL,
    aadhar_number character varying(100),
    aadhar_image_location character varying(200),
    drivers_license_number character varying(100),
    drivers_license_image character varying(200),
    gender character varying(20),
    vid character varying(100),
    dob date,
    guardians_name character varying(100),
    address text,
    mobile_number character varying(100),
    visiting_person_name character varying(100),
    other_id_type text,
    other_id_number text,
    other_id_image_location text,
    CONSTRAINT persons_pkey PRIMARY KEY (id),
    CONSTRAINT persons_enrollment_id_key UNIQUE (enrollment_id),
    CONSTRAINT persons_person_image_location_key UNIQUE (person_image_location),
    CONSTRAINT persons_aadhar_number_key UNIQUE (aadhar_number),
    CONSTRAINT persons_drivers_license_number_key UNIQUE (drivers_license_number),
    CONSTRAINT persons_drivers_license_image_key UNIQUE (drivers_license_image),
    CONSTRAINT unique_other_id_type_number UNIQUE (other_id_type, other_id_number),
    CONSTRAINT unique_other_id_number_image UNIQUE (other_id_number, other_id_image_location)
);


CREATE TABLE passes (
    id serial,
    create_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by bigint NOT NULL,
    type text,
    sub_type text,
    number character varying(50) NOT NULL,
    assigned_to bigint NOT NULL,
    pass_start_date timestamp without time zone,
    pass_end_date timestamp without time zone,
    pass_issue_date timestamp without time zone,
    pass_image_location character varying(200) NOT NULL,
    CONSTRAINT passes_pkey PRIMARY KEY (id),
    CONSTRAINT passes_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES persons (id) ON DELETE CASCADE,
    -- created_by is mandatory, so a user who issued passes can't be deleted
    CONSTRAINT passes_created_by_fkey FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE INDEX passes_assigned_to_idx ON passes (assigned_to);


CREATE TABLE trips (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_by bigint NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    person_id bigint NOT NULL,
    vehicle_number_plate character varying(50),
    entry_time timestamp without time zone NOT NULL,
    exit_time timestamp without time zone,
    is_finished boolean DEFAULT false NOT NULL,
    coming_from character varying(100),
    going_to character varying(100),
    traveler_type character varying(100) NOT NULL,
    number_of_male_passengers bigint,
    number_of_female_passengers bigint,
    number_of_child_passengers bigint,
    trip_reason character varying(200),
    trip_permit_type character varying(200),
    trip_permit_image_location character varying(200),
    driver_trip_id bigint,
    visit_duration interval,
    token_number character varying(200),
    CONSTRAINT trips_pkey PRIMARY KEY (id),
    CONSTRAINT fk_person_id FOREIGN KEY (person_id) REFERENCES persons (id)
);

CREATE INDEX trips_person_id_idx ON trips (person_id);
CREATE INDEX trips_vehicle_number_plate_idx ON trips (vehicle_number_plate);
CREATE INDEX trips_entry_time_idx ON trips (entry_time);
CREATE INDEX trips_unfinished_entry_time_idx ON trips (entry_time) WHERE is_finished = false;


CREATE TABLE vehicles (
    id bigint GENERATED ALWAYS AS IDENTITY,
    created_by bigint NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    vehicle_number_plate character varying(50) NOT NULL,
    vehicle_image_location character varying(200) NOT NULL,
    vehicle_make character varying(50),
    vehicle_model character varying(50),
    vehicle_color character varying(50),
    vehicle_type character varying(50),
    vehicle_registered_to character varying(50) NOT NULL,
    vehicle_registration_number character varying(50),
    vehicle_owner_id bigint NOT NULL,
    CONSTRAINT vehicles_pkey PRIMARY KEY (id),
    CONSTRAINT fk_vehicle_owner FOREIGN KEY (vehicle_owner_id) REFERENCES persons (id)
);

CREATE INDEX vehicles_vehicle_number_plate_idx ON vehicles (vehicle_number_plate);
CREATE INDEX vehicles_vehicle_owner_id_idx ON vehicles (vehicle_owner_id);


CREATE TABLE anpr_vehicle_readings (
    id serial,
    camera_id character varying,
    plate character varying,
    make character varying,
    model character varying,
    color character varying,
    "timestamp" character varying,
    vehicle_type character varying,
    vehicle_chargeable_type character varying,
    file character varying,
    vehicle_image_link character varying,
    plate_image_link character varying,
    comments character varying,
    is_pattern_matched boolean,
    status character varying,
    CONSTRAINT anpr_vehicle_readings_pkey PRIMARY KEY (id)
);

CREATE INDEX anpr_vehicle_readings_plate_idx ON anpr_vehicle_readings (plate);


-- Initial accounts. The password is 'password' for all of them: change it after the first login.
INSERT INTO users (created_by, user_name, email, password, user_type)
VALUES
    ('Super Admin', 'Tushar Khichariya', 'tushar@censuscounters.com', crypt('password', gen_salt('bf')), 'Admin'),
    ('Super Admin', 'Manish Mohanty', 'manish@censuscounters.com', crypt('password', gen_salt('bf')), 'Admin'),
    ('Super Admin', 'Pavel Zolotykh', 'pavel@censuscounters.com', crypt('password', gen_salt('bf')), 'Admin'),
    ('Super Admin', 'Support Guy', 'support@censuscounters.com', crypt('password', gen_salt('bf')), 'Reader');

COMMIT;
