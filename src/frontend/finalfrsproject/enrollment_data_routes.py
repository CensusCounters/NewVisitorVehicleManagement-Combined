"""Admin UI/API. Jobs run outside Flask request processes."""
import uuid
from functools import wraps

import psycopg2
from flask import Blueprint, abort, g, jsonify, render_template, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required

from enrollment_data import config, jobs, package, postgres_store
from enrollment_data.guard import guard, MaintenanceBusy
from enrollment_data import readiness

bp = Blueprint('enrollment_data', __name__, url_prefix='/enrollment-data')


def admin(view):
    @wraps(view)
    @jwt_required()
    def wrapped(*args, **kwargs):
        identity = get_jwt_identity()
        if not isinstance(identity, dict) or str(identity.get('logged_in_user_type', '')).lower() != 'admin':
            abort(403)
        # Recheck the persisted account rather than trusting a potentially stale role claim.
        row = jobs.query('SELECT user_type FROM users WHERE id=%s', (identity['logged_in_user_id'],), one=True)
        if not row or row['user_type'].lower() != 'admin':
            abort(403)
        g.enrollment_actor = identity['logged_in_user_id']
        return view(*args, **kwargs)
    return wrapped


@bp.errorhandler(ValueError)
def invalid(error):
    return jsonify(error=str(error)), 400


@bp.errorhandler(psycopg2.errors.UniqueViolation)
def busy(error):
    return jsonify(error='Another enrollment operation is queued, running, or awaiting recovery.'), 409


@bp.errorhandler(MaintenanceBusy)
def maintenance(error):
    return jsonify(error=str(error)), 409


@bp.errorhandler(readiness.BackgroundUnavailable)
def background_unavailable(error):
    return jsonify(error=error.state['message'], code=error.state['code']), 503


@bp.route('')
@admin
def page():
    identity = get_jwt_identity()
    details = {
        'message': '',
        'page_title': 'Enrollment Data',
        'logged_in_user_type': 'Admin',
        'logged_in_user': identity.get('logged_in_user_name', 'Administrator'),
    }
    return render_template('enrollment_data.html', details=details, user=identity)


@bp.route('/jobs')
@admin
def history():
    try:
        return jsonify(jobs=jobs.history(), availability=readiness.availability())
    except psycopg2.errors.UndefinedTable:
        return jsonify(
            code='enrollment_setup_required',
            error='Enrollment maintenance is not ready on this system. Ask the person who '
                  'manages this system to complete the enrollment maintenance setup, '
                  'then select Check again.',
        ), 503


@bp.route('/jobs/<uuid:job_id>')
@admin
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        abort(404)
    return jsonify(job)


@bp.route('/export', methods=['POST'])
@admin
def export():
    readiness.require_available()
    return jsonify(job_id=jobs.create('export', g.enrollment_actor)), 202


@bp.route('/import/validate', methods=['POST'])
@admin
def upload():
    readiness.require_available()
    config.initialize_storage()
    if request.content_length and request.content_length > config.MAX_BYTES + 1024 * 1024:
        return jsonify(error='Upload exceeds the configured package limit.'), 413
    request.max_content_length = config.MAX_BYTES + 1024 * 1024
    file = request.files.get('dataset')
    if not file:
        raise ValueError('Choose an enrollment ZIP package.')
    input_id = str(uuid.uuid4())
    target = config.ROOT / 'uploads' / f'{input_id}.zip'
    try:
        size = 0
        with target.open('xb') as out:
            while True:
                chunk = file.stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.MAX_BYTES:
                    raise ValueError('Uploaded package exceeds the configured limit.')
                out.write(chunk)
        return jsonify(job_id=jobs.create('validate', g.enrollment_actor, input_id), input_id=input_id), 202
    except Exception:
        target.unlink(missing_ok=True)
        raise


@bp.route('/import', methods=['POST'])
@admin
def load():
    readiness.require_available()
    input_id = str(uuid.UUID((request.get_json() or {}).get('input_id', '')))
    preview_id = str(uuid.UUID((request.get_json() or {}).get('validation_job_id', '')))
    validated = jobs.get(preview_id)
    if not validated or validated['operation'] != 'validate' or validated['status'] != 'completed' or str(validated['input_id']) != input_id or not validated['result'].get('plan_digest') or not (config.ROOT / 'uploads' / f'{input_id}.zip').is_file():
        raise ValueError('Upload and check this package first.')
    return jsonify(job_id=jobs.create('import', g.enrollment_actor, input_id, preview_id)), 202



@bp.route('/reset/preview', methods=['POST'])
@admin
def preview():
    with guard(), jobs.connection() as conn:
        counts = postgres_store.check_reset(conn)
    return jsonify(counts=counts, message='Reset removes enrolled persons, vehicles, their default-collection vectors and private enrollment images. A recovery export is created first. Users, blacklist and history are preserved.')


@bp.route('/reset', methods=['POST'])
@admin
def reset():
    readiness.require_available()
    if (request.get_json() or {}).get('confirmation') != 'RESET ENROLLMENTS':
        raise ValueError('Type RESET ENROLLMENTS to confirm.')
    with guard(), jobs.connection() as conn:
        postgres_store.check_reset(conn)
    return jsonify(job_id=jobs.create('reset', g.enrollment_actor)), 202


@bp.route('/jobs/<uuid:job_id>/resume', methods=['POST'])
@admin
def resume(job_id):
    readiness.require_available()
    jobs.resume(str(job_id))
    return jsonify(job_id=str(job_id)), 202


@bp.route('/jobs/<uuid:job_id>/cancel', methods=['POST'])
@admin
def cancel(job_id):
    jobs.cancel(str(job_id))
    return jsonify(job_id=str(job_id), status='cancelled')


@bp.route('/download/<uuid:job_id>')
@admin
def download(job_id):
    job = jobs.get(job_id)
    if not job or job['status'] != 'completed' or not job['result'].get('download'):
        abort(404)
    path = config.ROOT / 'exports' / f'{job_id}.zip'
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=f'enrollments-{job_id}.zip', max_age=0)


def install(app):
    app.register_blueprint(bp)

    @app.before_request
    def maintenance_guard():
        if request.blueprint == bp.name or request.endpoint in {'static', 'login', 'logout', 'set_language'}:
            return
        ctx = guard()
        try:
            ctx.__enter__()
        except MaintenanceBusy as error:
            return jsonify(error=str(error)), 503
        g.enrollment_guard = ctx

    @app.teardown_request
    def release_guard(error):
        ctx = g.pop('enrollment_guard', None)
        if ctx:
            ctx.__exit__(None, None, None)
