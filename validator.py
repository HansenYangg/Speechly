import re
import os
from config import LANGUAGES
from exceptions import ValidationError
from logger import setup_logger

logger = setup_logger(__name__)

class Validator:
    """input validation and sanitization utilities"""
    
    @staticmethod
    def validate_language(language_code):
        """validate language code"""
        if not language_code:
            raise ValidationError("Language code cannot be empty")
        
        if language_code not in LANGUAGES:
            raise ValidationError(f"Invalid language code: {language_code}")
        
        logger.debug(f"Language validated: {language_code}")
        return True
    
    @staticmethod
    def sanitize_topic(topic):
        """Sanitize and validate speech topic"""
        if not topic or not topic.strip():
            raise ValidationError("Topic cannot be empty")
        
        # Remove extra whitespace
        topic = topic.strip()
        
        # Check length
        if len(topic) > 200:
            raise ValidationError("Topic too long (max 200 characters)")
        
        # Remove potentially dangerous characters but keep basic punctuation
        sanitized = re.sub(r'[<>:"/\\|?*]', '', topic)
        
        if not sanitized:
            raise ValidationError("Topic contains only invalid characters")
        
        logger.debug(f"Topic sanitized: '{topic}' -> '{sanitized}'")
        return sanitized
    
    @staticmethod
    def sanitize_speech_type(speech_type):
        """Sanitize and validate speech type"""
        if not speech_type or not speech_type.strip():
            raise ValidationError("Speech type cannot be empty")
        
        # Remove extra whitespace
        speech_type = speech_type.strip()
        
        # Check length
        if len(speech_type) > 100:
            raise ValidationError("Speech type too long (max 100 characters)")
        
        # Basic sanitization
        sanitized = re.sub(r'[<>:"/\\|?*]', '', speech_type)
        
        if not sanitized:
            raise ValidationError("Speech type contains only invalid characters")
        
        logger.debug(f"Speech type sanitized: '{speech_type}' -> '{sanitized}'")
        return sanitized
    
    @staticmethod
    def validate_filename(filename):
        """Validate audio filename"""
        if not filename:
            raise ValidationError("Filename cannot be empty")
        
        # Check if it's a valid audio file
        if not filename.lower().endswith('.wav'):
            raise ValidationError("Invalid audio file format (must be .wav)")
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise ValidationError("Invalid filename (path traversal detected)")
        
        logger.debug(f"Filename validated: {filename}")
        return True
    
    @staticmethod
    def validate_file_exists(filepath):
        """Validate that file exists and is readable"""
        if not os.path.exists(filepath):
            raise ValidationError(f"File does not exist: {filepath}")
        
        if not os.path.isfile(filepath):
            raise ValidationError(f"Path is not a file: {filepath}")
        
        if not os.access(filepath, os.R_OK):
            raise ValidationError(f"File is not readable: {filepath}")
        
        logger.debug(f"File existence validated: {filepath}")
        return True
    
    @staticmethod
    def validate_duration(duration):
        """Validate recording duration"""
        if duration <= 0:
            raise ValidationError("Recording duration must be positive")
        
        if duration > 3600:  # 1 hour max
            raise ValidationError("Recording too long (max 1 hour)")
        
        logger.debug(f"Duration validated: {duration} seconds")
        return True
    

    