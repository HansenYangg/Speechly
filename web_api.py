import os
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

try:
    from speech_evaluator import SpeechEvaluator
    from config_validator import ConfigValidator
    from exceptions import *
    from logger import setup_logger
    from validator import Validator
    PRODUCTION_MODE = False
    print("🏠 Development mode: All modules loaded")
except ImportError as e:
    PRODUCTION_MODE = True
    print(f"🌐 Production mode: {e}")
    
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg, **kwargs): print(f"ERROR: {msg}")
    
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
    print(f"📁 Saved recording to session {session_id}: {filename}")
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

logger = setup_logger(__name__)

if PRODUCTION_MODE:
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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
                'error': 'Recording not found'
            }), 404
        
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
                language_instruction = f"Try to tailor the feedback based off the context of the user presentation. Make sure to do this in English."
                
                MIN_RECORDING_DURATION = 5
                SHORT_RECORDING_THRESHOLD = 30
                
                if MIN_RECORDING_DURATION < duration < SHORT_RECORDING_THRESHOLD:
                    prompt = (
                        f"The following speech is pretty short and may lack sufficient content. "
                        f"Please evaluate and critique it given the following topic and type of the speech. "
                        f"Give appropriate feedback accordingly based on these:\n\n"
                        f"Speech topic: '{topic}'\n"
                        f"Speech type: {speech_type}\n"
                        f"Transcription: '{transcription_text}'\n\n"
                        f"{repeat_context}\n"
                        f"Please grade out of a total 100 points and give constructive feedback without being overly nice. "
                        f"Provide scores out of 20 for these following categories: Structure, Content, Delivery and Voice, Overall Flow and Rhythm, and Conclusion. Add up the sum of these scores to get the total out of 100 points.\n"
                        f"Don't always have scores in increments of 5, use more varied/granular scores. \n"
                        f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc.\n"
                        f"Note good things they did and things they can improve on, and don't be overly nice.\n"
                        f"Please put adequate spacing. There MUST be a clear separating line between each major point for clarity.\n" 
                        f"{language_instruction}"
                    )
                else:
                    prompt = (
                        f"Please evaluate and critique it given the following topic and type of the speech. "
                        f"Give appropriate feedback accordingly based on this information about the presentation:\n\n"
                        f"Speech topic: '{topic}'\n"
                        f"Speech type: {speech_type}\n"
                        f"Transcription: '{transcription_text}'\n\n"
                        f"{repeat_context}\n"
                        f"Please grade out of a total 100 points and give constructive feedback without being overly nice. "
                        f"Provide scores out of 20 for these following categories: Structure, Content, Delivery and Voice, Overall Flow and Rhythm, and Conclusion. Add up the sum of these scores to get the total out of 100 points.\n"
                        f"Don't always have scores in increments of 5, use more varied/granular scores. \n"
                        f"Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc.\n"
                        f"Note good things they did and things they can improve on, and don't be overly nice.\n"
                        f"Please put adequate spacing. There MUST be a clear separating line between each major point for clarity.\n" 
                        f"{language_instruction}"
                    )
                
                return prompt
            
            feedback_prompt = build_feedback_prompt(
                topic, speech_type, transcription_text, duration, 'en', False
            )
            
            # Stream the response from OpenAI
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "user", "content": feedback_prompt}
                ],
                max_tokens=1500,
                temperature=0.5,
                stream=True
            )
            
            full_feedback = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_feedback += content
                    yield f"data: {json.dumps({'content': content, 'type': 'chunk'})}\n\n"
            
            # Send completion message
            yield f"data: {json.dumps({'type': 'complete', 'full_feedback': full_feedback})}\n\n"
            
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
    if PRODUCTION_MODE:
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Speech Evaluator</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            --secondary-gradient: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            --success-gradient: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            --warning-gradient: linear-gradient(135deg, #f9ca24 0%, #f0932b 100%);
            --danger-gradient: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
            --dark-gradient: linear-gradient(135deg, #2c3e50 0%, #4a6741 100%);
            --feedback-gradient: linear-gradient(135deg, rgba(147, 112, 219, 0.95) 0%, rgba(123, 104, 238, 0.95) 50%, rgba(138, 43, 226, 0.95) 100%);
            --glass-bg: rgba(255, 255, 255, 0.1);
            --glass-border: rgba(255, 255, 255, 0.2);
            --text-primary: #2d3748;
            --text-secondary: #718096;
            --shadow-xl: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--primary-gradient);
            min-height: 100vh;
            color: var(--text-primary);
            overflow-x: hidden;
        }

        .floating-shapes {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        }

        .shape {
            position: absolute;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 50%;
            animation: float 20s infinite linear;
        }

        .shape:nth-child(1) { width: 80px; height: 80px; top: 20%; left: 10%; animation-delay: 0s; }
        .shape:nth-child(2) { width: 120px; height: 120px; top: 60%; left: 80%; animation-delay: -5s; }
        .shape:nth-child(3) { width: 60px; height: 60px; top: 30%; left: 70%; animation-delay: -10s; }
        .shape:nth-child(4) { width: 100px; height: 100px; top: 80%; left: 20%; animation-delay: -15s; }

        @keyframes float {
            0% { transform: translateY(0px) rotate(0deg); opacity: 0.7; }
            50% { transform: translateY(-20px) rotate(180deg); opacity: 1; }
            100% { transform: translateY(0px) rotate(360deg); opacity: 0.7; }
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
            z-index: 2;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
            animation: slideInDown 1s ease-out;
        }

        .header-icon {
            font-size: 4rem;
            background: var(--success-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }

        .header h1 {
            font-size: 3.5rem;
            font-weight: 800;
            color: white;
            text-shadow: 0 4px 20px rgba(0,0,0,0.3);
            margin-bottom: 15px;
            letter-spacing: -0.02em;
        }

        .header p {
            font-size: 1.3rem;
            color: rgba(255,255,255,0.9);
            font-weight: 400;
            max-width: 600px;
            margin: 0 auto;
        }

        .session-info {
            text-align: center;
            margin-bottom: 20px;
            padding: 10px;
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            color: rgba(255,255,255,0.8);
            font-size: 0.9rem;
        }

        .glass-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 24px;
            padding: 40px;
            margin-bottom: 30px;
            box-shadow: var(--shadow-xl);
            animation: slideInUp 1s ease-out;
            position: relative;
            overflow: hidden;
        }

        .glass-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.4), transparent);
        }

        .section-title {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-bottom: 30px;
            font-size: 1.5rem;
            font-weight: 700;
            color: #2d3748;
            min-height: 40px;
        }

        .section-icon {
            width: 40px;
            height: 40px;
            background: var(--success-gradient);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.2rem;
        }

        .language-selector {
            margin-bottom: 40px;
        }

        .language-selector label {
            display: block;
            margin-bottom: 15px;
            font-weight: 600;
            color: white;
            font-size: 16px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        .custom-select {
            position: relative;
            margin-top: 10px;
        }

        .custom-select select {
            width: 100%;
            padding: 20px 60px 20px 28px;
            background: linear-gradient(135deg, rgba(79, 172, 254, 0.2) 0%, rgba(0, 242, 254, 0.1) 100%);
            border: 2px solid transparent;
            border-radius: 20px;
            font-size: 16px;
            color: #2d3748;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            appearance: none;
            backdrop-filter: blur(20px);
            box-shadow: 
                0 8px 32px rgba(79, 172, 254, 0.1),
                inset 0 1px 0 rgba(255, 255, 255, 0.2),
                0 1px 0 rgba(255, 255, 255, 0.1);
            font-weight: 500;
            position: relative;
            outline: none;
        }

        .custom-select select:hover {
            transform: translateY(-3px) scale(1.02);
            background: linear-gradient(135deg, rgba(79, 172, 254, 0.3) 0%, rgba(0, 242, 254, 0.15) 100%);
            box-shadow: 
                0 15px 45px rgba(79, 172, 254, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.3),
                0 1px 0 rgba(255, 255, 255, 0.2);
        }

        .custom-select select:focus {
            transform: translateY(-2px);
            background: linear-gradient(135deg, rgba(79, 172, 254, 0.25) 0%, rgba(0, 242, 254, 0.12) 100%);
            border-color: rgba(79, 172, 254, 0.5);
            box-shadow: 
                0 0 0 4px rgba(79, 172, 254, 0.2),
                0 12px 40px rgba(79, 172, 254, 0.15),
                inset 0 1px 0 rgba(255, 255, 255, 0.25);
        }

        .custom-select select option {
            background: linear-gradient(135deg, #2d3748 0%, #1a202c 100%);
            color: #2d3748;
            padding: 15px;
            border: none;
            font-weight: 500;
        }

        .custom-select select option:hover {
            background: linear-gradient(135deg, rgba(79, 172, 254, 0.3) 0%, rgba(0, 242, 254, 0.2) 100%);
        }

        .custom-select::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, transparent 50%, rgba(255,255,255,0.05) 100%);
            border-radius: 20px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .custom-select:hover::before {
            opacity: 1;
        }

        .custom-select::after {
            content: '\\f0d7';
            font-family: 'Font Awesome 6 Free';
            font-weight: 900;
            position: absolute;
            right: 25px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.9);
            pointer-events: none;
            font-size: 20px;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        .custom-select:hover::after {
            color: white;
            transform: translateY(-50%) scale(1.2) rotate(180deg);
            text-shadow: 0 0 12px rgba(79, 172, 254, 0.6);
        }

        .custom-select select:focus + ::after {
            color: #4facfe;
            transform: translateY(-50%) scale(1.1) rotate(180deg);
        }

        .controls-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .btn {
            padding: 20px 30px;
            border: none;
            border-radius: 20px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            box-shadow: var(--shadow-lg);
            min-height: 60px;
            min-width: 200px;
            white-space: nowrap;
        }

        .btn::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.5s;
        }

        .btn:hover::before {
            left: 100%;
        }

        .btn:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(0,0,0,0.2);
        }

        .btn:active {
            transform: translateY(-4px) scale(0.98);
        }

        .btn-record {
            background: var(--danger-gradient);
            color: white;
        }

        .btn-record.recording {
            animation: recordingPulse 1.5s infinite;
            background: linear-gradient(135deg, #ff3838 0%, #c23616 100%);
        }

        .btn-list {
            background: var(--dark-gradient);
            color: white;
        }

        .btn-play {
            background: var(--success-gradient);
            color: white;
        }

        .btn-stop {
            background: var(--warning-gradient);
            color: white;
        }

        .btn-secondary {
            background: rgba(255,255,255,0.1);
            color: white;
            border: 2px solid rgba(255,255,255,0.3);
        }

        @keyframes recordingPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(255, 56, 56, 0.7); }
            50% { transform: scale(1.05); box-shadow: 0 0 0 15px rgba(255, 56, 56, 0); }
        }

        .recording-setup {
            display: none;
            margin-bottom: 40px;
        }

        .recording-setup.active {
            display: block;
            animation: slideInUp 0.5s ease-out;
        }

        .form-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }

        .input-group {
            position: relative;
        }

        .input-group label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: white;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            min-height: 20px;
        }

        .input-group input {
            width: 100%;
            padding: 18px 24px;
            background: rgba(255,255,255,0.1);
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 16px;
            font-size: 16px;
            color: white;
            transition: all 0.3s ease;
        }

        .input-group input:focus {
            outline: none;
            border-color: rgba(255,255,255,0.4);
            background: rgba(255,255,255,0.15);
        }

        .input-group input::placeholder {
            color: rgba(255,255,255,0.6);
        }

        .checkbox-wrapper {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 20px;
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            margin-top: 20px;
        }

        .checkbox-wrapper input[type="checkbox"] {
            width: 20px;
            height: 20px;
            accent-color: #4facfe;
        }

        .recording-status {
            text-align: center;
            margin: 40px 0;
            display: none;
        }

        .recording-status.active {
            display: block;
            animation: slideInUp 0.5s ease-out;
        }

        .recording-indicator {
            width: 80px;
            height: 80px;
            background: var(--danger-gradient);
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            animation: recordingPulse 1s infinite;
            box-shadow: var(--shadow-lg);
        }

        .recording-indicator i {
            font-size: 2rem;
            color: white;
        }

        .status-text {
            font-size: 1.5rem;
            font-weight: 700;
            color: white;
            margin-bottom: 10px;
        }

        .status-subtext {
            font-size: 1.1rem;
            color: rgba(255,255,255,0.8);
            margin-bottom: 30px;
        }

        .recordings-list {
            display: none;
            margin-top: 30px;
        }

        .recordings-list.active {
            display: block;
            animation: slideInUp 0.5s ease-out;
        }

        .recordings-grid {
            display: grid;
            gap: 20px;
            margin-top: 20px;
        }

        .recording-item {
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 20px;
            padding: 25px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }

        .recording-item:hover {
            background: rgba(255,255,255,0.15);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .recording-info h4 {
            color: white;
            font-size: 1.2rem;
            margin-bottom: 8px;
        }

        .recording-meta {
            color: rgba(255,255,255,0.7);
            font-size: 0.9rem;
        }

        .recording-actions {
            display: flex;
            gap: 12px;
        }

        .btn-small {
            padding: 12px 20px;
            font-size: 14px;
            border-radius: 12px;
            min-width: 100px;
            min-height: 44px;
        }

        /* ENHANCED FEEDBACK SECTION STYLES */
        .feedback-section {
            display: none;
            margin-top: 40px;
        }

        .feedback-section.active {
            display: block;
            animation: slideInUp 0.5s ease-out;
        }

        .feedback-content {
            background: var(--feedback-gradient);
            backdrop-filter: blur(25px);
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 25px;
            padding: 35px;
            margin-top: 25px;
            color: white;
            line-height: 1.8;
            font-size: 16px;
            position: relative;
            overflow: hidden;
            box-shadow: 
                0 25px 50px rgba(123, 104, 238, 0.4),
                inset 0 2px 0 rgba(255, 255, 255, 0.4),
                0 0 60px rgba(147, 112, 219, 0.3);
            animation: feedbackGlow 3s ease-in-out infinite alternate;
        }

        @keyframes feedbackGlow {
            0% { box-shadow: 0 25px 50px rgba(123, 104, 238, 0.4), inset 0 2px 0 rgba(255, 255, 255, 0.4), 0 0 60px rgba(147, 112, 219, 0.3); }
            100% { box-shadow: 0 30px 60px rgba(123, 104, 238, 0.6), inset 0 2px 0 rgba(255, 255, 255, 0.5), 0 0 80px rgba(147, 112, 219, 0.5); }
        }

        .feedback-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: 
                radial-gradient(circle at 20% 20%, rgba(255, 255, 255, 0.1) 0%, transparent 30%),
                radial-gradient(circle at 80% 80%, rgba(255, 255, 255, 0.08) 0%, transparent 30%),
                radial-gradient(circle at 40% 70%, rgba(147, 112, 219, 0.1) 0%, transparent 40%);
            animation: bubbleFloat 15s ease-in-out infinite;
            pointer-events: none;
        }

        @keyframes bubbleFloat {
            0%, 100% { transform: translate(0, 0) rotate(0deg); }
            33% { transform: translate(30px, -30px) rotate(120deg); }
            66% { transform: translate(-20px, 20px) rotate(240deg); }
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
                radial-gradient(circle at 60% 30%, rgba(255, 255, 255, 0.05) 0%, transparent 50%);
            pointer-events: none;
            animation: shimmer 8s ease-in-out infinite;
        }

        @keyframes shimmer {
            0%, 100% { opacity: 0.5; transform: translateX(-10px); }
            50% { opacity: 1; transform: translateX(10px); }
        }

        .feedback-content .feedback-text {
            position: relative;
            z-index: 2;
            text-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
            font-weight: 500;
        }

        .feedback-streaming {
            opacity: 0;
            animation: fadeInText 0.3s ease-out forwards;
        }

        @keyframes fadeInText {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .feedback-loading {
            display: flex;
            align-items: center;
            gap: 15px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 600;
            justify-content: center;
            padding: 20px;
        }

        .feedback-loading .loading-dots {
            display: flex;
            gap: 5px;
        }

        .feedback-loading .loading-dots span {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.8);
            animation: loadingDots 1.5s ease-in-out infinite;
        }

        .feedback-loading .loading-dots span:nth-child(1) { animation-delay: 0s; }
        .feedback-loading .loading-dots span:nth-child(2) { animation-delay: 0.2s; }
        .feedback-loading .loading-dots span:nth-child(3) { animation-delay: 0.4s; }

        @keyframes loadingDots {
            0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
            40% { transform: scale(1.2); opacity: 1; }
        }

        .transcription-section {
            background: rgba(255,255,255,0.9);
            border-left: 4px solid #00f2fe;
            padding: 30px;
            border-radius: 16px;
            margin-top: 20px;
            backdrop-filter: blur(10px);
            color: #2d3748;
            line-height: 1.6;
        }

        .status-message {
            padding: 20px 30px;
            border-radius: 16px;
            margin: 20px 0;
            text-align: center;
            font-weight: 600;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }

        .status-success {
            background: rgba(79, 172, 254, 0.2);
            color: #4facfe;
            border-color: #4facfe;
        }

        .status-error {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
            border-color: #ff6b6b;
        }

        .status-info {
            background: rgba(249, 202, 36, 0.2);
            color: #f9ca24;
            border-color: #f9ca24;
        }

        .audio-controls {
            margin: 30px 0;
            text-align: center;
        }

        .audio-controls audio {
            width: 100%;
            max-width: 500px;
            border-radius: 20px;
            background: rgba(255,255,255,0.1);
        }

        .hidden {
            display: none !important;
        }

        .loading {
            display: inline-block;
            width: 24px;
            height: 24px;
            border: 3px solid rgba(255,255,255,0.3);
            border-top: 3px solid white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes slideInUp {
            from {
                opacity: 0;
                transform: translateY(50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }

        @media (max-width: 768px) {
            .container {
                padding: 15px;
            }
            
            .header h1 {
                font-size: 2.5rem;
            }
            
            .glass-card {
                padding: 25px;
            }
            
            .controls-grid {
                grid-template-columns: 1fr;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .recording-item {
                flex-direction: column;
                gap: 20px;
                text-align: center;
            }
            
            .feedback-content {
                padding: 25px;
                font-size: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="floating-shapes">
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
            <p>Transform your speaking skills with cutting-edge AI-powered feedback and analysis</p>
        </div>

        <div class="session-info" id="sessionInfo">
            <i class="fas fa-user-circle"></i> Your Session: <span id="sessionId">Connecting...</span>
        </div>

        <div class="glass-card">
            <div class="section-title">
                <div class="section-icon">
                    <i class="fas fa-globe"></i>
                </div>
                <span>Language Selection</span>
            </div>
            
            <div class="language-selector">
                <label for="languageSelect" style="color: white; font-weight: 600;">Choose your target language:</label>
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
                    <i class="fas fa-play-circle"></i>
                </div>
                <span>Quick Actions</span>
            </div>

            <div class="controls-grid">
                <button class="btn btn-record" id="recordBtn" onclick="startRecording()">
                    <i class="fas fa-microphone"></i>
                    Record Speech (R)
                </button>
                <button class="btn btn-list" onclick="listRecordings()">
                    <i class="fas fa-list"></i>
                    View Recordings (L)
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
                        <i class="fas fa-cog"></i>
                    </div>
                    <span>Recording Setup</span>
                </div>
                
                <div class="form-grid">
                    <div class="input-group">
                        <label for="topicInput">Speech Topic</label>
                        <input type="text" id="topicInput" placeholder="What will you be speaking about?" maxlength="200">
                    </div>
                    <div class="input-group">
                        <label for="speechTypeInput">Speech Type</label>
                        <input type="text" id="speechTypeInput" placeholder="e.g., interview, presentation, debate" maxlength="100">
                    </div>
                </div>
                
                <div class="checkbox-wrapper">
                    <input type="checkbox" id="repeatSpeech">
                    <label for="repeatSpeech" style="color: white; text-transform: none; letter-spacing: normal;">This is a repeat attempt on the same topic</label>
                </div>
                
                <div class="controls-grid" style="margin-top: 30px;">
                    <button class="btn btn-record" onclick="confirmRecording()">
                        <i class="fas fa-play"></i>
                        Start Recording (T)
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
                <div class="status-text">Recording in Progress</div>
                <div class="status-subtext">Speak clearly into your microphone. Click stop when finished or cancel to discard.</div>
                <div style="margin-top: 20px; display: flex; gap: 15px; justify-content: center;">
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
                    <span>Your Recordings</span>
                </div>
                <div class="recordings-grid" id="recordingsContainer">
                </div>
            </div>

            <div class="feedback-section" id="feedbackSection">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-brain"></i>
                    </div>
                    <span>AI Feedback & Analysis</span>
                </div>
                <div class="feedback-content" id="feedbackContent">
                    <div class="feedback-loading" id="feedbackLoading">
                        <i class="fas fa-robot" style="font-size: 1.5rem;"></i>
                        <span>AI is analyzing your speech</span>
                        <div class="loading-dots">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                    </div>
                    <div class="feedback-text" id="feedbackText" style="display: none;"></div>
                </div>
            </div>

            <div class="transcription-section hidden" id="transcriptionSection">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-file-alt"></i>
                    </div>
                    <span>Speech Transcription</span>
                </div>
                <div id="transcriptionContent">
                </div>
            </div>

            <div class="audio-controls hidden" id="audioControls">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-volume-up"></i>
                    </div>
                    <span>Recording Playback</span>
                </div>
                <audio controls id="audioPlayer">
                    Your browser does not support the audio element.
                </audio>
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

        const API_BASE = 'https://speakeasyy.onrender.com/api';

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
                recordingTooShortText: "Sorry! The recording was too short to generate feedback for. Please try again with a longer speech."
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
            document.querySelector('.btn-list').innerHTML = `<i class="fas fa-list"></i> ${lang.viewBtn}`;
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
                showStatus('❌ Cannot connect to backend. Please start the API server.', 'error');
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
                showStatus('Already recording!', 'error');
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
            
            showStatus('🚫 Recording cancelled - no feedback generated', 'info');
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
                showStatus('Please fill in both topic and speech type', 'error');
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
                
                showStatus('🎤 Recording started! Speak now...', 'info', 0);

            } catch (error) {
                console.error('Error starting recording:', error);
                showStatus('❌ Failed to start recording: ' + error.message, 'error');
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
            
            showStatus('⏹️ Recording stopped. Processing...', 'info', 0);
        }

        function cancelRecording() {
            document.getElementById('recordingSetup').classList.remove('active');
            showStatus('Recording cancelled', 'info');
        }

        async function processRecording() {
            if (!recordedBlob) {
                showStatus('No recording to process', 'error');
                return;
            }

            if (!sessionId) {
                showStatus('Session not initialized!', 'error');
                return;
            }

            try {
                showStatus('🔄 Processing recording...', 'info', 0);

                if (recordedBlob.size === 0) {
                    showStatus('❌ Recording is empty. Please try recording again.', 'error');
                    return;
                }

                if (recordedBlob.size < 1000) {
                    showStatus('❌ Recording too short. Please record for at least a few seconds.', 'error');
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
                    showStatus('✅ Recording processed successfully!', 'success');
                } else {
                    showStatus('❌ Processing failed: ' + result.error, 'error');
                }

            } catch (error) {
                console.error('Processing error:', error);
                showStatus('❌ Failed to process recording: ' + error.message, 'error');
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

            feedbackEventSource = new EventSource(streamUrl);
            
            feedbackEventSource.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    
                    if (data.error) {
                        console.error('Stream error:', data.error);
                        showStatus('❌ Feedback generation failed: ' + data.error, 'error');
                        feedbackEventSource.close();
                        return;
                    }
                    
                    if (data.type === 'chunk' && data.content) {
                        // Hide loading and show text on first chunk
                        if (document.getElementById('feedbackLoading').style.display !== 'none') {
                            document.getElementById('feedbackLoading').style.display = 'none';
                            document.getElementById('feedbackText').style.display = 'block';
                        }
                        
                        // Append the new content with streaming animation
                        const feedbackText = document.getElementById('feedbackText');
                        const newSpan = document.createElement('span');
                        newSpan.className = 'feedback-streaming';
                        newSpan.textContent = data.content;
                        feedbackText.appendChild(newSpan);
                        
                        // Scroll to bottom to follow the text
                        feedbackText.scrollTop = feedbackText.scrollHeight;
                    }
                    
                    if (data.type === 'complete') {
                        console.log('Feedback streaming completed');
                        feedbackEventSource.close();
                        feedbackEventSource = null;
                        
                        // Remove streaming classes
                        const streamingElements = document.querySelectorAll('.feedback-streaming');
                        streamingElements.forEach(el => el.classList.remove('feedback-streaming'));
                    }
                } catch (error) {
                    console.error('Error parsing stream data:', error);
                }
            };
            
            feedbackEventSource.onerror = function(event) {
                console.error('EventSource error:', event);
                showStatus('❌ Lost connection to feedback stream', 'error');
                feedbackEventSource.close();
                feedbackEventSource = null;
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
                    showStatus(recordings.length === 0 ? '📁 No recordings found' : 'Found ' + recordings.length + ' recordings', 'info');
                } else {
                    recordings = [];
                    displayRecordingsList();
                    document.getElementById('recordingsList').classList.add('active');
                    showStatus('📁 No recordings saved yet', 'info');
                }
            } catch (error) {
                recordings = [];
                displayRecordingsList();
                document.getElementById('recordingsList').classList.add('active');
                document.getElementById('recordingSetup').classList.remove('active');
                document.getElementById('feedbackSection').classList.remove('active');
                showStatus('📁 No recordings saved yet', 'info');
            }
        }

        function displayRecordingsList() {
            const container = document.getElementById('recordingsContainer');
            const lang = translations[currentLanguage] || translations.en;
    
            if (recordings.length === 0) {
                container.innerHTML = `<div class="recording-item" style="background: rgba(255,255,255,0.9);"><div class="recording-info"><h4 style="color: #2d3748;">📁 ${lang.noRecordings}</h4><div class="recording-meta" style="color: #2d3748;">${lang.noRecordingsSubtext}</div></div></div>`;
                return;
            }

            const recordingItems = recordings.map(function(recording) {
                const safeFilename = recording.filename.replace(/'/g, "\\\\'");
                return `<div class="recording-item"><div class="recording-info"><h4 style="color: #2d3748;"><i class="fas fa-file-audio"></i> ${recording.filename}</h4><div class="recording-meta">Size: ${formatFileSize(recording.size)} | Created: ${formatDate(recording.created)}</div></div><div class="recording-actions"><button class="btn btn-play btn-small" onclick="playRecording('${safeFilename}')"><i class="fas fa-play"></i> ${lang.playRecBtn}</button><button class="btn btn-stop btn-small" onclick="deleteRecording('${safeFilename}')" style="background: var(--danger-gradient);"><i class="fas fa-trash"></i> ${lang.deleteBtn}</button></div></div>`;
            });

            container.innerHTML = recordingItems.join('');
        }

        async function playRecording(filename) {
            try {
                showStatus('▶️ Loading ' + filename + '...', 'info');
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
                showStatus('🔊 Playing ' + filename, 'success');
            } catch (error) {
                showStatus('❌ Failed to play recording', 'error');
            }
        }

        async function deleteRecording(filename) {
            if (!confirm('Are you sure you want to delete "' + filename + '"?')) {
                return;
            }
            try {
                const result = await apiCall('/recordings/' + filename, { method: 'DELETE' });
                if (result.success) {
                    showStatus('✅ Deleted ' + filename, 'success');
                    listRecordings();
                } else {
                    showStatus('❌ Failed to delete recording', 'error');
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
    </script>
</body>
</html>
"""
    else:
        return "API is running. Frontend at http://localhost:3000"

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