"""Production configuration for cloud deployment."""
import os
from .base import Config


class ProductionConfig(Config):
    """Production-specific configuration."""

    DEBUG = False
    TESTING = False
    PRODUCTION_MODE = True

    # PostgreSQL for production
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL must be set in production")

    # Handle Heroku's postgres:// -> postgresql:// conversion
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            'postgres://', 'postgresql://', 1
        )

    # Store audio as base64 in database (no filesystem in cloud)
    AUDIO_STORAGE = 'base64'

    # Require strong secret key in production
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY or SECRET_KEY == 'dev-secret-key-change-in-production':
        raise ValueError("SECRET_KEY must be set to a strong random value in production")

    # CORS settings - configure based on frontend deployment
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

    # Disable SQL query logging in production
    SQLALCHEMY_ECHO = False
