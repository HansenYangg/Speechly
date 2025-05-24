import sounddevice as sd
import wavio
import numpy as np
import threading
from config import SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_FORMAT
from translation import TranslationService

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.recorded_data = []
        self.translation_service = TranslationService()
    
    def start_recording(self, language):
        """Start recording audio"""
        if self.recording:
            return False, "Already recording"
        
        self.recording = True
        self.recorded_data = []
        
        print(self.translation_service.translate("Recording... you can speak into the microphone now. ", language))
        
        recording_thread = threading.Thread(target=self._record_audio)
        recording_thread.start()
        
        return True, recording_thread
    
    def _record_audio(self):
        """Internal method to handle audio recording"""
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=AUDIO_CHANNELS, dtype=AUDIO_FORMAT) as stream:
            while self.recording:
                chunk = stream.read(int(1 * SAMPLE_RATE))
                self.recorded_data.append(chunk[0])
    
    def stop_recording(self, language):
        """Stop the current recording"""
        if not self.recording:
            return False, "No recording in progress"
        
        input(self.translation_service.translate("Press Enter to stop recording at any time... ", language))
        self.recording = False
        print(self.translation_service.translate("You have stopped the recording. ", language))
        return True, None
    
    def save_recording(self, filename, language):
        """Save the recorded audio to a file"""
        if not self.recorded_data:
            return False, "No recorded data to save"
        
        try:
            recorded_data_combined = np.concatenate(self.recorded_data)
            wavio.write(filename, recorded_data_combined, SAMPLE_RATE, sampwidth=2)
            
            # Calculate duration
            duration = len(recorded_data_combined) / SAMPLE_RATE
            
            print(self.translation_service.translate(f"Recording saved as {filename}", language))
            
            # Clear recorded data for next recording
            self.recorded_data.clear()
            
            return True, duration
        except Exception as e:
            return False, f"Failed to save recording: {e}"
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording