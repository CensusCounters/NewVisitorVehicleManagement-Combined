from .site_dispatch import get_workflow


def get_handler(jwt_details, redis_conn):
    return get_workflow("vehicle_report_helper").get_handler(jwt_details, redis_conn)


def post_handler(jwt_details, redis_conn, form):
    return get_workflow("vehicle_report_helper").post_handler(jwt_details, redis_conn, form)
