import os

# API Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-api-key-here')

# Audio Configuration
SAMPLE_RATE = 44100
AUDIO_FORMAT = 'int16'
AUDIO_CHANNELS = 1

# Recording Configuration
MIN_RECORDING_DURATION = 5  # seconds
SHORT_RECORDING_THRESHOLD = 20  # seconds

# Supported Languages
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

# Translation API Configuration
TRANSLATION_API_URL = "https://api.mymemory.translated.net/get"