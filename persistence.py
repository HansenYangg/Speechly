import json
import os
from datetime import datetime
from logger import setup_logger
from exceptions import ValidationError

logger = setup_logger(__name__)

class DataPersistence:
    """handles data persistence for user preferences and session data"""
    
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.preferences_file = os.path.join(data_dir, "user_preferences.json")
        self.session_file = os.path.join(data_dir, "session_data.json")
        self._ensure_data_directory()
    
    def _ensure_data_directory(self):
        """ccreate data directory if it doesn't exist"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"Created data directory: {self.data_dir}")
    
    def save_user_preferences(self, preferences):
        """save user preferences to file"""
        try:
            preferences['last_updated'] = datetime.now().isoformat()
            
            with open(self.preferences_file, 'w') as f:
                json.dump(preferences, f, indent=2)
            
            logger.info("User preferences saved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save preferences: {e}")
            return False
    
    def load_user_preferences(self):
        """load user preferences from file"""
        try:
            if not os.path.exists(self.preferences_file):
                return self._get_default_preferences()
            
            with open(self.preferences_file, 'r') as f:
                preferences = json.load(f)
            
            logger.info("User preferences loaded")
            return preferences
            
        except Exception as e:
            logger.error(f"Failed to load preferences: {e}")
            return self._get_default_preferences()
    
    def _get_default_preferences(self):
        """get default user preferences"""
        return {
            'language': 'en',
            'show_transcripts_by_default': True,
            'audio_quality': 'high',
            'created': datetime.now().isoformat()
        }
    
    def save_session_data(self, session_data):
        """save current session data"""
        try:
            session_data['saved_at'] = datetime.now().isoformat()
            
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            logger.info("Session data saved")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")
            return False
    
    def load_session_data(self):
        """load previous session data"""
        try:
            if not os.path.exists(self.session_file):
                return {}
            
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            logger.info("Session data loaded")
            return session_data
            
        except Exception as e:
            logger.error(f"Failed to load session data: {e}")
            return {}
    
    def save_speech_history(self, speech_record):
        """save individual speech record to history"""
        try:
            history_file = os.path.join(self.data_dir, "speech_history.json")
            
            # load existing history
            history = []
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    history = json.load(f)
            
            # add new record
            speech_record['recorded_at'] = datetime.now().isoformat()
            history.append(speech_record)
            
            # keep only last 100 records to prevent file from growing too large
            if len(history) > 100:
                history = history[-100:]
            
            # Ssave updated history
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
            
            logger.info("Speech record added to history")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save speech history: {e}")
            return False
    
    def load_speech_history(self, limit=50):
        """load speech history"""
        try:
            history_file = os.path.join(self.data_dir, "speech_history.json")
            
            if not os.path.exists(history_file):
                return []
            
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            # return most recent records first
            return history[-limit:] if limit else history
            
        except Exception as e:
            logger.error(f"Failed to load speech history: {e}")
            return []
    
    def cleanup_old_data(self, days_old=30):
        """Clean up old session data and history"""
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            # clean up old speech history
            history = self.load_speech_history()
            cleaned_history = []
            
            for record in history:
                try:
                    record_date = datetime.fromisoformat(record.get('recorded_at', ''))
                    if record_date > cutoff_date:
                        cleaned_history.append(record)
                except:
                    # keep records with invalid dates
                    cleaned_history.append(record)
            
            if len(cleaned_history) < len(history):
                history_file = os.path.join(self.data_dir, "speech_history.json")
                with open(history_file, 'w') as f:
                    json.dump(cleaned_history, f, indent=2)
                
                logger.info(f"Cleaned up {len(history) - len(cleaned_history)} old speech records")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False