"""Dispatch the legacy-named Aadhaar route to the active ID lookup workflow."""

from finalfrsproject import app

from . import (
    aadhar_lookup_ganganagar_helper,
    aadhar_lookup_kupwara_helper,
    aadhar_lookup_ncpass_helper,
)


_WORKFLOWS = {
    "ganganagar": aadhar_lookup_ganganagar_helper,
    "kupwara": aadhar_lookup_kupwara_helper,
    "ncpass": aadhar_lookup_ncpass_helper,
}


def _active_workflow():
    return _WORKFLOWS[app.config["ID_LOOKUP_WORKFLOW"]]


def get_handler(jwt_details, redis_conn):
    return _active_workflow().get_handler(jwt_details, redis_conn)


def post_handler(jwt_details, redis_conn, form):
    return _active_workflow().post_handler(jwt_details, redis_conn, form)
