"""Recording management routes."""
from flask import Blueprint, request, jsonify, send_file, current_app
import os

bp = Blueprint('recordings', __name__, url_prefix='/api')


def get_session_id(request_obj):
    """Extract session ID from request headers."""
    return request_obj.headers.get('Session-ID')


@bp.route('/recordings', methods=['GET'])
def get_recordings():
    """Get all recordings for a session."""
    session_id = get_session_id(request)

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400

    recording_repo = current_app.container.get_recording_repository()
    recordings = recording_repo.get_session_recordings(session_id)

    return jsonify({
        'success': True,
        'recordings': [r.to_dict() for r in recordings]
    })


@bp.route('/recordings/<filename>', methods=['GET'])
def get_recording(filename):
    """Get a specific recording file."""
    recording_repo = current_app.container.get_recording_repository()
    recording = recording_repo.get_by_filename(filename)

    if not recording:
        return jsonify({
            'success': False,
            'error': 'Recording not found'
        }), 404

    # If audio is stored as file, send it
    if recording.file_path and os.path.exists(recording.file_path):
        return send_file(recording.file_path, mimetype='audio/wav')

    # If audio is stored as base64, return it in JSON
    if recording.audio_data:
        return jsonify({
            'success': True,
            'audio_data': recording.audio_data,
            'filename': recording.filename
        })

    return jsonify({
        'success': False,
        'error': 'Audio data not available'
    }), 404


@bp.route('/recordings/<filename>', methods=['DELETE'])
def delete_recording(filename):
    """Delete a specific recording."""
    recording_repo = current_app.container.get_recording_repository()
    success = recording_repo.delete_by_filename(filename)

    if success:
        return jsonify({
            'success': True,
            'message': f'Recording {filename} deleted'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Recording not found'
        }), 404


@bp.route('/recordings', methods=['DELETE'])
def delete_all_recordings():
    """Delete all recordings for a session."""
    session_id = get_session_id(request)

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400

    recording_repo = current_app.container.get_recording_repository()
    recordings = recording_repo.get_session_recordings(session_id)

    count = 0
    for recording in recordings:
        if recording_repo.delete_recording(recording.id):
            count += 1

    return jsonify({
        'success': True,
        'message': f'Deleted {count} recordings'
    })


__all__ = ['bp']
