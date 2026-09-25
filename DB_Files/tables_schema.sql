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
-- Name: persons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.persons (
    id bigint NOT NULL,
    created_by bigint NOT NULL,
    date_created timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    enrollment_id uuid NOT NULL,
    person_name character varying(100) NOT NULL,
    person_image_location character varying(200) NOT NULL,
    aadhar_number character varying(100) NOT NULL,
    aadhar_image_location character varying(200) NOT NULL,
    drivers_license_number character varying(100),
    drivers_license_image character varying(200),
    gender character varying(20),
    vid character varying(100),
    address text,
    dob date,
    fathers_name character varying(100),
    resident_of character varying(100),
    mobile_number character varying(100),
    visiting_person_name character varying(100)
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
    coming_from character varying(100) NOT NULL,
    going_to character varying(100) NOT NULL,
    traveler_type character varying(100) NOT NULL,
    number_of_male_passengers bigint,
    number_of_female_passengers bigint,
    number_of_child_passengers bigint,
    trip_reason character varying(200) NOT NULL,
    trip_permit_type character varying(200) NOT NULL,
    trip_permit_image_location character varying(200),
    driver_trip_id bigint,
    visit_duration interval NOT NULL,
    pass_number character varying(200) NOT NULL
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
    vehicle_type character varying(50) NOT NULL,
    vehicle_registered_to character varying(50) NOT NULL,
    vehicle_registration_number character varying(50) NOT NULL
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
-- Data for Name: anpr_vehicle_readings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.anpr_vehicle_readings (id, camera_id, plate, make, model, color, "timestamp", vehicle_type, vehicle_chargeable_type, file, vehicle_image_link, plate_image_link, comments, is_pattern_matched, status) FROM stdin;
2951	camera-1	KA51C0582				2024-08-28 09:58:44.913613+05:30	Big Truck		09-58-44.913613_camera-1_KA51C0582.jpg			[{"score": 0.883, "plate": "ka51c0582"}, {"score": 0.828, "plate": "ka51c0532"}, {"score": 0.816, "plate": "ka51co582"}, {"score": 0.816, "plate": "ka5ic0582"}, {"score": 0.761, "plate": "ka51co532"}, {"score": 0.761, "plate": "ka5ic0532"}, {"score": 0.749, "plate": "ka5ico582"}, {"score": 0.693, "plate": "ka5ico532"}]	t	new
2952	camera-1	KA01JK2924				2024-08-28 09:58:45.400182+05:30	Motorcycle		09-58-45.400182_camera-1_KA01JK2924.jpg			[{"score": 0.897, "plate": "ka01jk2924"}, {"score": 0.836, "plate": "ka0ijk2924"}]	t	new
2953	camera-1	KA51AE0086				2024-08-28 09:58:48.841074+05:30	Bus		09-58-48.841074_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.84, "plate": "ka5iae0086"}, {"score": 0.839, "plate": "ka51aeo086"}]	t	new
2954	camera-1	KA04MT0565				2024-08-28 09:58:50.867900+05:30	Sedan		09-58-50.867900_camera-1_KA04MT0565.jpg			[{"score": 0.837, "plate": "ka04mt0565"}, {"score": 0.83, "plate": "ka04nt0565"}, {"score": 0.794, "plate": "ka04mto565"}, {"score": 0.787, "plate": "ka04nto565"}, {"score": 0.783, "plate": "ka04mt0665"}, {"score": 0.781, "plate": "ra04mt0565"}, {"score": 0.777, "plate": "ka04nt0665"}, {"score": 0.774, "plate": "ra04nt0565"}, {"score": 0.74, "plate": "ka04mto665"}, {"score": 0.738, "plate": "ra04mto565"}]	t	new
2955	camera-1	KA02AC9911				2024-08-28 09:58:55.605425+05:30	Sedan		09-58-55.605425_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
2956	camera-1	KA01R4987				2024-08-28 09:58:53.723296+05:30	Motorcycle		09-58-53.723296_camera-1_KA01R4987.jpg			[{"score": 0.808, "plate": "ka01r4987"}, {"score": 0.808, "plate": "ka01ur4987"}, {"score": 0.759, "plate": "ka01r4997"}, {"score": 0.759, "plate": "ka0ar4987"}, {"score": 0.759, "plate": "ka0aur4987"}, {"score": 0.758, "plate": "ka01ur4997"}, {"score": 0.756, "plate": "ka0ir4987"}, {"score": 0.756, "plate": "ka0iur4987"}, {"score": 0.74, "plate": "ka40ar4987"}, {"score": 0.74, "plate": "ka40aur4987"}]	t	new
2957	camera-1	KA04MP7575				2024-08-28 09:59:01.541804+05:30	Sedan		09-59-01.541804_camera-1_KA04MP7575.jpg			[{"score": 0.896, "plate": "ka04mp7575"}]	t	new
2958	camera-1	KA51AF1973				2024-08-28 09:59:03.918727+05:30	Big Truck		09-59-03.918727_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.84, "plate": "ka51afi973"}, {"score": 0.84, "plate": "ka5iaf1973"}]	t	new
2959	camera-1	KA01AK0126				2024-08-28 09:59:02.192838+05:30	Van		09-59-02.192838_camera-1_KA01AK0126.jpg			[{"score": 0.899, "plate": "ka01ak0126"}, {"score": 0.839, "plate": "ka01ako126"}, {"score": 0.838, "plate": "ka0iak0126"}]	t	new
2960	camera-1	KA3HD6924				2024-08-28 09:59:09.059353+05:30	Motorcycle		09-59-09.059353_camera-1_KA3HD6924.jpg			[{"score": 0.777, "plate": "ka3hd6924"}, {"score": 0.743, "plate": "ka3d6924"}, {"score": 0.739, "plate": "ka3hd6904"}, {"score": 0.729, "plate": "ka3ho6924"}, {"score": 0.704, "plate": "ka3d6904"}, {"score": 0.695, "plate": "ka306924"}, {"score": 0.694, "plate": "ka3o6924"}, {"score": 0.691, "plate": "ka3ho6904"}, {"score": 0.656, "plate": "ka306904"}, {"score": 0.656, "plate": "ka3o6904"}]	t	new
2961	camera-1	KA03AC9138				2024-08-28 09:59:12.201977+05:30	Van		09-59-12.201977_camera-1_KA03AC9138.jpg			[{"score": 0.793, "plate": "ka03ac9138"}, {"score": 0.758, "plate": "ma03ac9138"}]	t	new
2962	camera-1	KA04MV0753				2024-08-28 09:59:13.326111+05:30	Sedan		09-59-13.326111_camera-1_KA04MV0753.jpg			[{"score": 0.899, "plate": "ka04mv0753"}, {"score": 0.838, "plate": "ka04mvo753"}]	t	new
2963	camera-1	KA03KD6851				2024-08-28 09:59:14.054179+05:30	Motorcycle		09-59-14.054179_camera-1_KA03KD6851.jpg			[{"score": 0.897, "plate": "ka03kd6851"}]	t	new
2964	camera-1	KA01MN4163				2024-08-28 09:59:17.529256+05:30	Sedan		09-59-17.529256_camera-1_KA01MN4163.jpg			[{"score": 0.9, "plate": "ka01mn4163"}, {"score": 0.839, "plate": "ka0imn4163"}]	t	new
2965	camera-1	DL8CAH6452				2024-08-28 09:59:19.929665+05:30	Sedan		09-59-19.929665_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
2966	camera-1	KA03KK2819				2024-08-28 09:59:20.202912+05:30	Motorcycle		09-59-20.202912_camera-1_KA03KK2819.jpg			[{"score": 0.892, "plate": "ka03kk2819"}, {"score": 0.843, "plate": "ka03xk2819"}]	t	new
2967	camera-1	KA03NE8669				2024-08-28 09:59:25.642629+05:30	Sedan		09-59-25.642629_camera-1_KA03NE8669.jpg			[{"score": 0.899, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03neb669"}]	t	new
2968	camera-1	KA03MS1507				2024-08-28 09:59:29.911829+05:30	Sedan		09-59-29.911829_camera-1_KA03MS1507.jpg			[{"score": 0.882, "plate": "ka03ms1507"}, {"score": 0.854, "plate": "ka03ns1507"}, {"score": 0.821, "plate": "ka03msi507"}, {"score": 0.794, "plate": "ka03nsi507"}]	t	new
2969	camera-1	KA41D0023				2024-08-28 09:59:36.145967+05:30	SUV		09-59-36.145967_camera-1_KA41D0023.jpg			[{"score": 0.9, "plate": "ka41d0023"}, {"score": 0.833, "plate": "ka41do023"}, {"score": 0.833, "plate": "ka4id0023"}, {"score": 0.766, "plate": "ka4ido023"}]	t	new
2970	camera-1	KA03NJ1636				2024-08-28 09:59:46.566150+05:30	Van		09-59-46.566150_camera-1_KA03NJ1636.jpg			[{"score": 0.9, "plate": "ka03nj1636"}, {"score": 0.84, "plate": "ka03nji636"}]	t	new
2971	camera-1	KA53U6438				2024-08-28 09:59:45.839716+05:30	Motorcycle		09-59-45.839716_camera-1_KA53U6438.jpg			[{"score": 0.882, "plate": "ka53u6438"}]	t	new
2972	camera-1	TN294306				2024-08-28 10:00:27.165957+05:30	Motorcycle		10-00-27.165957_camera-1_TN294306.jpg			[{"score": 0.897, "plate": "tn294306"}]	t	new
2973	camera-1	KA51A8901				2024-08-28 10:00:31.412132+05:30	Unknown		10-00-31.412132_camera-1_KA51A8901.jpg			[{"score": 0.891, "plate": "ka51a8901"}, {"score": 0.828, "plate": "ka51a9901"}, {"score": 0.828, "plate": "ka51ab901"}, {"score": 0.823, "plate": "ka5ia8901"}, {"score": 0.761, "plate": "ka5ia9901"}, {"score": 0.76, "plate": "ka5iab901"}]	t	new
2974	camera-1	KA51C0582				2024-08-28 10:00:32.001522+05:30	Big Truck		10-00-32.001522_camera-1_KA51C0582.jpg			[{"score": 0.89, "plate": "ka51c0582"}, {"score": 0.822, "plate": "ka51co582"}, {"score": 0.822, "plate": "ka5ic0582"}, {"score": 0.755, "plate": "ka5ico582"}]	t	new
2975	camera-1	KA01JK2924				2024-08-28 10:00:33.392878+05:30	Motorcycle		10-00-33.392878_camera-1_KA01JK2924.jpg			[{"score": 0.898, "plate": "ka01jk2924"}, {"score": 0.837, "plate": "ka0ijk2924"}]	t	new
2976	camera-1	KA51AE0086				2024-08-28 10:00:36.544427+05:30	Bus		10-00-36.544427_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.839, "plate": "ka51aeo086"}, {"score": 0.839, "plate": "ka5iae0086"}]	t	new
2977	camera-1	KA02AC9911				2024-08-28 10:00:43.247705+05:30	Sedan		10-00-43.247705_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3008	camera-1	KA02AG9003				2025-01-07 17:51:28.796533+05:30	Unknown		17-51-28.796533_camera-1_KA02AG9003.jpg			[{"score": 0.9, "plate": "ka02ag9003"}]	t	new
3009	camera-1	KA03KK2819				2025-01-07 17:51:29.863131+05:30	Motorcycle		17-51-29.863131_camera-1_KA03KK2819.jpg			[{"score": 0.895, "plate": "ka03kk2819"}, {"score": 0.84, "plate": "ka03kx2819"}]	t	new
2978	camera-1	KA01UR8987				2024-08-28 10:00:41.565226+05:30	Motorcycle		10-00-41.565226_camera-1_KA01UR8987.jpg			[{"score": 0.835, "plate": "ka01ur8987"}, {"score": 0.812, "plate": "ka01jr8987"}, {"score": 0.802, "plate": "ka01ur6987"}, {"score": 0.791, "plate": "ka01urb987"}, {"score": 0.787, "plate": "ka01aur8987"}, {"score": 0.784, "plate": "ka01ur8997"}, {"score": 0.779, "plate": "ka01jr6987"}, {"score": 0.774, "plate": "ka0iur8987"}, {"score": 0.768, "plate": "ka01jrb987"}, {"score": 0.766, "plate": "ka01ajr8987"}]	t	new
2979	camera-1	KA51AF1973				2024-08-28 10:00:50.630470+05:30	Big Truck		10-00-50.630470_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
2980	camera-1	KA04MP7575				2024-08-28 10:00:49.106105+05:30	SUV		10-00-49.106105_camera-1_KA04MP7575.jpg			[{"score": 0.9, "plate": "ka04mp7575"}]	t	new
2981	camera-1	KA01AK0126				2024-08-28 10:00:49.888238+05:30	Van		10-00-49.888238_camera-1_KA01AK0126.jpg			[{"score": 0.891, "plate": "ka01ak0126"}, {"score": 0.839, "plate": "ka01akd126"}, {"score": 0.838, "plate": "ka01ako126"}, {"score": 0.831, "plate": "ka0iak0126"}]	t	new
2982	camera-1	KA03HD6924				2024-08-28 10:00:56.517493+05:30	Motorcycle		10-00-56.517493_camera-1_KA03HD6924.jpg			[{"score": 0.821, "plate": "ka03hd6924"}, {"score": 0.811, "plate": "ka05hd6924"}, {"score": 0.792, "plate": "ka03hz6924"}, {"score": 0.782, "plate": "ka05hz6924"}, {"score": 0.768, "plate": "ka03d6924"}, {"score": 0.757, "plate": "ka05d6924"}, {"score": 0.738, "plate": "ka03z6924"}, {"score": 0.728, "plate": "ka05z6924"}]	t	new
2983	camera-1	KA03AC9138				2024-08-28 10:00:59.545918+05:30	Unknown		10-00-59.545918_camera-1_KA03AC9138.jpg			[{"score": 0.871, "plate": "ka03ac9138"}, {"score": 0.836, "plate": "ma03ac9138"}, {"score": 0.785, "plate": "kk03ac9138"}, {"score": 0.754, "plate": "mk03ac9138"}]	t	new
2984	camera-1	KA04MV0753				2024-08-28 10:01:00.961242+05:30	Sedan		10-01-00.961242_camera-1_KA04MV0753.jpg			[{"score": 0.899, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
2985	camera-1	KA03KD6851				2024-08-28 10:01:01.776123+05:30	Motorcycle		10-01-01.776123_camera-1_KA03KD6851.jpg			[{"score": 0.891, "plate": "ka03kd6851"}, {"score": 0.8, "plate": "ka03kd651"}]	t	new
2986	camera-1	KA01MN4163				2024-08-28 10:01:05.155725+05:30	Sedan		10-01-05.155725_camera-1_KA01MN4163.jpg			[{"score": 0.898, "plate": "ka01mn4163"}, {"score": 0.837, "plate": "ka0imn4163"}]	t	new
2987	camera-1	DL8CAH6452				2024-08-28 10:01:06.575257+05:30	SUV		10-01-06.575257_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
2988	camera-1	KA02AG9003				2024-08-28 10:01:06.575257+05:30	Unknown		10-01-06.575257_camera-1_KA02AG9003.jpg			[{"score": 0.9, "plate": "ka02ag9003"}]	t	new
2989	camera-1	KA03NJ1636				2025-01-07 17:19:39.039915+05:30	Van		17-19-39.039915_camera-1_KA03NJ1636.jpg			[{"score": 0.899, "plate": "ka03nj1636"}, {"score": 0.839, "plate": "ka03nji636"}]	t	new
2990	camera-1	KA02AC9911				2025-01-07 17:27:46.263975+05:30	Sedan		17-27-46.263975_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
2991	camera-1	KA02AC9911				2025-01-07 17:27:46.263975+05:30	Sedan		17-27-46.263975_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
2992	camera-1	KA02AC9911				2025-01-07 17:27:46.263975+05:30	Sedan		17-27-46.263975_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
2993	camera-1	KA02AC9911				2025-01-07 17:27:46.263975+05:30	Sedan		17-27-46.263975_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
2994	camera-1	HA51C0582				2025-01-07 17:50:52.595679+05:30	Big Truck		17-50-52.595679_camera-1_HA51C0582.jpg			[{"score": 0.868, "plate": "ha51c0582"}, {"score": 0.818, "plate": "ka51c0582"}, {"score": 0.813, "plate": "hi51c0582"}, {"score": 0.801, "plate": "ha5ic0582"}, {"score": 0.8, "plate": "ha51co582"}, {"score": 0.763, "plate": "ki51c0582"}, {"score": 0.751, "plate": "ka51co582"}, {"score": 0.751, "plate": "ka5ic0582"}, {"score": 0.745, "plate": "hi51co582"}, {"score": 0.745, "plate": "hi5ic0582"}]	t	new
2995	camera-1	KA51A8901				2025-01-07 17:50:53.122299+05:30	Big Truck		17-50-53.122299_camera-1_KA51A8901.jpg			[{"score": 0.897, "plate": "ka51a8901"}, {"score": 0.829, "plate": "ka51ab901"}, {"score": 0.829, "plate": "ka5ia8901"}, {"score": 0.762, "plate": "ka5iab901"}]	t	new
2996	camera-1	KA01JK2924				2025-01-07 17:50:55.596842+05:30	Motorcycle		17-50-55.596842_camera-1_KA01JK2924.jpg			[{"score": 0.881, "plate": "ka01jk2924"}, {"score": 0.839, "plate": "ka0ijk2924"}]	t	new
2997	camera-1	KA51AE0086				2025-01-07 17:50:58.590067+05:30	Bus		17-50-58.590067_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.84, "plate": "ka51aeo086"}, {"score": 0.84, "plate": "ka5iae0086"}]	t	new
2998	camera-1	KA04MT0565				2025-01-07 17:51:00.716374+05:30	Sedan		17-51-00.716374_camera-1_KA04MT0565.jpg			[{"score": 0.859, "plate": "ka04mt0565"}, {"score": 0.812, "plate": "ka04mtd565"}, {"score": 0.807, "plate": "ka04mto565"}, {"score": 0.777, "plate": "ka04mt0665"}, {"score": 0.741, "plate": "ka04mtd6565"}, {"score": 0.737, "plate": "ka04mto6565"}, {"score": 0.735, "plate": "ka04mtd665"}, {"score": 0.73, "plate": "ka04mto665"}]	t	new
2999	camera-1	KA02AC9911				2025-01-07 17:51:05.193918+05:30	Sedan		17-51-05.193918_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3000	camera-1	KA51AF1973				2025-01-07 17:51:12.441009+05:30	Big Truck		17-51-12.441009_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.84, "plate": "ka5iaf1973"}, {"score": 0.839, "plate": "ka51afi973"}]	t	new
3001	camera-1	KA04MP7575				2025-01-07 17:51:11.364528+05:30	SUV		17-51-11.364528_camera-1_KA04MP7575.jpg			[{"score": 0.9, "plate": "ka04mp7575"}]	t	new
3002	camera-1	KA0AK0126				2025-01-07 17:51:11.902749+05:30	Unknown		17-51-11.902749_camera-1_KA0AK0126.jpg			[{"score": 0.859, "plate": "ka0ak0126"}, {"score": 0.823, "plate": "ka01ak0126"}, {"score": 0.802, "plate": "ka0iak0126"}, {"score": 0.791, "plate": "ka0ako126"}, {"score": 0.787, "plate": "ka1ak0126"}, {"score": 0.763, "plate": "ka01ako126"}, {"score": 0.726, "plate": "ka1ako126"}]	t	new
3003	camera-1	KA03AC9138				2025-01-07 17:51:21.642715+05:30	Unknown		17-51-21.642715_camera-1_KA03AC9138.jpg			[{"score": 0.877, "plate": "ka03ac9138"}, {"score": 0.778, "plate": "ko3ac9138"}]	t	new
3004	camera-1	KA04MV0753				2025-01-07 17:51:22.797395+05:30	Sedan		17-51-22.797395_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3005	camera-1	KA03KD6851				2025-01-07 17:51:23.882099+05:30	Motorcycle		17-51-23.882099_camera-1_KA03KD6851.jpg			[{"score": 0.892, "plate": "ka03kd6851"}]	t	new
3006	camera-1	KA01MN4163				2025-01-07 17:51:27.254090+05:30	Sedan		17-51-27.254090_camera-1_KA01MN4163.jpg			[{"score": 0.899, "plate": "ka01mn4163"}, {"score": 0.838, "plate": "ka0imn4163"}]	t	new
3007	camera-1	DL8CAH6452				2025-01-07 17:51:29.991149+05:30	SUV		17-51-29.991149_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
3010	camera-1	KA03NE8669				2025-01-07 17:51:35.068144+05:30	Sedan		17-51-35.068144_camera-1_KA03NE8669.jpg			[{"score": 0.898, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03neb669"}]	t	new
3011	camera-1	KA03MS1507				2025-01-07 17:51:39.128141+05:30	Sedan		17-51-39.128141_camera-1_KA03MS1507.jpg			[{"score": 0.899, "plate": "ka03ms1507"}, {"score": 0.839, "plate": "ka03msi507"}]	t	new
3012	camera-1	CA41D0023				2025-01-07 17:51:44.329242+05:30	SUV		17-51-44.329242_camera-1_CA41D0023.jpg			[{"score": 0.831, "plate": "ca41d0023"}, {"score": 0.824, "plate": "ka41d0023"}, {"score": 0.773, "plate": "ca41dd023"}, {"score": 0.771, "plate": "ca41do023"}, {"score": 0.765, "plate": "ka41dd023"}, {"score": 0.764, "plate": "ca4id0023"}, {"score": 0.764, "plate": "ka41do023"}, {"score": 0.757, "plate": "ka4id0023"}, {"score": 0.706, "plate": "ca4idd023"}, {"score": 0.704, "plate": "ca4ido023"}]	t	new
3013	camera-1	KA03NJ1636				2025-01-07 17:51:56.785938+05:30	Van		17-51-56.785938_camera-1_KA03NJ1636.jpg			[{"score": 0.898, "plate": "ka03nj1636"}, {"score": 0.837, "plate": "ka03nji636"}]	t	new
3014	camera-1	AK01JO4074				2025-01-07 17:52:02.463412+05:30	Motorcycle		17-52-02.463412_camera-1_AK01JO4074.jpg			[{"score": 0.762, "plate": "ak01jo4074"}, {"score": 0.703, "plate": "ak0ijo4074"}, {"score": 0.697, "plate": "ar01jo4074"}, {"score": 0.672, "plate": "ak10ijo4074"}, {"score": 0.643, "plate": "ar0ijo4074"}, {"score": 0.619, "plate": "ar10ijo4074"}]	t	new
3015	camera-1	HA51C0582				2025-01-07 17:52:40.283935+05:30	Big Truck		17-52-40.283935_camera-1_HA51C0582.jpg			[{"score": 0.871, "plate": "ha51c0582"}, {"score": 0.825, "plate": "ma51c0582"}, {"score": 0.818, "plate": "ha51c0562"}, {"score": 0.804, "plate": "ha51co582"}, {"score": 0.804, "plate": "ha5ic0582"}, {"score": 0.772, "plate": "ma51c0562"}, {"score": 0.758, "plate": "ma5ic0582"}, {"score": 0.757, "plate": "ma51co582"}, {"score": 0.751, "plate": "ha51co562"}, {"score": 0.751, "plate": "ha5ic0562"}]	t	new
3016	camera-1	KA51A8901				2025-01-07 17:52:40.757175+05:30	Big Truck		17-52-40.757175_camera-1_KA51A8901.jpg			[{"score": 0.896, "plate": "ka51a8901"}, {"score": 0.829, "plate": "ka51ab901"}, {"score": 0.829, "plate": "ka5ia8901"}, {"score": 0.761, "plate": "ka5iab901"}]	t	new
3017	camera-1	KA01JK2924				2025-01-07 17:52:43.166432+05:30	Motorcycle		17-52-43.166432_camera-1_KA01JK2924.jpg			[{"score": 0.9, "plate": "ka01jk2924"}, {"score": 0.839, "plate": "ka0ijk2924"}]	t	new
3018	camera-1	KA51AE0086				2025-01-07 17:52:46.549088+05:30	Bus		17-52-46.549088_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.839, "plate": "ka51aeo086"}, {"score": 0.839, "plate": "ka5iae0086"}]	t	new
3019	camera-1	KA04MT0665				2025-01-07 17:52:48.745753+05:30	Sedan		17-52-48.745753_camera-1_KA04MT0665.jpg			[{"score": 0.847, "plate": "ka04mt0665"}, {"score": 0.844, "plate": "ka04mt0565"}, {"score": 0.787, "plate": "ka04mto665"}, {"score": 0.784, "plate": "ka04mto565"}]	t	new
3020	camera-1	KA02AC9911				2025-01-07 17:52:53.058695+05:30	Sedan		17-52-53.058695_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3021	camera-1	KA01UR4987				2025-01-07 17:52:51.311393+05:30	Motorcycle		17-52-51.311393_camera-1_KA01UR4987.jpg			[{"score": 0.825, "plate": "ka01ur4987"}, {"score": 0.813, "plate": "ra01ur4987"}, {"score": 0.766, "plate": "ka0iur4987"}, {"score": 0.754, "plate": "ra0iur4987"}]	t	new
3022	camera-1	KA51AF1973				2025-01-07 17:53:00.144254+05:30	Big Truck		17-53-00.144254_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
3023	camera-1	KA04MP7575				2025-01-07 17:52:58.817804+05:30	SUV		17-52-58.817804_camera-1_KA04MP7575.jpg			[{"score": 0.9, "plate": "ka04mp7575"}]	t	new
3024	camera-1	KA50J6820				2025-01-07 17:53:00.209473+05:30	Motorcycle		17-53-00.209473_camera-1_KA50J6820.jpg			[{"score": 0.843, "plate": "ka50j6820"}, {"score": 0.789, "plate": "ka50j6829"}, {"score": 0.789, "plate": "ka5oj6820"}, {"score": 0.786, "plate": "ka50j6920"}, {"score": 0.783, "plate": "ka90j6820"}, {"score": 0.735, "plate": "ka5oj6829"}, {"score": 0.733, "plate": "ka50j6929"}, {"score": 0.732, "plate": "ka5oj6920"}, {"score": 0.729, "plate": "ka90j6829"}, {"score": 0.729, "plate": "ka9oj6820"}]	t	new
3025	camera-1	KA03AC9138				2025-01-07 17:53:09.309662+05:30	Unknown		17-53-09.309662_camera-1_KA03AC9138.jpg			[{"score": 0.831, "plate": "ka03ac9138"}, {"score": 0.825, "plate": "ma03ac9138"}, {"score": 0.803, "plate": "kh03ac9138"}, {"score": 0.796, "plate": "mh03ac9138"}]	t	new
3026	camera-1	KA04MV0753				2025-01-07 17:53:10.446403+05:30	Sedan		17-53-10.446403_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3027	camera-1	KA03KD6851				2025-01-07 17:53:11.507711+05:30	Motorcycle		17-53-11.507711_camera-1_KA03KD6851.jpg			[{"score": 0.888, "plate": "ka03kd6851"}]	t	new
3028	camera-1	KA04W0753				2025-01-07 17:53:13.178331+05:30	SUV		17-53-13.178331_camera-1_KA04W0753.jpg			[{"score": 0.875, "plate": "ka04w0753"}, {"score": 0.848, "plate": "ka04m0753"}, {"score": 0.825, "plate": "ka04ww0753"}, {"score": 0.808, "plate": "ka04wo753"}, {"score": 0.801, "plate": "ka04mw0753"}, {"score": 0.781, "plate": "ka04mo753"}, {"score": 0.765, "plate": "ka04wwo753"}, {"score": 0.741, "plate": "ka04mwo753"}]	t	new
3029	camera-1	KA01MN4163				2025-01-07 17:53:14.921415+05:30	Sedan		17-53-14.921415_camera-1_KA01MN4163.jpg			[{"score": 0.9, "plate": "ka01mn4163"}, {"score": 0.839, "plate": "ka0imn4163"}]	t	new
3030	camera-1	DL8CAH6452				2025-01-07 17:53:17.666811+05:30	Sedan		17-53-17.666811_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
3031	camera-1	KA03KK2819				2025-01-07 17:53:17.596652+05:30	Motorcycle		17-53-17.596652_camera-1_KA03KK2819.jpg			[{"score": 0.883, "plate": "ka03kk2819"}, {"score": 0.828, "plate": "ka03kx2819"}, {"score": 0.771, "plate": "ao3kk2819"}, {"score": 0.716, "plate": "ao3kx2819"}]	t	new
3032	camera-1	KA03NE8669				2025-01-07 17:53:22.649407+05:30	Sedan		17-53-22.649407_camera-1_KA03NE8669.jpg			[{"score": 0.899, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03neb669"}]	t	new
3033	camera-1	KA03MS1507				2025-01-07 17:53:27.637964+05:30	Sedan		17-53-27.637964_camera-1_KA03MS1507.jpg			[{"score": 0.9, "plate": "ka03ms1507"}, {"score": 0.839, "plate": "ka03msi507"}]	t	new
3034	camera-1	KA41D0023				2025-01-07 17:53:31.996349+05:30	SUV		17-53-31.996349_camera-1_KA41D0023.jpg			[{"score": 0.871, "plate": "ka41dd023"}, {"score": 0.818, "plate": "ca41dd023"}, {"score": 0.809, "plate": "ka41d0023"}, {"score": 0.809, "plate": "ka41do023"}, {"score": 0.806, "plate": "ka4idd023"}, {"score": 0.756, "plate": "ca41d0023"}, {"score": 0.756, "plate": "ca41do023"}, {"score": 0.753, "plate": "ca4idd023"}, {"score": 0.744, "plate": "ka4id0023"}, {"score": 0.744, "plate": "ka4ido023"}]	t	new
3035	camera-1	KA03NJ1636				2025-01-07 17:53:44.449081+05:30	Van		17-53-44.449081_camera-1_KA03NJ1636.jpg			[{"score": 0.9, "plate": "ka03nj1636"}, {"score": 0.839, "plate": "ka03nji636"}]	t	new
3036	camera-1	HA51C0582				2025-01-07 17:54:28.418348+05:30	Big Truck		17-54-28.418348_camera-1_HA51C0582.jpg			[{"score": 0.868, "plate": "ha51c0582"}, {"score": 0.811, "plate": "ha51c0562"}, {"score": 0.801, "plate": "ha51co582"}, {"score": 0.801, "plate": "ha5ic0582"}, {"score": 0.744, "plate": "ha51co562"}, {"score": 0.744, "plate": "ha5ic0562"}, {"score": 0.734, "plate": "ha5ico582"}, {"score": 0.676, "plate": "ha5ico562"}]	t	new
3037	camera-1	KA51A8901				2025-01-07 17:54:27.887482+05:30	Big Truck		17-54-27.887482_camera-1_KA51A8901.jpg			[{"score": 0.899, "plate": "ka51a8901"}, {"score": 0.832, "plate": "ka51ab901"}, {"score": 0.831, "plate": "ka5ia8901"}, {"score": 0.765, "plate": "ka5iab901"}]	t	new
3038	camera-1	KA01JK2924				2025-01-07 17:54:30.849991+05:30	Motorcycle		17-54-30.849991_camera-1_KA01JK2924.jpg			[{"score": 0.9, "plate": "ka01jk2924"}, {"score": 0.839, "plate": "ka0ijk2924"}]	t	new
3039	camera-1	KA04MT0665				2025-01-07 17:54:36.248059+05:30	Sedan		17-54-36.248059_camera-1_KA04MT0665.jpg			[{"score": 0.823, "plate": "ka04mt0665"}, {"score": 0.787, "plate": "ka04nt0665"}, {"score": 0.777, "plate": "ka04mto665"}, {"score": 0.769, "plate": "ka04mt0655"}, {"score": 0.741, "plate": "ka04nto665"}, {"score": 0.733, "plate": "ka04nt0655"}, {"score": 0.723, "plate": "ka04mto655"}, {"score": 0.687, "plate": "ka04nto655"}]	t	new
3040	camera-1	KA02AC9911				2025-01-07 17:54:40.755745+05:30	Sedan		17-54-40.755745_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3041	camera-1	KA01UB4987				2025-01-07 17:54:38.934024+05:30	Motorcycle		17-54-38.934024_camera-1_KA01UB4987.jpg			[{"score": 0.782, "plate": "ka01ub4987"}, {"score": 0.734, "plate": "ka01b4987"}, {"score": 0.724, "plate": "ka0iub4987"}, {"score": 0.675, "plate": "ka0ib4987"}]	t	new
3042	camera-1	KA51AF1973				2025-01-07 17:54:47.747836+05:30	Big Truck		17-54-47.747836_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
3043	camera-1	KA04MP7575				2025-01-07 17:54:46.400183+05:30	SUV		17-54-46.400183_camera-1_KA04MP7575.jpg			[{"score": 0.899, "plate": "ka04mp7575"}]	t	new
3044	camera-1	KA01AK0126				2025-01-07 17:54:47.146391+05:30	Unknown		17-54-47.146391_camera-1_KA01AK0126.jpg			[{"score": 0.877, "plate": "ka01ak0126"}, {"score": 0.847, "plate": "ka0ak0126"}, {"score": 0.833, "plate": "ka0iak0126"}, {"score": 0.825, "plate": "ka1ak0126"}, {"score": 0.816, "plate": "ka01ako126"}, {"score": 0.786, "plate": "ka0ako126"}, {"score": 0.765, "plate": "ka1ako126"}]	t	new
3045	camera-1	KA03AC9138				2025-01-07 17:54:56.900417+05:30	Unknown		17-54-56.900417_camera-1_KA03AC9138.jpg			[{"score": 0.859, "plate": "ka03ac9138"}, {"score": 0.783, "plate": "ko3ac9138"}]	t	new
3046	camera-1	KA04MV0753				2025-01-07 17:54:58.114650+05:30	Sedan		17-54-58.114650_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3047	camera-1	KA03KD6851				2025-01-07 17:54:59.116662+05:30	Motorcycle		17-54-59.116662_camera-1_KA03KD6851.jpg			[{"score": 0.891, "plate": "ka03kd6851"}]	t	new
3048	camera-1	KA01MN4163				2025-01-07 17:55:02.552073+05:30	Sedan		17-55-02.552073_camera-1_KA01MN4163.jpg			[{"score": 0.898, "plate": "ka01mn4163"}, {"score": 0.838, "plate": "ka0imn4163"}]	t	new
3049	camera-1	DL8CAH6452				2025-01-07 17:55:05.944056+05:30	Sedan		17-55-05.944056_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
3050	camera-1	KA03KX2819				2025-01-07 17:55:05.216260+05:30	Motorcycle		17-55-05.216260_camera-1_KA03KX2819.jpg			[{"score": 0.883, "plate": "ka03kx2819"}, {"score": 0.829, "plate": "ka03kk2819"}]	t	new
3051	camera-1	KA03NE8669				2025-01-07 17:55:10.315648+05:30	Sedan		17-55-10.315648_camera-1_KA03NE8669.jpg			[{"score": 0.898, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03neb669"}]	t	new
3052	camera-1	KA03MS1507				2025-01-07 17:55:15.442285+05:30	Sedan		17-55-15.442285_camera-1_KA03MS1507.jpg			[{"score": 0.898, "plate": "ka03ms1507"}, {"score": 0.837, "plate": "ka03msi507"}]	t	new
3053	camera-1	KA41D0023				2025-01-07 17:55:19.617773+05:30	SUV		17-55-19.617773_camera-1_KA41D0023.jpg			[{"score": 0.845, "plate": "ka41dd023"}, {"score": 0.839, "plate": "ka41d0023"}, {"score": 0.816, "plate": "ka41do023"}, {"score": 0.78, "plate": "ka4idd023"}, {"score": 0.774, "plate": "ka4id0023"}, {"score": 0.751, "plate": "ka4ido023"}]	t	new
3054	camera-1	KA03NJ1636				2025-01-07 17:55:31.844536+05:30	Van		17-55-31.844536_camera-1_KA03NJ1636.jpg			[{"score": 0.898, "plate": "ka03nj1636"}, {"score": 0.838, "plate": "ka03nji636"}]	t	new
3055	camera-1	TN294306				2025-01-07 17:56:12.375970+05:30	Motorcycle		17-56-12.375970_camera-1_TN294306.jpg			[{"score": 0.897, "plate": "tn294306"}]	t	new
3056	camera-1	HA51C0582				2025-01-07 17:56:15.851811+05:30	Big Truck		17-56-15.851811_camera-1_HA51C0582.jpg			[{"score": 0.831, "plate": "ha51c0582"}, {"score": 0.816, "plate": "ma51c0582"}, {"score": 0.79, "plate": "ha51c0562"}, {"score": 0.778, "plate": "ha51g0582"}, {"score": 0.776, "plate": "ma51c0562"}, {"score": 0.763, "plate": "ma51g0582"}, {"score": 0.763, "plate": "ha51co582"}, {"score": 0.763, "plate": "ha5ic0582"}, {"score": 0.749, "plate": "ma51co582"}, {"score": 0.749, "plate": "ma5ic0582"}]	t	new
3057	camera-1	KA51A8901				2025-01-07 17:56:15.510995+05:30	Big Truck		17-56-15.510995_camera-1_KA51A8901.jpg			[{"score": 0.897, "plate": "ka51a8901"}, {"score": 0.831, "plate": "ka51ab901"}, {"score": 0.829, "plate": "ka5ia8901"}, {"score": 0.764, "plate": "ka5iab901"}]	t	new
3058	camera-1	KA01JK2924				2025-01-07 17:56:17.995224+05:30	Motorcycle		17-56-17.995224_camera-1_KA01JK2924.jpg			[{"score": 0.9, "plate": "ka01jk2924"}, {"score": 0.839, "plate": "ka0ijk2924"}]	t	new
3059	camera-1	KA51AE0086				2025-01-07 17:56:21.823428+05:30	Bus		17-56-21.823428_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.84, "plate": "ka51aeo086"}, {"score": 0.84, "plate": "ka5iae0086"}]	t	new
3060	camera-1	KAD4M70665				2025-01-07 17:56:24.044277+05:30	Sedan		17-56-24.044277_camera-1_KAD4M70665.jpg			[{"score": 0.841, "plate": "kad4m70665"}, {"score": 0.812, "plate": "ka04m70665"}, {"score": 0.808, "plate": "kad4m70565"}, {"score": 0.802, "plate": "kao4m70665"}, {"score": 0.796, "plate": "kad4k70665"}, {"score": 0.785, "plate": "kad4m7o665"}, {"score": 0.779, "plate": "ka04m70565"}, {"score": 0.768, "plate": "kao4m70565"}, {"score": 0.767, "plate": "ka04k70665"}, {"score": 0.762, "plate": "kad4k70565"}]	f	new
3061	camera-1	KA02AC9911				2025-01-07 17:56:28.220925+05:30	Sedan		17-56-28.220925_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3062	camera-1	RA01U24987				2025-01-07 17:56:26.564711+05:30	Motorcycle		17-56-26.564711_camera-1_RA01U24987.jpg			[{"score": 0.833, "plate": "ra01u24987"}, {"score": 0.818, "plate": "bra01u24987"}, {"score": 0.809, "plate": "bsa01u24987"}, {"score": 0.795, "plate": "rsa01u24987"}, {"score": 0.795, "plate": "8ra01u24987"}, {"score": 0.786, "plate": "8sa01u24987"}, {"score": 0.773, "plate": "ra0iu24987"}, {"score": 0.773, "plate": "rao1u24987"}, {"score": 0.772, "plate": "ra01u249b7"}, {"score": 0.764, "plate": "bra0iu24987"}]	f	new
3063	camera-1	KA51AF1973				2025-01-07 17:56:35.371388+05:30	Big Truck		17-56-35.371388_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
3064	camera-1	KA04MP7575				2025-01-07 17:56:34.021559+05:30	SUV		17-56-34.021559_camera-1_KA04MP7575.jpg			[{"score": 0.899, "plate": "ka04mp7575"}]	t	new
3065	camera-1	KA01AK0126				2025-01-07 17:56:34.772865+05:30	Unknown		17-56-34.772865_camera-1_KA01AK0126.jpg			[{"score": 0.839, "plate": "ka01ak0126"}, {"score": 0.835, "plate": "ka0ak0126"}, {"score": 0.808, "plate": "ka0iak0126"}, {"score": 0.787, "plate": "ka1ak0126"}, {"score": 0.779, "plate": "ka01ako126"}, {"score": 0.774, "plate": "ka0ako126"}, {"score": 0.726, "plate": "ka1ako126"}]	t	new
3066	camera-1	MA03AC9138				2025-01-07 17:56:44.566441+05:30	Unknown		17-56-44.566441_camera-1_MA03AC9138.jpg			[{"score": 0.858, "plate": "ma03ac9138"}, {"score": 0.77, "plate": "ao3ac9138"}, {"score": 0.75, "plate": "mo3ac9138"}]	t	new
3067	camera-1	KA04MV0753				2025-01-07 17:56:45.694026+05:30	Sedan		17-56-45.694026_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3068	camera-1	KA03KD6851				2025-01-07 17:56:46.701130+05:30	Motorcycle		17-56-46.701130_camera-1_KA03KD6851.jpg			[{"score": 0.875, "plate": "ka03kd6851"}]	t	new
3069	camera-1	KA04W0753				2025-01-07 17:56:48.582757+05:30	SUV		17-56-48.582757_camera-1_KA04W0753.jpg			[{"score": 0.882, "plate": "ka04w0753"}, {"score": 0.829, "plate": "ka04w0751"}, {"score": 0.823, "plate": "ka04w6753"}, {"score": 0.822, "plate": "ka04wo753"}, {"score": 0.769, "plate": "ka04w6751"}, {"score": 0.769, "plate": "ka04wo751"}]	t	new
3070	camera-1	KA01MN4163				2025-01-07 17:56:50.179020+05:30	Sedan		17-56-50.179020_camera-1_KA01MN4163.jpg			[{"score": 0.897, "plate": "ka01mn4163"}, {"score": 0.836, "plate": "ka0imn4163"}]	t	new
3071	camera-1	DL8CAH6452				2025-01-07 17:56:53.590545+05:30	Sedan		17-56-53.590545_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
3072	camera-1	KA02AG9003				2025-01-07 17:56:51.670498+05:30	Unknown		17-56-51.670498_camera-1_KA02AG9003.jpg			[{"score": 0.899, "plate": "ka02ag9003"}]	t	new
3073	camera-1	KA03KK2819				2025-01-07 17:56:52.731067+05:30	Motorcycle		17-56-52.731067_camera-1_KA03KK2819.jpg			[{"score": 0.898, "plate": "ka03kk2819"}]	t	new
3074	camera-1	KA03NE8669				2025-01-07 17:56:57.941389+05:30	Sedan		17-56-57.941389_camera-1_KA03NE8669.jpg			[{"score": 0.897, "plate": "ka03ne8669"}, {"score": 0.837, "plate": "ka03neb669"}]	t	new
3075	camera-1	KA03MS1507				2025-01-07 17:57:03.065121+05:30	Sedan		17-57-03.065121_camera-1_KA03MS1507.jpg			[{"score": 0.9, "plate": "ka03ms1507"}, {"score": 0.839, "plate": "ka03msi507"}]	t	new
3076	camera-1	KA41D0023				2025-01-07 17:57:07.076743+05:30	SUV		17-57-07.076743_camera-1_KA41D0023.jpg			[{"score": 0.884, "plate": "ka41d0023"}, {"score": 0.82, "plate": "ka41do023"}, {"score": 0.818, "plate": "ka4id0023"}, {"score": 0.754, "plate": "ka4ido023"}]	t	new
3077	camera-1	KA03NJ1636				2025-01-07 17:57:19.704747+05:30	Van		17-57-19.704747_camera-1_KA03NJ1636.jpg			[{"score": 0.9, "plate": "ka03nj1636"}, {"score": 0.839, "plate": "ka03nji636"}]	t	new
3078	camera-1	HA51C0582				2025-01-07 17:58:03.627228+05:30	Big Truck		17-58-03.627228_camera-1_HA51C0582.jpg			[{"score": 0.865, "plate": "ha51c0582"}, {"score": 0.826, "plate": "ma51c0582"}, {"score": 0.807, "plate": "ha51c0562"}, {"score": 0.798, "plate": "ha51co582"}, {"score": 0.798, "plate": "ha5ic0582"}, {"score": 0.768, "plate": "ma51c0562"}, {"score": 0.759, "plate": "ma51co582"}, {"score": 0.759, "plate": "ma5ic0582"}, {"score": 0.74, "plate": "ha51co562"}, {"score": 0.74, "plate": "ha5ic0562"}]	t	new
3079	camera-1	KA51A8901				2025-01-07 17:58:03.627228+05:30	Big Truck		17-58-03.627228_camera-1_KA51A8901.jpg			[{"score": 0.895, "plate": "ka51a8901"}, {"score": 0.828, "plate": "ka51ab901"}, {"score": 0.827, "plate": "ka5ia8901"}, {"score": 0.76, "plate": "ka5iab901"}]	t	new
3080	camera-1	KA01JK2924				2025-01-07 17:58:06.038535+05:30	Motorcycle		17-58-06.038535_camera-1_KA01JK2924.jpg			[{"score": 0.9, "plate": "ka01jk2924"}, {"score": 0.839, "plate": "ka0ijk2924"}]	t	new
3081	camera-1	KA04MT0665				2025-01-07 17:58:11.492725+05:30	Sedan		17-58-11.492725_camera-1_KA04MT0665.jpg			[{"score": 0.855, "plate": "ka04mt0665"}, {"score": 0.808, "plate": "ka04mto665"}, {"score": 0.808, "plate": "ka04ht0665"}, {"score": 0.803, "plate": "ka04mt0565"}, {"score": 0.761, "plate": "ka04hto665"}, {"score": 0.756, "plate": "ka04mto565"}, {"score": 0.756, "plate": "ka04ht0565"}, {"score": 0.709, "plate": "ka04hto565"}]	t	new
3082	camera-1	KA02AC9911				2025-01-07 17:58:15.896330+05:30	Sedan		17-58-15.896330_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3083	camera-1	KA51AF1973				2025-01-07 17:58:23.020764+05:30	Big Truck		17-58-23.020764_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
3084	camera-1	KA04MP7575				2025-01-07 17:58:21.698170+05:30	SUV		17-58-21.698170_camera-1_KA04MP7575.jpg			[{"score": 0.9, "plate": "ka04mp7575"}]	t	new
3085	camera-1	KA50J6820				2025-01-07 17:58:23.075072+05:30	Motorcycle		17-58-23.075072_camera-1_KA50J6820.jpg			[{"score": 0.818, "plate": "ka50j6820"}, {"score": 0.815, "plate": "ka50j8820"}, {"score": 0.787, "plate": "ka50jb820"}, {"score": 0.771, "plate": "ka90j6820"}, {"score": 0.769, "plate": "ka90j8820"}, {"score": 0.76, "plate": "ka50j6829"}, {"score": 0.757, "plate": "ka50j8829"}, {"score": 0.757, "plate": "ka5oj6820"}, {"score": 0.754, "plate": "ka5oj8820"}, {"score": 0.741, "plate": "ka90jb820"}]	t	new
3086	camera-1	KA03AC9138				2025-01-07 17:58:32.089464+05:30	Unknown		17-58-32.089464_camera-1_KA03AC9138.jpg			[{"score": 0.891, "plate": "ka03ac9138"}]	t	new
3087	camera-1	KA04MV0753				2025-01-07 17:58:33.365314+05:30	Sedan		17-58-33.365314_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3088	camera-1	KA03KD6851				2025-01-07 17:58:34.371322+05:30	Motorcycle		17-58-34.371322_camera-1_KA03KD6851.jpg			[{"score": 0.891, "plate": "ka03kd6851"}]	t	new
3089	camera-1	KA01MN4163				2025-01-07 17:58:37.756321+05:30	Sedan		17-58-37.756321_camera-1_KA01MN4163.jpg			[{"score": 0.898, "plate": "ka01mn4163"}, {"score": 0.838, "plate": "ka0imn4163"}]	t	new
3090	camera-1	DL8CAH6452				2025-01-07 17:58:40.559443+05:30	Sedan		17-58-40.559443_camera-1_DL8CAH6452.jpg			[{"score": 0.9, "plate": "dl8cah6452"}]	t	new
3091	camera-1	KA03KK2819				2025-01-07 17:58:40.301016+05:30	Motorcycle		17-58-40.301016_camera-1_KA03KK2819.jpg			[{"score": 0.894, "plate": "ka03kk2819"}, {"score": 0.841, "plate": "ka03kx2819"}]	t	new
3092	camera-1	KA03NE8669				2025-01-07 17:58:45.566850+05:30	Sedan		17-58-45.566850_camera-1_KA03NE8669.jpg			[{"score": 0.898, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03neb669"}]	t	new
3093	camera-1	KA03MS1507				2025-01-07 17:58:50.447377+05:30	Sedan		17-58-50.447377_camera-1_KA03MS1507.jpg			[{"score": 0.899, "plate": "ka03ms1507"}, {"score": 0.839, "plate": "ka03msi507"}]	t	new
3094	camera-1	KA41D0023				2025-01-07 17:58:54.712902+05:30	SUV		17-58-54.712902_camera-1_KA41D0023.jpg			[{"score": 0.862, "plate": "ka41d0023"}, {"score": 0.815, "plate": "ra41d0023"}, {"score": 0.797, "plate": "ka4id0023"}, {"score": 0.795, "plate": "ka41do023"}, {"score": 0.751, "plate": "ra4id0023"}, {"score": 0.748, "plate": "ra41do023"}, {"score": 0.731, "plate": "ka4ido023"}, {"score": 0.684, "plate": "ra4ido023"}]	t	new
3095	camera-1	KA03NJ1636				2025-01-07 17:59:07.395354+05:30	Van		17-59-07.395354_camera-1_KA03NJ1636.jpg			[{"score": 0.898, "plate": "ka03nj1636"}, {"score": 0.838, "plate": "ka03nji636"}]	t	new
3096	camera-1	HA51C0582				2025-01-07 17:59:51.053945+05:30	Big Truck		17-59-51.053945_camera-1_HA51C0582.jpg			[{"score": 0.858, "plate": "ha51c0582"}, {"score": 0.826, "plate": "ka51c0582"}, {"score": 0.806, "plate": "ha51c0562"}, {"score": 0.79, "plate": "ha51co582"}, {"score": 0.79, "plate": "ha5ic0582"}, {"score": 0.775, "plate": "ka51c0562"}, {"score": 0.759, "plate": "ka51co582"}, {"score": 0.759, "plate": "ka5ic0582"}, {"score": 0.739, "plate": "ha51co562"}, {"score": 0.739, "plate": "ha5ic0562"}]	t	new
3097	camera-1	KA51A8901				2025-01-07 17:59:51.245344+05:30	Big Truck		17-59-51.245344_camera-1_KA51A8901.jpg			[{"score": 0.893, "plate": "ka51a8901"}, {"score": 0.834, "plate": "ka51a8801"}, {"score": 0.826, "plate": "ka51ab901"}, {"score": 0.826, "plate": "ka5ia8901"}, {"score": 0.767, "plate": "ka51ab801"}, {"score": 0.767, "plate": "ka5ia8801"}, {"score": 0.758, "plate": "ka5iab901"}, {"score": 0.7, "plate": "ka5iab801"}]	t	new
3098	camera-1	KA01JK2924				2025-01-07 17:59:53.719150+05:30	Motorcycle		17-59-53.719150_camera-1_KA01JK2924.jpg			[{"score": 0.897, "plate": "ka01jk2924"}, {"score": 0.836, "plate": "ka0ijk2924"}]	t	new
3099	camera-1	KA51AE0086				2025-01-07 17:59:56.954561+05:30	Bus		17-59-56.954561_camera-1_KA51AE0086.jpg			[{"score": 0.9, "plate": "ka51ae0086"}, {"score": 0.84, "plate": "ka5iae0086"}, {"score": 0.839, "plate": "ka51aeo086"}]	t	new
3100	camera-1	KA04MT0665				2025-01-07 17:59:59.207282+05:30	Sedan		17-59-59.207282_camera-1_KA04MT0665.jpg			[{"score": 0.839, "plate": "ka04mt0665"}, {"score": 0.8, "plate": "ka04mt0655"}, {"score": 0.792, "plate": "ka04mt0565"}, {"score": 0.786, "plate": "ka04mtd665"}, {"score": 0.785, "plate": "ka04mto665"}, {"score": 0.753, "plate": "ka04mt0555"}, {"score": 0.747, "plate": "ka04mtd655"}, {"score": 0.747, "plate": "ka04mto655"}, {"score": 0.739, "plate": "ka04mtd565"}, {"score": 0.739, "plate": "ka04mto565"}]	t	new
3101	camera-1	KA02AC9911				2025-01-07 18:00:03.516724+05:30	Sedan		18-00-03.516724_camera-1_KA02AC9911.jpg			[{"score": 0.9, "plate": "ka02ac9911"}]	t	new
3102	camera-1	KA51AF1973				2025-01-07 18:00:10.573653+05:30	Big Truck		18-00-10.573653_camera-1_KA51AF1973.jpg			[{"score": 0.9, "plate": "ka51af1973"}, {"score": 0.839, "plate": "ka51afi973"}, {"score": 0.839, "plate": "ka5iaf1973"}]	t	new
3103	camera-1	KA04MP7575				2025-01-07 18:00:09.322331+05:30	SUV		18-00-09.322331_camera-1_KA04MP7575.jpg			[{"score": 0.9, "plate": "ka04mp7575"}]	t	new
3104	camera-1	KA03D6924				2025-01-07 18:00:16.922964+05:30	Motorcycle		18-00-16.922964_camera-1_KA03D6924.jpg			[{"score": 0.762, "plate": "ka03d6924"}, {"score": 0.752, "plate": "ka03o6924"}, {"score": 0.707, "plate": "ka05d6924"}, {"score": 0.697, "plate": "ka05o6924"}]	t	new
3105	camera-1	KA03AC9138				2025-01-07 18:00:19.876460+05:30	Unknown		18-00-19.876460_camera-1_KA03AC9138.jpg			[{"score": 0.829, "plate": "ka03ac9138"}, {"score": 0.814, "plate": "ka03hc9138"}, {"score": 0.808, "plate": "kh03ac9138"}, {"score": 0.792, "plate": "kh03hc9138"}, {"score": 0.784, "plate": "ma03ac9138"}, {"score": 0.769, "plate": "ma03hc9138"}, {"score": 0.763, "plate": "mh03ac9138"}, {"score": 0.747, "plate": "mh03hc9138"}]	t	new
3106	camera-1	KA04MV0753				2025-01-07 18:00:20.941187+05:30	Sedan		18-00-20.941187_camera-1_KA04MV0753.jpg			[{"score": 0.9, "plate": "ka04mv0753"}, {"score": 0.839, "plate": "ka04mvo753"}]	t	new
3107	camera-1	KA03KD6851				2025-01-07 18:00:22.009412+05:30	Motorcycle		18-00-22.009412_camera-1_KA03KD6851.jpg			[{"score": 0.875, "plate": "ka03kd6851"}]	t	new
3108	camera-1	KA01MN4163				2025-01-07 18:00:25.423995+05:30	Sedan		18-00-25.423995_camera-1_KA01MN4163.jpg			[{"score": 0.899, "plate": "ka01mn4163"}, {"score": 0.839, "plate": "ka0imn4163"}]	t	new
3109	camera-1	DL8CAH6452				2025-01-07 18:00:28.881379+05:30	Sedan		18-00-28.881379_camera-1_DL8CAH6452.jpg			[{"score": 0.899, "plate": "dl8cah6452"}]	t	new
3110	camera-1	KA03KK2819				2025-01-07 18:00:27.940105+05:30	Motorcycle		18-00-27.940105_camera-1_KA03KK2819.jpg			[{"score": 0.895, "plate": "ka03kk2819"}]	t	new
3111	camera-1	KA03NE8669				2025-01-07 18:00:33.150496+05:30	Sedan		18-00-33.150496_camera-1_KA03NE8669.jpg			[{"score": 0.896, "plate": "ka03ne8669"}, {"score": 0.838, "plate": "ka03n8669"}, {"score": 0.835, "plate": "ka03neb669"}, {"score": 0.778, "plate": "ka03nb669"}]	t	new
3112	camera-1	KA03MS1507				2025-01-07 18:00:38.305355+05:30	Sedan		18-00-38.305355_camera-1_KA03MS1507.jpg			[{"score": 0.9, "plate": "ka03ms1507"}, {"score": 0.839, "plate": "ka03msi507"}]	t	new
3113	camera-1	KA41DD023				2025-01-07 18:00:42.580622+05:30	SUV		18-00-42.580622_camera-1_KA41DD023.jpg			[{"score": 0.87, "plate": "ka41dd023"}, {"score": 0.832, "plate": "ra41dd023"}, {"score": 0.802, "plate": "ka4idd023"}, {"score": 0.765, "plate": "ra4idd023"}]	f	new
3114	camera-1	KA03NJ1636				2025-01-07 18:00:54.714903+05:30	Van		18-00-54.714903_camera-1_KA03NJ1636.jpg			[{"score": 0.898, "plate": "ka03nj1636"}, {"score": 0.837, "plate": "ka03nji636"}]	t	new
2949	camera-1	TN294306				2024-08-28 09:58:39.409323+05:30	Motorcycle		09-58-39.409323_camera-1_TN294306.jpg			[{"score": 0.898, "plate": "tn294306"}]	t	new
2950	camera-1	KA51A8901				2024-08-28 09:58:43.453938+05:30	Big Truck		09-58-43.453938_camera-1_KA51A8901.jpg			[{"score": 0.896, "plate": "ka51a8901"}, {"score": 0.83, "plate": "ka51ab901"}, {"score": 0.829, "plate": "ka5ia8901"}, {"score": 0.763, "plate": "ka5iab901"}]	t	new
\.


--
-- Data for Name: persons; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.persons (id, created_by, date_created, enrollment_id, person_name, person_image_location, aadhar_number, aadhar_image_location, drivers_license_number, drivers_license_image, gender, vid, address, dob, fathers_name, resident_of, mobile_number, visiting_person_name) FROM stdin;
\.


--
-- Data for Name: trips; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.trips (id, created_by, date_created, person_id, vehicle_number_plate, entry_time, exit_time, is_finished, coming_from, going_to, traveler_type, number_of_male_passengers, number_of_female_passengers, number_of_child_passengers, trip_reason, trip_permit_type, trip_permit_image_location, driver_trip_id, visit_duration, pass_number) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, created_by, date_created, user_name, email, password, user_type) FROM stdin;
1	Super Admin	2024-07-23 07:46:50.28705	Tushar Khichariya	tushar@censuscounters.com	$2a$06$rcrwuzdWKb.FZXA9g4P0W.hVyxBDojA8kyB9PG34LBvtnbDIgeUAG	Admin
2	Super Admin	2024-07-23 07:46:50.28705	Manish Mohanty	manish@censuscounters.com	$2a$06$GCyZeobMTyYynaV41RA1vOLBDmiPMUl5UBfUzXBBeIoBnM1dh4TcS	Admin
3	Super Admin	2024-07-23 07:46:50.28705	Pavel Zolotykh	pavel@censuscounters.com	$2a$06$dAPs4I5BMdydIw7JfBq9reGDjVbP2gzQkffH4Rhic7w3kCsZc9b3S	Admin
4	Super Admin	2024-07-23 07:46:50.28705	Support Guy	support@censuscounters.com	$2a$06$oXt2mRPx/dEawMtDHuK.au9Bo6g.qIX39aHBCYA0jYV6d94Bik9f6	Reader
\.


--
-- Data for Name: vehicles; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.vehicles (id, created_by, date_created, vehicle_number_plate, vehicle_image_location, vehicle_make, vehicle_model, vehicle_color, vehicle_type, vehicle_registered_to, vehicle_registration_number) FROM stdin;
\.


--
-- Name: anpr_vehicle_readings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.anpr_vehicle_readings_id_seq', 3114, true);


--
-- Name: persons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.persons_id_seq', 9, true);


--
-- Name: trips_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.trips_id_seq', 18, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 4, true);


--
-- Name: vehicles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.vehicles_id_seq', 1, false);


--
-- Name: anpr_vehicle_readings anpr_vehicle_readings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.anpr_vehicle_readings
    ADD CONSTRAINT anpr_vehicle_readings_pkey PRIMARY KEY (id);


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
-- PostgreSQL database dump complete
--

