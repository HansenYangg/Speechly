"""Flask application factory and dependency injection container."""
from flask import Flask
from flask_cors import CORS
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class ServiceContainer:
    """Dependency injection container for services and repositories."""

    def __init__(self, app):
        """
        Initialize service container.

        Args:
            app: Flask application instance
        """
        self.app = app
        self.config = app.config
        self._services = {}
        self._repositories = {}

    def get_openai_client(self):
        """Get OpenAI client (real or mock based on config)."""
        if 'openai_client' not in self._services:
            if self.config.get('TESTING'):
                from tests.mocks.mock_openai import MockOpenAIClient
                self._services['openai_client'] = MockOpenAIClient()
            else:
                self._services['openai_client'] = openai.OpenAI(
                    api_key=self.config.get('OPENAI_API_KEY')
                )
        return self._services['openai_client']

    def get_speech_recognizer(self):
        """Get speech recognizer (real or mock based on config)."""
        if 'speech_recognizer' not in self._services:
            if self.config.get('TESTING'):
                from tests.mocks.mock_google_speech import MockRecognizer
                self._services['speech_recognizer'] = MockRecognizer()
            else:
                import speech_recognition as sr
                self._services['speech_recognizer'] = sr.Recognizer()
        return self._services['speech_recognizer']

    def get_translation_service(self):
        """Get translation service."""
        if 'translation_service' not in self._services:
            from translation import TranslationService
            self._services['translation_service'] = TranslationService()
        return self._services['translation_service']

    def get_transcription_service(self):
        """Get transcription service with dependencies."""
        if 'transcription_service' not in self._services:
            from app.services import TranscriptionService
            openai_client = self.get_openai_client()
            recognizer = self.get_speech_recognizer()
            translation_service = self.get_translation_service()
            self._services['transcription_service'] = TranscriptionService(
                openai_client=openai_client,
                recognizer=recognizer,
                translation_service=translation_service
            )
        return self._services['transcription_service']

    def get_feedback_service(self):
        """Get feedback service with dependencies."""
        if 'feedback_service' not in self._services:
            from app.services import FeedbackService
            client = self.get_openai_client()
            translation_service = self.get_translation_service()

            # Pass config object for thresholds
            config_obj = type('Config', (), {
                'MIN_RECORDING_DURATION': self.config.get('MIN_RECORDING_DURATION', 5),
                'SHORT_RECORDING_THRESHOLD': self.config.get('SHORT_RECORDING_THRESHOLD', 20)
            })()

            self._services['feedback_service'] = FeedbackService(
                openai_client=client,
                translation_service=translation_service,
                config=config_obj
            )
        return self._services['feedback_service']

    def get_evaluation_service(self):
        """Get evaluation service with dependencies."""
        if 'evaluation_service' not in self._services:
            from app.services import EvaluationService
            transcription_service = self.get_transcription_service()
            feedback_service = self.get_feedback_service()
            translation_service = self.get_translation_service()

            self._services['evaluation_service'] = EvaluationService(
                transcription_service=transcription_service,
                feedback_service=feedback_service,
                translation_service=translation_service
            )
        return self._services['evaluation_service']

    def get_session_repository(self, legacy_sessions_dict=None):
        """Get session repository with dependencies."""
        if 'session_repository' not in self._repositories:
            from app.repositories import SessionRepository
            from app.models import db

            self._repositories['session_repository'] = SessionRepository(
                db_session=db,
                legacy_sessions_dict=legacy_sessions_dict
            )
        return self._repositories['session_repository']

    def get_recording_repository(self, legacy_sessions_dict=None, legacy_json_file=None):
        """Get recording repository with dependencies."""
        if 'recording_repository' not in self._repositories:
            from app.repositories import RecordingRepository
            from app.models import db

            self._repositories['recording_repository'] = RecordingRepository(
                db_session=db,
                config=type('Config', (), self.config)(),
                legacy_sessions_dict=legacy_sessions_dict,
                legacy_json_file=legacy_json_file
            )
        return self._repositories['recording_repository']

    def get_speech_history_repository(self, legacy_json_file=None):
        """Get speech history repository with dependencies."""
        if 'speech_history_repository' not in self._repositories:
            from app.repositories import SpeechHistoryRepository
            from app.models import db

            self._repositories['speech_history_repository'] = SpeechHistoryRepository(
                db_session=db,
                legacy_json_file=legacy_json_file
            )
        return self._repositories['speech_history_repository']


def create_app(config_name=None):
    """
    Application factory pattern.

    Args:
        config_name: Name of configuration to use ('development', 'production', 'testing')

    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__, static_folder='../static', static_url_path='/static')

    # Load configuration
    from app.config import get_config
    config = get_config(config_name)

    # Apply configuration to Flask app
    for key in dir(config):
        if key.isupper():
            app.config[key] = getattr(config, key)

    # Initialize extensions
    from app.models import init_db
    init_db(app)

    CORS(app)

    # Create service container
    app.container = ServiceContainer(app)

    # Register blueprints
    from app.routes import health, sessions, recordings, evaluation, frontend

    app.register_blueprint(health.bp)
    app.register_blueprint(sessions.bp)
    app.register_blueprint(recordings.bp)
    app.register_blueprint(evaluation.bp)
    app.register_blueprint(frontend.bp)

    return app


__all__ = ['create_app', 'ServiceContainer']
