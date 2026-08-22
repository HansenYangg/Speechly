"""Session management routes."""
from flask import Blueprint, request, jsonify, current_app
import uuid

bp = Blueprint('sessions', __name__, url_prefix='/api')


def get_session_id(request_obj):
    """Extract session ID from request headers or generate new one."""
    return request_obj.headers.get('Session-ID') or str(uuid.uuid4())


@bp.route('/session/new', methods=['POST'])
def create_new_session():
    """Create a new session."""
    session_id = str(uuid.uuid4())

    # Use repository to create session
    session_repo = current_app.container.get_session_repository()
    session_repo.get_or_create(session_id)

    return jsonify({
        'success': True,
        'session_id': session_id
    })


@bp.route('/session', methods=['GET'])
def get_session_data():
    """Get session data and recordings."""
    session_id = get_session_id(request)

    # Get repositories
    recording_repo = current_app.container.get_recording_repository()

    # Get recordings for this session
    recordings = recording_repo.get_session_recordings(session_id)

    return jsonify({
        'success': True,
        'session_data': {
            'session_id': session_id,
            'speech_count': len(recordings),
            'recordings': [r.to_dict() for r in recordings]
        }
    })


@bp.route('/session', methods=['DELETE'])
def clear_session():
    """Clear session data."""
    session_id = get_session_id(request)

    # Use repository to delete session
    session_repo = current_app.container.get_session_repository()
    success = session_repo.delete_session(session_id)

    if success:
        return jsonify({
            'success': True,
            'message': 'Session cleared successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Session not found'
        }), 404


@bp.route('/session/cleanup', methods=['POST'])
def cleanup_user_session():
    """Cleanup old sessions - but preserve sessions with authenticated user recordings."""
    import sys
    import psycopg2
    import os

    session_id = get_session_id(request)

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400

    # Check if this session has any recordings with a user_id (authenticated recordings)
    # If so, DON'T delete the session to preserve the recordings
    db_url = os.getenv('DATABASE_URL')
    if db_url:
        try:
            conn = psycopg2.connect(db_url)
            conn.set_session(autocommit=True)
            cur = conn.cursor()

            cur.execute("""
                SELECT COUNT(*) FROM recordings
                WHERE session_id = %s AND user_id IS NOT NULL
            """, (session_id,))
            user_recording_count = cur.fetchone()[0]

            cur.close()
            conn.close()

            if user_recording_count > 0:
                print(f"[CLEANUP] Skipping session {session_id[:8]} - has {user_recording_count} authenticated recordings", file=sys.stderr, flush=True)
                return jsonify({
                    'success': True,
                    'message': 'Session preserved (has authenticated recordings)'
                })
        except Exception as e:
            print(f"[CLEANUP ERROR] {str(e)}", file=sys.stderr, flush=True)

    session_repo = current_app.container.get_session_repository()
    session_repo.delete_session(session_id)

    return jsonify({
        'success': True,
        'message': 'Session cleaned up successfully'
    })


__all__ = ['bp']
