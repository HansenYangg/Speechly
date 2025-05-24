import speech_recognition as sr
import os
from translation import TranslationService
from file_manager import FileManager

class TranscriptionService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.translation_service = TranslationService()
        self.file_manager = FileManager()
    
    def transcribe_audio(self, filename, language, show_output=True):
        """transcribe audio file to text"""
        try:
            # Get full path if just filename is provided
            if not filename.startswith(self.file_manager.recordings_dir):
                full_path = self.file_manager.get_recording_path(filename)
            else:
                full_path = filename
            
            with sr.AudioFile(full_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                
                if show_output:
                    display_filename = os.path.basename(full_path)
                    print(self.translation_service.translate(f"Here is the transcription of {display_filename}:", language))
                    print(text)
                
                return text
        except sr.UnknownValueError:
            error_msg = self.translation_service.translate("Sorry, I could not understand the audio.", language)
            if show_output:
                print(error_msg)
            return None
        except sr.RequestError as e:
            error_msg = self.translation_service.translate(f"Could not request results; {e}.", language)
            if show_output:
                print(error_msg)
            return None
        except Exception as e:
            error_msg = f"Transcription error: {e}"
            if show_output:
                print(error_msg)
            return None