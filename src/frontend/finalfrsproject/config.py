# config.py
"""Typed site-profile configuration (Pydantic).

Replaces the previous SITE_PROFILES dict plus hand-written validators with one
validated model per site. All per-site differences live here as data; the shared
helpers/templates read the active profile through app.config["SITE_PROFILE_CONFIG"].

This mirrors the reference design Pavel shared in commit 8d6cf61, extended to cover
every feature-config block our sites actually use (vehicle, person, trip, recognize,
report and template blocks) rather than only the aadhaar-lookup fields.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class AadhaarLookupConfig(BaseModel):
    custom_dropdown: bool
    support_male_passenger_skip: bool
    default_message_key: Literal["id_type", "visitor_type"]
    lookup_strategy: Literal["multi", "aadhar_only"]
    force_id_type: Optional[str]
    require_input_validation: bool
    pass_holder_teacher_uses_pass_image: bool
    exception_template_post: str
    show_id_type_first: List[str] = Field(default_factory=list)
    show_id_number_only: List[str] = Field(default_factory=list)


class UnknownPersonPageFields(BaseModel):
    purpose_input: str
    require_dl_for: List[str] = Field(default_factory=list)


class VehicleFieldEntry(BaseModel):
    fields: List[str]
    required_fields: List[str]


class VehicleFieldsConfig(BaseModel):
    known_vehicle: VehicleFieldEntry
    unknown_vehicle: VehicleFieldEntry


class KnownVehicleConfig(BaseModel):
    person_log_label: str


class UnknownVehicleConfig(BaseModel):
    translate_messages: bool
    include_vehicle_choices: bool
    owner_result_key: str


class TranslateMessagesConfig(BaseModel):
    translate_messages: bool


class MakeTripSummaryConfig(BaseModel):
    passenger_registration_loop: bool
    translate_messages: bool


class TripRegistrationConfig(BaseModel):
    translate_messages: bool
    reset_driver_trip_id: bool
    duration_in_days: bool


class RecognizeVehicleConfig(BaseModel):
    translate_messages: bool
    manual_plate_search: bool
    strict_lookup_result: bool
    require_vehicle_url: bool
    require_cached_vehicle_list: bool
    post_log_name: str


class ReportHomeConfig(BaseModel):
    redirect_missing_session: bool
    string_session_key: bool


class VehicleReportConfig(BaseModel):
    load_initial_records: bool
    post_exception_message: str
    post_query_failure_session_message: str
    log_traceback: bool


class SiteProfile(BaseModel):
    id_lookup_workflow: str
    app_title: str
    logo_path: str
    visitor_categories: List[str]
    id_lookup_categories: List[str]
    allowed_id_types_by_visitor: Dict[str, List[str]]
    unknown_person_page_fields: UnknownPersonPageFields
    trip_duration_default_hours: int = Field(ge=1)
    face_match_confidence: float = Field(gt=0, le=1)
    summary_table_by_visitor_type: bool
    summary_table_by_men_women: bool
    trip_closure_mode: Literal["manual", "manual_and_anpr"]
    vehicle_types: List[str]
    vehicle_categories: List[str]
    vehicle_fields: VehicleFieldsConfig
    aadhaar_lookup: AadhaarLookupConfig
    known_vehicle: KnownVehicleConfig
    unknown_vehicle: UnknownVehicleConfig
    person_lookup: TranslateMessagesConfig
    person_report: TranslateMessagesConfig
    make_trip_summary: MakeTripSummaryConfig
    trip_registration: TripRegistrationConfig
    recognize_vehicle: RecognizeVehicleConfig
    report_home: ReportHomeConfig
    vehicle_report: VehicleReportConfig
    templates: Dict[str, Dict[str, Any]]

    @model_validator(mode="after")
    def _check_id_rules(self):
        if set(self.visitor_categories) != set(self.allowed_id_types_by_visitor.keys()):
            raise ValueError(
                f"{self.id_lookup_workflow} ID rules must cover every visitor category exactly"
            )
        known = set(self.id_lookup_categories)
        for visitor_type, id_types in self.allowed_id_types_by_visitor.items():
            unsupported = set(id_types) - known
            if unsupported:
                raise ValueError(
                    f"{self.id_lookup_workflow}/{visitor_type} contains unsupported IDs: "
                    f"{sorted(unsupported)}"
                )
        return self


# Shared Aadhaar-lookup settings. tangdhar reuses kupwara's because its
# id_lookup_workflow is "kupwara" (no verbatim copy of the whole profile).
_KUPWARA_AADHAAR_LOOKUP = AadhaarLookupConfig(
    custom_dropdown=False,
    support_male_passenger_skip=True,
    default_message_key="id_type",
    lookup_strategy="multi",
    force_id_type=None,
    require_input_validation=False,
    pass_holder_teacher_uses_pass_image=False,
    exception_template_post="500.html",
    show_id_type_first=["PASS HOLDER", "PERMISSION", "CIVILIAN", "GUEST", "OTHERS"],
    show_id_number_only=["TEACHER"],
)

_NCPASS_AADHAAR_LOOKUP = AadhaarLookupConfig(
    custom_dropdown=True,
    support_male_passenger_skip=False,
    default_message_key="visitor_type",
    lookup_strategy="aadhar_only",
    force_id_type="AADHAR",
    require_input_validation=True,
    pass_holder_teacher_uses_pass_image=False,
    exception_template_post="home.html",
    show_id_type_first=[],
    show_id_number_only=[],
)

_GANGANAGAR_AADHAAR_LOOKUP = AadhaarLookupConfig(
    custom_dropdown=False,
    support_male_passenger_skip=True,
    default_message_key="id_type",
    lookup_strategy="multi",
    force_id_type=None,
    require_input_validation=False,
    pass_holder_teacher_uses_pass_image=True,
    exception_template_post="500.html",
    show_id_type_first=[
        "PASS HOLDER",
        "PERMISSION",
        "CIVILIAN",
        "GUEST",
        "OTHERS",
        "MES",
        "LABOUR",
    ],
    show_id_number_only=["TEACHER"],
)


_BASIC_VEHICLE_FIELDS = VehicleFieldsConfig(
    known_vehicle=VehicleFieldEntry(
        fields=["vehicle_number", "vehicle_owner_name", "make", "color"],
        required_fields=["vehicle_number", "vehicle_owner_name", "make", "color"],
    ),
    unknown_vehicle=VehicleFieldEntry(
        fields=[
            "vehicle_number",
            "vehicle_owner_name",
            "vehicle_make",
            "vehicle_color",
        ],
        required_fields=["vehicle_number", "vehicle_owner_name"],
    ),
)

_NCPASS_VEHICLE_FIELDS = VehicleFieldsConfig(
    known_vehicle=VehicleFieldEntry(
        fields=[
            "vehicle_number",
            "vehicle_type",
            "vehicle_model",
            "vehicle_owner_name",
            "vehicle_registration_number",
            "make",
            "color",
        ],
        required_fields=[
            "vehicle_number",
            "vehicle_type",
            "vehicle_model",
            "vehicle_owner_name",
            "make",
            "color",
        ],
    ),
    unknown_vehicle=VehicleFieldEntry(
        fields=[
            "vehicle_number",
            "vehicle_type",
            "vehicle_model",
            "vehicle_owner_name",
            "vehicle_registration_number",
            "vehicle_make",
            "vehicle_color",
        ],
        required_fields=["vehicle_number", "vehicle_owner_name"],
    ),
)


_KUPWARA_TEMPLATES = {
    "401": {"translate_labels": True},
    "404": {"translate_labels": True},
    "500": {"translate_labels": True},
    "add_trip": {
        "translate_labels": True,
        "address_max_length": 30,
        "extended_vehicle_details": False,
    },
    "close_trip": {"translate_labels": True},
    "trip_report_details_styles": {"compact_link_styles": False},
    "trip_report_summary_script": {"separate_other_column": False},
    "known_vehicle": {"translate_labels": True, "extended_vehicle_details": False},
    "person_lookup": {"translate_labels": True},
    "person_lookup_result_list": {"translate_labels": True},
    "person_report": {
        "translate_labels": True,
        "destination_gate_columns": False,
        "extended_vehicle_details": False,
    },
    "static_recognize_vehicle": {"translate_labels": True},
    "static_recognize": {"translate_labels": True},
    "static_trip_summary": {"translate_labels": True},
    "trip_summary": {
        "translate_labels": True,
        "show_missing_value_labels": False,
        "enhanced_image_preview": False,
    },
    "unknown_vehicle": {"translate_labels": True, "extended_vehicle_details": False},
}

_NCPASS_TEMPLATES = {
    "401": {"translate_labels": False},
    "404": {"translate_labels": False},
    "500": {"translate_labels": False},
    "add_trip": {
        "translate_labels": False,
        "address_max_length": 30,
        "extended_vehicle_details": True,
    },
    "close_trip": {"translate_labels": False},
    "trip_report_details_styles": {"compact_link_styles": True},
    "trip_report_summary_script": {"separate_other_column": True},
    "known_vehicle": {"translate_labels": False, "extended_vehicle_details": True},
    "person_lookup": {"translate_labels": False},
    "person_lookup_result_list": {"translate_labels": False},
    "person_report": {
        "translate_labels": False,
        "destination_gate_columns": False,
        "extended_vehicle_details": True,
    },
    "static_recognize_vehicle": {"translate_labels": False},
    "static_recognize": {"translate_labels": False},
    "static_trip_summary": {"translate_labels": False},
    "trip_summary": {
        "translate_labels": False,
        "show_missing_value_labels": False,
        "enhanced_image_preview": True,
    },
    "unknown_vehicle": {"translate_labels": False, "extended_vehicle_details": True},
}

_GANGANAGAR_TEMPLATES = {
    "401": {"translate_labels": False},
    "404": {"translate_labels": False},
    "500": {"translate_labels": False},
    "add_trip": {
        "translate_labels": True,
        "address_max_length": 100,
        "extended_vehicle_details": False,
    },
    "close_trip": {"translate_labels": False},
    "trip_report_details_styles": {"compact_link_styles": False},
    "trip_report_summary_script": {"separate_other_column": False},
    "known_vehicle": {"translate_labels": False, "extended_vehicle_details": False},
    "person_lookup": {"translate_labels": False},
    "person_lookup_result_list": {"translate_labels": False},
    "person_report": {
        "translate_labels": False,
        "destination_gate_columns": True,
        "extended_vehicle_details": False,
    },
    "static_recognize_vehicle": {"translate_labels": False},
    "static_recognize": {"translate_labels": False},
    "static_trip_summary": {"translate_labels": False},
    "trip_summary": {
        "translate_labels": False,
        "show_missing_value_labels": False,
        "enhanced_image_preview": False,
    },
    "unknown_vehicle": {"translate_labels": False, "extended_vehicle_details": False},
}


KUPWARA_PROFILE = SiteProfile(
    id_lookup_workflow="kupwara",
    app_title="Vajr Entry Management System",
    logo_path="images/vajr-28-div-logo.jpeg",
    visitor_categories=["PASS HOLDER", "PERMISSION", "CIVILIAN", "GUEST", "OTHERS"],
    id_lookup_categories=["AADHAR", "DRIVERS LICENSE", "PASS"],
    allowed_id_types_by_visitor={
        "PASS HOLDER": ["AADHAR", "DRIVERS LICENSE", "PASS"],
        "PERMISSION": ["AADHAR", "DRIVERS LICENSE"],
        "CIVILIAN": ["AADHAR", "DRIVERS LICENSE"],
        "GUEST": ["AADHAR", "DRIVERS LICENSE"],
        "OTHERS": ["AADHAR", "DRIVERS LICENSE"],
    },
    unknown_person_page_fields=UnknownPersonPageFields(
        purpose_input="text", require_dl_for=[]
    ),
    trip_duration_default_hours=1,
    face_match_confidence=0.7,
    summary_table_by_visitor_type=True,
    summary_table_by_men_women=True,
    trip_closure_mode="manual",
    vehicle_types=[],
    vehicle_categories=[],
    vehicle_fields=_BASIC_VEHICLE_FIELDS,
    aadhaar_lookup=_KUPWARA_AADHAAR_LOOKUP,
    known_vehicle=KnownVehicleConfig(person_log_label="new_vehicle_owner: "),
    unknown_vehicle=UnknownVehicleConfig(
        translate_messages=True,
        include_vehicle_choices=False,
        owner_result_key="vehicle_registered_to",
    ),
    person_lookup=TranslateMessagesConfig(translate_messages=True),
    person_report=TranslateMessagesConfig(translate_messages=True),
    make_trip_summary=MakeTripSummaryConfig(
        passenger_registration_loop=True, translate_messages=True
    ),
    trip_registration=TripRegistrationConfig(
        translate_messages=True, reset_driver_trip_id=False, duration_in_days=False
    ),
    recognize_vehicle=RecognizeVehicleConfig(
        translate_messages=True,
        manual_plate_search=True,
        strict_lookup_result=False,
        require_vehicle_url=True,
        require_cached_vehicle_list=False,
        post_log_name="recognize_vehicle_helper_post",
    ),
    report_home=ReportHomeConfig(
        redirect_missing_session=False, string_session_key=False
    ),
    vehicle_report=VehicleReportConfig(
        load_initial_records=False,
        post_exception_message="An unexpected error occurred while generating the report. Please try again.",
        post_query_failure_session_message="An unexpected error occurred while generating the vehicle report. Please try again.",
        log_traceback=True,
    ),
    templates=_KUPWARA_TEMPLATES,
)

NCPASS_PROFILE = SiteProfile(
    id_lookup_workflow="ncpass",
    app_title="SM Hill Visitor Management System",
    logo_path="images/7RR-Logo.jpeg",
    visitor_categories=["DRIVER", "PASSENGER"],
    id_lookup_categories=["AADHAR"],
    allowed_id_types_by_visitor={"DRIVER": ["AADHAR"], "PASSENGER": ["AADHAR"]},
    unknown_person_page_fields=UnknownPersonPageFields(
        purpose_input="select", require_dl_for=["DRIVER"]
    ),
    trip_duration_default_hours=12,
    face_match_confidence=0.7,
    summary_table_by_visitor_type=True,
    summary_table_by_men_women=True,
    trip_closure_mode="manual",
    vehicle_types=["LOCAL", "TOURIST"],
    vehicle_categories=["LIGHT VEHICLE", "HEAVY VEHICLE", "AMBULANCE", "LD CARRIER"],
    vehicle_fields=_NCPASS_VEHICLE_FIELDS,
    aadhaar_lookup=_NCPASS_AADHAAR_LOOKUP,
    known_vehicle=KnownVehicleConfig(person_log_label="new_vehicle_rider: "),
    unknown_vehicle=UnknownVehicleConfig(
        translate_messages=False,
        include_vehicle_choices=True,
        owner_result_key="vehicle_owner",
    ),
    person_lookup=TranslateMessagesConfig(translate_messages=False),
    person_report=TranslateMessagesConfig(translate_messages=False),
    make_trip_summary=MakeTripSummaryConfig(
        passenger_registration_loop=False, translate_messages=False
    ),
    trip_registration=TripRegistrationConfig(
        translate_messages=False, reset_driver_trip_id=True, duration_in_days=True
    ),
    recognize_vehicle=RecognizeVehicleConfig(
        translate_messages=False,
        manual_plate_search=False,
        strict_lookup_result=True,
        require_vehicle_url=False,
        require_cached_vehicle_list=True,
        post_log_name="known_vehicle_helper_post",
    ),
    report_home=ReportHomeConfig(
        redirect_missing_session=True, string_session_key=True
    ),
    vehicle_report=VehicleReportConfig(
        load_initial_records=True,
        post_exception_message="An unexpected error occurred while generating the vehicle report. Please try again..",
        post_query_failure_session_message="An unexpected error occurred while generating the person report. Please try again.",
        log_traceback=False,
    ),
    templates=_NCPASS_TEMPLATES,
)

GANGANAGAR_PROFILE = SiteProfile(
    id_lookup_workflow="ganganagar",
    app_title="Amogh Entry Management System",
    logo_path="images/amogh-ganganagar-logo.png",
    visitor_categories=[
        "PASS HOLDER",
        "TEACHER",
        "PERMISSION",
        "CIVILIAN",
        "GUEST",
        "MES",
        "LABOUR",
        "OTHERS",
    ],
    id_lookup_categories=["AADHAR", "DRIVERS LICENSE", "PASS"],
    allowed_id_types_by_visitor={
        "PASS HOLDER": ["AADHAR", "DRIVERS LICENSE", "PASS"],
        "TEACHER": ["PASS"],
        "PERMISSION": ["AADHAR", "DRIVERS LICENSE"],
        "CIVILIAN": ["AADHAR", "DRIVERS LICENSE"],
        "GUEST": ["AADHAR", "DRIVERS LICENSE"],
        "MES": ["AADHAR", "DRIVERS LICENSE"],
        "LABOUR": ["AADHAR", "DRIVERS LICENSE"],
        "OTHERS": ["AADHAR", "DRIVERS LICENSE"],
    },
    unknown_person_page_fields=UnknownPersonPageFields(
        purpose_input="text", require_dl_for=[]
    ),
    trip_duration_default_hours=1,
    face_match_confidence=0.7,
    summary_table_by_visitor_type=True,
    summary_table_by_men_women=True,
    trip_closure_mode="manual_and_anpr",
    vehicle_types=[],
    vehicle_categories=[],
    vehicle_fields=_BASIC_VEHICLE_FIELDS,
    aadhaar_lookup=_GANGANAGAR_AADHAAR_LOOKUP,
    known_vehicle=KnownVehicleConfig(person_log_label="new_vehicle_owner: "),
    unknown_vehicle=UnknownVehicleConfig(
        translate_messages=True,
        include_vehicle_choices=False,
        owner_result_key="vehicle_registered_to",
    ),
    person_lookup=TranslateMessagesConfig(translate_messages=False),
    person_report=TranslateMessagesConfig(translate_messages=False),
    make_trip_summary=MakeTripSummaryConfig(
        passenger_registration_loop=True, translate_messages=False
    ),
    trip_registration=TripRegistrationConfig(
        translate_messages=False, reset_driver_trip_id=True, duration_in_days=False
    ),
    recognize_vehicle=RecognizeVehicleConfig(
        translate_messages=True,
        manual_plate_search=True,
        strict_lookup_result=False,
        require_vehicle_url=True,
        require_cached_vehicle_list=False,
        post_log_name="recognize_vehicle_helper_post",
    ),
    report_home=ReportHomeConfig(
        redirect_missing_session=False, string_session_key=False
    ),
    vehicle_report=VehicleReportConfig(
        load_initial_records=False,
        post_exception_message="An unexpected error occurred while generating the report. Please try again.",
        post_query_failure_session_message="An unexpected error occurred while generating the vehicle report. Please try again.",
        log_traceback=True,
    ),
    templates=_GANGANAGAR_TEMPLATES,
)

TANGDHAR_PROFILE = SiteProfile(
    id_lookup_workflow="kupwara",
    app_title="Shakti Vijay Entry Management System",
    logo_path="images/shakti-vijay-logo.jpeg",
    visitor_categories=["PASS HOLDER", "PERMISSION", "CIVILIAN", "GUEST", "OTHERS"],
    id_lookup_categories=["AADHAR", "DRIVERS LICENSE", "PASS"],
    allowed_id_types_by_visitor={
        "PASS HOLDER": ["AADHAR", "DRIVERS LICENSE", "PASS"],
        "PERMISSION": ["AADHAR", "DRIVERS LICENSE"],
        "CIVILIAN": ["AADHAR", "DRIVERS LICENSE"],
        "GUEST": ["AADHAR", "DRIVERS LICENSE"],
        "OTHERS": ["AADHAR", "DRIVERS LICENSE"],
    },
    unknown_person_page_fields=UnknownPersonPageFields(
        purpose_input="text", require_dl_for=[]
    ),
    trip_duration_default_hours=1,
    face_match_confidence=0.7,
    summary_table_by_visitor_type=True,
    summary_table_by_men_women=True,
    trip_closure_mode="manual",
    vehicle_types=[],
    vehicle_categories=[],
    vehicle_fields=_BASIC_VEHICLE_FIELDS,
    aadhaar_lookup=_KUPWARA_AADHAAR_LOOKUP,
    known_vehicle=KnownVehicleConfig(person_log_label="new_vehicle_owner: "),
    unknown_vehicle=UnknownVehicleConfig(
        translate_messages=True,
        include_vehicle_choices=False,
        owner_result_key="vehicle_registered_to",
    ),
    person_lookup=TranslateMessagesConfig(translate_messages=True),
    person_report=TranslateMessagesConfig(translate_messages=True),
    make_trip_summary=MakeTripSummaryConfig(
        passenger_registration_loop=True, translate_messages=True
    ),
    trip_registration=TripRegistrationConfig(
        translate_messages=True, reset_driver_trip_id=False, duration_in_days=False
    ),
    recognize_vehicle=RecognizeVehicleConfig(
        translate_messages=True,
        manual_plate_search=True,
        strict_lookup_result=False,
        require_vehicle_url=True,
        require_cached_vehicle_list=False,
        post_log_name="recognize_vehicle_helper_post",
    ),
    report_home=ReportHomeConfig(
        redirect_missing_session=False, string_session_key=False
    ),
    vehicle_report=VehicleReportConfig(
        load_initial_records=False,
        post_exception_message="An unexpected error occurred while generating the report. Please try again.",
        post_query_failure_session_message="An unexpected error occurred while generating the vehicle report. Please try again.",
        log_traceback=True,
    ),
    templates=_KUPWARA_TEMPLATES,
)


SITE_PROFILES = {
    "kupwara": KUPWARA_PROFILE,
    "ncpass": NCPASS_PROFILE,
    "ganganagar": GANGANAGAR_PROFILE,
    "tangdhar": TANGDHAR_PROFILE,
}


def get_active_profile(profile_name: str) -> SiteProfile:
    if profile_name not in SITE_PROFILES:
        raise ValueError(f"Unsupported SITE_PROFILE={profile_name}")
    return SITE_PROFILES[profile_name]
