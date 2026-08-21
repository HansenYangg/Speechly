"""Speech evaluation routes."""
from flask import Blueprint, request, jsonify, Response, current_app
import tempfile
import os
import base64
from werkzeug.utils import secure_filename

bp = Blueprint('evaluation', __name__, url_prefix='/api')


def get_session_id(request_obj):
    """Extract session ID from request headers."""
    return request_obj.headers.get('Session-ID')


@bp.route('/record', methods=['POST'])
def record_and_evaluate():
    """
    Record and evaluate speech.

    Accepts JSON with base64-encoded audio:
    {
        "audio_data": "base64_encoded_audio",
        "topic": "speech topic",
        "speech_type": "practice",
        "language": "en",
        "is_repeat": false
    }
    """
    session_id = get_session_id(request)

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400

    # Get JSON data
    data = request.get_json()
    if not data:
        return jsonify({
            'success': False,
            'error': 'No JSON data provided'
        }), 400

    topic = data.get('topic')
    speech_type = data.get('speech_type')
    language = data.get('language', 'en')
    is_repeat = data.get('is_repeat', False)
    audio_data_base64 = data.get('audio_data')

    if not audio_data_base64:
        return jsonify({
            'success': False,
            'error': 'No audio data provided'
        }), 400

    # Decode base64 audio and save to temporary file
    try:
        audio_bytes = base64.b64decode(audio_data_base64)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Invalid base64 audio data: {str(e)}'
        }), 400

    # Save to temporary file - Whisper supports WebM directly
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name

    try:
        # Use OpenAI Whisper directly (supports WebM, WAV, and many formats)
        openai_client = current_app.container.get_openai_client()

        with open(temp_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language if language not in ['en', 'zh'] else ('zh-CN' if language == 'zh' else None)
            )
            transcription = transcript.text

        if not transcription or len(transcription.strip()) < 3:
            return jsonify({
                'success': False,
                'error': 'Could not transcribe audio. Feedback cannot be generated.',
                'transcription': None,
                'feedback': None
            }), 400

        # Get audio duration (rough estimate from file size)
        file_size = os.path.getsize(temp_path)
        duration = file_size / (16000 * 2)  # Rough estimate for WebM

        # Generate feedback using feedback service
        feedback_service = current_app.container.get_feedback_service()
        feedback = feedback_service.generate_feedback(
            topic=topic,
            speech_type=speech_type,
            transcription=transcription,
            recording_duration=duration,
            language=language,
            is_repeat=is_repeat,
            previous_transcription=None
        )

        result = {
            'success': True,
            'transcription': transcription,
            'feedback': feedback,
            'duration': duration
        }

        if not result['success']:
            return jsonify(result), 400

        # Save to repository
        recording_repo = current_app.container.get_recording_repository()

        # Generate unique filename with timestamp
        import time
        timestamp = int(time.time() * 1000)
        filename = secure_filename(f"{topic}_{session_id[:8]}_{timestamp}.webm")

        # Determine storage mode
        config = current_app.config
        if config.get('AUDIO_STORAGE') == 'base64':
            # Read file and encode as base64
            with open(temp_path, 'rb') as f:
                audio_data_base64 = base64.b64encode(f.read()).decode('utf-8')
            file_path = None
        else:
            # Move file to recordings directory
            recordings_dir = config.get('RECORDINGS_DIR', 'recordings')
            os.makedirs(recordings_dir, exist_ok=True)
            final_path = os.path.join(recordings_dir, filename)

            # Remove existing file if it exists (Windows compatibility)
            if os.path.exists(final_path):
                os.remove(final_path)

            os.rename(temp_path, final_path)
            file_path = final_path
            audio_data_base64 = None

        # Save recording
        recording = recording_repo.save_recording(
            session_id=session_id,
            filename=filename,
            topic=topic,
            speech_type=speech_type,
            language=language,
            audio_file_path=file_path,
            audio_data_base64=audio_data_base64,
            transcription=result['transcription'],
            feedback=result['feedback'],
            duration=duration,
            is_repeat=is_repeat
        )

        # Prepare response in expected format for frontend
        response_data = {
            'transcription': result['transcription'],
            'feedback': result['feedback'],
            'duration': duration,
            'filename': filename,
            'stream_url': f'/api/stream-feedback/{session_id}/{filename}'
        }

        return jsonify({
            'success': True,
            'result': response_data
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    finally:
        # Clean up temp file if it still exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


@bp.route('/transcribe', methods=['POST'])
def transcribe_audio():
    """Transcribe audio file."""
    # Similar to record but only transcription
    return jsonify({
        'success': False,
        'error': 'Not yet implemented in refactored version'
    }), 501


@bp.route('/feedback', methods=['POST'])
def generate_feedback():
    """Generate feedback for transcription."""
    # Similar to record but only feedback
    return jsonify({
        'success': False,
        'error': 'Not yet implemented in refactored version'
    }), 501


@bp.route('/stream-feedback/<session_id>/<filename>')
def stream_feedback(session_id, filename):
    """Stream feedback using Server-Sent Events."""
    # Get recording
    recording_repo = current_app.container.get_recording_repository()
    recording = recording_repo.get_by_filename(filename)

    if not recording or not recording.feedback:
        return jsonify({
            'success': False,
            'error': 'Recording or feedback not found'
        }), 404

    def generate():
        """Generate SSE events."""
        import json

        # Send feedback in chunks
        feedback = recording.feedback
        chunk_size = 50  # Characters per chunk
        total_chunks = (len(feedback) + chunk_size - 1) // chunk_size

        for i in range(0, len(feedback), chunk_size):
            chunk = feedback[i:i + chunk_size]
            data = json.dumps({'type': 'chunk', 'content': chunk})
            yield f"data: {data}\n\n"

        # Send completion message
        completion_data = json.dumps({'type': 'complete', 'total_chunks': total_chunks})
        yield f"data: {completion_data}\n\n"

    return Response(generate(), mimetype='text/event-stream')


__all__ = ['bp']
