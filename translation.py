import requests

def translate_text_mymemory(text, target_language):
    url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_language}"
    response = requests.get(url)
    return response.json()['responseData']['translatedText']

print(translate_text_mymemory("apples are great", "ko"))
