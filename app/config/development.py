"""Development configuration for local development."""
import os
from sqlalchemy.pool import NullPool
from .base import Config


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    TESTING = False
    PRODUCTION_MODE = False

    # Database - use Supabase PostgreSQL if DATABASE_URL is set
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        f'sqlite:///{Config.BASE_DIR}/dev.db'
    )

    # Use NullPool for Supabase - let Supabase handle all pooling
    # This prevents connection state issues with external poolers
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': NullPool,
    }

    # Disable SQL query logging for better performance (set to True to debug SQL)
    SQLALCHEMY_ECHO = False

    # Store audio as files locally (not base64 in DB)
    AUDIO_STORAGE = 'file'

    # CORS settings for local development
    CORS_ORIGINS = ['http://localhost:5001', 'http://localhost:5000', 'http://127.0.0.1:5001']
