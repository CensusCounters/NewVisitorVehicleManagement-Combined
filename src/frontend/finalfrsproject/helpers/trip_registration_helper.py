from .site_dispatch import get_workflow


def get_handler(jwt_details, redis_conn):
    return get_workflow("trip_registration_helper").get_handler(jwt_details, redis_conn)


def post_handler(jwt_details, redis_conn, request):
    return get_workflow("trip_registration_helper").post_handler(jwt_details, redis_conn, request)
