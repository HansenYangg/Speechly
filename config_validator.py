import os
import openai
import sounddevice as sd
import requests
from config import OPENAI_API_KEY, TRANSLATION_API_URL, SAMPLE_RATE
from exceptions import ConfigurationError
from logger import setup_logger

logger = setup_logger(__name__)

class ConfigValidator:
    """Validates system configuration and dependencies"""
    
    @staticmethod
    def validate_openai_api():
        """Validate OpenAI API key and connectivity"""
        try:
            if not OPENAI_API_KEY or OPENAI_API_KEY == 'your-api-key-here':
                raise ConfigurationError("OpenAI API key not configured")
            
            # set the API key
            openai.api_key = OPENAI_API_KEY
            
            # test API with a minimal request
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            
            logger.info("OpenAI API validation successful")
            return True
            
        except openai.error.AuthenticationError:
            raise ConfigurationError("Invalid OpenAI API key")
        except openai.error.RateLimitError:
            logger.warning("OpenAI API rate limit reached, but key is valid")
            return True
        except Exception as e:
            raise ConfigurationError(f"OpenAI API validation failed: {e}")
    
    @staticmethod
    def validate_audio_system():
        """Validate audio recording capabilities"""
        try:
            # check if audio devices are available
            devices = sd.query_devices()
            
            # check for input devices
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            if not input_devices:
                raise ConfigurationError("No audio input devices found")
            
            # test if we can create an input stream
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16'):
                pass
            
            logger.info("Audio system validation successful")
            return True
            
        except Exception as e:
            raise ConfigurationError(f"Audio system validation failed: {e}")
    
    @staticmethod
    def validate_translation_api():
        """Validate translation API connectivity"""
        try:
            # test with a simple translation request
            test_url = f"{TRANSLATION_API_URL}?q=test&langpair=en|es"
            response = requests.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'responseData' in data:
                    logger.info("Translation API validation successful")
                    return True
            
            raise ConfigurationError("Translation API returned invalid response")
            
        except requests.RequestException as e:
            logger.warning(f"Translation API validation failed: {e}")
            # don't raise error for translation API as it's not critical
            return False
    
    @staticmethod
    def validate_speech_recognition():
        """Validate speech recognition capabilities"""
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            
            # test Google Speech Recognition availability
            # we can't fully test without audio, but we can check imports
            logger.info("Speech recognition validation successful")
            return True
            
        except ImportError as e:
            raise ConfigurationError(f"Speech recognition not available: {e}")
        except Exception as e:
            logger.warning(f"Speech recognition validation warning: {e}")
            return True
    
    @staticmethod
    def validate_file_system():
        """Validate file system permissions"""
        try:
            # test if we can create directories
            test_dir = "test_permissions"
            os.makedirs(test_dir, exist_ok=True)
            
            # test if we can write files
            test_file = os.path.join(test_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            
            # test if we can read files
            with open(test_file, 'r') as f:
                content = f.read()
            
            # clean up
            os.remove(test_file)
            os.rmdir(test_dir)
            
            logger.info("File system validation successful")
            return True
            
        except Exception as e:
            raise ConfigurationError(f"File system validation failed: {e}")
    
    @staticmethod
    def validate_all():
        """Run all validation checks"""
        logger.info("Starting system validation...")
        
        validations = [
            ("File System", ConfigValidator.validate_file_system),
            ("Audio System", ConfigValidator.validate_audio_system),
            ("Speech Recognition", ConfigValidator.validate_speech_recognition),
            ("OpenAI API", ConfigValidator.validate_openai_api),
            ("Translation API", ConfigValidator.validate_translation_api),
        ]
        
        results = {}
        critical_failed = False
        
        for name, validator in validations:
            try:
                results[name] = validator()
                logger.info(f"✓ {name} validation passed")
            except ConfigurationError as e:
                results[name] = False
                logger.error(f"✗ {name} validation failed: {e}")
                if name in ["File System", "Audio System", "OpenAI API"]:
                    critical_failed = True
            except Exception as e:
                results[name] = False
                logger.error(f"✗ {name} validation error: {e}")
        
        if critical_failed:
            raise ConfigurationError("Critical system validation failed")
        
        logger.info("System validation completed")
        return results