import requests
from config import TRANSLATION_API_URL

class TranslationService:
    @staticmethod
    def translate(text, target_language):
        """ranslate text to target language using MyMemory API"""
        if target_language != "en":
            try:
                url = f"{TRANSLATION_API_URL}?q={text}&langpair=en|{target_language}"
                response = requests.get(url)
                return response.json()['responseData']['translatedText']
            except Exception as e:
                print(f"Translation error: {e}")
                return text  # Return original text if translation fails
        return text