import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found. Please create a .env file with your API key")

# audio Configuration
SAMPLE_RATE = 44100
AUDIO_FORMAT = 'int16'
AUDIO_CHANNELS = 1

# recording Configuration
MIN_RECORDING_DURATION = 5  # seconds
SHORT_RECORDING_THRESHOLD = 20  # seconds

# supported Languages
LANGUAGE_DISPLAY = [
    "en: English",
    "ko: Korean", 
    "zh-CN: Chinese (Simplified)",
    "it: Italian",
    "ja: Japanese",
    "pt: Portuguese",
    "ru: Russian",
    "ar: Arabic",
    "hi: Hindi",
    "tr: Turkish",
    "nl: Dutch",
    "fr: French",
    "es: Spanish",
    "de: German",
    "bn: Bengali",
    "zh: Mandarin Chinese"
]

LANGUAGES = {
    "en": "English",
    "ko": "Korean",
    "zh-CN": "Chinese (Simplified)",
    "it": "Italian",
    "ja": "Japanese",
    "pt": "Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "nl": "Dutch",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "bn": "Bengali",
    "zh": "Mandarin Chinese"
}


TRANSLATION_API_URL = "https://api.mymemory.translated.net/get"

RECORDINGS_DIR = "recordings"
AUDIO_FILE_EXTENSION = ".wav"