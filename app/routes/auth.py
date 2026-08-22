"""Authentication routes."""
from flask import Blueprint, request, jsonify, redirect, url_for, current_app
from app.services.auth_service import get_auth_service, require_auth

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.route('/signup', methods=['POST'])
def signup():
    """Register a new user."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    auth_service = get_auth_service()
    result = auth_service.sign_up(email, password)

    if result.get('success'):
        return jsonify(result), 201
    else:
        return jsonify(result), 400


@bp.route('/signin', methods=['POST'])
def signin():
    """Sign in a user."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    auth_service = get_auth_service()
    result = auth_service.sign_in(email, password)

    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 401


@bp.route('/signout', methods=['POST'])
@require_auth
def signout():
    """Sign out a user."""
    from flask import g
    auth_service = get_auth_service()
    result = auth_service.sign_out(g.access_token)
    return jsonify(result), 200


@bp.route('/refresh', methods=['POST'])
def refresh():
    """Refresh an expired session."""
    data = request.get_json()

    if not data:
        return jsonify({"error": "No data provided"}), 400

    refresh_token = data.get('refresh_token')

    if not refresh_token:
        return jsonify({"error": "Refresh token is required"}), 400

    auth_service = get_auth_service()
    result = auth_service.refresh_session(refresh_token)

    if result.get('success'):
        return jsonify(result), 200
    else:
        return jsonify(result), 401


@bp.route('/user', methods=['GET'])
@require_auth
def get_user():
    """Get current user info."""
    from flask import g
    return jsonify({
        "success": True,
        "user": g.user
    }), 200


@bp.route('/verify', methods=['GET'])
def verify():
    """Verify if access token is valid."""
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return jsonify({"valid": False}), 200

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return jsonify({"valid": False}), 200

    access_token = parts[1]

    auth_service = get_auth_service()
    user = auth_service.get_user(access_token)

    if user:
        return jsonify({"valid": True, "user": user}), 200
    else:
        return jsonify({"valid": False}), 200


@bp.route('/oauth/google', methods=['GET'])
def google_oauth():
    """Initiate Google OAuth flow."""
    redirect_url = request.args.get('redirect_url', request.host_url)

    auth_service = get_auth_service()
    result = auth_service.get_oauth_url('google', redirect_url)

    if result.get('success'):
        return redirect(result['url'])
    else:
        return jsonify(result), 400


__all__ = ['bp']
