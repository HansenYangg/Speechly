"""Speech evaluation routes."""
from flask import Blueprint, request, jsonify, Response, current_app
import tempfile
import os
import base64
import shutil
import sys
from werkzeug.utils import secure_filename
from app.services.auth_service import get_auth_service
from app.models import Recording, Session, db

bp = Blueprint('evaluation', __name__, url_prefix='/api')

def log(msg):
    """Force flush log message to stderr."""
    print(msg, file=sys.stderr, flush=True)


def get_session_id(request_obj):
    """Extract session ID from request headers."""
    return request_obj.headers.get('Session-ID')


def get_user_id_from_token(request_obj):
    """Extract user ID from Authorization header."""
    auth_header = request_obj.headers.get('Authorization')
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return None

    access_token = parts[1]
    auth_service = get_auth_service()
    user = auth_service.get_user(access_token)

    return user.get('id') if user else None


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
    log("[RECORD] ========== STARTING RECORD REQUEST ==========")
    session_id = get_session_id(request)
    log(f"[RECORD] Session ID: {session_id}")

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400

    # Get user ID from auth token (for persistent storage across sessions)
    user_id = get_user_id_from_token(request)

    # Ensure session exists in database before saving recording (direct DB)
    existing_session = db.session.query(Session).filter_by(id=session_id).first()
    if not existing_session:
        new_session = Session(id=session_id)
        db.session.add(new_session)
        db.session.commit()
        log(f"[DB] Created session {session_id[:8]} directly")

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

    # Get previous recording data for repeat/improvement mode
    previous_transcription = data.get('previous_transcription')
    previous_feedback = data.get('previous_feedback')
    previous_score = data.get('previous_score')
    previous_recording_id = data.get('previous_recording_id')

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

        if not transcription or len(transcription.strip()) < 1:
            return jsonify({
                'success': False,
                'error': 'Could not transcribe audio.',
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
            previous_transcription=previous_transcription,
            previous_feedback=previous_feedback,
            previous_score=previous_score
        )

        result = {
            'success': True,
            'transcription': transcription,
            'feedback': feedback,
            'duration': duration
        }

        if not result['success']:
            return jsonify(result), 400

        # Generate unique filename with timestamp
        import time
        timestamp = int(time.time() * 1000)
        filename = secure_filename(f"{topic}_{session_id[:8]}_{timestamp}.webm")

        # Determine storage mode
        config = current_app.config
        audio_storage_mode = config.get('AUDIO_STORAGE', 'file')
        log(f"[SAVE] Storage mode: {audio_storage_mode}, filename: {filename}")

        if audio_storage_mode == 'supabase':
            # Upload to Supabase Storage
            from app.services.storage_service import get_storage_service
            storage_service = get_storage_service()

            with open(temp_path, 'rb') as f:
                file_data = f.read()

            upload_result = storage_service.upload_audio(
                file_data=file_data,
                filename=filename,
                session_id=session_id,
                content_type='audio/webm'
            )

            if upload_result.get('success'):
                file_path = upload_result['file_path']  # Supabase path
                audio_url = upload_result['public_url']
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to upload audio: {upload_result.get("error")}'
                }), 500

            audio_data_base64 = None

        elif audio_storage_mode == 'base64':
            # Read file and encode as base64
            with open(temp_path, 'rb') as f:
                audio_data_base64 = base64.b64encode(f.read()).decode('utf-8')
            file_path = None
            audio_url = None
        else:
            # Move file to recordings directory (local file storage)
            recordings_dir = config.get('RECORDINGS_DIR', 'recordings')
            os.makedirs(recordings_dir, exist_ok=True)
            final_path = os.path.join(recordings_dir, filename)
            log(f"[SAVE] Moving file to: {final_path}")

            # Remove existing file if it exists
            if os.path.exists(final_path):
                os.remove(final_path)

            # Use shutil.move instead of os.rename for cross-device compatibility
            shutil.move(temp_path, final_path)
            file_path = final_path
            audio_data_base64 = None
            audio_url = None
            log(f"[SAVE] File saved successfully: {os.path.exists(final_path)}")

        # Determine recording mode for analytics
        if is_repeat:
            recording_mode = 'improvement'
        elif topic.startswith('BEHAVIORAL:'):
            recording_mode = 'behavioral'
        else:
            recording_mode = 'standard'

        # Save recording using raw SQL with psycopg2 (bypass SQLAlchemy completely)
        log(f"[SAVE] Saving with raw SQL: session={session_id[:8]}, user_id={user_id}")
        import psycopg2

        db_url = os.getenv('DATABASE_URL')

        # Extract scores from feedback for analytics
        from app.models import Recording
        scores = Recording.extract_scores_from_feedback(result['feedback'])
        log(f"[SAVE] Extracted scores: overall={scores['score_overall']}")

        try:
            # Use a simple connection with autocommit
            conn = psycopg2.connect(db_url)
            conn.set_session(autocommit=True)
            cur = conn.cursor()

            # Log the actual values being inserted
            log(f"[SAVE] INSERT params: session_id={session_id}, user_id={user_id}, topic={topic}")

            cur.execute("""
                INSERT INTO recordings
                (session_id, user_id, filename, topic, speech_type, language,
                 file_path, transcription, feedback, duration, is_repeat,
                 recording_mode, score_overall, score_content, score_organization,
                 score_delivery, score_language, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id
            """, (
                session_id, user_id, filename, topic, speech_type, language,
                file_path, result['transcription'], result['feedback'],
                duration, is_repeat, recording_mode,
                scores['score_overall'], scores['score_content'], scores['score_organization'],
                scores['score_delivery'], scores['score_language']
            ))
            recording_id = cur.fetchone()[0]
            log(f"[SAVE] Inserted recording id={recording_id}")

            # Force sync to disk
            cur.execute("SELECT 1")
            cur.fetchone()

            cur.close()
            conn.close()

            # Longer pause and verify via Session Pooler (port 5432) instead of Transaction Pooler
            import time
            time.sleep(0.5)

            # Use Session Pooler for verification to get a truly different connection
            verify_url = db_url.replace(':6543/', ':5432/')
            verify_conn = psycopg2.connect(verify_url)
            verify_conn.set_session(autocommit=True)
            verify_cur = verify_conn.cursor()
            verify_cur.execute("SELECT id, topic, user_id FROM recordings WHERE id = %s", (recording_id,))
            verify = verify_cur.fetchone()
            verify_cur.close()
            verify_conn.close()

            if verify:
                log(f"[SAVE] CONFIRMED (via 5432): id={verify[0]}, topic='{verify[1]}', user_id={verify[2]}")
            else:
                log(f"[SAVE] CRITICAL: Recording {recording_id} NOT in database (checked via 5432)!")

        except Exception as save_error:
            log(f"[SAVE ERROR] {str(save_error)}")
            raise

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
