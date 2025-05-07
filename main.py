import os
import sounddevice as sd
import wavio
import threading
import numpy as np
import speech_recognition as sr
import openai
import requests
import time
import sys

#NON-UI to-do:
#incorporate visual diagrams on volume level, WPM, etc.

#incorporate prev scores and prev speeches into feedback. find way to get score from ai feedback and append. 
#append every speech transcription to list as well for ai to note the improvements in future speeches on same topic. 

#add feature: when user enters topic, ask if theyve done it before and try to find in map if so, else just continue as usual
#need to only have files saved in current session

#probably a lot of quality of life features

#UI to-do:
#build website for this, potentally publish to app store (?)

lang = ""
prev_scores = {} #file/topic name to score (most recent score for that topic)
prev_speeches = {} #file/topic name to transcription

n = [
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

languages = {
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
    # can easily add up to 1200 total languages but only listed the most common
}

OPENAI_API_KEY='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'

k = languages.keys()

openai.api_key = "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"


def translate(text, target_language):
    if target_language != "en":
        url = f"https://api.mymemory.translated.net/get?q={text}&langpair=en|{target_language}"
        response = requests.get(url)
        return response.json()['responseData']['translatedText']
    return text


fs = 44100 # samp rate
recording = False 
recorded_data = []


def record_speech():
    global recording, recorded_data
    print(translate("Recording... you can speak into the microphone now. ", lang))
    
    with sd.InputStream(samplerate = fs, channels = 1, dtype = 'int16') as stream:
        while recording:
            chunk = stream.read(int(1 * fs)) 
            recorded_data.append(chunk[0])  


def get_feedback(topic, speech_type, transcription, recording_duration, dupe, prev):
   
    if recording_duration <= 5:  
        print(translate("Speech was too short to generate feedback for (<5 seconds). Please try again.", lang))
        return
    
    elif 5 < recording_duration < 20: 
        if dupe: 
            prompt = (
                f"The following speech is pretty short and may lack sufficient content. "
                f"Please evaluate and critique it given the following topic and type of the speech. "
                f"Give appropriate feedback accordingly based on these:\n\n"
                f"Speech topic: '{translate(topic, 'en')}'\n"
                f"Speech type: {translate(speech_type, 'en')}\n"
                f"Transcription: '{translate(transcription, 'en')}'\n\n"
                f"also, the user has already done a speech on this topic. here is the original transcription: {prev_speeches[prev]}. Compare the two and note improvements"
                "Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice.You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. Dont always have scores in incremenets of 5, use more varied/granular scores"
                "Try to tailor to their specific speech style. Make sure to do this in {lang}"
            )
        else:
            prompt = (
                f"The following speech is pretty short and may lack sufficient content. "
                f"Please evaluate and critique it given the following topic and type of the speech. "
                f"Give appropriate feedback accordingly based on these..\n\n"
                f"Speech topic: '{translate(topic, 'en')}'\n"
                f"Speech type: {translate(speech_type, 'en')}\n"
                f"Transcription: '{translate(transcription, 'en')}'\n\n"
                "Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice.You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. Dont always have scores in incremenets of 5, use more varied/granular scores"
                "Try to tailor to their specific speech style. Make sure to do this in {lang}"
            )

    else:  
        if dupe:
            prompt = (

                f"First, give a grading on a strict scale of 1-100 on the speech. Dont always have scores in incremenets of 5, use use more varied/granular scores"
                f"You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc."
                f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
                f"Note good things they did and things they can improve on, and don't be overly nice. "
                f"For context, the speech was '{translate(topic, 'en')}' for a {translate(speech_type, 'en')}."
                f"also, the user has already done a speech on this topic. here is the original transcription: {prev_speeches[prev]}. Compare the two and note improvements"
                f"In {lang}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said.\n"
                f"The speech is:\n\n{translate(transcription, 'en')}\n\nFeedback:"
            )
        else:
            prompt = (

                f"First, give a grading on a strict scale of 1-100 on the speech. Dont always have scores in incremenets of 5, use use more varied/granular scores"
                f"You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc."
                f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
                f"Note good things they did and things they can improve on, and don't be overly nice. "
                f"For context, the speech was '{translate(topic, 'en')}' for a {translate(speech_type, 'en')}."
                f"In {lang}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said.\n"
                f"The speech is:\n\n{translate(transcription, 'en')}\n\nFeedback:"
            )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  
            messages=[{"role": "user", "content": prompt}]
        )
        feedback = response['choices'][0]['message']['content']
        print(translate("Here's your feedback!: ", lang))
        print(feedback)

    except Exception as e:
        print(f"Error while getting feedback: {e}")


