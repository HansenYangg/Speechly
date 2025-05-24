class SpeechDataManager:
    """Manages speech recordings, transcriptions, and scores"""
    
    def __init__(self):
        self.previous_scores = {}  # filename/topic -> score
        self.previous_speeches = {}  # filename -> transcription
    
    def add_speech_data(self, filename, transcription, score=None):
        """Add speech data to the manager"""
        self.previous_speeches[filename] = transcription
        if score:
            self.previous_scores[filename] = score
    
    def get_previous_transcription(self, filename):
        """Get previous transcription for a filename"""
        return self.previous_speeches.get(filename)
    
    def get_previous_score(self, filename):
        """Get previous score for a filename"""
        return self.previous_scores.get(filename)
    
    def has_previous_speech(self, filename):
        """Check if we have a previous speech for this filename"""
        return filename in self.previous_speeches
    
    def list_previous_speeches(self):
        """List all previous speech filenames"""
        return list(self.previous_speeches.keys())
    
    def clear_session_data(self):
        """Clear all session data"""
        self.previous_scores.clear()
        self.previous_speeches.clear()
    
    def get_speech_count(self):
        """Get total number of speeches recorded in session"""
        return len(self.previous_speeches)