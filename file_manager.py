import os
from datetime import datetime
from config import RECORDINGS_DIR, AUDIO_FILE_EXTENSION

class FileManager:
    """manages file operations and directory structure for recordings"""
    
    def __init__(self):
        self.recordings_dir = RECORDINGS_DIR
        self._ensure_recordings_directory()
    
    def _ensure_recordings_directory(self):
        """create recordings directory if it doesn't exist"""
        if not os.path.exists(self.recordings_dir):
            os.makedirs(self.recordings_dir)
            print(f"Created recordings directory: {self.recordings_dir}")
    
    def generate_filename(self, topic, include_timestamp=True):
        """generate a filename for a recording"""
        # Clean the topic name for use as filename
        clean_topic = self._clean_filename(topic)
        
        if include_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{clean_topic}_{timestamp}{AUDIO_FILE_EXTENSION}"
        else:
            filename = f"{clean_topic}{AUDIO_FILE_EXTENSION}"
        
        return os.path.join(self.recordings_dir, filename)
    
    def _clean_filename(self, filename):
        """clean filename by removing/replacing invalid characters"""
        # Remove or replace characters that aren't safe for filenames
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove extra spaces and replace with underscores
        filename = '_'.join(filename.split())
        
        # Limit length to avoid filesystem issues
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename
    
    def get_recording_path(self, filename):
        """get full path for a recording file"""
        if not filename.endswith(AUDIO_FILE_EXTENSION):
            filename += AUDIO_FILE_EXTENSION
        
        return os.path.join(self.recordings_dir, filename)
    
    def list_recordings(self):
        """list all recording files in the recordings directory"""
        if not os.path.exists(self.recordings_dir):
            return []
        
        recordings = []
        for file in os.listdir(self.recordings_dir):
            if file.endswith(AUDIO_FILE_EXTENSION):
                recordings.append(file)
        
        return sorted(recordings)  # Sort alphabetically
    
    def recording_exists(self, filename):
        """check if a recording file exists"""
        full_path = self.get_recording_path(filename)
        return os.path.exists(full_path)
    
    def delete_recording(self, filename):
        """delete a recording file"""
        full_path = self.get_recording_path(filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            return True
        return False
    
    def get_recordings_directory(self):
        """get the recordings directory path"""
        return self.recordings_dir
    
    def cleanup_empty_directory(self):
        """remove recordings directory if it's empty"""
        if os.path.exists(self.recordings_dir) and not os.listdir(self.recordings_dir):
            os.rmdir(self.recordings_dir)
            return True
        return False