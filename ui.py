import sys
from config import LANGUAGES, LANGUAGE_DISPLAY
from translation import TranslationService

class UserInterface:
    def __init__(self, speech_evaluator):
        self.speech_evaluator = speech_evaluator
        self.translation_service = TranslationService()
        self.current_language = "en"
    
    def select_language(self):
        """language selection interface"""
        while True:
            print("\nAvailable Languages:")
            for lang_option in LANGUAGE_DISPLAY:
                print(lang_option)
            
            lang_code = input("Please select the language you would like to present in (use the two-letter abbreviation): ")
            
            if lang_code in LANGUAGES.keys():
                self.current_language = lang_code
                break
            else:
                print("Please enter a valid language.")
        
        welcome_msg = self.translation_service.translate(
            "Welcome to the AI Speech Evaluation Tool! Hit any of the keys listed below to get started. ", 
            self.current_language
        )
        print(welcome_msg)
    
    def main_menu(self):
        """Main command interface"""
        while True:
            menu_prompt = self.translation_service.translate(
                "\nEnter 'R' To Record, 'L' To List Recordings, 'P' To Play A Recording, or 'Q' To Quit: ", 
                self.current_language
            )
            command = input(menu_prompt).lower()
            
            if command in 'rR':
                self._handle_record_command()
            elif command in 'lL':
                self._handle_list_command()
            elif command in 'pP':
                self._handle_play_command()
            elif command in 'qQ':
                self._handle_quit_command()
            else:
                invalid_msg = self.translation_service.translate(
                    "Invalid option. Please press a valid key. ", 
                    self.current_language
                )
                print(invalid_msg)
    
    def _handle_record_command(self):
        """Handle recording command"""
        if self.speech_evaluator.audio_recorder.is_recording():
            already_recording_msg = self.translation_service.translate(
                "Already recording. Please stop the current recording before starting a new one or continue your speech. ",
                self.current_language
            )
            print(already_recording_msg)
            return
        
        # Get topic
        topic_prompt = self.translation_service.translate(
            "Please enter the topic of your speech so we know what to look out for, or 'b' if you want to go back. ",
            self.current_language
        )
        topic = input(topic_prompt)
        
        if topic.lower() in 'bB':
            return
        
        # Check for repeat speech
        is_repeat, previous_filename = self._check_repeat_speech()
        
        # Get speech type
        speech_type_prompt = self.translation_service.translate(
            "What is this speech for (interview, school presentation, etc.)? This will be used to give you specific feedback. Press 'b' if you want to go back. ",
            self.current_language
        )
        speech_type = input(speech_type_prompt)
        
        if speech_type.lower() in 'bB':
            return
        
        # Confirm start recording
        if not self._confirm_start_recording():
            return
        
        # Start recording process
        self.speech_evaluator.record_and_evaluate_speech(
            topic, speech_type, self.current_language, is_repeat, previous_filename
        )
    
    def _check_repeat_speech(self):
        """Check if this is a repeat speech on the same topic"""
        repeat_prompt = self.translation_service.translate(
            "Have you done a speech on this topic in this session already? (Y/N) ",
            self.current_language
        )
        repeated = input(repeat_prompt)
        
        if repeated.lower() in 'yY':
            prev_prompt = self.translation_service.translate(
                "What is the name of the recording? Press 'p' to view all recordings. ",
                self.current_language
            )
            prev = input(prev_prompt)
            
            if prev.lower() in 'pP':
                self.speech_evaluator.audio_player.list_recordings(self.current_language)
                select_prompt = self.translation_service.translate(
                    "These are all the recordings. Please type the name of the one on the same topic. ",
                    self.current_language
                )
                prev = input(select_prompt)
            
            if self.speech_evaluator.data_manager.has_previous_speech(prev):
                return True, prev
            else:
                print("That recording does not exist.")
                return False, None
        
        return False, None
    
    def _confirm_start_recording(self):
        """Confirm user wants to start recording"""
        while True:
            confirm_prompt = self.translation_service.translate(
                "Press 't' to begin recording or 'b' to go back.",
                self.current_language
            )
            var = input(confirm_prompt)
            
            if var.lower() in 'bB':
                return False
            elif var.lower() in 'tT':
                return True
            else:
                print("Please enter a valid input.")
    
    def _handle_list_command(self):
        """Handle list recordings command"""
        self.speech_evaluator.audio_player.list_recordings(self.current_language)
    
    def _handle_play_command(self):
        """Handle play recording command"""
        filename_prompt = self.translation_service.translate(
            "Enter the name of the recording you want to play: ",
            self.current_language
        )
        
        filename = input(filename_prompt)
        success, error = self.speech_evaluator.audio_player.play_recording(filename, self.current_language)
        if not success:
            print(error)
    
    def _handle_quit_command(self):
        """Handle quit command"""
        quit_msg = self.translation_service.translate("Exiting the tool. ", self.current_language)
        print(quit_msg)
        sys.exit(0)
    
    def ask_for_transcript(self):
        """Ask user if they want to see transcript"""
        transcript_prompt = self.translation_service.translate(
            "Would you like a transcript of your speech for reference? (Y/N) ",
            self.current_language
        )
        response = input(transcript_prompt)
        return response.lower() in 'yY'
