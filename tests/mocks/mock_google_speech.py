"""Mock Google Speech Recognition for testing."""


class MockAudioData:
    """Mock audio data object."""

    def __init__(self, data=b'mock audio data'):
        self.frame_data = data

    def get_wav_data(self):
        """Get WAV data."""
        return self.frame_data


class MockMicrophone:
    """Mock microphone source."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockRecognizer:
    """Mock speech recognizer."""

    def __init__(self):
        self.energy_threshold = 4000
        self.dynamic_energy_threshold = True
        self.pause_threshold = 0.8

    def record(self, source, duration=None):
        """Record audio from source."""
        return MockAudioData()

    def listen(self, source):
        """Listen for audio from source."""
        return MockAudioData()

    def recognize_google(self, audio_data, language='en-US', show_all=False):
        """
        Mock Google Speech Recognition.

        Returns a predictable transcription for testing.
        """
        if show_all:
            return {
                'alternative': [
                    {
                        'transcript': 'This is a mock transcription for testing purposes',
                        'confidence': 0.95
                    }
                ]
            }
        return 'This is a mock transcription for testing purposes'

    def adjust_for_ambient_noise(self, source, duration=1):
        """Adjust for ambient noise (no-op in mock)."""
        pass


__all__ = ['MockRecognizer', 'MockMicrophone', 'MockAudioData']
