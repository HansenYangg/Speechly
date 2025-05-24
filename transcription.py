import speech_recognition as sr
from translation import TranslationService

class TranscriptionService:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.translation_service = TranslationService()
    
    def transcribe_audio(self, filename, language, show_output=True):
        """Transcribe audio file to text"""
        try:
            with sr.AudioFile(filename) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                
                if show_output:
                    print(self.translation_service.translate(f"Here is the transcription of {filename}:", language))
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