"""Testing configuration for pytest."""
from .base import Config


class TestingConfig(Config):
    """Testing-specific configuration."""

    TESTING = True
    DEBUG = True
    PRODUCTION_MODE = False

    # In-memory SQLite for fast tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Mock external services
    OPENAI_API_KEY = 'test-key-123'

    # Store audio in memory for tests
    AUDIO_STORAGE = 'base64'

    # Test-specific storage mode
    STORAGE_MODE = 'database'

    # Disable SQL echo in tests (less noise)
    SQLALCHEMY_ECHO = False
