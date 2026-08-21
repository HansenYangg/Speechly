"""Base configuration for Speechly application."""
import os
from pathlib import Path


class Config:
    """Base configuration class with common settings."""

    # Base directory
    BASE_DIR = Path(__file__).parent.parent.parent

    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # OpenAI API
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    if not OPENAI_API_KEY and os.getenv('FLASK_ENV') != 'testing':
        raise ValueError("OPENAI_API_KEY not found. Please create a .env file with your API key")

    # Audio Configuration
    SAMPLE_RATE = 44100
    AUDIO_FORMAT = 'int16'
    AUDIO_CHANNELS = 1

    # Recording Configuration
    MIN_RECORDING_DURATION = 5  # seconds
    SHORT_RECORDING_THRESHOLD = 20  # seconds

    # Supported Languages
    LANGUAGE_DISPLAY = [
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
    ]

    LANGUAGES = {
        "en": "English",
        "ko": "Korean",
        "zh-CN": "Chinese (Simplified)",
        "it": "Italian",
        "ja": "Japanese",
        "pt": "Portuguese",
        "ru": "Russian",
        "ar": "Arabic",
        "hi": "Hindi",
        "tr": "Turkish",
        "nl": "Dutch",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        "bn": "Bengali",
        "zh": "Mandarin Chinese"
    }

    # Translation API
    TRANSLATION_API_URL = "https://api.mymemory.translated.net/get"

    # Directory paths
    RECORDINGS_DIR = BASE_DIR / 'recordings'
    DATA_DIR = BASE_DIR / 'data'
    LOGS_DIR = BASE_DIR / 'logs'

    # File settings
    AUDIO_FILE_EXTENSION = ".wav"

    # Storage configuration
    STORAGE_MODE = 'database'  # 'database' or 'file'
    AUDIO_STORAGE = 'file'  # 'file' or 'base64'

    # Feature flags
    TESTING = False
    PRODUCTION_MODE = False
