from finalfrsproject import app, jwt
from flask_jwt_extended import get_jwt_identity, get_jwt, jwt_required
from flask import render_template, jsonify
from flask_wtf.csrf import CSRFError
from flask_babel import _
import sys, os

from werkzeug.exceptions import RequestEntityTooLarge


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    print("csrf error")
    print(f"Error: {str(e)}")
    send_to_html_json = {
        'message': _('You have been logged out due to inactivity. Please login again.'),
        'page_title': _('Error'),
        'redirect': "url_for('login')"
    }
    print("expired csrf details: ", send_to_html_json)
    return render_template('token_error.html', details=send_to_html_json), 400

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    send_to_html_json = {
        'message': _('The token has expired. Please login again.'),
        'page_title': _('Error'),
        'redirect': "url_for('login')"
    }
    print("expired_token details: ", send_to_html_json)
    return render_template('token_error.html', details=send_to_html_json), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    send_to_html_json = {
        'message': _('Invalid token. Please login again.'),
        'page_title': _('Error')
    }
    print("invalid_token details: ", send_to_html_json)
    return render_template('token_error.html', details=send_to_html_json), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    print(f"Error: {str(error)}")
    send_to_html_json = {
        'message': _('Missing token. Please login again.'),
        'page_title': _('Error')
    }
    print("missing token details: ", send_to_html_json)
    return render_template('token_error.html', details=send_to_html_json), 401

@app.errorhandler(RequestEntityTooLarge)
def handle_413(e):
    send_to_html_json = {
        'message': _('Uploaded file too large. Max 2GB allowed.'),
        'page_title': _('Error'),
        'redirect': "url_for('login')"
    }
    print("RequestEntityTooLarge error")
    return render_template('token_error.html', details=send_to_html_json), 401
