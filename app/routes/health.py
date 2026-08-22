"""Health check and configuration routes."""
from flask import Blueprint, jsonify, current_app
from app.models import Recording, Session, db
import uuid

bp = Blueprint('health', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Speechly API'
    })


@bp.route('/test-db-save', methods=['GET'])
def test_db_save():
    """Test database save in HTTP context."""
    try:
        # Create session
        session_id = f'http-test-{uuid.uuid4().hex[:8]}'
        session = Session(id=session_id)
        db.session.add(session)
        db.session.commit()

        # Create recording
        recording = Recording(
            session_id=session_id,
            filename=f'{session_id}.webm',
            topic='HTTP Test',
            speech_type='practice',
            language='en'
        )
        db.session.add(recording)
        db.session.commit()

        return jsonify({
            'success': True,
            'recording_id': recording.id,
            'message': 'Created and committed'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/languages', methods=['GET'])
def get_languages():
    """Get supported languages."""
    languages = current_app.config.get('LANGUAGE_DISPLAY', [
        "en: English",
        "ko: Korean",
        "zh-CN: Chinese (Simplified)",
        "it: Italian",
        "ja: Japanese",
        "pt: Portuguese",
        "ru: Russian",
        "ar: Arabic",
        "hi: Hindi",
        "tr: Turkish",
        "nl: Dutch",
        "fr: French",
        "es: Spanish",
        "de: German",
        "bn: Bengali",
        "zh: Mandarin Chinese"
    ])
    return jsonify({
        'success': True,
        'display_options': languages
    })


@bp.route('/validate-config', methods=['GET'])
def validate_config():
    """Validate API configuration."""
    return jsonify({
        'success': True,
        'openai_configured': bool(current_app.config.get('OPENAI_API_KEY'))
    })


__all__ = ['bp']
