"""Pytest configuration and fixtures."""
import pytest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import get_config
from app.models import db as _db, Session, Recording, SpeechHistory


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Set testing environment
    os.environ['FLASK_ENV'] = 'testing'

    # Import here to avoid circular imports
    from flask import Flask
    from flask_cors import CORS

    app = Flask(__name__)
    config = get_config('testing')

    # Apply configuration
    for key in dir(config):
        if key.isupper():
            app.config[key] = getattr(config, key)

    # Initialize extensions
    _db.init_app(app)
    CORS(app)

    # Create tables
    with app.app_context():
        _db.create_all()

    yield app

    # Cleanup
    with app.app_context():
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    """Create a database session for a test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """Create a new database session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()

    session = db.create_scoped_session(
        options={'bind': connection, 'binds': {}}
    )
    db.session = session

    yield session

    transaction.rollback()
    connection.close()
    session.remove()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_openai(monkeypatch):
    """Mock OpenAI API."""
    from tests.mocks.mock_openai import MockOpenAIClient

    # Mock the openai module
    mock_client = MockOpenAIClient()

    def mock_init(*args, **kwargs):
        return mock_client

    # This will be used when services are initialized
    monkeypatch.setattr('openai.OpenAI', mock_init)

    return mock_client


@pytest.fixture
def mock_speech_recognizer(monkeypatch):
    """Mock Google Speech Recognition."""
    from tests.mocks.mock_google_speech import MockRecognizer

    mock_recognizer = MockRecognizer()

    # Mock the speech_recognition module
    def mock_recognizer_init(*args, **kwargs):
        return mock_recognizer

    monkeypatch.setattr('speech_recognition.Recognizer', mock_recognizer_init)

    return mock_recognizer


@pytest.fixture
def sample_session(db):
    """Create a sample session for testing."""
    session = Session(id='test-session-123')
    db.session.add(session)
    db.session.commit()
    return session


@pytest.fixture
def sample_recording(db, sample_session):
    """Create a sample recording for testing."""
    recording = Recording(
        session_id=sample_session.id,
        filename='test_recording_001.wav',
        topic='Test Topic',
        speech_type='practice',
        language='en',
        transcription='This is a test transcription',
        feedback='This is test feedback',
        duration=10.5,
        is_repeat=False
    )
    db.session.add(recording)
    db.session.commit()
    return recording
