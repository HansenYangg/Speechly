# from translation import translate
# import openai
# from main import get_lang, get_speeches


# lang = get_lang()
# prev_speeches = get_speeches()


# def get_feedback(topic, speech_type, transcription, recording_duration, dupe, prev):
   
#     if recording_duration <= 5:  
#         print(translate("Speech was too short to generate feedback for (<5 seconds). Please try again.", lang))
#         return
    
#     elif 5 < recording_duration < 20: 
#         if dupe: 
#             prompt = (
#                 f"The following speech is pretty short and may lack sufficient content. "
#                 f"Please evaluate and critique it given the following topic and type of the speech. "
#                 f"Give appropriate feedback accordingly based on these:\n\n"
#                 f"Speech topic: '{translate(topic, 'en')}'\n"
#                 f"Speech type: {translate(speech_type, 'en')}\n"
#                 f"Transcription: '{translate(transcription, 'en')}'\n\n"
#                 f"also, the user has already done a speech on this topic. here is the original transcription: {prev_speeches[prev]}. Compare the two and note improvements"
#                 "Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice.You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. Dont always have scores in incremenets of 5, use more varied/granular scores"
#                 "Try to tailor to their specific speech style. Make sure to do this in {lang}"
#             )
#         else:
#             prompt = (
#                 f"The following speech is pretty short and may lack sufficient content. "
#                 f"Please evaluate and critique it given the following topic and type of the speech. "
#                 f"Give appropriate feedback accordingly based on these..\n\n"
#                 f"Speech topic: '{translate(topic, 'en')}'\n"
#                 f"Speech type: {translate(speech_type, 'en')}\n"
#                 f"Transcription: '{translate(transcription, 'en')}'\n\n"
#                 "Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice.You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. Dont always have scores in incremenets of 5, use more varied/granular scores"
#                 "Try to tailor to their specific speech style. Make sure to do this in {lang}"
#             )

#     else:  
#         if dupe:
#             prompt = (

#                 f"First, give a grading on a strict scale of 1-100 on the speech. Dont always have scores in incremenets of 5, use use more varied/granular scores"
#                 f"You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc."
#                 f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
#                 f"Note good things they did and things they can improve on, and don't be overly nice. "
#                 f"For context, the speech was '{translate(topic, 'en')}' for a {translate(speech_type, 'en')}."
#                 f"also, the user has already done a speech on this topic. here is the original transcription: {prev_speeches[prev]}. Compare the two and note improvements"
#                 f"In {lang}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said.\n"
#                 f"The speech is:\n\n{translate(transcription, 'en')}\n\nFeedback:"
#             )
#         else:
#             prompt = (

#                 f"First, give a grading on a strict scale of 1-100 on the speech. Dont always have scores in incremenets of 5, use use more varied/granular scores"
#                 f"You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc."
#                 f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
#                 f"Note good things they did and things they can improve on, and don't be overly nice. "
#                 f"For context, the speech was '{translate(topic, 'en')}' for a {translate(speech_type, 'en')}."
#                 f"In {lang}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said.\n"
#                 f"The speech is:\n\n{translate(transcription, 'en')}\n\nFeedback:"
#             )
#     try:
#         response = openai.ChatCompletion.create(
#             model="gpt-4o-mini",  
#             messages=[{"role": "user", "content": prompt}]
#         )
#         feedback = response['choices'][0]['message']['content']
#         print(translate("Here's your feedback!: ", lang))
#         print(feedback)

#     except Exception as e:
#         print(f"Error while getting feedback: {e}")

