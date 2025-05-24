import openai
from config import OPENAI_API_KEY, MIN_RECORDING_DURATION, SHORT_RECORDING_THRESHOLD
from translation import TranslationService

class FeedbackService:
    def __init__(self):
        openai.api_key = OPENAI_API_KEY
        self.translation_service = TranslationService()
    
    def generate_feedback(self, topic, speech_type, transcription, recording_duration, 
                         language, is_repeat=False, previous_transcription=None):
        """generate AI feedback for a speech"""
        
        if recording_duration <= MIN_RECORDING_DURATION:
            message = self.translation_service.translate(
                "Speech was too short to generate feedback for (<5 seconds). Please try again.", 
                language
            )
            print(message)
            return
        
        prompt = self._build_prompt(
            topic, speech_type, transcription, recording_duration, 
            language, is_repeat, previous_transcription
        )
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            feedback = response['choices'][0]['message']['content']
            
            print(self.translation_service.translate("Here's your feedback!: ", language))
            print(feedback)
            
            return feedback
            
        except Exception as e:
            print(f"Error while getting feedback: {e}")
            return None
    
    def _build_prompt(self, topic, speech_type, transcription, recording_duration, 
                     language, is_repeat, previous_transcription):
        """Build the prompt for AI feedback"""
        
        # Base prompt components
        grading_instruction = (
            "First, give a grading on a strict scale of 1-100 on the speech. "
            "Don't always have scores in increments of 5, use more varied/granular scores. "
            "You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc."
        )
        
        feedback_instruction = (
            "Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
            "Note good things they did and things they can improve on, and don't be overly nice. "
        )
        
        context = f"For context, the speech was '{self.translation_service.translate(topic, 'en')}' for a {self.translation_service.translate(speech_type, 'en')}."
        
        repeat_context = ""
        if is_repeat and previous_transcription:
            repeat_context = f"Also, the user has already done a speech on this topic. Here is the original transcription: {previous_transcription}. Compare the two and note improvements."
        
        language_instruction = f"Try to tailor to their specific speech style. Make sure to do this in {language}."
        
        # Different prompts based on recording duration
        if MIN_RECORDING_DURATION < recording_duration < SHORT_RECORDING_THRESHOLD:
            prompt = (
                f"The following speech is pretty short and may lack sufficient content. "
                f"Please evaluate and critique it given the following topic and type of the speech. "
                f"Give appropriate feedback accordingly based on these:\n\n"
                f"Speech topic: '{self.translation_service.translate(topic, 'en')}'\n"
                f"Speech type: {self.translation_service.translate(speech_type, 'en')}\n"
                f"Transcription: '{self.translation_service.translate(transcription, 'en')}'\n\n"
                f"{repeat_context}\n"
                f"Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice. "
                f"You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. "
                f"Don't always have scores in increments of 5, use more varied/granular scores. "
                f"{language_instruction}"
            )
        else:
            prompt = (
                f"{grading_instruction} "
                f"{feedback_instruction} "
                f"{context} "
                f"{repeat_context} "
                f"In {language}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said.\n"
                f"The speech is:\n\n{self.translation_service.translate(transcription, 'en')}\n\nFeedback:"
            )
        
        return prompt