"""Mock OpenAI client for testing."""


class MockChatCompletionChoice:
    """Mock chat completion choice."""

    def __init__(self, content):
        self.message = MockMessage(content)
        self.finish_reason = 'stop'
        self.index = 0


class MockMessage:
    """Mock message."""

    def __init__(self, content):
        self.content = content
        self.role = 'assistant'


class MockChatCompletionResponse:
    """Mock chat completion response."""

    def __init__(self, content):
        self.choices = [MockChatCompletionChoice(content)]
        self.id = 'mock-completion-id'
        self.model = 'gpt-4o-mini'
        self.object = 'chat.completion'


class MockChatCompletion:
    """Mock chat completion API."""

    def create(self, model, messages, **kwargs):
        """Create a mock chat completion."""
        # Return predictable feedback for testing
        feedback_content = """# Speech Evaluation Feedback

## Overall Assessment
Your speech was clear and well-structured. Good use of pauses and emphasis.

## Strengths
- Clear articulation
- Good pacing
- Engaging tone

## Areas for Improvement
- Could use more varied vocabulary
- Add more specific examples

## Score: 85/100

Keep practicing!"""
        return MockChatCompletionResponse(feedback_content)


class MockAudioTranscription:
    """Mock audio transcription API."""

    def create(self, model, file, **kwargs):
        """Create a mock transcription."""
        # Return a mock transcription object
        class MockTranscription:
            text = "This is a mock transcription for testing purposes. The audio has been successfully transcribed."

        return MockTranscription()


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self, api_key=None):
        self.api_key = api_key or 'test-key'
        self.chat = MockChat()
        self.audio = MockAudio()


class MockChat:
    """Mock chat API."""

    def __init__(self):
        self.completions = MockChatCompletion()


class MockAudio:
    """Mock audio API."""

    def __init__(self):
        self.transcriptions = MockAudioTranscription()


__all__ = ['MockOpenAIClient']
