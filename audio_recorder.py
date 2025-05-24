import sounddevice as sd
import wavio
import numpy as np
import threading
import os
from config import SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_FORMAT
from translation import TranslationService
from file_manager import FileManager
from exceptions import AudioRecordingError
from logger import setup_logger
from validator import Validator

logger = setup_logger(__name__)

class AudioRecorder:
    def __init__(self):
        self.recording = False
        self.recorded_data = []
        self.translation_service = TranslationService()
        self.file_manager = FileManager()
    
    def start_recording(self, language):
        """start recording audio"""
        try:
            Validator.validate_language(language)
            
            if self.recording:
                return False, "Already recording"
            
            self.recording = True
            self.recorded_data = []
            
            print(self.translation_service.translate("Recording... you can speak into the microphone now. ", language))
            
            recording_thread = threading.Thread(target=self._record_audio)
            recording_thread.start()
            
            logger.info("Audio recording started")
            return True, recording_thread
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False, str(e)
    
    def _record_audio(self):
        """internal method to handle audio recording"""
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=AUDIO_CHANNELS, dtype=AUDIO_FORMAT) as stream:
                while self.recording:
                    chunk = stream.read(int(1 * SAMPLE_RATE))
                    self.recorded_data.append(chunk[0])
        except Exception as e:
            logger.error(f"Audio recording error: {e}")
            raise AudioRecordingError(f"Failed to record audio: {e}")
    
    def stop_recording(self, language):
        """stop the current recording"""
        if not self.recording:
            return False, "No recording in progress"
        
        input(self.translation_service.translate("Press Enter to stop recording at any time... ", language))
        self.recording = False
        print(self.translation_service.translate("You have stopped the recording. ", language))
        return True, None
    
    def save_recording(self, topic, language):
        """save the recorded audio to a file in the recordings directory"""
        try:
            if not self.recorded_data:
                return False, "No recorded data to save", None
            
            # validate and sanitize topic
            clean_topic = Validator.sanitize_topic(topic)
            
            # generate filename with timestamp
            filename = self.file_manager.generate_filename(clean_topic, include_timestamp=True)
            
            recorded_data_combined = np.concatenate(self.recorded_data)
            wavio.write(filename, recorded_data_combined, SAMPLE_RATE, sampwidth=2)
            
            # calculate duration
            duration = len(recorded_data_combined) / SAMPLE_RATE
            Validator.validate_duration(duration)
            
            # extract just the filename (without path) for display
            display_filename = os.path.basename(filename)
            print(self.translation_service.translate(f"Recording saved as {display_filename}", language))
            
            # clear recorded data for next recording
            self.recorded_data.clear()
            
            logger.info(f"Recording saved: {display_filename} ({duration:.1f}s)")
            return True, duration, filename
            
        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return False, f"Failed to save recording: {e}", None
    
    def is_recording(self):
        """Check if currently recording"""
        return self.recording