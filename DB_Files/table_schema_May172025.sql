--
-- PostgreSQL database dump
--

-- Dumped from database version 15.1
-- Dumped by pg_dump version 15.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: anpr_vehicle_readings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.anpr_vehicle_readings (
    id integer NOT NULL,
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
    status character varying
);


ALTER TABLE public.anpr_vehicle_readings OWNER TO postgres;

--
-- Name: anpr_vehicle_readings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.anpr_vehicle_readings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.anpr_vehicle_readings_id_seq OWNER TO postgres;

--
-- Name: anpr_vehicle_readings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.anpr_vehicle_readings_id_seq OWNED BY public.anpr_vehicle_readings.id;


--
-- Name: passes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.passes (
    id integer NOT NULL,
    create_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_by bigint NOT NULL,
    type text,
    sub_type text,
    number character varying(50) NOT NULL,
    assigned_to bigint NOT NULL,
    pass_start_date timestamp without time zone,
    pass_end_date timestamp without time zone,
    pass_issue_date timestamp without time zone,
    pass_image_location character varying(200) NOT NULL
);


ALTER TABLE public.passes OWNER TO postgres;

--
-- Name: passes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.passes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.passes_id_seq OWNER TO postgres;

--
-- Name: passes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.passes_id_seq OWNED BY public.passes.id;


--
-- Name: persons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.persons (
    id bigint NOT NULL,
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
    address character varying(100),
    mobile_number character varying(100),
    visiting_person_name character varying(100),
    other_id_type text,
    other_id_number text,
    other_id_image_location text
);


ALTER TABLE public.persons OWNER TO postgres;

--
-- Name: persons_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.persons ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.persons_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: trips; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.trips (
    id bigint NOT NULL,
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
    token_number character varying(200)
);


ALTER TABLE public.trips OWNER TO postgres;

--
-- Name: trips_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.trips ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.trips_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id bigint NOT NULL,
    created_by character varying(50) NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_name character varying(100) NOT NULL,
    email character varying(50) NOT NULL,
    password character varying(100) NOT NULL,
    user_type character varying(20) NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.users ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: vehicles; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vehicles (
    id bigint NOT NULL,
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
    vehicle_owner_id bigint NOT NULL
);


ALTER TABLE public.vehicles OWNER TO postgres;

--
-- Name: vehicles_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.vehicles ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.vehicles_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: anpr_vehicle_readings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anpr_vehicle_readings ALTER COLUMN id SET DEFAULT nextval('public.anpr_vehicle_readings_id_seq'::regclass);


--
-- Name: passes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.passes ALTER COLUMN id SET DEFAULT nextval('public.passes_id_seq'::regclass);


--
-- Name: anpr_vehicle_readings anpr_vehicle_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anpr_vehicle_readings
    ADD CONSTRAINT anpr_vehicle_readings_pkey PRIMARY KEY (id);


--
-- Name: passes passes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.passes
    ADD CONSTRAINT passes_pkey PRIMARY KEY (id);


--
-- Name: persons persons_aadhar_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_aadhar_number_key UNIQUE (aadhar_number);


--
-- Name: persons persons_drivers_license_image_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_drivers_license_image_key UNIQUE (drivers_license_image);


--
-- Name: persons persons_drivers_license_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_drivers_license_number_key UNIQUE (drivers_license_number);


--
-- Name: persons persons_enrollment_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_enrollment_id_key UNIQUE (enrollment_id);


--
-- Name: persons persons_person_image_location_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_person_image_location_key UNIQUE (person_image_location);


--
-- Name: persons persons_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (id);


--
-- Name: trips trips_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.trips
    ADD CONSTRAINT trips_pkey PRIMARY KEY (id);


--
-- Name: persons unique_other_id_number_image; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT unique_other_id_number_image UNIQUE (other_id_number, other_id_image_location);


--
-- Name: persons unique_other_id_type_number; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT unique_other_id_type_number UNIQUE (other_id_type, other_id_number);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: trips fk_person_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.trips
    ADD CONSTRAINT fk_person_id FOREIGN KEY (person_id) REFERENCES public.persons(id);


--
-- Name: vehicles fk_vehicle_owner; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehicles
    ADD CONSTRAINT fk_vehicle_owner FOREIGN KEY (vehicle_owner_id) REFERENCES public.persons(id);


--
-- Name: passes passes_assigned_to_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.passes
    ADD CONSTRAINT passes_assigned_to_fkey FOREIGN KEY (assigned_to) REFERENCES public.persons(id) ON DELETE CASCADE;


--
-- Name: passes passes_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.passes
    ADD CONSTRAINT passes_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

