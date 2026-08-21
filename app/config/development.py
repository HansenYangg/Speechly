"""Development configuration for local development."""
import os
from .base import Config


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    TESTING = False
    PRODUCTION_MODE = False

    # SQLite for local development
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{Config.BASE_DIR}/dev.db'
    )

    # Disable SQL query logging for better performance (set to True to debug SQL)
    SQLALCHEMY_ECHO = False

    # Store audio as files locally (not base64 in DB)
    AUDIO_STORAGE = 'file'

    # CORS settings for local development
    CORS_ORIGINS = ['http://localhost:5001', 'http://localhost:5000', 'http://127.0.0.1:5001']
