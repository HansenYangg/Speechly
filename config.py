"""Configuration constants for backward compatibility with legacy modules."""
import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI API
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-api-key-here')

# Translation API (not used in refactored version)
TRANSLATION_API_URL = "https://api.mymemory.translated.net/get"

# Audio settings
SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_FORMAT = 'int16'

# File paths
RECORDINGS_DIR = 'recordings'
AUDIO_FILE_EXTENSION = '.wav'

# Recording settings
MIN_RECORDING_DURATION = 5
SHORT_RECORDING_THRESHOLD = 20

# Languages
LANGUAGES = ['en', 'es', 'fr', 'de', 'zh', 'ja', 'ko', 'ar', 'hi', 'ru', 'pt', 'it', 'nl', 'tr', 'bn']

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
