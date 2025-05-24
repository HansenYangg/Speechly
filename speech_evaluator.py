from audio_recorder import AudioRecorder
from audio_player import AudioPlayer
from transcription import TranscriptionService
from feedback import FeedbackService
from speech_manager import SpeechDataManager
from translation import TranslationService

class SpeechEvaluator:
    """Main class that orchestrates all speech evaluation functionality"""
    
    def __init__(self):
        self.audio_recorder = AudioRecorder()
        self.audio_player = AudioPlayer()
        self.transcription_service = TranscriptionService()
        self.feedback_service = FeedbackService()
        self.data_manager = SpeechDataManager()
        self.translation_service = TranslationService()
    
    def record_and_evaluate_speech(self, topic, speech_type, language, is_repeat=False, previous_filename=None):
        """Complete workflow for recording and evaluating a speech"""
        
        # Start recording
        success, recording_thread = self.audio_recorder.start_recording(language)
        if not success:
            print(recording_thread)  # Error message
            return
        
        # Stop recording (waits for user input)
        self.audio_recorder.stop_recording(language)
        recording_thread.join()
        
        # Save recording
        filename = f"{topic}.wav"
        success, duration = self.audio_recorder.save_recording(filename, language)
        if not success:
            print(duration)  # Error message
            return
        
        # Transcribe audio
        transcription = self.transcription_service.transcribe_audio(filename, language, show_output=False)
        if transcription:
            # Store transcription
            self.data_manager.add_speech_data(filename, transcription)
            
            # Ask if user wants to see transcript
            from ui import UserInterface
            ui = UserInterface(self)  # Note: This creates circular import, consider refactoring
            
            show_transcript = ui.ask_for_transcript()
            if show_transcript:
                print("Here's the transcription of your speech: ")
                print(transcription)
            else:
                print("Okay! Proceeding to generating feedback.")
            
            # Get previous transcription if this is a repeat
            previous_transcription = None
            if is_repeat and previous_filename:
                previous_transcription = self.data_manager.get_previous_transcription(previous_filename)
            
            # Generate feedback
            feedback = self.feedback_service.generate_feedback(
                topic, speech_type, transcription, duration, language,
                is_repeat, previous_transcription
            )
            
            return {
                'filename': filename,
                'transcription': transcription,
                'duration': duration,
                'feedback': feedback
            }
        else:
            error_msg = self.translation_service.translate(
                "Could not transcribe audio. Feedback cannot be generated.",
                language
            )
            print(error_msg)
            return None