def stop_recording():
    global recording
    input(translate("Press Enter to stop recording at any time... ", lang))
    recording = False
    print(translate("You have stopped the recording. ", lang))


def listen_for_commands():
    global recording
    repeat = False
    prev = None
    while True:
        command = input(translate("\nEnter 'R' To Record, 'L' To List Recordings, 'P' To Play A Recording, or 'Q' To Quit: ", lang)).lower()
        if command in 'Rr':
            if not recording:
                topic = input(translate("Please enter the topic of your speech so we know what to look out for, or 'b' if you want to go back. ", lang))


                if topic in 'Bb':
                    listen_for_commands()
                    break
                
                repeated = input(translate("Have you done a speech on this topic in this session already? (Y/N) ", lang))
                if repeated in 'yY':
                    prev = input(translate("What is the name of the recording? Press 'p' to view all recordings. ", lang))
                    if prev in 'pP':
                        list_recordings()
                        prev = input(translate("These are all the recordings. Plese type the name of the one on the same topic. ", lang))
                    
                    if prev in prev_speeches:
                        repeat = True
                        
                    else:
                        print("That recording does not exist.")
                        

                speech_type = input(translate("What is this speech for (interview, school presentation, etc.)? This will be used to give you specific feedback. Press 'b' if you want to go back. ", lang))
                if speech_type in 'Bb':
                    listen_for_commands()
                    break
                

                while True:
                    var = input(translate("Press 't' to begin recording or 'b' to go back.", lang))
                    if var in 'Bb':
                        listen_for_commands()
                        break
                    elif var in 'tT':
                        break
                    else:
                        print("Please enter a valid input.")

                recording = True
                recording_thread = threading.Thread(target=record_speech)
                recording_thread.start()

               
                stop_recording()
                recording_thread.join()

             
                filename = f"{topic}.wav"
                recorded_data_combined = np.concatenate(recorded_data)  
                wavio.write(filename, recorded_data_combined, fs, sampwidth=2)
                print(translate(f"Recording saved as {filename}", lang))
                prev_speeches[filename] = transcribe_audio(filename)
                recorded_data.clear()  
                recording_duration = len(recorded_data_combined) / fs
                text = input(translate("Would you like a transcript of your speech for reference? (Y/N) ", lang))
                temp = None
                if text in 'Yy':
                    print("Here's the transcription of your speech: ")
                    temp = transcribe_audio(filename)
                else:
                    print("Okay! Proceeding to generating feedback.")
                get_feedback(topic, speech_type, temp, recording_duration, repeat, prev)
            else:
                print(translate("Already recording. Please stop the current recording before starting a new one or continue your speech. " ,lang))

        elif command in 'Ll':
            list_recordings()

        elif command in 'Pp':
            filename = input(translate("Enter the name of the recording you want to play: ", lang))
            if os.path.exists(filename):
                play_recording(filename)
            else:
                print(translate("Recording not found. ", lang))

        elif command in 'Qq':
            print(translate("Exiting the tool. ", lang))
            
            sys.exit(0)
        
        else:
            print(translate("Invalid option. Please press a valid key. ", lang))



def list_recordings():
    print(translate("Saved Recordings:", lang))
    for file in os.listdir('.'):
        if file.endswith('.wav'):
            print(file)



def play_recording(filename):
    print(translate(f"Playing {filename}...", lang))
    audio = wavio.read(filename)
    sd.play(audio.data, audio.rate)
    sd.wait()
    print(translate("Playback complete!", lang))



def transcribe_audio(filename):
    recognizer = sr.Recognizer()
    with sr.AudioFile(filename) as source:
        audio_data = recognizer.record(source)
        try:
            text = recognizer.recognize_google(audio_data)
            print(translate(f"Here is the transcription of {filename}:", lang))
            print(text)
        except sr.UnknownValueError:
            print(translate("Sorry, I could not understand the audio.", lang))
        except sr.RequestError as e:
            print(translate(f"Could not request results; {e}.", lang))

def main():
    global lang 

    while True:
        for i in n:
            print(i)
        lang = input("Please select the language you would like to present in (use the two-letter abbreviation): ")
        if lang in k:
            break
        else:
            print("Please enter a valid language.")
        
    print(translate("Welcome to the AI Speech Evaluation Tool! Hit any of the keys listed below to get started. ", lang))

    listen_for_commands()


if __name__ == "__main__":
    main()



