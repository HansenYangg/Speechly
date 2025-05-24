from persistence import DataPersistence
from logger import setup_logger

logger = setup_logger(__name__)

class SpeechDataManager:
    """manages speech recordings, transcriptions, and scores"""
    
    def __init__(self):
        self.previous_scores = {}  # filename/topic -> score
        self.previous_speeches = {}  # filename -> transcription
        self.persistence = DataPersistence()
        self._load_session_data()
    
    def _load_session_data(self):
        """load previous session data if available"""
        try:
            session_data = self.persistence.load_session_data()
            self.previous_scores = session_data.get('previous_scores', {})
            self.previous_speeches = session_data.get('previous_speeches', {})
            logger.info(f"Loaded {len(self.previous_speeches)} previous speeches from session")
        except Exception as e:
            logger.error(f"Failed to load session data: {e}")
    
    def save_session_data(self):
        """save current session data"""
        try:
            session_data = {
                'previous_scores': self.previous_scores,
                'previous_speeches': self.previous_speeches
            }
            self.persistence.save_session_data(session_data)
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")
    
    def add_speech_data(self, filename, transcription, score=None, topic=None, speech_type=None):
        """add speech data to the manager and persist it"""
        self.previous_speeches[filename] = transcription
        if score:
            self.previous_scores[filename] = score
        
        # Save to persistent history
        speech_record = {
            'filename': filename,
            'transcription': transcription,
            'score': score,
            'topic': topic,
            'speech_type': speech_type
        }
        self.persistence.save_speech_history(speech_record)
        
        # Save session data
        self.save_session_data()
        
        logger.info(f"Added speech data for {filename}")
    
    def get_previous_transcription(self, filename):
        """get previous transcription for a filename"""
        return self.previous_speeches.get(filename)
    
    def get_previous_score(self, filename):
        """get previous score for a filename"""
        return self.previous_scores.get(filename)
    
    def has_previous_speech(self, filename):
        """check if we have a previous speech for this filename"""
        return filename in self.previous_speeches
    
    def list_previous_speeches(self):
        """list all previous speech filenames"""
        return list(self.previous_speeches.keys())
    
    def clear_session_data(self):
        """clear all session data"""
        self.previous_scores.clear()
        self.previous_speeches.clear()
        self.save_session_data()
        logger.info("Session data cleared")
    
    def get_speech_count(self):
        """get total number of speeches recorded in session"""
        return len(self.previous_speeches)
    
    def get_speech_history(self, limit=20):
        """get persistent speech history"""
        return self.persistence.load_speech_history(limit)