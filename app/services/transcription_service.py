"""Transcription service for converting speech to text."""
import os
from translation import TranslationService
from file_manager import FileManager


class TranscriptionService:
    """Service for transcribing audio files to text."""

    def __init__(self, openai_client=None, recognizer=None, translation_service=None, file_manager=None):
        """
        Initialize transcription service with injected dependencies.

        Args:
            openai_client: OpenAI client for Whisper API (preferred)
            recognizer: Speech recognition instance (fallback, real or mock)
            translation_service: Translation service instance (optional)
            file_manager: File manager instance (optional)
        """
        self.openai_client = openai_client

        if recognizer is None and openai_client is None:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
        else:
            self.recognizer = recognizer

        self.translation_service = translation_service or TranslationService()
        self.file_manager = file_manager or FileManager()

    def transcribe_audio(self, filename, language, show_output=True):
        """
        Transcribe audio file to text.

        Args:
            filename: Path to audio file or just filename
            language: Language code for error messages
            show_output: Whether to print output to console

        Returns:
            str: Transcribed text or None if error
        """
        try:
            # Determine full path
            # If it's an absolute path or temp file, use it directly
            if os.path.isabs(filename) or os.path.exists(filename):
                full_path = filename
            else:
                # Otherwise, look in recordings directory
                full_path = self.file_manager.get_recording_path(filename)

            if not os.path.exists(full_path):
                print(f"Error: Audio file not found at {full_path}")
                return None

            # Try OpenAI Whisper first (supports WebM, WAV, and many other formats)
            if self.openai_client:
                try:
                    with open(full_path, 'rb') as audio_file:
                        transcript = self.openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language=language if language != 'en' else None  # Whisper auto-detects for English
                        )
                        text = transcript.text

                        if show_output:
                            display_filename = os.path.basename(full_path)
                            print(self.translation_service.translate(f"Here is the transcription of {display_filename}:", language))
                            print(text)

                        return text
                except Exception as whisper_error:
                    print(f"Whisper API error: {whisper_error}, falling back to Google Speech Recognition")

            # Fallback to Google Speech Recognition (only works with WAV)
            import speech_recognition as sr

            with sr.AudioFile(full_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)

                if show_output:
                    display_filename = os.path.basename(full_path)
                    print(self.translation_service.translate(f"Here is the transcription of {display_filename}:", language))
                    print(text)

                return text

        except Exception as e:
            # Log the actual error for debugging
            print(f"Transcription error: {type(e).__name__}: {str(e)}")

            # Handle all speech recognition exceptions
            if 'UnknownValueError' in str(type(e)):
                error_msg = self.translation_service.translate("Sorry, I could not understand the audio.", language)
            elif 'RequestError' in str(type(e)):
                error_msg = self.translation_service.translate(f"Could not request results; {e}.", language)
            else:
                error_msg = f"Transcription error: {e}"

            if show_output:
                print(error_msg)
            return None


__all__ = ['TranscriptionService']
