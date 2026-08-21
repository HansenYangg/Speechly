"""Health check and configuration routes."""
from flask import Blueprint, jsonify, current_app

bp = Blueprint('health', __name__, url_prefix='/api')


@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'Speechly API'
    })


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
