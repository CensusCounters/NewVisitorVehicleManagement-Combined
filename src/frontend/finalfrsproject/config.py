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
    purpose_input: str = "text"
    require_dl_for: List[str] = Field(default_factory=list)


class VehicleFieldEntry(BaseModel):
    fields: List[str]
    required_fields: List[str]


class VehicleFieldsConfig(BaseModel):
    known_vehicle: VehicleFieldEntry
    unknown_vehicle: VehicleFieldEntry


class KnownVehicleConfig(BaseModel):
    person_log_label: str = "new_vehicle_owner: "

class UnknownVehicleConfig(BaseModel):
    translate_messages: bool = True
    include_vehicle_choices: bool = False
    owner_result_key: str = "vehicle_registered_to"

class TranslateMessagesConfig(BaseModel):
    translate_messages: bool = True

class MakeTripSummaryConfig(BaseModel):
    passenger_registration_loop: bool = True
    translate_messages: bool = True

class TripRegistrationConfig(BaseModel):
    translate_messages: bool = True
    reset_driver_trip_id: bool = False
    duration_in_days: bool = False

class RecognizeVehicleConfig(BaseModel):
    translate_messages: bool = True
    manual_plate_search: bool = True
    strict_lookup_result: bool = False
    require_vehicle_url: bool = True
    require_cached_vehicle_list: bool = False
    post_log_name: str = "recognize_vehicle_helper_post"

class ReportHomeConfig(BaseModel):
    redirect_missing_session: bool = False
    string_session_key: bool = False

class VehicleReportConfig(BaseModel):
    load_initial_records: bool = False
    post_exception_message: str = "An unexpected error occurred while generating the report. Please try again."
    post_query_failure_session_message: str = "An unexpected error occurred while generating the vehicle report. Please try again."
    log_traceback: bool = True



# Base model with the most common template settings
class BaseTemplateConfig(BaseModel):
    translate_labels: bool = True
    extended_vehicle_details: bool = False

# Specific templates that need extra fields can inherit and extend
class AddTripTemplateConfig(BaseTemplateConfig):
    address_max_length: int = 30

class PersonReportTemplateConfig(BaseTemplateConfig):
    destination_gate_columns: bool = False

class TripSummaryTemplateConfig(BaseTemplateConfig):
    show_missing_value_labels: bool = False
    enhanced_image_preview: bool = False

# Models for scripts/styles that don't share the base labels
class TripReportDetailsStylesConfig(BaseModel):
    compact_link_styles: bool = False

class TripReportSummaryScriptConfig(BaseModel):
    separate_other_column: bool = False

# The main templates wrapper
class SiteTemplates(BaseModel):
    # Error pages (Python variables cannot start with a number, so we use aliases)
    page_401: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig, alias="401")
    page_404: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig, alias="404")
    page_500: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig, alias="500")

    # Standard pages using base defaults
    close_trip: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    known_vehicle: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    person_lookup: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    person_lookup_result_list: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    static_recognize_vehicle: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    static_recognize: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    static_trip_summary: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)
    unknown_vehicle: BaseTemplateConfig = Field(default_factory=BaseTemplateConfig)

    # Pages with custom fields
    add_trip: AddTripTemplateConfig = Field(default_factory=AddTripTemplateConfig)
    person_report: PersonReportTemplateConfig = Field(default_factory=PersonReportTemplateConfig)
    trip_summary: TripSummaryTemplateConfig = Field(default_factory=TripSummaryTemplateConfig)
    trip_report_details_styles: TripReportDetailsStylesConfig = Field(default_factory=TripReportDetailsStylesConfig)
    trip_report_summary_script: TripReportSummaryScriptConfig = Field(default_factory=TripReportSummaryScriptConfig)

