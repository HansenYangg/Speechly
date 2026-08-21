"""Basic health check tests to verify test infrastructure."""
import pytest


def test_app_exists(app):
    """Test that the app fixture works."""
    assert app is not None
    assert app.config['TESTING'] is True


def test_db_exists(db):
    """Test that the database fixture works."""
    assert db is not None


def test_client_exists(client):
    """Test that the test client fixture works."""
    assert client is not None


def test_mock_openai(mock_openai):
    """Test that the mock OpenAI client works."""
    assert mock_openai is not None
    assert mock_openai.api_key == 'test-key'


def test_mock_speech_recognizer(mock_speech_recognizer):
    """Test that the mock speech recognizer works."""
    assert mock_speech_recognizer is not None


def test_sample_session(sample_session):
    """Test that sample session fixture works."""
    assert sample_session is not None
    assert sample_session.id == 'test-session-123'


def test_sample_recording(sample_recording):
    """Test that sample recording fixture works."""
    assert sample_recording is not None
    assert sample_recording.filename == 'test_recording_001.wav'
    assert sample_recording.topic == 'Test Topic'
