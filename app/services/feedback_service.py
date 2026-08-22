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
                          language, is_repeat=False, previous_transcription=None,
                          previous_feedback=None, previous_score=None):
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
            previous_feedback: Feedback from previous attempt (if repeat)
            previous_score: Overall score from previous attempt (if repeat)

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

        # Use comparison prompt if this is a repeat attempt with previous data
        if is_repeat and previous_transcription:
            prompt = self._build_comparison_prompt(
                topic, speech_type, transcription, recording_duration,
                language, previous_transcription, previous_feedback, previous_score
            )
        else:
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
        """Build the prompt for AI feedback with expert-level evaluation."""

        # Translate content to English for analysis
        translated_topic = self.translation_service.translate(topic, 'en')
        translated_type = self.translation_service.translate(speech_type, 'en')
        translated_transcription = self.translation_service.translate(transcription, 'en')

        # Build context
        repeat_context = ""
        if is_repeat and previous_transcription:
            repeat_context = f"\n\nThis is a repeat attempt. Previous version: {previous_transcription}"

        # Check if this is a behavioral interview question
        is_behavioral = "BEHAVIORAL:" in topic or "behavioral" in speech_type.lower()

        # Get speech-type specific criteria
        type_criteria = self._get_type_specific_criteria(translated_type, is_behavioral)

        # Expert evaluation prompt with calibrated rubric
        prompt = f"""You are a world-class speech coach and communication professor with 20+ years of experience evaluating presentations, interviews, and public speaking. Your feedback is honest, specific, and actionable.

═══════════════════════════════════════════════════════════════
SPEECH EVALUATION
═══════════════════════════════════════════════════════════════
Type: {translated_type}
Topic: "{translated_topic}"
Duration: ~{int(recording_duration)} seconds
{repeat_context}

TRANSCRIPTION:
"{translated_transcription}"

═══════════════════════════════════════════════════════════════
EVALUATION CRITERIA FOR THIS SPEECH TYPE
═══════════════════════════════════════════════════════════════
{type_criteria}

═══════════════════════════════════════════════════════════════
CALIBRATED SCORING RUBRIC
═══════════════════════════════════════════════════════════════

CONTENT & RELEVANCE (0-25 points):
• 0-5: Empty, inaudible, complete nonsense, or utterly off-topic
• 6-10: Minimal content (1-2 vague sentences), barely touches topic
• 11-14: Surface-level response, lacks depth or specific examples
• 15-18: Adequate content with some relevant points but missing key elements
• 19-22: Strong content with clear examples and good topic coverage
• 23-25: Exceptional depth, compelling evidence, fully addresses the topic

ORGANIZATION & CLARITY (0-25 points):
• 0-5: No discernible structure, rambling or incoherent
• 6-10: Fragments of ideas with no logical flow
• 11-14: Basic structure exists but transitions are weak or abrupt
• 15-18: Clear beginning/middle/end with reasonable flow
• 19-22: Well-organized with smooth transitions and logical progression
• 23-25: Masterfully structured, each point builds on the previous

DELIVERY & CONFIDENCE (0-25 points):
• 0-5: Mostly silence, extreme hesitation, unable to form sentences
• 6-10: Heavy filler words (um, uh, like), constant restarts, lacks conviction
• 11-14: Noticeable hesitations but maintains some flow
• 15-18: Generally fluent with occasional stumbles, adequate confidence
• 19-22: Confident delivery, minimal filler, engaging pace
• 23-25: Commanding presence, natural rhythm, highly persuasive tone

LANGUAGE & EXPRESSION (0-25 points):
• 0-5: Broken phrases, severe grammar issues, vocabulary of a few words
• 6-10: Basic vocabulary, frequent grammatical errors, repetitive word choice
• 11-14: Functional language but generic phrasing, some errors
• 15-18: Varied vocabulary, mostly correct grammar, some vivid language
• 19-22: Sophisticated word choice, excellent grammar, memorable phrases
• 23-25: Eloquent expression, precise vocabulary, stylistically excellent

═══════════════════════════════════════════════════════════════
AUTOMATIC SCORING GUIDELINES
═══════════════════════════════════════════════════════════════

Word count matters for context:
• Under 10 meaningful words → Maximum total: 30/100
• 10-30 words → Maximum total: 50/100
• 30-75 words → Maximum total: 70/100
• 75-150 words → Can score up to 85/100 if quality is high
• 150+ words → Full range available based on quality

Empty/gibberish content:
• Transcription of "...", "[inaudible]", silence, or pure nonsense = 8-15/100 max
• Single word or phrase with no substance = 15-25/100 max

Provide feedback in {language} using this EXACT format:

[2-3 sentence executive summary - what you received and your honest assessment]

Content & Relevance (Score: X/25)
[2-3 sentences: Did they address the topic? What was present/missing? Specific examples.]

Organization & Clarity (Score: X/25)
[2-3 sentences: What structure existed? How was the flow? What could be reorganized?]

Delivery & Confidence (Score: X/25)
[2-3 sentences: How did they sound? Filler words? Hesitations? Energy level?]

Language & Expression (Score: X/25)
[2-3 sentences: Vocabulary range? Grammar? Any memorable phrases or issues?]

Overall Score: X/100

Key Strengths:
• [Specific strength 1]
• [Specific strength 2]

Priority Improvements:
• [Most important thing to work on]
• [Second priority]

Bottom Line:
[1-2 direct sentences with your honest professional assessment and encouragement for next steps]

CRITICAL SCORING RULES - VIOLATIONS WILL BE FLAGGED:
1. Each category score MUST be 0-25. NEVER exceed 25 for any category.
2. Overall Score = Content + Organization + Delivery + Language (MUST add up exactly)
3. If your feedback is negative/critical, scores MUST be low. If feedback is positive, scores can be higher.
4. CONSISTENCY CHECK: Re-read your feedback before scoring. Negative comments = low scores. Positive comments = higher scores.
5. Use precise scores (67, 73, 81) not rounded numbers (65, 75, 80)
6. Short responses (<50 words) cannot score above 70/100 total regardless of quality
7. Be encouraging but never dishonest - growth comes from accurate feedback

BEFORE SUBMITTING: Verify that Content + Organization + Delivery + Language = Overall Score"""

        return prompt

    def _get_type_specific_criteria(self, speech_type, is_behavioral):
        """Return evaluation criteria specific to the speech type."""

        speech_type_lower = speech_type.lower()

        if is_behavioral or "behavioral" in speech_type_lower:
            return """BEHAVIORAL INTERVIEW RESPONSE - STAR Method Expected:
• SITUATION (20%): Did they set the scene? Context, time, place, stakeholders?
• TASK (20%): What was their specific responsibility or challenge?
• ACTION (40%): What concrete steps did THEY take? (First person, specific actions)
• RESULT (20%): What was the outcome? Quantifiable impact preferred.

Red Flags: Speaking in "we" instead of "I", vague generalities, no specific example, hypothetical answers instead of real experiences, not answering the actual question asked."""

        elif "persuasive" in speech_type_lower or "argument" in speech_type_lower or "debate" in speech_type_lower:
            return """PERSUASIVE/DEBATE SPEECH Criteria:
• Clear thesis statement or position
• Logical arguments with evidence or examples
• Anticipation and refutation of counterarguments
• Emotional appeal balanced with logic
• Strong call to action or memorable conclusion

Red Flags: Weak or unclear position, unsupported claims, ignoring opposing views, circular reasoning, no concrete evidence."""

        elif "elevator" in speech_type_lower or "pitch" in speech_type_lower:
            return """ELEVATOR PITCH Criteria:
• Hook in first 5 seconds - grab attention immediately
• Clear value proposition - what problem do you solve?
• Unique differentiator - why you/your idea specifically?
• Credibility indicator - why should they trust you?
• Clear ask or next step - what do you want from them?

Red Flags: Too long/rambling, no clear ask, burying the lead, generic claims, missing the "so what?" factor."""

        elif "introduction" in speech_type_lower or "intro" in speech_type_lower:
            return """PROFESSIONAL INTRODUCTION Criteria:
• Name and current role/status clearly stated
• Relevant background or expertise
• Connection to the audience or context
• Memorable element (passion, unique experience, goal)
• Appropriate length for setting (usually 30-60 seconds)

Red Flags: Too much irrelevant detail, forgetting to state name, no connection to context, either too brief or rambling."""

        elif "toast" in speech_type_lower or "special occasion" in speech_type_lower:
            return """SPECIAL OCCASION SPEECH Criteria:
• Acknowledge the occasion and honoree(s) appropriately
• Personal anecdote or story that illustrates your point
• Emotional connection - humor, warmth, or inspiration as appropriate
• Universal message that resonates with the audience
• Clear, memorable ending (raise the glass, call to action)

Red Flags: Inside jokes others won't understand, inappropriate humor, making it about yourself, going too long, forgetting to actually toast."""

        elif "story" in speech_type_lower or "narrative" in speech_type_lower:
            return """STORYTELLING Criteria:
• Clear beginning that hooks the listener
• Vivid details - show don't tell (sensory language)
• Rising tension or conflict that creates interest
• Climax or turning point
• Resolution with a clear takeaway or lesson

Red Flags: Too much exposition, no conflict/stakes, telling not showing, unclear point, anticlimatic ending."""

        elif "demonstration" in speech_type_lower or "demo" in speech_type_lower or "presentation" in speech_type_lower:
            return """DEMONSTRATION/PRESENTATION Criteria:
• Clear explanation of what will be demonstrated
• Logical step-by-step progression
• Anticipation of audience questions
• Practical examples or applications
• Summary of key points and benefits

Red Flags: Assuming too much prior knowledge, skipping steps, no clear structure, failing to highlight value."""

        elif "interview" in speech_type_lower:
            return """INTERVIEW RESPONSE Criteria:
• Direct answer to the question asked
• Specific examples from real experience
• Relevant skills or achievements highlighted
• Professional tone and appropriate length
• Clear connection to the role/opportunity

Red Flags: Not answering the actual question, speaking in generalities, negativity about past experiences, too short or rambling."""

        else:
            # Generic criteria for other speech types
            return """GENERAL SPEECH Criteria:
• Clear main message or thesis
• Supporting points with examples
• Logical organization and flow
• Appropriate vocabulary for audience
• Strong opening and memorable closing

Evaluate based on: How well did they communicate their intended message? Would their audience understand and remember the key points?"""

    def _build_comparison_prompt(self, topic, speech_type, transcription, recording_duration,
                                  language, previous_transcription, previous_feedback, previous_score):
        """Build the prompt for comparing a repeat attempt with the previous one."""

        # Translate content to English for analysis
        translated_topic = self.translation_service.translate(topic, 'en')
        translated_type = self.translation_service.translate(speech_type, 'en')
        translated_transcription = self.translation_service.translate(transcription, 'en')
        translated_previous = self.translation_service.translate(previous_transcription, 'en')

        # Parse previous score
        prev_score_str = str(previous_score) if previous_score else "unknown"

        # Check if this is a behavioral interview question
        is_behavioral = "BEHAVIORAL:" in topic or "behavioral" in speech_type.lower()
        type_criteria = self._get_type_specific_criteria(translated_type, is_behavioral)

        # Comparison evaluation prompt
        prompt = f"""You are a world-class speech coach comparing two attempts at the same speech to evaluate improvement and provide actionable feedback.

═══════════════════════════════════════════════════════════════
COMPARISON EVALUATION
═══════════════════════════════════════════════════════════════
Type: {translated_type}
Topic: "{translated_topic}"
New Attempt Duration: ~{int(recording_duration)} seconds

═══════════════════════════════════════════════════════════════
EVALUATION CRITERIA FOR THIS SPEECH TYPE
═══════════════════════════════════════════════════════════════
{type_criteria}

═══════════════════════════════════════════════════════════════
PREVIOUS ATTEMPT (Score: {prev_score_str}/100)
═══════════════════════════════════════════════════════════════
"{translated_previous}"

═══════════════════════════════════════════════════════════════
NEW ATTEMPT (Being Evaluated)
═══════════════════════════════════════════════════════════════
"{translated_transcription}"

═══════════════════════════════════════════════════════════════

Provide a detailed comparison and evaluation in {language}.

IMPROVEMENT ANALYSIS

[2-3 sentence overview: Did they improve, regress, or stay flat? What's the most notable difference? Be direct.]

What Improved:
• [Specific improvement 1 with concrete example from the transcription]
• [Specific improvement 2 - if nothing improved, say "No significant improvements observed"]
• [Specific improvement 3 - optional]

What Still Needs Work:
• [Area needing improvement 1 - be specific about what to fix]
• [Area needing improvement 2]
• [Any regressions from previous attempt]

Side-by-Side Breakdown:

Content & Relevance (Previous: X/25 → New: Y/25)
[What changed in substance? More/less depth? Better/worse examples?]

Organization & Clarity (Previous: X/25 → New: Y/25)
[Better/worse structure? Clearer/muddier flow?]

Delivery & Confidence (Previous: X/25 → New: Y/25)
[More/less confident? Filler words improved/worsened?]

Language & Expression (Previous: X/25 → New: Y/25)
[Vocabulary richer/poorer? Grammar better/worse?]

═══════════════════════════════════════════════════════════════
SCORE COMPARISON: {prev_score_str}/100 → X/100 (change: ±Y)
═══════════════════════════════════════════════════════════════

Overall Score: X/100

[Progress indicator based on actual change]

Key Strengths This Attempt:
• [What they did well in THIS attempt]

Priority for Next Attempt:
• [Single most important thing to focus on next time]

Bottom Line:
[1-2 direct sentences - honest assessment of progress and clear next step]

SCORING RULES:
• Score the NEW attempt on its own merits using the calibrated rubric
• Previous score of {prev_score_str} is REFERENCE ONLY - new attempt may be higher OR lower
• Sum of 4 categories MUST equal Overall Score
• Use precise scores (67, 73, 81) not rounded (65, 75, 80)
• Word count limits still apply - short responses cannot score high regardless of previous score
• Be honest about regressions - sometimes practice attempts get worse before getting better"""

        return prompt


__all__ = ['FeedbackService']