class SiteProfile(BaseModel):
    app_title: str
    logo_path: str
    visitor_categories: List[str]
    id_lookup_categories: List[str]
    allowed_id_types_by_visitor: Dict[str, List[str]]
    aadhaar_lookup: AadhaarLookupConfig
    templates: SiteTemplates = Field(default_factory=SiteTemplates)

    # Defaults applied directly
    unknown_person_page_fields: UnknownPersonPageFields = Field(default_factory=UnknownPersonPageFields)
    trip_duration_default_hours: int = Field(default=1, ge=1)
    face_match_confidence: float = Field(default=0.7, gt=0, le=1)
    summary_table_by_visitor_type: bool = True
    summary_table_by_men_women: bool = True
    trip_closure_mode: Literal["manual", "manual_and_anpr"] = "manual"
    vehicle_types: List[str] = Field(default_factory=list)
    vehicle_categories: List[str] = Field(default_factory=list)
    vehicle_fields: VehicleFieldsConfig = _BASIC_VEHICLE_FIELDS

    # Nested config block defaults
    known_vehicle: KnownVehicleConfig = Field(default_factory=KnownVehicleConfig)
    unknown_vehicle: UnknownVehicleConfig = Field(default_factory=UnknownVehicleConfig)
    person_lookup: TranslateMessagesConfig = Field(default_factory=TranslateMessagesConfig)
    person_report: TranslateMessagesConfig = Field(default_factory=TranslateMessagesConfig)
    make_trip_summary: MakeTripSummaryConfig = Field(default_factory=MakeTripSummaryConfig)
    trip_registration: TripRegistrationConfig = Field(default_factory=TripRegistrationConfig)
    recognize_vehicle: RecognizeVehicleConfig = Field(default_factory=RecognizeVehicleConfig)
    report_home: ReportHomeConfig = Field(default_factory=ReportHomeConfig)
    vehicle_report: VehicleReportConfig = Field(default_factory=VehicleReportConfig)

    @model_validator(mode="after")
    def _check_id_rules(self):
        if set(self.visitor_categories) != set(self.allowed_id_types_by_visitor.keys()):
            raise ValueError(
                f"{self.app_title} ID rules must cover every visitor category exactly"
            )
        known = set(self.id_lookup_categories)
        for visitor_type, id_types in self.allowed_id_types_by_visitor.items():
            unsupported = set(id_types) - known
            if unsupported:
                raise ValueError(
                    f"{self.app_title}/{visitor_type} contains unsupported IDs: "
                    f"{sorted(unsupported)}"
                )
        return self


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


# Helper instances to keep the overrides clean
_untranslated = BaseTemplateConfig(translate_labels=False)
_untranslated_extended = BaseTemplateConfig(translate_labels=False, extended_vehicle_details=True)

_NCPASS_TEMPLATES = SiteTemplates(
    page_401=_untranslated,
    page_404=_untranslated,
    page_500=_untranslated,
    close_trip=_untranslated,
    person_lookup=_untranslated,
    person_lookup_result_list=_untranslated,
    static_recognize_vehicle=_untranslated,
    static_recognize=_untranslated,
    static_trip_summary=_untranslated,
    known_vehicle=_untranslated_extended,
    unknown_vehicle=_untranslated_extended,
    add_trip=AddTripTemplateConfig(translate_labels=False, extended_vehicle_details=True),
    person_report=PersonReportTemplateConfig(translate_labels=False, extended_vehicle_details=True),
    trip_summary=TripSummaryTemplateConfig(translate_labels=False, enhanced_image_preview=True),
    trip_report_details_styles=TripReportDetailsStylesConfig(compact_link_styles=True),
    trip_report_summary_script=TripReportSummaryScriptConfig(separate_other_column=True),
)

_GANGANAGAR_TEMPLATES = SiteTemplates(
    page_401=_untranslated,
    page_404=_untranslated,
    page_500=_untranslated,
    close_trip=_untranslated,
    known_vehicle=_untranslated,
    person_lookup=_untranslated,
    person_lookup_result_list=_untranslated,
    static_recognize_vehicle=_untranslated,
    static_recognize=_untranslated,
    static_trip_summary=_untranslated,
    unknown_vehicle=_untranslated,
    add_trip=AddTripTemplateConfig(translate_labels=True, address_max_length=100),
    person_report=PersonReportTemplateConfig(translate_labels=False, destination_gate_columns=True),
    trip_summary=TripSummaryTemplateConfig(translate_labels=False),
)


KUPWARA_PROFILE = SiteProfile(
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
    aadhaar_lookup=_KUPWARA_AADHAAR_LOOKUP,
)

