import sounddevice as sd
import wavio
import os
from translation import TranslationService

class AudioPlayer:
    def __init__(self):
        self.translation_service = TranslationService()
    
    def play_recording(self, filename, language):
        """Play an audio recording"""
        if not os.path.exists(filename):
            return False, self.translation_service.translate("Recording not found. ", language)
        
        try:
            print(self.translation_service.translate(f"Playing {filename}...", language))
            audio = wavio.read(filename)
            sd.play(audio.data, audio.rate)
            sd.wait()
            print(self.translation_service.translate("Playback complete!", language))
            return True, None
        except Exception as e:
            return False, f"Failed to play recording: {e}"
    
    def list_recordings(self, language):
        """List all available recordings"""
        print(self.translation_service.translate("Saved Recordings:", language))
        recordings = []
        for file in os.listdir('.'):
            if file.endswith('.wav'):
                recordings.append(file)
                print(file)
        return recordings