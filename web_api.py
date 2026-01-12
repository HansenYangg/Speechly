# -*- coding: utf-8 -*-
import os
import sys
import json
import tempfile
import uuid
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
import base64
import openai
from dotenv import load_dotenv
import time
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Check if production mode is forced via environment variable
FORCE_PRODUCTION = os.getenv('FORCE_PRODUCTION', '').lower() in ('true', '1', 'yes')

# Define MockLogger for production mode
class MockLogger:
    def info(self, msg): print(f"INFO: {msg}")
    def error(self, msg, **kwargs): print(f"ERROR: {msg}")

try:
    from speech_evaluator import SpeechEvaluator
    from config_validator import ConfigValidator
    from exceptions import *
    from logger import setup_logger
    from validator import Validator
    PRODUCTION_MODE = FORCE_PRODUCTION
    if FORCE_PRODUCTION:
        print("🌐 Forced production mode via FORCE_PRODUCTION env var")
    else:
        print("🏠 Development mode: All modules loaded")
except ImportError as e:
    PRODUCTION_MODE = True
    print(f"🌐 Production mode: {e}")
    
    def setup_logger(name):
        return MockLogger()
    
    class ValidationError(Exception):
        pass

load_dotenv()

user_sessions = {}
session_counters = {}

def get_session_id(request):
    return request.headers.get('Session-ID')

def ensure_session_exists(session_id):
    if session_id and session_id not in user_sessions:
        user_sessions[session_id] = []
        session_counters[session_id] = 0
        print(f"🆔 Created new session: {session_id}")

def generate_session_filename(session_id, topic):
    if not session_id:
        return None
    
    session_counters[session_id] = session_counters.get(session_id, 0) + 1
    
    import re
    clean_topic = re.sub(r'[^\w\s-]', '', topic)[:20]
    clean_topic = clean_topic.replace(' ', '_')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{clean_topic}_{timestamp}_{session_counters[session_id]}.wav"

def save_session_recording(session_id, filename, audio_data, topic, speech_type, transcription, feedback):
    if not session_id:
        return False

    ensure_session_exists(session_id)

    recording_info = {
        'filename': filename,
        'audio_data': audio_data,
        'topic': topic,
        'speech_type': speech_type,
        'transcription': transcription,
        'feedback': feedback,
        'size': len(audio_data),
        'created': time.time(),
        'modified': time.time()
    }

    user_sessions[session_id].append(recording_info)
    return True

def get_session_recordings(session_id):
    if not session_id or session_id not in user_sessions:
        return []
    
    return [{
        'filename': rec['filename'],
        'size': rec['size'],
        'created': rec['created'],
        'modified': rec['modified']
    } for rec in user_sessions[session_id]]

def get_session_recording_data(session_id, filename):
    if not session_id or session_id not in user_sessions:
        return None
    
    for rec in user_sessions[session_id]:
        if rec['filename'] == filename:
            return rec
    return None

def delete_session_recording(session_id, filename):
    if not session_id or session_id not in user_sessions:
        return False
    
    initial_count = len(user_sessions[session_id])
    user_sessions[session_id] = [rec for rec in user_sessions[session_id] if rec['filename'] != filename]
    return len(user_sessions[session_id]) < initial_count

def clear_all_session_recordings(session_id):
    if not session_id:
        return False
    
    if session_id in user_sessions:
        user_sessions[session_id] = []
        session_counters[session_id] = 0
        print(f"🗑️ Cleared all recordings for session: {session_id}")
        return True
    return False

def cleanup_session(session_id):
    if session_id in user_sessions:
        del user_sessions[session_id]
    if session_id in session_counters:
        del session_counters[session_id]
    print(f"🧹 Cleaned up session: {session_id}")

app = Flask(__name__)
CORS(app)

if PRODUCTION_MODE:
    logger = MockLogger()
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    speech_evaluator = None
else:
    logger = setup_logger(__name__)

if not PRODUCTION_MODE:
    try:
        ConfigValidator.validate_all()
        speech_evaluator = SpeechEvaluator()
        logger.info("Speech evaluator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize speech evaluator: {e}")
        speech_evaluator = None
        PRODUCTION_MODE = True
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
else:
    speech_evaluator = None
    print("🌐 Running in production mode with OpenAI API")

@app.errorhandler(Exception)
def handle_error(error):
    logger.error(f"API Error: {error}", exc_info=True)
    return jsonify({
        'success': False,
        'error': str(error),
        'type': type(error).__name__
    }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'success': True,
        'status': 'healthy',
        'version': '1.0.0',
        'mode': 'production' if PRODUCTION_MODE else 'development',
        'active_sessions': len(user_sessions)
    })

@app.route('/api/session/new', methods=['POST'])
def create_new_session():
    session_id = str(uuid.uuid4())
    ensure_session_exists(session_id)
    return jsonify({
        'success': True,
        'session_id': session_id
    })

@app.route('/api/session/cleanup', methods=['POST'])
def cleanup_user_session():
    session_id = get_session_id(request)
    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400
    
    cleanup_session(session_id)
    return jsonify({
        'success': True,
        'message': 'Session cleaned up successfully'
    })

@app.route('/api/validate-config', methods=['GET'])
def validate_configuration():
    if PRODUCTION_MODE:
        return jsonify({
            'success': True,
            'validation_results': {'production_mode': True}
        })
    
    try:
        results = ConfigValidator.validate_all()
        return jsonify({
            'success': True,
            'validation_results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'validation_results': {}
        }), 400

@app.route('/api/languages', methods=['GET'])
def get_languages():
    if PRODUCTION_MODE:
        LANGUAGES = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi', 'tr', 'nl', 'bn']
        LANGUAGE_DISPLAY = [
            "en: English",
            "es: Spanish", 
            "fr: French",
            "de: German",
            "it: Italian",
            "pt: Portuguese", 
            "ru: Russian",
            "ja: Japanese",
            "ko: Korean",
            "zh: Chinese",
            "ar: Arabic",
            "hi: Hindi",
            "tr: Turkish",
            "nl: Dutch",
            "bn: Bengali"
        ]
    else:
        from config import LANGUAGES, LANGUAGE_DISPLAY
    
    return jsonify({
        'success': True,
        'languages': LANGUAGES,
        'display_options': LANGUAGE_DISPLAY
    })

@app.route('/api/recordings', methods=['GET'])
def list_recordings():
    session_id = get_session_id(request)
    
    if PRODUCTION_MODE:
        recordings = get_session_recordings(session_id)
        return jsonify({
            'success': True,
            'recordings': recordings
        })
    
    try:
        recordings = speech_evaluator.audio_player.file_manager.list_recordings()
        recording_info = []
        
        for filename in recordings:
            full_path = speech_evaluator.audio_player.file_manager.get_recording_path(filename)
            if os.path.exists(full_path):
                stat = os.stat(full_path)
                recording_info.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'created': stat.st_ctime,
                    'modified': stat.st_mtime
                })
        
        return jsonify({
            'success': True,
            'recordings': recording_info
        })
    except Exception as e:
        logger.error(f"Error listing recordings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/recordings/<filename>', methods=['GET'])
def get_recording(filename):
    session_id = get_session_id(request)
    
    if PRODUCTION_MODE:
        recording = get_session_recording_data(session_id, filename)
        if not recording:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
        from flask import Response
        response = Response(
            recording['audio_data'],
            mimetype='audio/wav',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
        return response
    
    try:
        Validator.validate_filename(filename)
        full_path = speech_evaluator.audio_player.file_manager.get_recording_path(filename)
        
        if not os.path.exists(full_path):
            return jsonify({
                'success': False,
                'error': 'Recording not found'
            }), 404
        
        return send_file(full_path, as_attachment=True)
    except Exception as e:
        logger.error(f"Error getting recording {filename}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@app.route('/api/recordings/<filename>', methods=['DELETE'])
def delete_recording(filename):
    session_id = get_session_id(request)
    
    if PRODUCTION_MODE:
        success = delete_session_recording(session_id, filename)
        if success:
            return jsonify({
                'success': True,
                'message': f'Recording {filename} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Recording not found'
            }), 404
    
    try:
        Validator.validate_filename(filename)
        success = speech_evaluator.audio_player.file_manager.delete_recording(filename)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Recording {filename} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Recording not found'
            }), 404
    except Exception as e:
        logger.error(f"Error deleting recording {filename}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/recordings', methods=['DELETE'])
def clear_all_recordings():
    session_id = get_session_id(request)
    
    try:
        if PRODUCTION_MODE:
            success = clear_all_session_recordings(session_id)
            if success:
                return jsonify({
                    'success': True,
                    'message': 'All session recordings cleared'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Session not found'
                }), 404
        else:
            count = 0
            recordings = speech_evaluator.audio_player.file_manager.list_recordings()
            for filename in recordings:
                if speech_evaluator.audio_player.file_manager.delete_recording(filename):
                    count += 1
            
            return jsonify({
                'success': True,
                'message': f'Cleared {count} recordings'
            })
    except Exception as e:
        logger.error(f"Error clearing recordings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/record', methods=['POST'])
def process_recording():
    session_id = get_session_id(request)

    if not session_id:
        return jsonify({
            'success': False,
            'error': 'No session ID provided'
        }), 400
    
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        topic = data.get('topic', '').strip()
        speech_type = data.get('speech_type', '').strip()
        language = data.get('language', 'en')
        audio_data = data.get('audio_data')
        is_repeat = data.get('is_repeat', False)
        previous_filename = data.get('previous_filename')
        
        if not topic or not speech_type or not audio_data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: topic, speech_type, or audio_data'
            }), 400
        
        if PRODUCTION_MODE:
            import re
            topic = re.sub(r'[^\w\s-]', '', topic)[:100]
            speech_type = re.sub(r'[^\w\s-]', '', speech_type)[:50]
            
            valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi', 'tr', 'nl', 'bn']
            if language not in valid_languages:
                language = 'en'
        else:
            topic = Validator.sanitize_topic(topic)
            speech_type = Validator.sanitize_speech_type(speech_type)
            Validator.validate_language(language)
        
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Invalid audio data: {e}'
            }), 400
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        try:
            if PRODUCTION_MODE:
                print(f"🌐 Processing with OpenAI - Session: {session_id}, Topic: {topic}, Language: {language}")
                
                with open(temp_path, 'rb') as audio_file:
                    transcription = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language if language != 'zh' else 'zh-CN'
                    )
                
                transcription_text = transcription.text
                
                if not transcription_text or len(transcription_text.strip()) < 3:
                    return jsonify({
                        'success': False,
                        'error': 'Could not transcribe audio'
                    }), 400
                
                duration = len(audio_bytes) / (44100 * 2)
                
                MIN_RECORDING_DURATION = 5
                SHORT_RECORDING_THRESHOLD = 30
                
                if duration <= MIN_RECORDING_DURATION:
                    return jsonify({
                        'success': False,
                        'error': 'Speech was too short to generate feedback for (<5 seconds). Please try again.'
                    }), 400
                
                # Create the streaming response first
                filename = generate_session_filename(session_id, topic)
                if not filename:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to generate filename'
                    }), 500
                
                # Save basic recording info (we'll update with feedback later)
                save_session_recording(
                    session_id=session_id,
                    filename=filename,
                    audio_data=audio_bytes,
                    topic=topic,
                    speech_type=speech_type,
                    transcription=transcription_text,
                    feedback=""  # Will be updated later
                )

                # Return initial success response with transcription
                return jsonify({
                    'success': True,
                    'result': {
                        'filename': filename,
                        'transcription': transcription_text,
                        'topic': topic,
                        'speech_type': speech_type,
                        'duration': round(duration, 1),
                        'score_type': 'short' if duration < SHORT_RECORDING_THRESHOLD else 'full',
                        'stream_url': f'/api/stream-feedback/{session_id}/{filename}'
                    }
                })
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stream-feedback/<session_id>/<filename>')
def stream_feedback(session_id, filename):
    """Stream feedback generation in real-time"""
    
    # Get the language parameter BEFORE entering the generator function
    language = request.args.get('language', 'en')
    
    def generate_feedback():
        try:
            # Get the recording data
            recording = get_session_recording_data(session_id, filename)
            if not recording:
                yield f"data: {json.dumps({'error': 'Recording not found'})}\n\n"
                return
            
            topic = recording['topic']
            speech_type = recording['speech_type']
            transcription_text = recording['transcription']
            
            # Calculate duration
            duration = len(recording['audio_data']) / (44100 * 2)
            
            def build_feedback_prompt(topic, speech_type, transcription_text, duration, language, is_repeat, previous_transcription=None):
                grading_instruction = (
                    "First, give a grading on a strict scale of 1-100 on the speech. "
                    "Don't always have scores in increments of 5, use more varied/granular scores. "
                    "You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc.\n "
                    "Please put adequate spacing. There MUST be a clear separating line between each major point for clarity.\n"
                )
                
                feedback_instruction = (
                    "Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
                    "Note good things they did and things they can improve on, and don't be overly nice. "
                )
                
                repeat_context = ""
                
                # Language mapping for feedback instructions
                language_names = {
                    'en': 'English',
                    'es': 'Spanish',
                    'fr': 'French', 
                    'de': 'German',
                    'it': 'Italian',
                    'pt': 'Portuguese',
                    'ru': 'Russian',
                    'ja': 'Japanese',
                    'ko': 'Korean',
                    'zh': 'Chinese',
                    'ar': 'Arabic',
                    'hi': 'Hindi',
                    'tr': 'Turkish',
                    'nl': 'Dutch',
                    'bn': 'Bengali'
                }
                
                language_name = language_names.get(language, 'English')
                language_instruction = f"Try to tailor the feedback based off the context of the user presentation. Make sure to provide ALL feedback in {language_name}."
                
                MIN_RECORDING_DURATION = 5
                SHORT_RECORDING_THRESHOLD = 20
                
                if MIN_RECORDING_DURATION < duration < SHORT_RECORDING_THRESHOLD:
                    prompt = (
                        f"You're reviewing a {speech_type} speech about '{topic}'. Here's what they said:\n\n"
                        f"{transcription_text}\n\n"
                        f"{repeat_context}\n"
                        f"It's a quick one - about {int(duration)} seconds. Give them feedback like you're a experienced coach who's heard thousands of speeches.\n\n"
                        f"Format your response like this:\n\n"
                        f"**OVERALL: [X]/100**\n\n"
                        f"**📊 BREAKDOWN**\n"
                        f"Opening & Hook: [X]/20 - [quick comment]\n"
                        f"Content & Clarity: [X]/20 - [quick comment]\n"
                        f"Vocal Delivery: [X]/20 - [quick comment]\n"
                        f"Structure & Flow: [X]/20 - [quick comment]\n"
                        f"Closing Impact: [X]/20 - [quick comment]\n\n"
                        f"**💪 What worked:**\n"
                        f"[2-3 things, quote what they actually said when relevant]\n\n"
                        f"**🎯 Room to grow:**\n"
                        f"[2-3 things that need work, be specific about when/where it happened]\n\n"
                        f"**🔧 Here's how to fix it:**\n"
                        f"[Give them actual techniques they can try. Not \"be more confident\" but \"Try this: record yourself saying your opening line 5 times, each time a bit slower and louder than the last. Pick the one that feels most natural.\"]\n\n"
                        f"**🚀 Try this next time:**\n"
                        f"[One specific challenge for their next recording]\n\n"
                        f"Keep it real - use precise scores (like 16.5/20, not just round numbers). Write like a human coach, not a textbook. Quote their actual words when you can. Make every suggestion something they can actually do, not vague advice.\n"
                        f"{language_instruction}"
                    )
                else:
                    prompt = (
                        f"You're a speech coach reviewing a {speech_type} about '{topic}'. Duration: about {int(duration)} seconds.\n\n"
                        f"Here's what they said:\n{transcription_text}\n\n"
                        f"{repeat_context}\n"
                        f"Give them detailed feedback like you're sitting across from them after they just finished. Be real with them - they want to improve, not just hear they did great.\n\n"
                        f"**{topic.upper()}** - {speech_type.title()}\n"
                        f"*First impression:* [What's your gut reaction? 1-2 sentences]\n\n"
                        f"**OVERALL: [X]/100**\n\n"
                        f"**📊 THE BREAKDOWN**\n\n"
                        f"**Opening & Hook: [X]/20**\n"
                        f"[How'd they start? Did it hook you? Quote their first few lines and talk about whether it worked.]\n\n"
                        f"**Content & Clarity: [X]/20**\n"
                        f"[Did their points land? Were they clear? Give examples of where they nailed it or got muddy.]\n\n"
                        f"**Vocal Delivery: [X]/20**\n"
                        f"[Talk about their voice - pace, energy, tone. Call out specific moments. If they said \"um\" every other word or rushed through the middle, say when.]\n\n"
                        f"**Structure & Flow: [X]/20**\n"
                        f"[Did it flow naturally or feel choppy? How were the transitions? Walk through their structure.]\n\n"
                        f"**Closing: [X]/20**\n"
                        f"[How'd they wrap it up? Did it stick with you? Quote their ending.]\n\n"
                        f"**💪 What killed:**\n"
                        f"[3-4 things they genuinely did well. Quote them. Be specific - not \"good energy\" but \"when you said '[exact quote]', that landed really well because...\"\n\n"
                        f"**🎯 What needs work:**\n\n"
                        f"1. [First thing] - [Why it matters and where you noticed it]\n"
                        f"2. [Second thing] - [Be specific with examples]\n"
                        f"3. [Third thing] - [Don't hold back if it's important]\n\n"
                        f"**🔧 Here's how to actually fix it:**\n\n"
                        f"For each issue above, give them something they can practice TODAY:\n\n"
                        f"**[Name the technique]**\n"
                        f"[Real talk on how to do it. Example: \"Your pacing was all over the place. Here's what to do: Set a metronome to 140 BPM. Read your script out loud matching that rhythm for 5 minutes. It'll feel weird at first, but you'll find your sweet spot between too fast and putting people to sleep.\"]\n\n"
                        f"**[Another technique]**\n"
                        f"[Another concrete fix they can practice]\n\n"
                        f"**[Third technique]**\n"
                        f"[One more actionable thing]\n\n"
                        f"**📈 The numbers:**\n"
                        f"• Pace: roughly [X] words/min - [too fast/just right/kinda slow]\n"
                        f"• Filler words: [how many and which ones - be honest]\n"
                        f"• Sentence structure: [varied or monotonous?]\n"
                        f"• Energy: [did it stay flat, build up, or drop off?]\n\n"
                        f"**🚀 Next time you practice:**\n"
                        f"[One specific thing to try. Make it measurable. Like: \"Record this again but start with a personal story, pause 3 full seconds before your main point, and cut 'um/uh' in half. Shoot for under {int(duration*0.9)} seconds.\"]\n\n"
                        f"**💡 Level-up move:**\n"
                        f"[One advanced tip specific to this type of speech that could really elevate it]\n\n"
                        f"Remember: Use real scores (like 17/20, 16.5/20), quote their actual words, and make every tip something they can literally do in their next practice session. Write like you're texting them feedback, not writing a formal evaluation.\n"
                        f"{language_instruction}"
                    )
                
                return prompt
            
            feedback_prompt = build_feedback_prompt(
                topic, speech_type, transcription_text, duration, language, False
            )
            
            # Stream the response from OpenAI
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": feedback_prompt}
                ],
                max_tokens=2500,
                temperature=0.7,
                stream=True
            )

            full_feedback = ""
            chunk_count = 0
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_feedback += content
                    chunk_count += 1
                    yield f"data: {json.dumps({'content': content, 'type': 'chunk'})}\n\n"

            # Send completion signal
            print(f"✓ Stream completed - sent {chunk_count} chunks, {len(full_feedback)} chars")
            yield f"data: {json.dumps({'type': 'complete', 'total_chunks': chunk_count})}\n\n"

            # Update the recording with the complete feedback
            for rec in user_sessions.get(session_id, []):
                if rec['filename'] == filename:
                    rec['feedback'] = full_feedback
                    break
                    
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(generate_feedback(), mimetype='text/event-stream')

