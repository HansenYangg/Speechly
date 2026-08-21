"""Evaluation service for orchestrating speech evaluation workflow."""


class EvaluationService:
    """Service for orchestrating the complete speech evaluation workflow."""

    def __init__(self, transcription_service, feedback_service, translation_service=None):
        """
        Initialize evaluation service with injected dependencies.

        Args:
            transcription_service: Service for transcribing audio
            feedback_service: Service for generating feedback
            translation_service: Service for translations (optional)
        """
        self.transcription_service = transcription_service
        self.feedback_service = feedback_service

        if translation_service is None:
            from translation import TranslationService
            self.translation_service = TranslationService()
        else:
            self.translation_service = translation_service

    def evaluate_audio_file(self, audio_file_path, topic, speech_type, language,
                            duration, is_repeat=False, previous_transcription=None):
        """
        Evaluate an audio file and generate feedback.

        This is the core evaluation logic without the recording part
        (suitable for web API where audio is uploaded).

        Args:
            audio_file_path: Path to the audio file
            topic: Topic of the speech
            speech_type: Type of speech (e.g., 'practice', 'interview')
            language: Language code
            duration: Duration of the recording in seconds
            is_repeat: Whether this is a repeat attempt
            previous_transcription: Transcription from previous attempt

        Returns:
            dict: Evaluation results with transcription and feedback
        """
        # Transcribe the audio
        print(f"Attempting to transcribe audio file: {audio_file_path}")
        transcription = self.transcription_service.transcribe_audio(
            audio_file_path,
            language,
            show_output=True  # Enable output to see errors
        )

        if not transcription:
            print(f"Transcription failed for file: {audio_file_path}")
            error_msg = self.translation_service.translate(
                "Could not transcribe audio. Feedback cannot be generated.",
                language
            )
            return {
                'success': False,
                'error': error_msg,
                'transcription': None,
                'feedback': None
            }

        # Generate feedback
        feedback = self.feedback_service.generate_feedback(
            topic,
            speech_type,
            transcription,
            duration,
            language,
            is_repeat,
            previous_transcription
        )

        return {
            'success': True,
            'transcription': transcription,
            'feedback': feedback,
            'duration': duration
        }


__all__ = ['EvaluationService']
