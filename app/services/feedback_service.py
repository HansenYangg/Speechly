"""Feedback service for generating AI-powered speech feedback."""
from translation import TranslationService


class FeedbackService:
    """Service for generating AI feedback on speeches."""

    def __init__(self, openai_client, translation_service=None, config=None):
        """
        Initialize feedback service with injected dependencies.

        Args:
            openai_client: OpenAI client instance (real or mock)
            translation_service: Translation service instance (optional)
            config: Configuration object with MIN_RECORDING_DURATION, etc. (optional)
        """
        self.client = openai_client
        self.translation_service = translation_service or TranslationService()

        # Configuration defaults (can be injected via config object)
        if config:
            self.min_recording_duration = config.MIN_RECORDING_DURATION
            self.short_recording_threshold = config.SHORT_RECORDING_THRESHOLD
        else:
            self.min_recording_duration = 5
            self.short_recording_threshold = 20

    def generate_feedback(self, topic, speech_type, transcription, recording_duration,
                          language, is_repeat=False, previous_transcription=None):
        """
        Generate AI feedback for a speech.

        Args:
            topic: Topic of the speech
            speech_type: Type of speech (e.g., 'practice', 'interview')
            transcription: Transcribed text of the speech
            recording_duration: Duration in seconds
            language: Language code (e.g., 'en', 'es')
            is_repeat: Whether this is a repeat attempt
            previous_transcription: Transcription of previous attempt (if repeat)

        Returns:
            str: Generated feedback or None if error
        """
        if recording_duration <= self.min_recording_duration:
            message = self.translation_service.translate(
                "Speech was too short to generate feedback for (<5 seconds). Please try again.",
                language
            )
            print(message)
            return None

        prompt = self._build_prompt(
            topic, speech_type, transcription, recording_duration,
            language, is_repeat, previous_transcription
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            feedback = response.choices[0].message.content

            print(self.translation_service.translate("Here's your feedback!: ", language))
            print(feedback)

            return feedback

        except Exception as e:
            print(f"Error while getting feedback: {e}")
            return None

    def _build_prompt(self, topic, speech_type, transcription, recording_duration,
                      language, is_repeat, previous_transcription):
        """Build the prompt for AI feedback with professor-like evaluation."""

        # Translate content to English for analysis
        translated_topic = self.translation_service.translate(topic, 'en')
        translated_type = self.translation_service.translate(speech_type, 'en')
        translated_transcription = self.translation_service.translate(transcription, 'en')

        # Build context
        repeat_context = ""
        if is_repeat and previous_transcription:
            repeat_context = f"\n\nThis is a repeat attempt. Previous version: {previous_transcription}"

        # Structured evaluation prompt with specific categories
        prompt = f"""You are evaluating a {translated_type} on "{translated_topic}". Here's what the speaker said:

{translated_transcription}
{repeat_context}

Provide detailed, structured feedback in {language} using the following format. Be specific, honest, and accurate in your assessment. Scores should reflect genuine evaluation, not rounded numbers - use precise scores like 67, 73, 82, etc.

Format your response EXACTLY like this:

[Start with 1-2 sentences giving an initial reaction or overview - what's your first impression? Set the tone naturally before diving into categories.]

Content & Relevance (Score: X/25)
[2-3 sentences analyzing how well they addressed the topic, depth of ideas, and whether their response was meaningful and on-target. Be specific about what they said or didn't say.]

Organization & Clarity (Score: X/25)
[2-3 sentences evaluating the structure, logical flow, and how easy it was to follow their points. Mention specific issues with coherence or praise clear transitions.]

Delivery & Confidence (Score: X/25)
[2-3 sentences assessing their speaking style, pace, filler words, and apparent confidence level. Note specific patterns you observed in how they expressed themselves.]

Language & Expression (Score: X/25)
[2-3 sentences examining vocabulary choice, grammar, sentence variety, and overall communication effectiveness. Point out strengths or areas needing work.]

Overall Score: X/100

Bottom Line:
[2-3 sentences wrapping up with honest, direct feedback about their overall performance. What stood out most? What's the main takeaway? Be conversational and truthful - if it was weak, say so clearly; if it was strong, acknowledge that specifically. End with one concrete next step or key area to focus on.]

IMPORTANT GRADING GUIDELINES:
- If they only said 1-5 words or gave a nonsensical response: Content 3-8/25, Organization 2-6/25, Delivery 4-9/25, Language 3-8/25 (Total: 12-31/100)
- If they gave a brief, surface-level answer (10-20 words): Content 8-14/25, Organization 7-13/25, Delivery 10-16/25, Language 9-15/25 (Total: 34-58/100)
- If they gave a decent attempt with some substance: Content 15-20/25, Organization 14-19/25, Delivery 16-21/25, Language 15-20/25 (Total: 60-80/100)
- If they gave a well-developed, thoughtful response: Content 21-25/25, Organization 20-25/25, Delivery 21-25/25, Language 21-25/25 (Total: 83-100/100)

Use SPECIFIC scores (not multiples of 5). Examples: 67, 73, 82, 88, NOT 65, 75, 80, 85.
Be accurate and fair. Don't inflate scores. If something is mediocre, give it a mediocre score (55-65 range)."""

        return prompt


__all__ = ['FeedbackService']