@app.route('/api/transcribe', methods=['POST'])
def transcribe_recording():
    if PRODUCTION_MODE:
        return jsonify({
            'success': False,
            'error': 'Transcription of existing recordings not available in production'
        }), 400
    
    try:
        data = request.get_json()
        filename = data.get('filename')
        language = data.get('language', 'en')
        
        if not filename:
            return jsonify({
                'success': False,
                'error': 'Filename is required'
            }), 400
        
        Validator.validate_filename(filename)
        Validator.validate_language(language)
        
        transcription = speech_evaluator.transcription_service.transcribe_audio(
            filename, language, show_output=False
        )
        
        if transcription:
            return jsonify({
                'success': True,
                'transcription': transcription
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not transcribe audio'
            }), 400
            
    except Exception as e:
        logger.error(f"Error transcribing recording: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/feedback', methods=['POST'])
def generate_feedback():
    try:
        data = request.get_json()
        
        topic = data.get('topic', '').strip()
        speech_type = data.get('speech_type', '').strip()
        transcription = data.get('transcription', '').strip()
        duration = data.get('duration', 0)
        language = data.get('language', 'en')
        is_repeat = data.get('is_repeat', False)
        previous_transcription = data.get('previous_transcription')
        
        if not all([topic, speech_type, transcription]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: topic, speech_type, or transcription'
            }), 400
        
        if PRODUCTION_MODE:
            feedback_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user", 
                    "content": f"Provide speech feedback for topic '{topic}' of type '{speech_type}'. Transcription: {transcription}"
                }],
                max_tokens=1500
            )
            feedback = feedback_response.choices[0].message.content
        else:
            clean_topic = Validator.sanitize_topic(topic)
            clean_speech_type = Validator.sanitize_speech_type(speech_type)
            Validator.validate_language(language)
            Validator.validate_duration(duration)
            
            feedback = speech_evaluator.feedback_service.generate_feedback(
                clean_topic, clean_speech_type, transcription, duration,
                language, is_repeat, previous_transcription
            )
        
        if feedback:
            return jsonify({
                'success': True,
                'feedback': feedback
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not generate feedback'
            }), 400
            
    except Exception as e:
        logger.error(f"Error generating feedback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/session', methods=['GET'])
def get_session_data():
    session_id = get_session_id(request)
    
    if PRODUCTION_MODE:
        return jsonify({
            'success': True,
            'session_data': {
                'session_id': session_id,
                'speech_count': len(get_session_recordings(session_id)),
                'previous_speeches': [],
                'speech_history': []
            }
        })
    
    try:
        session_data = {
            'speech_count': speech_evaluator.data_manager.get_speech_count(),
            'previous_speeches': speech_evaluator.data_manager.list_previous_speeches(),
            'speech_history': speech_evaluator.data_manager.get_speech_history(10)
        }
        
        return jsonify({
            'success': True,
            'session_data': session_data
        })
    except Exception as e:
        logger.error(f"Error getting session data: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/')
def serve_frontend():
    global PRODUCTION_MODE
    if PRODUCTION_MODE:
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus AI Speech Evaluator</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            /* Enhanced Dark Purple Futuristic Theme */
            --primary-bg: #0a0a0f;
            --secondary-bg: #161625;
            --tertiary-bg: #1e1e35;
            --card-bg: rgba(25, 25, 50, 0.95);
            --glass-bg: rgba(60, 45, 120, 0.15);
            --glass-border: rgba(150, 100, 255, 0.25);
            
            /* Neon Purple Gradients */
            --primary-gradient: linear-gradient(135deg, #6A1B9A 0%, #4A148C 30%, #1A0933 100%);
            --secondary-gradient: linear-gradient(135deg, #9C27B0 0%, #7B1FA2 50%, #4A148C 100%);
            --accent-gradient: linear-gradient(135deg, #E1BEE7 0%, #BA68C8 50%, #8E24AA 100%);
            --neon-gradient: linear-gradient(135deg, #00E5FF 0%, #3D5AFE 50%, #7C4DFF 100%);
            --success-gradient: linear-gradient(135deg, #00E676 0%, #00C853 100%);
            --warning-gradient: linear-gradient(135deg, #FFD54F 0%, #FF8F00 100%);
            --danger-gradient: linear-gradient(135deg, #FF5722 0%, #D32F2F 100%);
            
            /* Neon Colors */
            --neon-purple: #9D4EDD;
            --neon-cyan: #00F5FF;
            --neon-pink: #FF10F0;
            --neon-blue: #3D5AFE;
            --electric-purple: #7209B7;
            
            /* Text Colors */
            --text-primary: #E8E3F3;
            --text-secondary: #B19CD9;
            --text-accent: #DDA0DD;
            --text-muted: rgba(184, 156, 217, 0.7);
            
            /* Enhanced Shadows */
            --shadow-neon: 0 0 30px rgba(157, 78, 221, 0.5);
            --shadow-glow: 0 0 60px rgba(157, 78, 221, 0.3);
            --shadow-deep: 0 25px 50px rgba(0, 0, 0, 0.6);
            --shadow-card: 0 15px 35px rgba(0, 0, 0, 0.4), 0 0 20px rgba(157, 78, 221, 0.1);
            
            /* Animation Variables */
            --transition-smooth: all 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            --transition-bounce: all 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        /* Performance optimizations */
        *,
        *::before,
        *::after {
            backface-visibility: hidden;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }

        body {
            font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
            background: var(--primary-bg);
            min-height: 100vh;
            color: var(--text-primary);
            overflow-x: hidden;
            position: relative;
        }

        /* Optimized Background Effects */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background:
                radial-gradient(circle at 20% 20%, rgba(157, 78, 221, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(61, 90, 254, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 40% 60%, rgba(124, 77, 255, 0.08) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        /* Static Grid Pattern - Animation removed for performance */
        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-image:
                linear-gradient(rgba(157, 78, 221, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(157, 78, 221, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            pointer-events: none;
            z-index: -1;
        }

        /* Enhanced Floating Shapes */
        .floating-shapes {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
            overflow: hidden;
        }

        .shape {
            position: absolute;
            background: linear-gradient(135deg, rgba(157, 78, 221, 0.1), rgba(61, 90, 254, 0.05));
            border: 1px solid rgba(157, 78, 221, 0.2);
            border-radius: 50%;
            animation: floatOptimized 25s infinite ease-in-out;
            will-change: transform;
        }

        .shape:nth-child(1) {
            width: 120px; height: 120px;
            top: 15%; left: 8%;
            animation-delay: 0s;
            box-shadow: 0 0 15px rgba(157, 78, 221, 0.15);
        }
        .shape:nth-child(2) {
            width: 80px; height: 80px;
            top: 70%; left: 85%;
            animation-delay: -8s;
            background: linear-gradient(135deg, rgba(61, 90, 254, 0.1), rgba(124, 77, 255, 0.05));
        }
        .shape:nth-child(3) {
            width: 150px; height: 150px;
            top: 25%; left: 75%;
            animation-delay: -15s;
            box-shadow: 0 0 15px rgba(61, 90, 254, 0.12);
        }
        .shape:nth-child(4) {
            width: 100px; height: 100px;
            top: 85%; left: 15%;
            animation-delay: -22s;
        }
        .shape:nth-child(5) {
            width: 60px; height: 60px;
            top: 50%; left: 90%;
            animation-delay: -12s;
            background: linear-gradient(135deg, rgba(0, 245, 255, 0.1), rgba(157, 78, 221, 0.05));
        }

        /* Optimized float animation - using only transform for GPU acceleration */
        @keyframes floatOptimized {
            0%, 100% {
                transform: translate3d(0, 0, 0);
            }
            50% {
                transform: translate3d(15px, -25px, 0);
            }
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
            position: relative;
            z-index: 2;
        }

        /* Futuristic Header */
        .header {
            text-align: center;
            margin-bottom: 50px;
            animation: slideInDown 1s ease-out;
            position: relative;
        }

        .header::before {
            content: '';
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            width: 200px;
            height: 2px;
            background: var(--neon-gradient);
            border-radius: 2px;
            box-shadow: 0 0 15px rgba(157, 78, 221, 0.6);
        }

        .header-icon {
            font-size: 5rem;
            background: var(--neon-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 25px;
            animation: pulse 3s infinite, iconGlow 2s ease-in-out infinite alternate;
            display: inline-block;
            position: relative;
        }

        .header-icon::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 120px;
            height: 120px;
            background: radial-gradient(circle, rgba(157, 78, 221, 0.2) 0%, transparent 70%);
            border-radius: 50%;
            z-index: -1;
            animation: iconPulse 3s ease-in-out infinite;
        }

        /* iconGlow removed - filter animations are expensive */

        @keyframes iconPulse {
            0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 0.3; }
            50% { transform: translate(-50%, -50%) scale(1.15); opacity: 0.6; }
        }

        .header h1 {
            font-size: 4rem;
            font-weight: 800;
            background: var(--accent-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            letter-spacing: -0.02em;
            text-shadow: 0 0 30px rgba(157, 78, 221, 0.3);
            position: relative;
        }

        .header h1::after {
            content: 'NEXUS';
            position: absolute;
            top: -15px;
            right: 0;
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--neon-cyan);
            letter-spacing: 0.2em;
            opacity: 0.8;
            animation: textGlow 2s ease-in-out infinite alternate;
        }

        @keyframes textGlow {
            0% { opacity: 0.7; }
            100% { opacity: 1; }
        }

        .header p {
            font-size: 1.4rem;
            color: var(--text-secondary);
            font-weight: 400;
            max-width: 700px;
            margin: 0 auto;
            line-height: 1.6;
            opacity: 0.9;
        }

        /* Enhanced Session Info */
        .session-info {
            text-align: center;
            margin-bottom: 30px;
            padding: 15px 25px;
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.8), rgba(60, 45, 120, 0.3));
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            color: var(--text-accent);
            font-size: 0.95rem;
            font-weight: 500;
            /* backdrop-filter removed for performance */
            box-shadow: var(--shadow-card);
            position: relative;
            overflow: hidden;
        }

        .session-info::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(157, 78, 221, 0.1), transparent);
            animation: shimmer 3s ease-in-out infinite;
        }

        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        /* Futuristic Glass Cards */
        .glass-card {
            background: var(--card-bg);
            /* backdrop-filter removed for performance */
            border: 1px solid var(--glass-border);
            border-radius: 25px;
            padding: 45px;
            margin-bottom: 40px;
            box-shadow: var(--shadow-card);
            animation: slideInUp 0.3s ease-out;
            position: relative;
            overflow: hidden;
        }

        .glass-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: var(--neon-gradient);
            opacity: 0.6;
        }

        .glass-card::after {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: 
                radial-gradient(circle at 30% 30%, rgba(157, 78, 221, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 70% 70%, rgba(61, 90, 254, 0.03) 0%, transparent 50%);
            pointer-events: none;
            animation: cardGlow 8s ease-in-out infinite;
        }

        @keyframes cardGlow {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.5; }
        }

        /* Enhanced Section Titles */
        .section-title {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-bottom: 35px;
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text-primary);
            min-height: 50px;
            position: relative;
            z-index: 2;
        }

        .section-icon {
            width: 50px;
            height: 50px;
            background: var(--neon-gradient);
            border-radius: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.4rem;
            box-shadow: var(--shadow-neon);
            position: relative;
            animation: iconFloat 4s ease-in-out infinite;
        }

        .section-icon::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: var(--neon-gradient);
            border-radius: 17px;
            z-index: -1;
            opacity: 0.5;
            animation: iconPulse 2s ease-in-out infinite;
        }

        @keyframes iconFloat {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-5px); }
        }

        /* Futuristic Language Selector */
        .language-selector {
            margin-bottom: 45px;
        }

        .language-selector label {
            display: block;
            margin-bottom: 18px;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .custom-select {
            position: relative;
            margin-top: 12px;
        }

        .custom-select select {
            width: 100%;
            padding: 22px 70px 22px 30px;
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.4));
            border: 2px solid var(--glass-border);
            border-radius: 20px;
            font-size: 16px;
            color: #4a5568;
            cursor: pointer;
            transition: var(--transition-smooth);
            appearance: none;
            /* backdrop-filter removed for performance */
            box-shadow: 
                0 10px 30px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                0 0 20px rgba(157, 78, 221, 0.1);
            font-weight: 500;
            outline: none;
            position: relative;
        }

        .custom-select select:hover {
            transform: translateY(-2px);
            background: linear-gradient(135deg, rgba(25, 25, 50, 1), rgba(60, 45, 120, 0.6));
            border-color: var(--neon-purple);
            box-shadow: 
                0 15px 40px rgba(0, 0, 0, 0.4),
                inset 0 1px 0 rgba(255, 255, 255, 0.2),
                0 0 30px rgba(157, 78, 221, 0.3);
        }

        .custom-select select:focus {
            transform: translateY(-1px);
            border-color: var(--neon-cyan);
            box-shadow: 
                0 0 0 4px rgba(0, 245, 255, 0.2),
                0 15px 40px rgba(0, 0, 0, 0.4),
                0 0 40px rgba(0, 245, 255, 0.3);
        }

        .custom-select::after {
            content: '\\f0d7';
            font-family: 'Font Awesome 6 Free';
            font-weight: 900;
            position: absolute;
            right: 25px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--neon-purple);
            pointer-events: none;
            font-size: 18px;
            transition: var(--transition-smooth);
        }

        .custom-select:hover::after {
            color: var(--neon-cyan);
            transform: translateY(-50%) scale(1.2);
        }

        /* Enhanced Control Grid */
        .controls-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 45px;
        }

        /* Futuristic Buttons */
        .btn {
            padding: 22px 35px;
            border: none;
            border-radius: 20px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: var(--transition-bounce);
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            min-height: 70px;
            min-width: 220px;
            white-space: nowrap;
            /* backdrop-filter removed for performance */
            border: 2px solid transparent;
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.6s;
        }

        .btn:hover::before {
            left: 100%;
        }

        .btn::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: radial-gradient(circle, rgba(255,255,255,0.3) 0%, transparent 70%);
            transform: translate(-50%, -50%);
            transition: all 0.6s;
            border-radius: 50%;
        }

        .btn:hover::after {
            width: 300px;
            height: 300px;
        }

        .btn:hover {
            transform: translateY(-8px) scale(1.03);
            box-shadow: 
                0 25px 50px rgba(0,0,0,0.4),
                0 0 30px var(--neon-purple);
        }

        .btn:active {
            transform: translateY(-4px) scale(0.98);
        }

        .btn-record {
            background: var(--danger-gradient);
            color: white;
            box-shadow: 0 8px 16px rgba(255, 87, 34, 0.3);
        }

        .btn-record.recording {
            animation: recordingPulse 1.5s infinite;
            background: linear-gradient(135deg, #FF1744 0%, #D32F2F 100%);
            box-shadow: 0 0 15px rgba(255, 23, 68, 0.6);
        }

        .btn-list {
            background: var(--secondary-gradient);
            color: white;
            box-shadow: 0 8px 16px rgba(156, 39, 176, 0.3);
        }

        .btn-play {
            background: var(--success-gradient);
            color: white;
            box-shadow: 0 8px 16px rgba(0, 230, 118, 0.3);
        }

        .btn-stop {
            background: var(--warning-gradient);
            color: white;
            box-shadow: 0 8px 16px rgba(255, 143, 0, 0.3);
        }

        .btn-secondary {
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.8), rgba(60, 45, 120, 0.5));
            color: var(--text-primary);
            border-color: var(--glass-border);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        }

        @keyframes recordingPulse {
            0%, 100% {
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(255, 23, 68, 0.7), 0 8px 16px rgba(255, 87, 34, 0.3);
            }
            50% {
                transform: scale(1.03);
                box-shadow: 0 0 0 15px rgba(255, 23, 68, 0), 0 8px 16px rgba(255, 87, 34, 0.5);
            }
        }

        /* Enhanced Recording Setup */
        .recording-setup {
            display: none;
            margin-bottom: 45px;
        }

        .recording-setup.active {
            display: block;
            animation: slideInUp 0.25s ease-out;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            margin-bottom: 35px;
        }

        .input-group {
            position: relative;
        }

        .input-group label {
            display: block;
            margin-bottom: 12px;
            font-weight: 600;
            color: var(--text-primary);
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            min-height: 20px;
        }

        .input-group input {
            width: 100%;
            padding: 20px 28px;
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.3));
            border: 2px solid var(--glass-border);
            border-radius: 18px;
            font-size: 16px;
            color: var(--text-primary);
            transition: var(--transition-smooth);
            /* backdrop-filter removed for performance */
            box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.3);
        }

        .input-group input:focus {
            outline: none;
            border-color: var(--neon-cyan);
            background: linear-gradient(135deg, rgba(25, 25, 50, 1), rgba(60, 45, 120, 0.5));
            box-shadow: 
                inset 0 2px 10px rgba(0, 0, 0, 0.3),
                0 0 0 4px rgba(0, 245, 255, 0.2),
                0 0 20px rgba(0, 245, 255, 0.3);
        }

        .input-group input::placeholder {
            color: var(--text-muted);
            font-style: italic;
        }

        .checkbox-wrapper {
            display: flex;
            align-items: center;
            gap: 18px;
            padding: 25px;
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.6), rgba(60, 45, 120, 0.2));
            border: 1px solid var(--glass-border);
            border-radius: 18px;
            margin-top: 25px;
            /* backdrop-filter removed for performance */
        }

        .checkbox-wrapper input[type="checkbox"] {
            width: 24px;
            height: 24px;
            accent-color: var(--neon-purple);
            border-radius: 4px;
        }

        /* Enhanced Recording Status */
        .recording-status {
            text-align: center;
            margin: 45px 0;
            display: none;
        }

        .recording-status.active {
            display: block;
            animation: slideInUp 0.25s ease-out;
        }

        .recording-indicator {
            width: 100px;
            height: 100px;
            background: var(--danger-gradient);
            border-radius: 50%;
            margin: 0 auto 25px;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: recordingPulse 1s infinite;
            box-shadow: var(--shadow-glow);
            position: relative;
        }

        .recording-indicator::before {
            content: '';
            position: absolute;
            top: -10px;
            left: -10px;
            right: -10px;
            bottom: -10px;
            border: 2px solid var(--neon-pink);
            border-radius: 50%;
            opacity: 0.5;
            animation: indicatorRing 2s ease-in-out infinite;
        }

        @keyframes indicatorRing {
            0% { transform: scale(1); opacity: 0.5; }
            100% { transform: scale(1.2); opacity: 0; }
        }

        .recording-indicator i {
            font-size: 2.5rem;
            color: white;
        }

        .status-text {
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 15px;
            text-shadow: 0 0 20px rgba(157, 78, 221, 0.5);
        }

        .status-subtext {
            font-size: 1.2rem;
            color: var(--text-secondary);
            margin-bottom: 35px;
            line-height: 1.5;
        }

        /* Enhanced Recordings List */
        .recordings-list {
            display: none;
            margin-top: 35px;
        }

        .recordings-list.active {
            display: block;
            animation: slideInUp 0.25s ease-out;
        }

        .recordings-grid {
            display: grid;
            gap: 25px;
            margin-top: 25px;
        }

        .recording-item {
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.4));
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: var(--transition-smooth);
            /* backdrop-filter removed for performance */
            position: relative;
            overflow: hidden;
        }

        .recording-item::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--neon-gradient);
            opacity: 0;
            transition: opacity 0.3s;
        }

        .recording-item:hover {
            background: linear-gradient(135deg, rgba(25, 25, 50, 1), rgba(60, 45, 120, 0.6));
            transform: translateY(-5px);
            box-shadow: var(--shadow-card);
            border-color: var(--neon-purple);
        }

        .recording-item:hover::before {
            opacity: 1;
        }

        .recording-info h4 {
            color: var(--text-primary);
            font-size: 1.3rem;
            margin-bottom: 10px;
            font-weight: 600;
        }

        .recording-meta {
            color: var(--text-muted);
            font-size: 0.95rem;
            font-family: 'JetBrains Mono', monospace;
        }

        .recording-actions {
            display: flex;
            gap: 15px;
        }

        .btn-small {
            padding: 15px 25px;
            font-size: 14px;
            border-radius: 12px;
            min-width: 120px;
            min-height: 50px;
        }

        /* ENHANCED FEEDBACK SECTION */
        .feedback-section {
            display: none;
            margin-top: 45px;
        }

        .feedback-section.active {
            display: block;
            animation: slideInUp 0.25s ease-out;
        }

        .feedback-content {
            background: linear-gradient(135deg,
                rgba(74, 20, 140, 0.95) 0%,
                rgba(123, 31, 162, 0.9) 30%,
                rgba(147, 112, 219, 0.85) 70%,
                rgba(138, 43, 226, 0.9) 100%);
            border: 2px solid rgba(157, 78, 221, 0.4);
            border-radius: 25px;
            padding: 40px;
            margin-top: 30px;
            color: white;
            line-height: 1.8;
            font-size: 16px;
            position: relative;
            overflow: hidden;
            box-shadow:
                0 30px 60px rgba(74, 20, 140, 0.5),
                inset 0 2px 0 rgba(255, 255, 255, 0.3);
        }

        .feedback-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background:
                radial-gradient(circle at 25% 25%, rgba(0, 245, 255, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 75% 75%, rgba(255, 16, 240, 0.06) 0%, transparent 40%),
                radial-gradient(circle at 50% 50%, rgba(157, 78, 221, 0.08) 0%, transparent 50%);
            pointer-events: none;
        }

        .feedback-content::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background:
                linear-gradient(45deg, transparent 30%, rgba(255, 255, 255, 0.03) 50%, transparent 70%),
                radial-gradient(circle at 30% 70%, rgba(0, 245, 255, 0.06) 0%, transparent 50%);
            pointer-events: none;
        }

        .feedback-content .feedback-text {
            position: relative;
            z-index: 2;
            text-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            font-weight: 500;
            white-space: pre-wrap;
            font-family: 'Inter', sans-serif;
            max-height: 600px;
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-width: thin;
            scrollbar-color: rgba(147, 51, 234, 0.5) rgba(255, 255, 255, 0.1);
        }

        .feedback-content .feedback-text::-webkit-scrollbar {
            width: 8px;
        }

        .feedback-content .feedback-text::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        .feedback-content .feedback-text::-webkit-scrollbar-thumb {
            background: rgba(147, 51, 234, 0.5);
            border-radius: 4px;
        }

        .feedback-content .feedback-text::-webkit-scrollbar-thumb:hover {
            background: rgba(147, 51, 234, 0.7);
        }


        .feedback-loading {
            display: flex;
            align-items: center;
            gap: 20px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 600;
            justify-content: center;
            padding: 25px;
            position: relative;
        }

        .feedback-loading i {
            font-size: 1.8rem;
            animation: robotPulse 2s ease-in-out infinite;
        }

        @keyframes robotPulse {
            0%, 100% { transform: scale(1); color: rgba(255, 255, 255, 0.9); }
            50% { transform: scale(1.1); color: var(--neon-cyan); }
        }

        .feedback-loading .loading-dots {
            display: flex;
            gap: 8px;
        }

        .feedback-loading .loading-dots span {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            animation: loadingDots 1.8s ease-in-out infinite;
            box-shadow: 0 0 15px rgba(0, 245, 255, 0.5);
        }

        .feedback-loading .loading-dots span:nth-child(1) { animation-delay: 0s; }
        .feedback-loading .loading-dots span:nth-child(2) { animation-delay: 0.3s; }
        .feedback-loading .loading-dots span:nth-child(3) { animation-delay: 0.6s; }

        @keyframes loadingDots {
            0%, 80%, 100% { 
                transform: scale(0.8); 
                opacity: 0.5; 
                box-shadow: 0 0 5px rgba(0, 245, 255, 0.3);
            }
            40% { 
                transform: scale(1.3); 
                opacity: 1; 
                box-shadow: 0 0 15px rgba(0, 245, 255, 0.8);
            }
        }

        /* Enhanced Transcription Section */
        .transcription-section {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(240, 240, 255, 0.9));
            border-left: 4px solid var(--neon-cyan);
            padding: 35px;
            border-radius: 20px;
            margin-top: 25px;
            /* backdrop-filter removed for performance */
            color: #4a5568;
            line-height: 1.7;
            box-shadow: 
                0 15px 35px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.8);
            position: relative;
            overflow: hidden;
        }
        #transcriptionSection .section-title {
            color: #4a5568;
        }

        .transcription-section::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: var(--neon-gradient);
            opacity: 0.6;
        }

        /* Enhanced Status Messages */
        .status-message {
            padding: 25px 35px;
            border-radius: 20px;
            margin: 25px 0;
            text-align: center;
            font-weight: 600;
            /* backdrop-filter removed for performance */
            border: 1px solid;
            position: relative;
            overflow: hidden;
        }

        .status-message::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
            animation: statusShimmer 2s ease-in-out infinite;
        }

        @keyframes statusShimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }

        .status-success {
            background: linear-gradient(135deg, rgba(0, 230, 118, 0.2), rgba(76, 175, 80, 0.1));
            color: var(--neon-cyan);
            border-color: rgba(0, 230, 118, 0.4);
            box-shadow: 0 0 15px rgba(0, 230, 118, 0.2);
        }

        .status-error {
            background: linear-gradient(135deg, rgba(255, 87, 34, 0.2), rgba(244, 67, 54, 0.1));
            color: #FF5722;
            border-color: rgba(255, 87, 34, 0.4);
            box-shadow: 0 0 15px rgba(255, 87, 34, 0.2);
        }

        .status-info {
            background: linear-gradient(135deg, rgba(255, 213, 79, 0.2), rgba(255, 152, 0, 0.1));
            color: #FFD54F;
            border-color: rgba(255, 213, 79, 0.4);
            box-shadow: 0 0 15px rgba(255, 213, 79, 0.2);
        }

        /* Enhanced Audio Controls */
        .audio-controls {
            margin: 35px 0;
            text-align: center;
        }

        .audio-controls audio {
            width: 100%;
            max-width: 600px;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.4));
            /* backdrop-filter removed for performance */
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.3);
        }

        /* Utility Classes */
        .hidden {
            display: none !important;
        }

        .loading {
            display: inline-block;
            width: 28px;
            height: 28px;
            border: 3px solid rgba(157, 78, 221, 0.3);
            border-top: 3px solid var(--neon-purple);
            border-radius: 50%;
            animation: spin 1.2s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Enhanced Animations */
        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-80px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(80px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }

        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                padding: 20px;
            }
            
            .header h1 {
                font-size: 2.8rem;
            }
            
            .header-icon {
                font-size: 4rem;
            }
            
            .glass-card {
                padding: 30px;
            }
            
            .controls-grid {
                grid-template-columns: 1fr;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .recording-item {
                flex-direction: column;
                gap: 25px;
                text-align: center;
            }
            
            .feedback-content {
                padding: 30px;
                font-size: 15px;
            }

            .btn {
                min-width: 200px;
                padding: 20px 30px;
            }

            .section-title {
                font-size: 1.4rem;
            }
        }

        @media (max-width: 480px) {
            .header h1 {
                font-size: 2.2rem;
            }
            
            .glass-card {
                padding: 25px;
                margin-bottom: 25px;
            }

            .form-grid {
                gap: 20px;
            }

            .controls-grid {
                gap: 15px;
            }
        }

        /* Performance Optimizations */
        * {
            will-change: auto;
        }

        .shape,
        .header-icon,
        .section-icon,
        .recording-indicator {
            will-change: transform;
        }

        .btn:hover {
            will-change: transform, box-shadow;
        }

        /* Accessibility Improvements */
        @media (prefers-reduced-motion: reduce) {
            *,
            *::before,
            *::after {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }
        }

        /* Focus Styles for Accessibility */
        .btn:focus,
        .custom-select select:focus,
        .input-group input:focus {
            outline: 2px solid var(--neon-cyan);
            outline-offset: 2px;
        }

        /* High Contrast Mode Support */
        @media (prefers-contrast: high) {
            :root {
                --text-primary: #ffffff;
                --text-secondary: #cccccc;
                --glass-border: rgba(255, 255, 255, 0.5);
            }
        }

        /* Navigation Tabs */
        .nav-tabs {
            display: flex;
            gap: 12px;
            margin: 25px 0;
            padding: 8px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-tab {
            flex: 1;
            padding: 14px 20px;
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 15px;
            font-weight: 500;
        }

        .nav-tab i {
            margin-right: 8px;
        }

        .nav-tab:hover {
            background: rgba(147, 51, 234, 0.1);
            border-color: rgba(147, 51, 234, 0.3);
            color: var(--text-primary);
            transform: translateY(-2px);
        }

        .nav-tab.active {
            background: linear-gradient(135deg, rgba(147, 51, 234, 0.3), rgba(79, 70, 229, 0.3));
            border-color: rgba(147, 51, 234, 0.5);
            color: var(--text-primary);
            box-shadow: 0 4px 15px rgba(147, 51, 234, 0.2);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Practice Scenarios */
        .scenarios-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 16px;
            margin-top: 20px;
        }

        .scenario-card {
            padding: 25px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            cursor: pointer;
            transition: background 0.2s ease, border-color 0.2s ease;
            text-align: center;
            will-change: background, border-color;
        }

        .scenario-card:hover {
            background: rgba(147, 51, 234, 0.1);
            border-color: rgba(147, 51, 234, 0.3);
        }

        .scenario-card i {
            font-size: 36px;
            color: var(--primary-purple);
            margin-bottom: 12px;
        }

        .scenario-card h3 {
            margin: 12px 0 8px;
            font-size: 18px;
            color: var(--text-primary);
        }

        .scenario-card p {
            font-size: 14px;
            color: var(--text-secondary);
            margin: 0;
        }

        /* Tips Container */
        .tips-container {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-top: 20px;
        }

        .tip-card {
            padding: 25px;
            background: rgba(255, 255, 255, 0.03);
            border-left: 4px solid var(--primary-purple);
            border-radius: 10px;
        }

        .tip-card h3 {
            margin: 0 0 12px;
            font-size: 18px;
            color: var(--text-primary);
        }

        .tip-card h3 i {
            margin-right: 10px;
            color: var(--primary-purple);
        }

        .tip-card p {
            margin: 0;
            line-height: 1.6;
            color: var(--text-secondary);
        }

        /* Copy Feedback Button */
        .copy-feedback-btn {
            margin-top: 15px;
            padding: 12px 24px;
            background: rgba(147, 51, 234, 0.2);
            border: 1px solid rgba(147, 51, 234, 0.3);
            border-radius: 8px;
            color: var(--text-primary);
            cursor: pointer;
            transition: background 0.2s ease;
            font-size: 14px;
            font-weight: 500;
        }

        .copy-feedback-btn:hover {
            background: rgba(147, 51, 234, 0.3);
        }

        .copy-feedback-btn i {
            margin-right: 8px;
        }
    </style>
</head>
<body>
    <div class="floating-shapes">
        <div class="shape"></div>
        <div class="shape"></div>
        <div class="shape"></div>
        <div class="shape"></div>
        <div class="shape"></div>
    </div>

    <div class="container">
        <div class="header">
            <div class="header-icon">
                <i class="fas fa-microphone-alt"></i>
            </div>
            <h1>AI Speech Evaluator</h1>
            <p>Elevate your speaking skills with cutting-edge AI-powered feedback and analysis</p>
        </div>

        <div class="session-info" id="sessionInfo">
            <i class="fas fa-user-circle"></i> Session: <span id="sessionId">Initializing...</span>
        </div>

        <!-- Navigation Tabs -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchTab('record')">
                <i class="fas fa-microphone"></i> Record Speech
            </button>
            <button class="nav-tab" onclick="switchTab('practice')">
                <i class="fas fa-dumbbell"></i> Practice Scenarios
            </button>
            <button class="nav-tab" onclick="switchTab('tips')">
                <i class="fas fa-lightbulb"></i> Common Tips
            </button>
        </div>

        <!-- Record Tab Content -->
        <div id="recordTab" class="tab-content active">
        <div class="glass-card">
            <div class="section-title">
                <div class="section-icon">
                    <i class="fas fa-globe"></i>
                </div>
                <span>Language Selection</span>
            </div>
            
            <div class="language-selector">
                <label for="languageSelect">Choose your target language:</label>
                <div class="custom-select">
                    <select id="languageSelect">
                        <option value="en">en: English</option>
                        <option value="ko">ko: Korean</option>
                        <option value="zh-CN">zh-CN: Chinese (Simplified)</option>
                        <option value="it">it: Italian</option>
                        <option value="ja">ja: Japanese</option>
                        <option value="pt">pt: Portuguese</option>
                        <option value="ru">ru: Russian</option>
                        <option value="ar">ar: Arabic</option>
                        <option value="hi">hi: Hindi</option>
                        <option value="tr">tr: Turkish</option>
                        <option value="nl">nl: Dutch</option>
                        <option value="fr">fr: French</option>
                        <option value="es">es: Spanish</option>
                        <option value="de">de: German</option>
                        <option value="bn">bn: Bengali</option>
                        <option value="zh">zh: Mandarin Chinese</option>
                    </select>
                </div>
            </div>

            <div class="section-title">
                <div class="section-icon">
                    <i class="fas fa-rocket"></i>
                </div>
                <span>Controls</span>
            </div>

            <div class="controls-grid">
                <button class="btn btn-record" id="recordBtn" onclick="startRecording()">
                    <i class="fas fa-microphone"></i>
                    Record Speech (R)
                </button>
                <button class="btn btn-list" onclick="listRecordings()">
                    <i class="fas fa-database"></i>
                    View Archive (L)
                </button>
                <button class="btn btn-play" onclick="showPlayDialog()">
                    <i class="fas fa-play"></i>
                    Play Recording (P)
                </button>
                <button class="btn btn-stop hidden" id="stopBtn" onclick="stopRecording()">
                    <i class="fas fa-stop"></i>
                    Stop Recording (Enter)
                </button>
            </div>

            <div id="statusMessage"></div>

            <div class="recording-setup" id="recordingSetup">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-cogs"></i>
                    </div>
                    <span>Configuration</span>
                </div>
                
                <div class="form-grid">
                    <div class="input-group">
                        <label for="topicInput">Speech Topic</label>
                        <input type="text" id="topicInput" placeholder="What will you be speaking about?" maxlength="200">
                    </div>
                    <div class="input-group">
                        <label for="speechTypeInput">Speech Type</label>
                        <input type="text" id="speechTypeInput" placeholder="e.g., short presentation, pitch for a company, interview" maxlength="100">
                    </div>
                </div>
                
                <div class="checkbox-wrapper">
                    <input type="checkbox" id="repeatSpeech">
                    <label for="repeatSpeech" style="color: var(--text-primary); text-transform: none; letter-spacing: normal;">This is a repeat attempt on the same topic</label>
                </div>
                
                <div class="controls-grid" style="margin-top: 35px;">
                    <button class="btn btn-record" onclick="confirmRecording()">
                        <i class="fas fa-play"></i>
                        Initiate Recording (T)
                    </button>
                    <button class="btn btn-secondary" onclick="cancelRecording()">
                        <i class="fas fa-times"></i>
                        Cancel (B)
                    </button>
                </div>
            </div>

            <div class="recording-status" id="recordingStatus">
                <div class="recording-indicator">
                    <i class="fas fa-microphone"></i>
                </div>
                <div class="status-text">Recording Active</div>
                <div class="status-subtext">Please speak clearly into your microphone.</div>
                <div style="margin-top: 25px; display: flex; gap: 20px; justify-content: center;">
                    <button class="btn btn-stop" onclick="stopRecording()">
                        <i class="fas fa-stop"></i>
                        Stop Recording (Enter)
                    </button>
                    <button class="btn btn-secondary" onclick="cancelActiveRecording()">
                        <i class="fas fa-times"></i>
                        Cancel (X)
                    </button>
                </div>
            </div>

            <div class="recordings-list" id="recordingsList">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <span>Recording List</span>
                </div>
                <div class="recordings-grid" id="recordingsContainer">
                </div>
            </div>

            <div class="feedback-section" id="feedbackSection">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-brain"></i>
                    </div>
                    <span>AI Analysis</span>
                </div>
                <div class="feedback-content" id="feedbackContent">
                    <div class="feedback-loading" id="feedbackLoading">
                        <i class="fas fa-robot"></i>
                        <span>AI is analyzing speech patterns</span>
                        <div class="loading-dots">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                    <div class="feedback-text" id="feedbackText" style="display: none;"></div>
                    <button class="copy-feedback-btn" id="copyFeedbackBtn" style="display: none;" onclick="copyFeedback()">
                        <i class="fas fa-copy"></i> Copy Feedback
                    </button>
                </div>
            </div>

            <div class="transcription-section hidden" id="transcriptionSection">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <span>Transcription</span>
                </div>
                <div id="transcriptionContent">
                </div>
            </div>

            <div class="audio-controls hidden" id="audioControls">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-volume-up"></i>
                    </div>
                    <span>Playback System</span>
                </div>
                <audio controls id="audioPlayer">
                    Your browser does not support the audio element.
                </audio>
            </div>
        </div>
        </div> <!-- End Record Tab -->

        <!-- Practice Scenarios Tab -->
        <div id="practiceTab" class="tab-content">
            <div class="glass-card">
                <div class="section-title">
                    <div class="section-icon"><i class="fas fa-dumbbell"></i></div>
                    <span>Practice Scenarios</span>
                </div>
                <p style="margin-bottom: 20px; opacity: 0.9;">Jump into common speaking situations. Pick a scenario, get a prompt, and start practicing!</p>

                <div class="scenarios-grid">
                    <div class="scenario-card" onclick="loadScenario('elevator')">
                        <i class="fas fa-briefcase"></i>
                        <h3>Elevator Pitch</h3>
                        <p>30 seconds to explain what you do</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('persuasive')">
                        <i class="fas fa-bullhorn"></i>
                        <h3>Persuasive Speech</h3>
                        <p>Convince someone of your position</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('toast')">
                        <i class="fas fa-glass-cheers"></i>
                        <h3>Wedding Toast</h3>
                        <p>Heartfelt speech for a special occasion</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('intro')">
                        <i class="fas fa-user-tie"></i>
                        <h3>Self Introduction</h3>
                        <p>Introduce yourself in a professional setting</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('demo')">
                        <i class="fas fa-chalkboard-teacher"></i>
                        <h3>Product Demo</h3>
                        <p>Present a product or idea clearly</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('story')">
                        <i class="fas fa-book-open"></i>
                        <h3>Storytelling</h3>
                        <p>Tell a compelling personal story</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('interview')">
                        <i class="fas fa-handshake"></i>
                        <h3>Job Interview</h3>
                        <p>Answer "Tell me about yourself"</p>
                    </div>
                    <div class="scenario-card" onclick="loadScenario('debate')">
                        <i class="fas fa-comments"></i>
                        <h3>Debate Argument</h3>
                        <p>Present a strong counterpoint</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Tips Tab -->
        <div id="tipsTab" class="tab-content">
            <div class="glass-card">
                <div class="section-title">
                    <div class="section-icon"><i class="fas fa-lightbulb"></i></div>
                    <span>Common Speaking Tips</span>
                </div>

                <div class="tips-container">
                    <div class="tip-card">
                        <h3><i class="fas fa-stopwatch"></i> Strategic Pauses</h3>
                        <p>Throw in a quick pause before your big points. A second or two of silence actually makes people pay attention - it builds tension and makes what you say next hit different. Most people talk way too fast anyway.</p>
                    </div>

                    <div class="tip-card">
                        <h3><i class="fas fa-volume-up"></i> Volume Variation</h3>
                        <p>Switch up how loud you talk. Go quieter when you're being real with them, louder when you're making your main point. Keeping the same volume the whole time is basically a lullaby.</p>
                    </div>

                    <div class="tip-card">
                        <h3><i class="fas fa-ban"></i> Ditch the Filler Words</h3>
                        <p>Every "um," "uh," and "like" makes you sound less confident. Just pause instead - silence actually sounds way better than filler. Record yourself and count them, then try to cut that number in half next time.</p>
                    </div>

                    <div class="tip-card">
                        <h3><i class="fas fa-question"></i> Start with a Question</h3>
                        <p>Opening with a question gets people thinking right away. "What would you do if..." or "Ever notice how..." beats "Today I'm gonna talk about..." every single time. Hook them from the jump.</p>
                    </div>

                    <div class="tip-card">
                        <h3><i class="fas fa-ruler"></i> Rule of Three</h3>
                        <p>People remember stuff in threes. Three points, three examples, three reasons why. It just works better - one feels incomplete, five is too much, three is that perfect balance.</p>
                    </div>

                    <div class="tip-card">
                        <h3><i class="fas fa-heart"></i> End with Feeling</h3>
                        <p>Don't just recap your points at the end. Tell them why it actually matters, how it changes things, what it means for them. People forget facts but they remember how you made them feel.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        let currentLanguage = 'en';
        let recordedBlob = null;
        let recordings = [];
        let sessionId = null;
        let feedbackEventSource = null;

        // Use current host for API calls (works for both local and production)
        const API_BASE = window.location.origin + '/api';

        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
        }

        document.addEventListener('DOMContentLoaded', function() {
            initializeSession();
            setupKeyboardShortcuts();
            loadLanguages();
            checkHealth();
            setupBeforeUnload();
        });

        async function initializeSession() {
            try {
                const response = await fetch(API_BASE + '/session/new', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                const result = await response.json();
                if (result.success) {
                    sessionId = result.session_id;
                    document.getElementById('sessionId').textContent = sessionId.substring(0, 8) + '...';
                    console.log('Session initialized:', sessionId);
                } else {
                    throw new Error('Failed to create session');
                }
            } catch (error) {
                console.error('Failed to initialize session:', error);
                sessionId = generateUUID();
                document.getElementById('sessionId').textContent = sessionId.substring(0, 8) + '... (offline)';
            }
        }

        function setupBeforeUnload() {
            window.addEventListener('beforeunload', function(e) {
                if (sessionId) {
                    clearAllRecordings();
                    cleanupSession();
                }
                if (feedbackEventSource) {
                    feedbackEventSource.close();
                }
            });
            
            window.addEventListener('unload', function(e) {
                if (sessionId) {
                    clearAllRecordings();
                    cleanupSession();
                }
                if (feedbackEventSource) {
                    feedbackEventSource.close();
                }
            });
        }

        async function clearAllRecordings() {
            if (!sessionId) return;
            
            try {
                await fetch(API_BASE + '/recordings', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    }
                });
            } catch (error) {
                console.log('Failed to clear recordings on page unload');
            }
        }

        async function cleanupSession() {
            if (!sessionId) return;
            
            try {
                await fetch(API_BASE + '/session/cleanup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    }
                });
            } catch (error) {
                console.log('Failed to cleanup session');
            }
        }

        const translations = {
            en: {
                title: "AI Speech Evaluator",
                subtitle: "Transform your speaking skills with cutting-edge AI-powered feedback and analysis",
                sessionText: "Your Session:",
                languageLabel: "Choose your target language:",
                languageSection: "Language Selection",
                actionsSection: "Quick Actions",
                recordBtn: "Record Speech (R)",
                viewBtn: "View Recordings (L)",
                playBtn: "Play Recording (P)",
                stopBtn: "Stop Recording (Enter)",
                setupSection: "Recording Setup",
                topicLabel: "Speech Topic",
                topicPlaceholder: "What will you be speaking about?",
                typeLabel: "Speech Type",
                typePlaceholder: "e.g., interview, presentation, debate",
                repeatLabel: "This is a repeat attempt on the same topic",
                startBtn: "Start Recording (T)",
                cancelBtn: "Cancel (B)",
                recordingText: "Recording in Progress",
                recordingSubtext: "Speak clearly into your microphone. Click stop when finished or cancel to discard.",
                cancelActiveBtn: "Cancel (X)",
                recordingsSection: "Your Recordings",
                feedbackSection: "AI Feedback & Analysis",
                transcriptionSection: "Speech Transcription",
                playbackSection: "Recording Playback",
                noRecordings: "No recordings found",
                noRecordingsSubtext: "Create your first recording to get started!",
                playRecBtn: "Play",
                deleteBtn: "Delete",
                recordingTooShort: "Recording Too Short",
                recordingTooShortText: "Sorry! The recording was too short to generate feedback for. Please try again with a longer speech.",
                aiAnalyzing: "AI is analyzing your speech"
            },
            es: {
                title: "Evaluador de Discursos IA",
                subtitle: "Transforma tus habilidades de habla con análisis y retroalimentación impulsados por IA de vanguardia",
                sessionText: "Tu Sesión:",
                languageLabel: "Elige tu idioma objetivo:",
                languageSection: "Selección de Idioma",
                actionsSection: "Acciones Rápidas",
                recordBtn: "Grabar Discurso (R)",
                viewBtn: "Ver Grabaciones (L)",
                playBtn: "Reproducir Grabación (P)",
                stopBtn: "Detener Grabación (Enter)",
                setupSection: "Configuración de Grabación",
                topicLabel: "Tema del Discurso",
                topicPlaceholder: "¿De qué vas a hablar?",
                typeLabel: "Tipo de Discurso",
                typePlaceholder: "ej., entrevista, presentación, debate",
                repeatLabel: "Este es un segundo intento del mismo tema",
                startBtn: "Iniciar Grabación (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Grabación en Progreso",
                recordingSubtext: "Habla claramente al micrófono. Haz clic en detener cuando termines o cancelar para descartar.",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Tus Grabaciones",
                feedbackSection: "Análisis y Retroalimentación IA",
                transcriptionSection: "Transcripción del Discurso",
                playbackSection: "Reproducción de Grabación",
                noRecordings: "No se encontraron grabaciones",
                noRecordingsSubtext: "¡Crea tu primera grabación para comenzar!",
                playRecBtn: "Reproducir",
                deleteBtn: "Eliminar",
                recordingTooShort: "Grabación Muy Corta",
                recordingTooShortText: "¡Lo siento! La grabación fue muy corta para generar retroalimentación. Por favor, inténtalo de nuevo con un discurso más largo.",
                aiAnalyzing: "La IA está analizando tu discurso"
            },
            fr: {
                title: "Évaluateur de Discours IA",
                subtitle: "Transformez vos compétences oratoires avec des commentaires et analyses IA de pointe",
                sessionText: "Votre Session:",
                languageLabel: "Choisissez votre langue cible:",
                languageSection: "Sélection de Langue",
                actionsSection: "Actions Rapides",
                recordBtn: "Enregistrer Discours (R)",
                viewBtn: "Voir Enregistrements (L)",
                playBtn: "Lire Enregistrement (P)",
                stopBtn: "Arrêter Enregistrement (Entrée)",
                setupSection: "Configuration d'Enregistrement",
                topicLabel: "Sujet du Discours",
                topicPlaceholder: "De quoi allez-vous parler?",
                typeLabel: "Type de Discours",
                typePlaceholder: "ex., entretien, présentation, débat",
                repeatLabel: "Ceci est une seconde tentative sur le même sujet",
                startBtn: "Démarrer Enregistrement (T)",
                cancelBtn: "Annuler (B)",
                recordingText: "Enregistrement en Cours",
                recordingSubtext: "Parlez clairement dans votre microphone. Cliquez arrêter quand terminé ou annuler pour ignorer.",
                cancelActiveBtn: "Annuler (X)",
                recordingsSection: "Vos Enregistrements",
                feedbackSection: "Analyse et Commentaires IA",
                transcriptionSection: "Transcription du Discours",
                playbackSection: "Lecture d'Enregistrement",
                noRecordings: "Aucun enregistrement trouvé",
                noRecordingsSubtext: "Créez votre premier enregistrement pour commencer!",
                playRecBtn: "Lire",
                deleteBtn: "Supprimer",
                recordingTooShort: "Enregistrement Trop Court",
                recordingTooShortText: "Désolé! L'enregistrement était trop court pour générer des commentaires. Veuillez réessayer avec un discours plus long.",
                aiAnalyzing: "L'IA analyse votre discours"
            },
            de: {
                title: "KI-Sprach-Evaluator",
                subtitle: "Verwandeln Sie Ihre Sprechfähigkeiten mit modernsten KI-gestützten Feedback und Analysen",
                sessionText: "Ihre Sitzung:",
                languageLabel: "Wählen Sie Ihre Zielsprache:",
                languageSection: "Sprachauswahl",
                actionsSection: "Schnelle Aktionen",
                recordBtn: "Rede Aufnehmen (R)",
                viewBtn: "Aufnahmen Anzeigen (L)",
                playBtn: "Aufnahme Abspielen (P)",
                stopBtn: "Aufnahme Stoppen (Enter)",
                setupSection: "Aufnahme-Einrichtung",
                topicLabel: "Rede-Thema",
                topicPlaceholder: "Worüber werden Sie sprechen?",
                typeLabel: "Rede-Typ",
                typePlaceholder: "z.B., Interview, Präsentation, Debatte",
                repeatLabel: "Dies ist ein zweiter Versuch zum gleichen Thema",
                startBtn: "Aufnahme Starten (T)",
                cancelBtn: "Abbrechen (B)",
                recordingText: "Aufnahme läuft",
                recordingSubtext: "Sprechen Sie deutlich in Ihr Mikrofon. Klicken Sie stoppen wenn fertig oder abbrechen zum Verwerfen.",
                cancelActiveBtn: "Abbrechen (X)",
                recordingsSection: "Ihre Aufnahmen",
                feedbackSection: "KI-Feedback & Analyse",
                transcriptionSection: "Rede-Transkription",
                playbackSection: "Aufnahme-Wiedergabe",
                noRecordings: "Keine Aufnahmen gefunden",
                noRecordingsSubtext: "Erstellen Sie Ihre erste Aufnahme um zu beginnen!",
                playRecBtn: "Abspielen",
                deleteBtn: "Löschen",
                recordingTooShort: "Aufnahme Zu Kurz",
                recordingTooShortText: "Entschuldigung! Die Aufnahme war zu kurz um Feedback zu generieren. Bitte versuchen Sie es erneut mit einer längeren Rede.",
                aiAnalyzing: "KI analysiert Ihre Rede"
            },
            it: {
                title: "Valutatore di Discorsi IA",
                subtitle: "Trasforma le tue abilità oratorie con feedback e analisi all'avanguardia basati sull'IA",
                sessionText: "La Tua Sessione:",
                languageLabel: "Scegli la tua lingua di destinazione:",
                languageSection: "Selezione Lingua",
                actionsSection: "Azioni Rapide",
                recordBtn: "Registra Discorso (R)",
                viewBtn: "Visualizza Registrazioni (L)",
                playBtn: "Riproduci Registrazione (P)",
                stopBtn: "Ferma Registrazione (Invio)",
                setupSection: "Configurazione Registrazione",
                topicLabel: "Argomento del Discorso",
                topicPlaceholder: "Di cosa parlerai?",
                typeLabel: "Tipo di Discorso",
                typePlaceholder: "es., intervista, presentazione, dibattito",
                repeatLabel: "Questo è un secondo tentativo sullo stesso argomento",
                startBtn: "Inizia Registrazione (T)",
                cancelBtn: "Annulla (B)",
                recordingText: "Registrazione in Corso",
                recordingSubtext: "Parla chiaramente nel microfono. Clicca ferma quando hai finito o annulla per scartare.",
                cancelActiveBtn: "Annulla (X)",
                recordingsSection: "Le Tue Registrazioni",
                feedbackSection: "Feedback e Analisi IA",
                transcriptionSection: "Trascrizione del Discorso",
                playbackSection: "Riproduzione Registrazione",
                noRecordings: "Nessuna registrazione trovata",
                noRecordingsSubtext: "Crea la tua prima registrazione per iniziare!",
                playRecBtn: "Riproduci",
                deleteBtn: "Elimina",
                recordingTooShort: "Registrazione Troppo Breve",
                recordingTooShortText: "Spiacente! La registrazione era troppo breve per generare feedback. Riprova con un discorso più lungo.",
                aiAnalyzing: "L'IA sta analizzando il tuo discorso"
            },
            pt: {
                title: "Avaliador de Discursos IA",
                subtitle: "Transforme suas habilidades de fala com feedback e análise de ponta baseados em IA",
                sessionText: "Sua Sessão:",
                languageLabel: "Escolha seu idioma alvo:",
                languageSection: "Seleção de Idioma",
                actionsSection: "Ações Rápidas",
                recordBtn: "Gravar Discurso (R)",
                viewBtn: "Ver Gravações (L)",
                playBtn: "Reproduzir Gravação (P)",
                stopBtn: "Parar Gravação (Enter)",
                setupSection: "Configuração de Gravação",
                topicLabel: "Tópico do Discurso",
                topicPlaceholder: "Sobre o que você vai falar?",
                typeLabel: "Tipo de Discurso",
                typePlaceholder: "ex., entrevista, apresentação, debate",
                repeatLabel: "Esta é uma segunda tentativa no mesmo tópico",
                startBtn: "Iniciar Gravação (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Gravação em Progresso",
                recordingSubtext: "Fale claramente no microfone. Clique parar quando terminar ou cancelar para descartar.",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Suas Gravações",
                feedbackSection: "Feedback e Análise IA",
                transcriptionSection: "Transcrição do Discurso",
                playbackSection: "Reprodução da Gravação",
                noRecordings: "Nenhuma gravação encontrada",
                noRecordingsSubtext: "Crie sua primeira gravação para começar!",
                playRecBtn: "Reproduzir",
                deleteBtn: "Excluir",
                recordingTooShort: "Gravação Muito Curta",
                recordingTooShortText: "Desculpe! A gravação foi muito curta para gerar feedback. Tente novamente com um discurso mais longo.",
                aiAnalyzing: "A IA está analisando seu discurso"
            },
            ru: {
                title: "ИИ Оценщик Речи",
                subtitle: "Преобразуйте свои навыки речи с помощью передовой обратной связи и анализа на основе ИИ",
                sessionText: "Ваша Сессия:",
                languageLabel: "Выберите целевой язык:",
                languageSection: "Выбор Языка",
                actionsSection: "Быстрые Действия",
                recordBtn: "Записать Речь (R)",
                viewBtn: "Просмотр Записей (L)",
                playBtn: "Воспроизвести Запись (P)",
                stopBtn: "Остановить Запись (Enter)",
                setupSection: "Настройка Записи",
                topicLabel: "Тема Речи",
                topicPlaceholder: "О чём вы будете говорить?",
                typeLabel: "Тип Речи",
                typePlaceholder: "напр., интервью, презентация, дебаты",
                repeatLabel: "Это вторая попытка на ту же тему",
                startBtn: "Начать Запись (T)",
                cancelBtn: "Отмена (B)",
                recordingText: "Запись в Процессе",
                recordingSubtext: "Говорите чётко в микрофон. Нажмите стоп когда закончите или отмена для отмены.",
                cancelActiveBtn: "Отмена (X)",
                recordingsSection: "Ваши Записи",
                feedbackSection: "ИИ Обратная Связь и Анализ",
                transcriptionSection: "Транскрипция Речи",
                playbackSection: "Воспроизведение Записи",
                noRecordings: "Записи не найдены",
                noRecordingsSubtext: "Создайте первую запись для начала!",
                playRecBtn: "Воспроизвести",
                deleteBtn: "Удалить",
                recordingTooShort: "Запись Слишком Короткая",
                recordingTooShortText: "Извините! Запись была слишком короткой для генерации обратной связи. Попробуйте снова с более длинной речью.",
                aiAnalyzing: "ИИ анализирует вашу речь"
            },
             ko: {
                title: "AI 스피치 평가기",
                subtitle: "최첨단 AI 기반 피드백과 분석으로 말하기 실력을 향상시키세요",
                sessionText: "세션:",
                languageLabel: "목표 언어를 선택하세요:",
                languageSection: "언어 선택",
                actionsSection: "빠른 작업",
                recordBtn: "스피치 녹음 (R)",
                viewBtn: "녹음 보기 (L)",
                playBtn: "녹음 재생 (P)",
                stopBtn: "녹음 중지 (Enter)",
                setupSection: "녹음 설정",
                topicLabel: "스피치 주제",
                topicPlaceholder: "무엇에 대해 말씀하실 건가요?",
                typeLabel: "스피치 유형",
                typePlaceholder: "예: 면접, 발표, 토론",
                repeatLabel: "같은 주제에 대한 재시도입니다",
                startBtn: "녹음 시작 (T)",
                cancelBtn: "취소 (B)",
                recordingText: "녹음 진행 중",
                recordingSubtext: "마이크에 대고 명확하게 말하세요. 완료되면 중지를 클릭하거나 취소를 클릭하여 삭제하세요.",
                cancelActiveBtn: "취소 (X)",
                recordingsSection: "녹음 목록",
                feedbackSection: "AI 피드백 및 분석",
                transcriptionSection: "스피치 전사",
                playbackSection: "녹음 재생",
                noRecordings: "녹음을 찾을 수 없습니다",
                noRecordingsSubtext: "첫 번째 녹음을 만들어 시작하세요!",
                playRecBtn: "재생",
                deleteBtn: "삭제",
                recordingTooShort: "녹음이 너무 짧습니다",
                recordingTooShortText: "죄송합니다! 녹음이 너무 짧아서 피드백을 생성할 수 없습니다. 더 긴 스피치로 다시 시도해 주세요.",
                aiAnalyzing: "AI가 당신의 스피치를 분석하고 있습니다"
            },
            zh: {
                title: "AI语音评估器",
                subtitle: "用尖端的AI驱动反馈和分析改变您的演讲技能",
                sessionText: "您的会话：",
                languageLabel: "选择您的目标语言：",
                languageSection: "语言选择",
                actionsSection: "快速操作",
                recordBtn: "录制演讲 (R)",
                viewBtn: "查看录音 (L)",
                playBtn: "播放录音 (P)",
                stopBtn: "停止录制 (Enter)",
                setupSection: "录制设置",
                topicLabel: "演讲主题",
                topicPlaceholder: "您将谈论什么？",
                typeLabel: "演讲类型",
                typePlaceholder: "例如：面试、演示、辩论",
                repeatLabel: "这是同一主题的重复尝试",
                startBtn: "开始录制 (T)",
                cancelBtn: "取消 (B)",
                recordingText: "录制进行中",
                recordingSubtext: "清楚地对着麦克风说话。完成时点击停止或点击取消放弃。",
                cancelActiveBtn: "取消 (X)",
                recordingsSection: "您的录音",
                feedbackSection: "AI反馈与分析",
                transcriptionSection: "演讲转录",
                playbackSection: "录音播放",
                noRecordings: "未找到录音",
                noRecordingsSubtext: "创建您的第一个录音开始吧！",
                playRecBtn: "播放",
                deleteBtn: "删除",
                recordingTooShort: "录音太短",
                recordingTooShortText: "抱歉！录音太短无法生成反馈。请用更长的演讲重试。",
                aiAnalyzing: "AI正在分析您的演讲"
            },
            ja: {
                title: "AIスピーチ評価器",
                subtitle: "最先端のAI駆動フィードバックと分析でスピーキングスキルを変革",
                sessionText: "あなたのセッション：",
                languageLabel: "対象言語を選択：",
                languageSection: "言語選択",
                actionsSection: "クイックアクション",
                recordBtn: "スピーチ録音 (R)",
                viewBtn: "録音を表示 (L)",
                playBtn: "録音再生 (P)",
                stopBtn: "録音停止 (Enter)",
                setupSection: "録音設定",
                topicLabel: "スピーチトピック",
                topicPlaceholder: "何について話しますか？",
                typeLabel: "スピーチタイプ",
                typePlaceholder: "例：面接、プレゼンテーション、討論",
                repeatLabel: "これは同じトピックの再試行です",
                startBtn: "録音開始 (T)",
                cancelBtn: "キャンセル (B)",
                recordingText: "録音中",
                recordingSubtext: "マイクに向かってはっきりと話してください。終了時は停止をクリック、破棄する場合はキャンセルをクリック。",
                cancelActiveBtn: "キャンセル (X)",
                recordingsSection: "あなたの録音",
                feedbackSection: "AIフィードバック＆分析",
                transcriptionSection: "スピーチ転写",
                playbackSection: "録音再生",
                noRecordings: "録音が見つかりません",
                noRecordingsSubtext: "最初の録音を作成して始めましょう！",
                playRecBtn: "再生",
                deleteBtn: "削除",
                recordingTooShort: "録音が短すぎます",
                recordingTooShortText: "申し訳ありません！録音が短すぎてフィードバックを生成できません。より長いスピーチで再試行してください。",
                aiAnalyzing: "AIがあなたのスピーチを分析しています"
            },
            ar: {
                title: "مُقيم الخطابات بالذكاء الاصطناعي",
                subtitle: "حول مهاراتك في التحدث مع تحليل وتغذية راجعة متطورة مدعومة بالذكاء الاصطناعي",
                sessionText: "جلستك:",
                languageLabel: "اختر لغتك المستهدفة:",
                languageSection: "اختيار اللغة",
                actionsSection: "إجراءات سريعة",
                recordBtn: "تسجيل خطاب (R)",
                viewBtn: "عرض التسجيلات (L)",
                playBtn: "تشغيل التسجيل (P)",
                stopBtn: "إيقاف التسجيل (Enter)",
                setupSection: "إعداد التسجيل",
                topicLabel: "موضوع الخطاب",
                topicPlaceholder: "عن ماذا ستتحدث؟",
                typeLabel: "نوع الخطاب",
                typePlaceholder: "مثال: مقابلة، عرض تقديمي، مناقشة",
                repeatLabel: "هذه محاولة ثانية لنفس الموضوع",
                startBtn: "بدء التسجيل (T)",
                cancelBtn: "إلغاء (B)",
                recordingText: "التسجيل قيد التقدم",
                recordingSubtext: "تحدث بوضوح في الميكروفون. انقر إيقاف عند الانتهاء أو إلغاء للتجاهل.",
                cancelActiveBtn: "إلغاء (X)",
                recordingsSection: "تسجيلاتك",
                feedbackSection: "تغذية راجعة وتحليل بالذكاء الاصطناعي",
                transcriptionSection: "نسخ الخطاب",
                playbackSection: "تشغيل التسجيل",
                noRecordings: "لم يتم العثور على تسجيلات",
                noRecordingsSubtext: "أنشئ تسجيلك الأول للبدء!",
                playRecBtn: "تشغيل",
                deleteBtn: "حذف",
                recordingTooShort: "التسجيل قصير جداً",
                recordingTooShortText: "عذراً! كان التسجيل قصيراً جداً لإنتاج تغذية راجعة. حاول مرة أخرى بخطاب أطول.",
                aiAnalyzing: "الذكاء الاصطناعي يحلل خطابك"
            },
            hi: {
                title: "एआई भाषण मूल्यांकनकर्ता",
                subtitle: "अत्याधुनिक एआई-संचालित फीडबैक और विश्लेषण के साथ अपने बोलने के कौशल को बदलें",
                sessionText: "आपका सत्र:",
                languageLabel: "अपनी लक्षित भाषा चुनें:",
                languageSection: "भाषा चयन",
                actionsSection: "त्वरित कार्य",
                recordBtn: "भाषण रिकॉर्ड करें (R)",
                viewBtn: "रिकॉर्डिंग देखें (L)",
                playBtn: "रिकॉर्डिंग चलाएं (P)",
                stopBtn: "रिकॉर्डिंग रोकें (Enter)",
                setupSection: "रिकॉर्डिंग सेटअप",
                topicLabel: "भाषण विषय",
                topicPlaceholder: "आप किस बारे में बात करेंगे?",
                typeLabel: "भाषण प्रकार",
                typePlaceholder: "जैसे: साक्षात्कार, प्रस्तुति, बहस",
                repeatLabel: "यह उसी विषय पर दूसरी कोशिश है",
                startBtn: "रिकॉर्डिंग शुरू करें (T)",
                cancelBtn: "रद्द करें (B)",
                recordingText: "रिकॉर्डिंग प्रगति में",
                recordingSubtext: "माइक्रोफोन में स्पष्ट रूप से बोलें। समाप्त होने पर रोकें क्लिक करें या रद्द करने के लिए रद्द करें।",
                cancelActiveBtn: "रद्द करें (X)",
                recordingsSection: "आपकी रिकॉर्डिंग",
                feedbackSection: "एआई फीडबैक और विश्लेषण",
                transcriptionSection: "भाषण प्रतिलेखन",
                playbackSection: "रिकॉर्डिंग प्लेबैक",
                noRecordings: "कोई रिकॉर्डिंग नहीं मिली",
                noRecordingsSubtext: "शुरू करने के लिए अपनी पहली रिकॉर्डिंग बनाएं!",
                playRecBtn: "चलाएं",
                deleteBtn: "हटाएं",
                recordingTooShort: "रिकॉर्डिंग बहुत छोटी",
                recordingTooShortText: "माफ़ करें! रिकॉर्डिंग फीडबैक उत्पन्न करने के लिए बहुत छोटी थी। कृपया लंबे भाषण के साथ फिर से कोशिश करें।",
                aiAnalyzing: "एआई आपके भाषण का विश्लेषण कर रहा है"
            },
            tr: {
                title: "AI Konuşma Değerlendirici",
                subtitle: "En son AI destekli geri bildirim ve analiz ile konuşma becerilerinizi dönüştürün",
                sessionText: "Oturumunuz:",
                languageLabel: "Hedef dilinizi seçin:",
                languageSection: "Dil Seçimi",
                actionsSection: "Hızlı İşlemler",
                recordBtn: "Konuşma Kaydet (R)",
                viewBtn: "Kayıtları Görüntüle (L)",
                playBtn: "Kaydı Oynat (P)",
                stopBtn: "Kaydı Durdur (Enter)",
                setupSection: "Kayıt Kurulumu",
                topicLabel: "Konuşma Konusu",
                topicPlaceholder: "Ne hakkında konuşacaksınız?",
                typeLabel: "Konuşma Türü",
                typePlaceholder: "örn., mülakat, sunum, tartışma",
                repeatLabel: "Bu aynı konu üzerinde ikinci bir deneme",
                startBtn: "Kaydı Başlat (T)",
                cancelBtn: "İptal (B)",
                recordingText: "Kayıt Devam Ediyor",
                recordingSubtext: "Mikrofona açık bir şekilde konuşun. Bitirdiğinde durdur'a veya atmak için iptal'e tıklayın.",
                cancelActiveBtn: "İptal (X)",
                recordingsSection: "Kayıtlarınız",
                feedbackSection: "AI Geri Bildirim ve Analiz",
                transcriptionSection: "Konuşma Transkripsiyonu",
                playbackSection: "Kayıt Oynatma",
                noRecordings: "Kayıt bulunamadı",
                noRecordingsSubtext: "Başlamak için ilk kaydınızı oluşturun!",
                playRecBtn: "Oynat",
                deleteBtn: "Sil",
                recordingTooShort: "Kayıt Çok Kısa",
                recordingTooShortText: "Üzgünüz! Kayıt geri bildirim üretmek için çok kısaydı. Lütfen daha uzun bir konuşma ile tekrar deneyin.",
                aiAnalyzing: "AI konuşmanızı analiz ediyor"
            },
            nl: {
                title: "AI Spraak Evaluator",
                subtitle: "Transformeer je spreekvaardigheden met geavanceerde AI-aangedreven feedback en analyse",
                sessionText: "Je Sessie:",
                languageLabel: "Kies je doeltaal:",
                languageSection: "Taalselectie",
                actionsSection: "Snelle Acties",
                recordBtn: "Spraak Opnemen (R)",
                viewBtn: "Opnames Bekijken (L)",
                playBtn: "Opname Afspelen (P)",
                stopBtn: "Opname Stoppen (Enter)",
                setupSection: "Opname Instellingen",
                topicLabel: "Spraak Onderwerp",
                topicPlaceholder: "Waar ga je over spreken?",
                typeLabel: "Spraak Type",
                typePlaceholder: "bijv., interview, presentatie, debat",
                repeatLabel: "Dit is een tweede poging op hetzelfde onderwerp",
                startBtn: "Opname Starten (T)",
                cancelBtn: "Annuleren (B)",
                recordingText: "Opname Bezig",
                recordingSubtext: "Spreek duidelijk in je microfoon. Klik stop wanneer klaar of annuleren om te verwijderen.",
                cancelActiveBtn: "Annuleren (X)",
                recordingsSection: "Je Opnames",
                feedbackSection: "AI Feedback & Analyse",
                transcriptionSection: "Spraak Transcriptie",
                playbackSection: "Opname Afspelen",
                noRecordings: "Geen opnames gevonden",
                noRecordingsSubtext: "Maak je eerste opname om te beginnen!",
                playRecBtn: "Afspelen",
                deleteBtn: "Verwijderen",
                recordingTooShort: "Opname Te Kort",
                recordingTooShortText: "Sorry! De opname was te kort om feedback te genereren. Probeer opnieuw met een langere spraak.",
                aiAnalyzing: "AI analyseert je spraak"
            },
            bn: {
                title: "এআই বক্তৃতা মূল্যায়নকারী",
                subtitle: "অত্যাধুনিক এআই-চালিত ফিডব্যাক এবং বিশ্লেষণের মাধ্যমে আপনার কথা বলার দক্ষতা পরিবর্তন করুন",
                sessionText: "আপনার সেশন:",
                languageLabel: "আপনার লক্ষ্য ভাষা বেছে নিন:",
                languageSection: "ভাষা নির্বাচন",
                actionsSection: "দ্রুত কর্ম",
                recordBtn: "বক্তৃতা রেকর্ড করুন (R)",
                viewBtn: "রেকর্ডিং দেখুন (L)",
                playBtn: "রেকর্ডিং চালান (P)",
                stopBtn: "রেকর্ডিং বন্ধ করুন (Enter)",
                setupSection: "রেকর্ডিং সেটআপ",
                topicLabel: "বক্তৃতার বিষয়",
                topicPlaceholder: "আপনি কি নিয়ে কথা বলবেন?",
                typeLabel: "বক্তৃতার ধরন",
                typePlaceholder: "যেমন: সাক্ষাৎকার, উপস্থাপনা, বিতর্ক",
                repeatLabel: "এটি একই বিষয়ে দ্বিতীয় চেষ্টা",
                startBtn: "রেকর্ডিং শুরু করুন (T)",
                cancelBtn: "বাতিল (B)",
                recordingText: "রেকর্ডিং চলছে",
                recordingSubtext: "মাইক্রোফোনে স্পষ্ট করে কথা বলুন। শেষ হলে বন্ধ ক্লিক করুন বা বাতিল করতে বাতিল ক্লিক করুন।",
                cancelActiveBtn: "বাতিল (X)",
                recordingsSection: "আপনার রেকর্ডিং",
                feedbackSection: "এআই ফিডব্যাক এবং বিশ্লেষণ",
                transcriptionSection: "বক্তৃতার প্রতিলিপি",
                playbackSection: "রেকর্ডিং প্লেব্যাক",
                noRecordings: "কোন রেকর্ডিং পাওয়া যায়নি",
                noRecordingsSubtext: "শুরু করতে আপনার প্রথম রেকর্ডিং তৈরি করুন!",
                playRecBtn: "চালান",
                deleteBtn: "মুছুন",
                recordingTooShort: "রেকর্ডিং খুব ছোট",
                recordingTooShortText: "দুঃখিত! রেকর্ডিংটি ফিডব্যাক তৈরি করার জন্য খুব ছোট ছিল। অনুগ্রহ করে আরও দীর্ঘ বক্তৃতা দিয়ে আবার চেষ্টা করুন।",
                aiAnalyzing: "এআই আপনার বক্তৃতা বিশ্লেষণ করছে"
            }




        };

        document.getElementById('languageSelect').addEventListener('change', function() {
            currentLanguage = this.value;
            updateLanguage();
        });

        function updateLanguage() {
            console.log('Language changed to: ' + currentLanguage);
            
            const lang = translations[currentLanguage] || translations.en;
            
            // Update main content
            document.querySelector('.header h1').textContent = lang.title;
            document.querySelector('.header p').textContent = lang.subtitle;
            document.querySelector('#sessionInfo').innerHTML = `<i class="fas fa-user-circle"></i> ${lang.sessionText} <span id="sessionId">${document.getElementById('sessionId').textContent}</span>`;
            
            // Update language selector
            document.querySelector('label[for="languageSelect"]').textContent = lang.languageLabel;
            document.querySelector('.language-selector').previousElementSibling.querySelector('span').textContent = lang.languageSection;
            
            // Update quick actions
            document.querySelector('.controls-grid').previousElementSibling.querySelector('span').textContent = lang.actionsSection;
            document.querySelector('#recordBtn').innerHTML = `<i class="fas fa-microphone"></i> ${lang.recordBtn}`;
            document.querySelector('.btn-list').innerHTML = `<i class="fas fa-database"></i> ${lang.viewBtn}`;
            document.querySelector('.btn-play').innerHTML = `<i class="fas fa-play"></i> ${lang.playBtn}`;
            document.querySelector('#stopBtn').innerHTML = `<i class="fas fa-stop"></i> ${lang.stopBtn}`;
            
            // Update recording setup
            document.querySelector('#recordingSetup .section-title span').textContent = lang.setupSection;
            document.querySelector('label[for="topicInput"]').textContent = lang.topicLabel;
            document.querySelector('#topicInput').placeholder = lang.topicPlaceholder;
            document.querySelector('label[for="speechTypeInput"]').textContent = lang.typeLabel;
            document.querySelector('#speechTypeInput').placeholder = lang.typePlaceholder;
            document.querySelector('label[for="repeatSpeech"]').textContent = lang.repeatLabel;
            
            // Update recording setup buttons
            const setupButtons = document.querySelectorAll('#recordingSetup .controls-grid .btn');
            setupButtons[0].innerHTML = `<i class="fas fa-play"></i> ${lang.startBtn}`;
            setupButtons[1].innerHTML = `<i class="fas fa-times"></i> ${lang.cancelBtn}`;
            
            // Update recording status
            document.querySelector('.status-text').textContent = lang.recordingText;
            document.querySelector('.status-subtext').textContent = lang.recordingSubtext;
            
            // Update recording status buttons
            const statusButtons = document.querySelectorAll('#recordingStatus .btn');
            statusButtons[0].innerHTML = `<i class="fas fa-stop"></i> ${lang.stopBtn}`;
            statusButtons[1].innerHTML = `<i class="fas fa-times"></i> ${lang.cancelActiveBtn}`;
            
            // Update sections
            document.querySelector('#recordingsList .section-title span').textContent = lang.recordingsSection;
            document.querySelector('#feedbackSection .section-title span').textContent = lang.feedbackSection;
            document.querySelector('#transcriptionSection .section-title span').textContent = lang.transcriptionSection;
            document.querySelector('#audioControls .section-title span').textContent = lang.playbackSection;
            
            // Update feedback loading text
            const feedbackLoadingSpan = document.querySelector('#feedbackLoading span');
            if (feedbackLoadingSpan) {
                feedbackLoadingSpan.textContent = lang.aiAnalyzing;
            }
        }

        async function apiCall(endpoint, options = {}) {
            try {
                const headers = {
                    'Content-Type': 'application/json',
                    ...options.headers
                };
                
                if (sessionId) {
                    headers['Session-ID'] = sessionId;
                }
                
                const response = await fetch(API_BASE + endpoint, {
                    headers: headers,
                    ...options
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'HTTP ' + response.status);
                }
                
                return data;
            } catch (error) {
                console.error('API call failed for ' + endpoint + ':', error);
                showStatus('API Error: ' + error.message, 'error');
                throw error;
            }
        }

        async function checkHealth() {
            try {
                const result = await apiCall('/health');
            } catch (error) {
                showStatus('❌ Cannot connect. Please start the API server.', 'error');
            }
        }

        async function loadLanguages() {
            try {
                const result = await apiCall('/languages');
                if (result.success) {
                    const select = document.getElementById('languageSelect');
                    select.innerHTML = '';
                    
                    result.display_options.forEach(function(option) {
                        const parts = option.split(': ');
                        const code = parts[0];
                        const name = parts[1];
                        const optionElement = document.createElement('option');
                        optionElement.value = code;
                        optionElement.textContent = code + ': ' + name;
                        select.appendChild(optionElement);
                    });
                }
            } catch (error) {
                console.error('Failed to load languages:', error);
            }
        }

        function showStatus(message, type, duration) {
            if (typeof type === 'undefined') type = 'info';
            if (typeof duration === 'undefined') duration = 5000;
            
            const statusDiv = document.getElementById('statusMessage');
            statusDiv.innerHTML = '<div class="status-message status-' + type + '">' + message + '</div>';
            
            if (duration > 0) {
                setTimeout(function() {
                    statusDiv.innerHTML = '';
                }, duration);
            }
        }

        function setupKeyboardShortcuts() {
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    return;
                }

                switch(e.key.toLowerCase()) {
                    case 'r':
                        e.preventDefault();
                        startRecording();
                        break;
                    case 'l':
                        e.preventDefault();
                        listRecordings();
                        break;
                    case 'p':
                        e.preventDefault();
                        showPlayDialog();
                        break;
                    case 'enter':
                        if (isRecording) {
                            e.preventDefault();
                            stopRecording();
                        }
                        break;
                    case 'x':
                        if (isRecording) {
                            e.preventDefault();
                            cancelActiveRecording();
                        }
                        break;
                    case 't':
                        if (document.getElementById('recordingSetup').classList.contains('active')) {
                            e.preventDefault();
                            confirmRecording();
                        }
                        break;
                    case 'b':
                        if (document.getElementById('recordingSetup').classList.contains('active')) {
                            e.preventDefault();
                            cancelRecording();
                        }
                        break;
                }
            });
        }

        function startRecording() {
            if (isRecording) {
                showStatus('Recording already active!', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            document.getElementById('recordingSetup').classList.add('active');
            document.getElementById('recordingsList').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('transcriptionSection').classList.add('hidden');
            document.getElementById('audioControls').classList.add('hidden');
            
            document.getElementById('topicInput').value = '';
            document.getElementById('speechTypeInput').value = '';
            document.getElementById('repeatSpeech').checked = false;
            document.getElementById('topicInput').focus();
        }

        function getSupportedMimeType() {
            const types = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/mp4',
                'audio/ogg;codecs=opus',
                'audio/wav'
            ];
            
            for (let type of types) {
                if (MediaRecorder.isTypeSupported(type)) {
                    console.log('Using MIME type:', type);
                    return type;
                }
            }
            
            console.log('Using default MIME type');
            return '';
        }

        async function convertToWAV(audioBlob) {
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const arrayBuffer = await audioBlob.arrayBuffer();
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                
                const wavArrayBuffer = audioBufferToWav(audioBuffer);
                return new Blob([wavArrayBuffer], { type: 'audio/wav' });
            } catch (error) {
                console.log('WAV conversion failed, using original:', error.message);
                return audioBlob;
            }
        }

        function cancelActiveRecording() {
            if (!isRecording || !mediaRecorder) {
                showStatus('No recording in progress', 'error');
                return;
            }

            window.shouldProcessRecording = false;
            
            try {
                if (mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                }
                
                if (mediaRecorder.stream) {
                    mediaRecorder.stream.getTracks().forEach(function(track) {
                        track.stop();
                    });
                }
            } catch (error) {
                console.log('Error stopping recorder:', error);
            }
            
            audioChunks = [];
            recordedBlob = null;
            isRecording = false;

            document.getElementById('recordingStatus').classList.remove('active');
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('stopBtn').classList.add('hidden');
            document.getElementById('recordingSetup').classList.remove('active');
            document.getElementById('feedbackSection').classList.remove('active');
            document.getElementById('transcriptionSection').classList.add('hidden');
            document.getElementById('audioControls').classList.add('hidden');
            
            showStatus('🚫 Recording cancelled - no analysis performed', 'info');
        }

        function audioBufferToWav(buffer) {
            const length = buffer.length;
            const numberOfChannels = Math.min(buffer.numberOfChannels, 2);
            const sampleRate = buffer.sampleRate;
            
            const arrayBuffer = new ArrayBuffer(44 + length * numberOfChannels * 2);
            const view = new DataView(arrayBuffer);
            
            writeString(view, 0, 'RIFF');
            view.setUint32(4, 36 + length * numberOfChannels * 2, true);
            writeString(view, 8, 'WAVE');
            writeString(view, 12, 'fmt ');
            view.setUint32(16, 16, true);
            view.setUint16(20, 1, true);
            view.setUint16(22, numberOfChannels, true);
            view.setUint32(24, sampleRate, true);
            view.setUint32(28, sampleRate * numberOfChannels * 2, true);
            view.setUint16(32, numberOfChannels * 2, true);
            view.setUint16(34, 16, true);
            writeString(view, 36, 'data');
            view.setUint32(40, length * numberOfChannels * 2, true);
            
            let offset = 44;
            for (let i = 0; i < length; i++) {
                for (let channel = 0; channel < numberOfChannels; channel++) {
                    const sample = Math.max(-1, Math.min(1, buffer.getChannelData(channel)[i]));
                    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
                    offset += 2;
                }
            }
            
            return arrayBuffer;
        }

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        async function confirmRecording() {
            const topic = document.getElementById('topicInput').value.trim();
            const speechType = document.getElementById('speechTypeInput').value.trim();
            
            if (!topic || !speechType) {
                showStatus('Please configure both topic and speech type for analysis', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        sampleRate: 44100,
                        channelCount: 1,
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    }
                });

                const mimeType = getSupportedMimeType();
                const options = mimeType ? { mimeType: mimeType } : {};
                mediaRecorder = new MediaRecorder(stream, options);

                audioChunks = [];
                
                mediaRecorder.ondataavailable = function(event) {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = function() {
                    const actualMimeType = mediaRecorder.mimeType || 'audio/webm';
                    const audioBlob = new Blob(audioChunks, { type: actualMimeType });
                    recordedBlob = audioBlob;
                    
                    if (window.shouldProcessRecording !== false) {
                        console.log('Recording completed. MIME type:', actualMimeType, 'Size:', audioBlob.size);
                        processRecording();
                    }
                    
                    window.shouldProcessRecording = true;
                };

                mediaRecorder.onerror = function(event) {
                    console.error('MediaRecorder error:', event.error);
                    showStatus('Recording error: ' + event.error.message, 'error');
                };

                mediaRecorder.start(1000);
                isRecording = true;

                document.getElementById('recordingSetup').classList.remove('active');
                document.getElementById('recordingStatus').classList.add('active');
                document.getElementById('recordBtn').classList.add('recording');
                document.getElementById('stopBtn').classList.remove('hidden');
                
                showStatus('🎤 Recording initiated! Speech patterns being captured...', 'info', 0);

            } catch (error) {
                console.error('Error starting recording:', error);
                showStatus('❌ Failed to initiate recording: ' + error.message, 'error');
            }
        }

        function stopRecording() {
            if (!isRecording || !mediaRecorder) {
                showStatus('No recording in progress', 'error');
                return;
            }

            window.shouldProcessRecording = true;
            
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(function(track) {
                track.stop();
            });
            isRecording = false;

            document.getElementById('recordingStatus').classList.remove('active');
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('stopBtn').classList.add('hidden');
            
            showStatus('⏹️ Recording completed. Initializing analysis...', 'info', 0);
        }

        function cancelRecording() {
            document.getElementById('recordingSetup').classList.remove('active');
            showStatus('Recording configuration cancelled', 'info');
        }

        async function processRecording() {
            if (!recordedBlob) {
                showStatus('No recording data to process', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            try {
                showStatus('🔄 Processing data...', 'info', 0);

                if (recordedBlob.size === 0) {
                    showStatus('❌ Recording is empty. Please try recording again.', 'error');
                    return;
                }

                if (recordedBlob.size < 1000) {
                    showStatus('❌ Recording too short for analysis. Please record for at least a few seconds.', 'error');
                    return;
                }

                const wavBlob = await convertToWAV(recordedBlob);
                
                const audioBase64 = await new Promise(function(resolve, reject) {
                    const reader = new FileReader();
                    reader.onload = function() { resolve(reader.result); };
                    reader.onerror = reject;
                    reader.readAsDataURL(wavBlob);
                });

                const topic = document.getElementById('topicInput').value.trim();
                const speechType = document.getElementById('speechTypeInput').value.trim();
                const isRepeat = document.getElementById('repeatSpeech').checked;

                let audioData = audioBase64;
                if (audioData.includes(',')) {
                    audioData = audioData.split(',')[1];
                }

                const payload = {
                    topic: topic,
                    speech_type: speechType,
                    language: currentLanguage,
                    audio_data: audioData,
                    audio_format: 'audio/wav',
                    is_repeat: isRepeat
                };

                showStatus('📤 Sending to AI for analysis...', 'info', 0);

                const response = await fetch(API_BASE + '/record', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }

                const result = await response.json();

                if (result.success) {
                    displayInitialResults(result.result);
                    startFeedbackStream(result.result.stream_url);
                    showStatus('✅ Analysis successfully initiated!', 'success');
                } else {
                    showStatus('❌ Processing failed: ' + result.error, 'error');
                }

            } catch (error) {
                console.error('Processing error:', error);
                showStatus('❌ Failed to process data: ' + error.message, 'error');
            }
        }

        function displayInitialResults(result) {
            const hasTranscription = result.transcription && result.transcription.trim().length > 0;
            
            if (hasTranscription) {
                document.getElementById('transcriptionContent').textContent = result.transcription;
                document.getElementById('transcriptionSection').classList.remove('hidden');
            }

            // Show feedback section with loading state
            document.getElementById('feedbackSection').classList.add('active');
            document.getElementById('feedbackLoading').style.display = 'flex';
            document.getElementById('feedbackText').style.display = 'none';
            document.getElementById('feedbackText').innerHTML = '';

            if (recordedBlob) {
                const audioURL = URL.createObjectURL(recordedBlob);
                document.getElementById('audioPlayer').src = audioURL;
                document.getElementById('audioControls').classList.remove('hidden');
            }
        }

        function startFeedbackStream(streamUrl) {
            // Close any existing stream
            if (feedbackEventSource) {
                feedbackEventSource.close();
            }

            // Add language parameter to stream URL
            const urlWithLang = streamUrl + '?language=' + encodeURIComponent(currentLanguage);
            feedbackEventSource = new EventSource(urlWithLang);
            
            let scrollThrottle = null;

            feedbackEventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);

                    if (data.error) {
                        console.error('Stream error:', data.error);
                        showStatus('❌ Analysis failed: ' + data.error, 'error');
                        feedbackEventSource.close();
                        return;
                    }

                    if (data.type === 'chunk' && data.content) {
                        // Hide loading and show text on first chunk
                        if (document.getElementById('feedbackLoading').style.display !== 'none') {
                            document.getElementById('feedbackLoading').style.display = 'none';
                            document.getElementById('feedbackText').style.display = 'block';
                        }

                        // Efficiently append content without creating spans
                        const feedbackText = document.getElementById('feedbackText');
                        feedbackText.textContent += data.content;

                        // Throttle scroll operations to improve performance
                        if (!scrollThrottle) {
                            scrollThrottle = setTimeout(() => {
                                feedbackText.scrollTop = feedbackText.scrollHeight;
                                scrollThrottle = null;
                            }, 50);
                        }
                    }

                    if (data.type === 'complete') {
                        console.log('✓ Analysis completed, chunks received:', data.total_chunks || 'unknown');
                        // Hide loading indicator
                        document.getElementById('feedbackLoading').style.display = 'none';
                        feedbackEventSource.close();
                        feedbackEventSource = null;

                        // Clear any pending scroll
                        if (scrollThrottle) {
                            clearTimeout(scrollThrottle);
                            scrollThrottle = null;
                        }

                        // Final scroll to bottom
                        const feedbackText = document.getElementById('feedbackText');
                        feedbackText.scrollTop = feedbackText.scrollHeight;

                        // Show copy button
                        document.getElementById('copyFeedbackBtn').style.display = 'block';
                    }
                } catch (error) {
                    console.error('Error parsing stream data:', error);
                }
            };
            
            feedbackEventSource.onerror = function(event) {
                console.error('EventSource error:', event);
                feedbackEventSource.close();
                feedbackEventSource = null;

                // Only show error if no feedback was received
                const feedbackText = document.getElementById('feedbackText');
                if (feedbackText.textContent.trim() === '') {
                    document.getElementById('feedbackLoading').style.display = 'none';
                    showStatus('❌ Analysis failed: Connection error', 'error');
                }
            };
        }

        async function listRecordings() {
            try {
                showStatus('📋 Loading recordings...', 'info');
                const result = await apiCall('/recordings');
                
                if (result.success) {
                    recordings = result.recordings || [];
                    displayRecordingsList();
                    document.getElementById('recordingsList').classList.add('active');
                    document.getElementById('recordingSetup').classList.remove('active');
                    document.getElementById('feedbackSection').classList.remove('active');
                    showStatus(recordings.length === 0 ? '📁 Recording list is empty' : 'Found ' + recordings.length + ' recordings', 'info');
                } else {
                    recordings = [];
                    displayRecordingsList();
                    document.getElementById('recordingsList').classList.add('active');
                    showStatus('📁 Recording list not yet initialized', 'info');
                }
            } catch (error) {
                recordings = [];
                displayRecordingsList();
                document.getElementById('recordingsList').classList.add('active');
                document.getElementById('recordingSetup').classList.remove('active');
                document.getElementById('feedbackSection').classList.remove('active');
                showStatus('📁 Recording list not yet initialized', 'info');
            }
        }

        function displayRecordingsList() {
            const container = document.getElementById('recordingsContainer');
            const lang = translations[currentLanguage] || translations.en;
    
            if (recordings.length === 0) {
                container.innerHTML = `<div class="recording-item" style="background: linear-gradient(135deg, rgba(25, 25, 50, 0.9), rgba(60, 45, 120, 0.6));"><div class="recording-info"><h4 style="color: var(--text-primary);">📁 ${lang.noRecordings}</h4><div class="recording-meta" style="color: var(--text-secondary);">${lang.noRecordingsSubtext}</div></div></div>`;
                return;
            }

            const recordingItems = recordings.map(function(recording) {
                const safeFilename = recording.filename.replace(/'/g, "\\\\'");
                return `<div class="recording-item"><div class="recording-info"><h4><i class="fas fa-file-audio"></i> ${recording.filename}</h4><div class="recording-meta">Size: ${formatFileSize(recording.size)} | Created: ${formatDate(recording.created)}</div></div><div class="recording-actions"><button class="btn btn-play btn-small" onclick="playRecording('${safeFilename}')"><i class="fas fa-play"></i> ${lang.playRecBtn}</button><button class="btn btn-stop btn-small" onclick="deleteRecording('${safeFilename}')" style="background: var(--danger-gradient);"><i class="fas fa-trash"></i> ${lang.deleteBtn}</button></div></div>`;
            });

            container.innerHTML = recordingItems.join('');
        }

        async function playRecording(filename) {
            try {
                showStatus('▶️ Loading recording: ' + filename + '...', 'info');
                const response = await fetch(API_BASE + '/recordings/' + filename, {
                    headers: {
                        'Session-ID': sessionId
                    }
                });
                if (!response.ok) {
                    throw new Error('Failed to load recording: ' + response.status);
                }
                const audioBlob = await response.blob();
                const audioURL = URL.createObjectURL(audioBlob);
                document.getElementById('audioPlayer').src = audioURL;
                document.getElementById('audioControls').classList.remove('hidden');
                document.getElementById('audioPlayer').play();
                showStatus('🔊 Playing recording: ' + filename, 'success');
            } catch (error) {
                showStatus('❌ Failed to play recording', 'error');
            }
        }

        async function deleteRecording(filename) {
            if (!confirm('Are you sure you want to delete "' + filename + '" from the recording list?')) {
                return;
            }
            try {
                const result = await apiCall('/recordings/' + filename, { method: 'DELETE' });
                if (result.success) {
                    showStatus('✅ Deleted from recording list: ' + filename, 'success');
                    listRecordings();
                } else {
                    showStatus('❌ Failed to delete from recording list', 'error');
                }
            } catch (error) {
                console.error('Error deleting recording:', error);
            }
        }

        function showPlayDialog() {
            listRecordings();
        }

        function formatFileSize(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }

        function formatDate(timestamp) {
            return new Date(timestamp * 1000).toLocaleString();
        }

        // Tab Switching
        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });

            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.add('active');
            event.target.closest('.nav-tab').classList.add('active');
        }

        // Practice Scenarios
        const scenarios = {
            elevator: {
                topic: "30-Second Elevator Pitch",
                type: "Professional Introduction"
            },
            persuasive: {
                topic: "Convincing Argument on My Position",
                type: "Persuasive Speech"
            },
            toast: {
                topic: "Wedding Toast for the Couple",
                type: "Special Occasion Speech"
            },
            intro: {
                topic: "Introduction to Who I Am",
                type: "Professional, Formal Introduction"
            },
            demo: {
                topic: "Product or Idea Presentation",
                type: "Demonstration Speech"
            },
            story: {
                topic: "Personal Story with a Lesson",
                type: "Storytelling"
            },
            interview: {
                topic: "Tell Me About Yourself - Job Interview",
                type: "Professional Interview Response"
            },
            debate: {
                topic: "Counterargument on a Controversial Topic",
                type: "Debate Speech"
            }
        };

        function loadScenario(scenarioKey) {
            const scenario = scenarios[scenarioKey];
            if (!scenario) return;

            // Switch to record tab
            const recordTab = document.querySelectorAll('.nav-tab')[0];
            recordTab.click();

            // Small delay to ensure tab is switched
            setTimeout(() => {
                // Make sure recording setup is visible
                document.getElementById('recordingSetup').classList.add('active');
                document.getElementById('recordingsList').classList.remove('active');
                document.getElementById('feedbackSection').classList.remove('active');
                document.getElementById('recordingStatus').classList.remove('active');

                // Fill in the form
                document.getElementById('topicInput').value = scenario.topic;
                document.getElementById('speechTypeInput').value = scenario.type;

                // Show confirmation
                showStatus('✓ Scenario loaded: ' + scenario.topic, 'success');

                // Scroll to the form inputs
                document.getElementById('topicInput').scrollIntoView({ behavior: 'smooth', block: 'center' });
            }, 150);
        }

        // Copy Feedback
        function copyFeedback() {
            const feedbackText = document.getElementById('feedbackText').innerText;

            navigator.clipboard.writeText(feedbackText).then(() => {
                const btn = document.getElementById('copyFeedbackBtn');
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                btn.style.background = 'rgba(34, 197, 94, 0.2)';
                btn.style.borderColor = 'rgba(34, 197, 94, 0.3)';

                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.style.background = '';
                    btn.style.borderColor = '';
                }, 2000);
            }).catch(err => {
                showStatus('Failed to copy feedback', 'error');
            });
        }

    </script>
</body>
</html>
"""
    else:
        return f"API is running. Frontend at http://localhost:3000 (PRODUCTION_MODE={PRODUCTION_MODE})"

@app.route('/api/session', methods=['DELETE'])
def clear_session():
    session_id = get_session_id(request)
    
    if PRODUCTION_MODE:
        success = clear_all_session_recordings(session_id)
        if success:
            return jsonify({
                'success': True,
                'message': 'Session data cleared (production mode)'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404
    
    try:
        speech_evaluator.data_manager.clear_session_data()
        return jsonify({
            'success': True,
            'message': 'Session data cleared successfully'
        })
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    print(f"🚀 Binding to port {port}")
    print(f"🌐 Host: 0.0.0.0")
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False,
        threaded=True
    )