NCPASS_PROFILE = SiteProfile(
    app_title="SM Hill Visitor Management System",
    logo_path="images/7RR-Logo.jpeg",
    visitor_categories=["DRIVER", "PASSENGER"],
    id_lookup_categories=["AADHAR"],
    allowed_id_types_by_visitor={"DRIVER": ["AADHAR"], "PASSENGER": ["AADHAR"]},
    unknown_person_page_fields=UnknownPersonPageFields(purpose_input="select", require_dl_for=["DRIVER"]),
    trip_duration_default_hours=12,
    vehicle_types=["LOCAL", "TOURIST"],
    vehicle_categories=["LIGHT VEHICLE", "HEAVY VEHICLE", "AMBULANCE", "LD CARRIER"],
    vehicle_fields=_NCPASS_VEHICLE_FIELDS,
    aadhaar_lookup=_NCPASS_AADHAAR_LOOKUP,
    templates=_NCPASS_TEMPLATES,
    # Overrides
    known_vehicle=KnownVehicleConfig(person_log_label="new_vehicle_rider: "),
    unknown_vehicle=UnknownVehicleConfig(translate_messages=False, include_vehicle_choices=True, owner_result_key="vehicle_owner"),
    person_lookup=TranslateMessagesConfig(translate_messages=False),
    person_report=TranslateMessagesConfig(translate_messages=False),
    make_trip_summary=MakeTripSummaryConfig(passenger_registration_loop=False, translate_messages=False),
    trip_registration=TripRegistrationConfig(translate_messages=False, reset_driver_trip_id=True, duration_in_days=True),
    recognize_vehicle=RecognizeVehicleConfig(
        translate_messages=False, manual_plate_search=False, strict_lookup_result=True,
        require_vehicle_url=False, require_cached_vehicle_list=True, post_log_name="known_vehicle_helper_post"
    ),
    report_home=ReportHomeConfig(redirect_missing_session=True, string_session_key=True),
    vehicle_report=VehicleReportConfig(
        load_initial_records=True, log_traceback=False,
        post_exception_message="An unexpected error occurred while generating the vehicle report. Please try again..",
        post_query_failure_session_message="An unexpected error occurred while generating the person report. Please try again.",
    ),
)

GANGANAGAR_PROFILE = SiteProfile(
    app_title="Amogh Entry Management System",
    logo_path="images/amogh-ganganagar-logo.png",
    visitor_categories=["PASS HOLDER", "TEACHER", "PERMISSION", "CIVILIAN", "GUEST", "MES", "LABOUR", "OTHERS"],
    id_lookup_categories=["AADHAR", "DRIVERS LICENSE", "PASS"],
    allowed_id_types_by_visitor={
        "PASS HOLDER": ["AADHAR", "DRIVERS LICENSE", "PASS"], "TEACHER": ["PASS"],
        "PERMISSION": ["AADHAR", "DRIVERS LICENSE"], "CIVILIAN": ["AADHAR", "DRIVERS LICENSE"],
        "GUEST": ["AADHAR", "DRIVERS LICENSE"], "MES": ["AADHAR", "DRIVERS LICENSE"],
        "LABOUR": ["AADHAR", "DRIVERS LICENSE"], "OTHERS": ["AADHAR", "DRIVERS LICENSE"],
    },
    trip_closure_mode="manual_and_anpr",
    aadhaar_lookup=_GANGANAGAR_AADHAAR_LOOKUP,
    templates=_GANGANAGAR_TEMPLATES,
    # Overrides
    person_lookup=TranslateMessagesConfig(translate_messages=False),
    person_report=TranslateMessagesConfig(translate_messages=False),
    make_trip_summary=MakeTripSummaryConfig(translate_messages=False),
    trip_registration=TripRegistrationConfig(translate_messages=False, reset_driver_trip_id=True),
)

TANGDHAR_PROFILE = SiteProfile(
    app_title="Shakti Vijay Entry Management System",
    logo_path="images/shakti-vijay-logo.jpeg",
    visitor_categories=["PASS HOLDER", "PERMISSION", "CIVILIAN", "GUEST", "OTHERS"],
    id_lookup_categories=["AADHAR", "DRIVERS LICENSE", "PASS"],
    allowed_id_types_by_visitor={
        "PASS HOLDER": ["AADHAR", "DRIVERS LICENSE", "PASS"], "PERMISSION": ["AADHAR", "DRIVERS LICENSE"],
        "CIVILIAN": ["AADHAR", "DRIVERS LICENSE"], "GUEST": ["AADHAR", "DRIVERS LICENSE"],
        "OTHERS": ["AADHAR", "DRIVERS LICENSE"],
    },
    aadhaar_lookup=_KUPWARA_AADHAAR_LOOKUP,
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
