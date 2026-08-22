"""Frontend serving routes."""
from flask import Blueprint, send_from_directory, current_app, redirect

bp = Blueprint('frontend', __name__)


@bp.route('/')
def serve_frontend():
    """Serve the main application (requires auth)."""
    static_folder = current_app.static_folder or 'static'
    return send_from_directory(static_folder, 'index.html')


@bp.route('/login')
def serve_login():
    """Serve the login page."""
    static_folder = current_app.static_folder or 'static'
    return send_from_directory(static_folder, 'login.html')


@bp.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, images)."""
    static_folder = current_app.static_folder or 'static'
    return send_from_directory(static_folder, filename)


__all__ = ['bp']
