import sounddevice as sd
import wavio
import os
from translation import TranslationService
from file_manager import FileManager

class AudioPlayer:
    def __init__(self):
        self.translation_service = TranslationService()
        self.file_manager = FileManager()
    
    def play_recording(self, filename, language):
        """play an audio recording from the recordings directory"""
    
        full_path = self.file_manager.get_recording_path(filename)
        
        if not os.path.exists(full_path):
            return False, self.translation_service.translate("Recording not found. ", language)
        
        try:
            print(self.translation_service.translate(f"Playing {filename}...", language))
            audio = wavio.read(full_path)
            sd.play(audio.data, audio.rate)
            sd.wait()
            print(self.translation_service.translate("Playback complete!", language))
            return True, None
        except Exception as e:
            return False, f"Failed to play recording: {e}"
    
    def list_recordings(self, language):
        """list all available recordings in the recordings directory"""
        print(self.translation_service.translate("Saved Recordings:", language))
        recordings = self.file_manager.list_recordings()
        
        if not recordings:
            print(self.translation_service.translate("No recordings found.", language))
            return recordings
        
        for i, recording in enumerate(recordings, 1):
            print(f"{i}. {recording}")
        
        return recordings