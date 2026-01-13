
class SpeechEvaluatorError(Exception):
    """Base exception for all speech evaluator errors"""
    pass

class AudioRecordingError(SpeechEvaluatorError):
    """Raised when audio recording fails"""
    pass

class AudioPlaybackError(SpeechEvaluatorError):
    """Raised when audio playback fails"""
    pass

class TranscriptionError(SpeechEvaluatorError):
    """Raised when speech transcription fails"""
    pass

class FeedbackGenerationError(SpeechEvaluatorError):
    """Raised when AI feedback generation fails"""
    pass

class ConfigurationError(SpeechEvaluatorError):
    """Raised when configuration is invalid"""
    pass

class ValidationError(SpeechEvaluatorError):
    """Raised when input validation fails"""
    pass

class APIError(SpeechEvaluatorError):
    """Raised when external API calls fail"""
    pass