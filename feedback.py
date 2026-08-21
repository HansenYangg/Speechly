"""Backward compatibility wrapper for FeedbackService."""
import openai
from app.services.feedback_service import FeedbackService as NewFeedbackService
from app.config import get_config
from translation import TranslationService


class FeedbackService:
    """
    Backward compatible wrapper for old code.

    This allows existing code to continue working while using the new
    injectable service architecture under the hood.
    """

    def __init__(self):
        # Get configuration
        config = get_config()

        # Create OpenAI client
        client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

        # Create translation service
        translation_service = TranslationService()

        # Initialize the new service with dependencies
        self._service = NewFeedbackService(
            openai_client=client,
            translation_service=translation_service,
            config=config
        )

    def generate_feedback(self, topic, speech_type, transcription, recording_duration,
                          language, is_repeat=False, previous_transcription=None):
        """Delegate to new service."""
        return self._service.generate_feedback(
            topic, speech_type, transcription, recording_duration,
            language, is_repeat, previous_transcription
        )

    def _build_prompt(self, topic, speech_type, transcription, recording_duration,
                      language, is_repeat, previous_transcription):
        """Delegate to new service."""
        return self._service._build_prompt(
            topic, speech_type, transcription, recording_duration,
            language, is_repeat, previous_transcription
        )


__all__ = ['FeedbackService']
