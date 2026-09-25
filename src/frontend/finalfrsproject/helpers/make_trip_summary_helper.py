from .site_dispatch import get_workflow


def get_handler(jwt_details, redis_conn):
    return get_workflow("make_trip_summary_helper").get_handler(jwt_details, redis_conn)


def post_handler(jwt_details, redis_conn, form):
    return get_workflow("make_trip_summary_helper").post_handler(jwt_details, redis_conn, form)
