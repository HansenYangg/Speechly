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
                        'stream_url': f'/api/stream-feedback/{session_id}/{filename}',
                        'language': language
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
            
            # Get language from request parameters
            language = request.args.get('language', 'en')
            
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
                
                # Language-specific instructions
                language_instructions = {
                    'en': "Make sure to do this in English.",
                    'es': "Asegúrate de hacer esto en español.",
                    'fr': "Assurez-vous de faire cela en français.",
                    'de': "Stellen Sie sicher, dass Sie dies auf Deutsch machen.",
                    'it': "Assicurati di farlo in italiano.",
                    'pt': "Certifique-se de fazer isso em português.",
                    'ru': "Убедитесь, что делаете это на русском языке.",
                    'ja': "これを日本語で行ってください。",
                    'ko': "이것을 한국어로 해주세요.",
                    'zh': "请确保用中文进行。",
                    'ar': "تأكد من القيام بذلك باللغة العربية.",
                    'hi': "सुनिश्चित करें कि आप इसे हिंदी में करते हैं।",
                    'tr': "Bunu Türkçe yaptığınızdan emin olun.",
                    'nl': "Zorg ervoor dat je dit in het Nederlands doet.",
                    'bn': "নিশ্চিত করুন যে আপনি এটি বাংলায় করছেন।"
                }
                
                language_instruction = language_instructions.get(language, "Make sure to do this in English.")
                
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
                        f"Please put adequate spacing. There MUST be a clear separating line between each major point for clarity, with either a new line or ---.\n" 
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
                        f"Please put adequate spacing. There MUST be a clear separating line between each major point for clarity. You MUST start each new paragraph with a new line or ---.\n" 
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
                max_tokens=1500,
                temperature=0.5,
                stream=True
            )
            
            full_feedback = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    # Add spacing only when detecting --- separators
                    if content and '---' in content:
                        spaced_content = content + "\n"
                    else:
                        spaced_content = content
                    full_feedback += spaced_content
                    yield f"data: {json.dumps({'content': spaced_content, 'type': 'chunk'})}\n\n"
                                            
                       
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
            white-space: pre-wrap;
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
            <h1 id="mainTitle">AI Speech Evaluator</h1>
            <p id="mainSubtitle">Transform your speaking skills with cutting-edge AI-powered feedback and analysis</p>
        </div>

        <div class="session-info" id="sessionInfo">
            <i class="fas fa-user-circle"></i> <span id="sessionText">Your Session:</span> <span id="sessionId">Connecting...</span>
        </div>

        <div class="glass-card">
            <div class="section-title">
                <div class="section-icon">
                    <i class="fas fa-globe"></i>
                </div>
                <span id="languageSectionTitle">Language Selection</span>
            </div>
            
            <div class="language-selector">
                <label for="languageSelect" id="languageLabel">Choose your target language:</label>
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
                <span id="actionsSectionTitle">Quick Actions</span>
            </div>

            <div class="controls-grid">
                <button class="btn btn-record" id="recordBtn" onclick="startRecording()">
                    <i class="fas fa-microphone"></i>
                    <span id="recordBtnText">Record Speech (R)</span>
                </button>
                <button class="btn btn-list" onclick="listRecordings()">
                    <i class="fas fa-list"></i>
                    <span id="viewBtnText">View Recordings (L)</span>
                </button>
                <button class="btn btn-play" onclick="showPlayDialog()">
                    <i class="fas fa-play"></i>
                    <span id="playBtnText">Play Recording (P)</span>
                </button>
                <button class="btn btn-stop hidden" id="stopBtn" onclick="stopRecording()">
                    <i class="fas fa-stop"></i>
                    <span id="stopBtnText">Stop Recording (Enter)</span>
                </button>
            </div>

            <div id="statusMessage"></div>

            <div class="recording-setup" id="recordingSetup">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-cog"></i>
                    </div>
                    <span id="setupSectionTitle">Recording Setup</span>
                </div>
                
                <div class="form-grid">
                    <div class="input-group">
                        <label for="topicInput" id="topicLabel">Speech Topic</label>
                        <input type="text" id="topicInput" placeholder="What will you be speaking about?" maxlength="200">
                    </div>
                    <div class="input-group">
                        <label for="speechTypeInput" id="typeLabel">Speech Type</label>
                        <input type="text" id="speechTypeInput" placeholder="e.g., interview, presentation, debate" maxlength="100">
                    </div>
                </div>
                
                <div class="checkbox-wrapper">
                    <input type="checkbox" id="repeatSpeech">
                    <label for="repeatSpeech" id="repeatLabel">This is a repeat attempt on the same topic</label>
                </div>
                
                <div class="controls-grid" style="margin-top: 30px;">
                    <button class="btn btn-record" onclick="confirmRecording()">
                        <i class="fas fa-play"></i>
                        <span id="startBtnText">Start Recording (T)</span>
                    </button>
                    <button class="btn btn-secondary" onclick="cancelRecording()">
                        <i class="fas fa-times"></i>
                        <span id="cancelBtnText">Cancel (B)</span>
                    </button>
                </div>
            </div>

            <div class="recording-status" id="recordingStatus">
                <div class="recording-indicator">
                    <i class="fas fa-microphone"></i>
                </div>
                <div class="status-text" id="recordingText">Recording in Progress</div>
                <div class="status-subtext" id="recordingSubtext">Speak clearly into your microphone. Click stop when finished or cancel to discard.</div>
                <div style="margin-top: 20px; display: flex; gap: 15px; justify-content: center;">
                    <button class="btn btn-stop" onclick="stopRecording()">
                        <i class="fas fa-stop"></i>
                        <span id="stopRecordingBtnText">Stop Recording (Enter)</span>
                    </button>
                    <button class="btn btn-secondary" onclick="cancelActiveRecording()">
                        <i class="fas fa-times"></i>
                        <span id="cancelActiveBtnText">Cancel (X)</span>
                    </button>
                </div>
            </div>

            <div class="recordings-list" id="recordingsList">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <span id="recordingsSectionTitle">Your Recordings</span>
                </div>
                <div class="recordings-grid" id="recordingsContainer">
                </div>
            </div>

            <div class="feedback-section" id="feedbackSection">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-brain"></i>
                    </div>
                    <span id="feedbackSectionTitle">AI Feedback & Analysis</span>
                </div>
                <div class="feedback-content" id="feedbackContent">
                    <div class="feedback-loading" id="feedbackLoading">
                        <i class="fas fa-robot" style="font-size: 1.5rem;"></i>
                        <span id="feedbackLoadingText">AI is analyzing your speech</span>
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
                    <span id="transcriptionSectionTitle">Speech Transcription</span>
                </div>
                <div id="transcriptionContent">
                </div>
            </div>

            <div class="audio-controls hidden" id="audioControls">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-volume-up"></i>
                    </div>
                    <span id="playbackSectionTitle">Recording Playback</span>
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

        // Dynamically determine API base URL based on current protocol
        const API_BASE = window.location.protocol === 'https:' 
            ? 'https://speakeasyy.onrender.com/api' 
            : window.location.protocol + '//' + window.location.host + '/api';

        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                const r = Math.random() * 16 | 0;
                const v = c == 'x' ? r : (r & 0x3 | 0x8);
                return v.toString(16);
            });
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
                stopRecordingBtn: "Stop Recording (Enter)",
                cancelActiveBtn: "Cancel (X)",
                recordingsSection: "Your Recordings",
                feedbackSection: "AI Feedback & Analysis",
                transcriptionSection: "Speech Transcription",
                playbackSection: "Recording Playback",
                noRecordings: "No recordings found",
                noRecordingsSubtext: "Create your first recording to get started!",
                playRecBtn: "Play",
                deleteBtn: "Delete",
                feedbackLoadingText: "AI is analyzing your speech"
            },
            es: {
                title: "Evaluador de Voz con IA",
                subtitle: "Transforma tus habilidades de habla con retroalimentación y análisis impulsados por IA de vanguardia",
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
                repeatLabel: "Este es un intento repetido del mismo tema",
                startBtn: "Iniciar Grabación (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Grabación en Progreso",
                recordingSubtext: "Habla claramente en tu micrófono. Haz clic en detener cuando termines o cancelar para descartar.",
                stopRecordingBtn: "Detener Grabación (Enter)",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Tus Grabaciones",
                feedbackSection: "Retroalimentación y Análisis de IA",
                transcriptionSection: "Transcripción del Discurso",
                playbackSection: "Reproducción de Grabación",
                noRecordings: "No se encontraron grabaciones",
                noRecordingsSubtext: "¡Crea tu primera grabación para comenzar!",
                playRecBtn: "Reproducir",
                deleteBtn: "Eliminar",
                feedbackLoadingText: "La IA está analizando tu discurso"
            },
            fr: {
                title: "Évaluateur de Parole IA",
                subtitle: "Transformez vos compétences oratoires avec des commentaires et analyses alimentés par une IA de pointe",
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
                repeatLabel: "C'est une tentative répétée sur le même sujet",
                startBtn: "Commencer l'Enregistrement (T)",
                cancelBtn: "Annuler (B)",
                recordingText: "Enregistrement en Cours",
                recordingSubtext: "Parlez clairement dans votre microphone. Cliquez sur arrêter quand vous avez terminé ou annuler pour rejeter.",
                stopRecordingBtn: "Arrêter l'Enregistrement (Entrée)",
                cancelActiveBtn: "Annuler (X)",
                recordingsSection: "Vos Enregistrements",
                feedbackSection: "Commentaires et Analyse IA",
                transcriptionSection: "Transcription du Discours",
                playbackSection: "Lecture de l'Enregistrement",
                noRecordings: "Aucun enregistrement trouvé",
                noRecordingsSubtext: "Créez votre premier enregistrement pour commencer!",
                playRecBtn: "Lire",
                deleteBtn: "Supprimer",
                feedbackLoadingText: "L'IA analyse votre discours"
            },
            de: {
                title: "KI-Sprachevaluator",
                subtitle: "Verwandeln Sie Ihre Sprechfähigkeiten mit modernster KI-gestützter Rückmeldung und Analyse",
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
                repeatLabel: "Dies ist ein wiederholter Versuch zum gleichen Thema",
                startBtn: "Aufnahme Starten (T)",
                cancelBtn: "Abbrechen (B)",
                recordingText: "Aufnahme Läuft",
                recordingSubtext: "Sprechen Sie deutlich in Ihr Mikrofon. Klicken Sie auf Stopp, wenn Sie fertig sind, oder auf Abbrechen zum Verwerfen.",
                stopRecordingBtn: "Aufnahme Stoppen (Enter)",
                cancelActiveBtn: "Abbrechen (X)",
                recordingsSection: "Ihre Aufnahmen",
                feedbackSection: "KI-Feedback & Analyse",
                transcriptionSection: "Rede-Transkription",
                playbackSection: "Aufnahme-Wiedergabe",
                noRecordings: "Keine Aufnahmen gefunden",
                noRecordingsSubtext: "Erstellen Sie Ihre erste Aufnahme, um zu beginnen!",
                playRecBtn: "Abspielen",
                deleteBtn: "Löschen",
                feedbackLoadingText: "KI analysiert Ihre Rede"
            },
            it: {
                title: "Valutatore di Voce AI",
                subtitle: "Trasforma le tue abilità oratorie con feedback e analisi all'avanguardia alimentati dall'AI",
                sessionText: "La Tua Sessione:",
                languageLabel: "Scegli la tua lingua target:",
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
                repeatLabel: "Questo è un tentativo ripetuto sullo stesso argomento",
                startBtn: "Inizia Registrazione (T)",
                cancelBtn: "Annulla (B)",
                recordingText: "Registrazione in Corso",
                recordingSubtext: "Parla chiaramente nel tuo microfono. Clicca ferma quando hai finito o annulla per scartare.",
                stopRecordingBtn: "Ferma Registrazione (Invio)",
                cancelActiveBtn: "Annulla (X)",
                recordingsSection: "Le Tue Registrazioni",
                feedbackSection: "Feedback e Analisi AI",
                transcriptionSection: "Trascrizione del Discorso",
                playbackSection: "Riproduzione Registrazione",
                noRecordings: "Nessuna registrazione trovata",
                noRecordingsSubtext: "Crea la tua prima registrazione per iniziare!",
                playRecBtn: "Riproduci",
                deleteBtn: "Elimina",
                feedbackLoadingText: "L'AI sta analizzando il tuo discorso"
            },
            pt: {
                title: "Avaliador de Fala IA",
                subtitle: "Transforme suas habilidades de fala com feedback e análise de ponta alimentados por IA",
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
                repeatLabel: "Esta é uma tentativa repetida no mesmo tópico",
                startBtn: "Iniciar Gravação (T)",
                cancelBtn: "Cancelar (B)",
                recordingText: "Gravação em Andamento",
                recordingSubtext: "Fale claramente no seu microfone. Clique em parar quando terminar ou cancelar para descartar.",
                stopRecordingBtn: "Parar Gravação (Enter)",
                cancelActiveBtn: "Cancelar (X)",
                recordingsSection: "Suas Gravações",
                feedbackSection: "Feedback e Análise IA",
                transcriptionSection: "Transcrição do Discurso",
                playbackSection: "Reprodução da Gravação",
                noRecordings: "Nenhuma gravação encontrada",
                noRecordingsSubtext: "Crie sua primeira gravação para começar!",
                playRecBtn: "Reproduzir",
                deleteBtn: "Deletar",
                feedbackLoadingText: "A IA está analisando seu discurso"
            },
            ru: {
                title: "ИИ Оценщик Речи",
                subtitle: "Преобразуйте свои речевые навыки с помощью передовой обратной связи и анализа на основе ИИ",
                sessionText: "Ваша Сессия:",
                languageLabel: "Выберите ваш целевой язык:",
                languageSection: "Выбор Языка",
                actionsSection: "Быстрые Действия",
                recordBtn: "Записать Речь (R)",
                viewBtn: "Просмотреть Записи (L)",
                playBtn: "Воспроизвести Запись (P)",
                stopBtn: "Остановить Запись (Enter)",
                setupSection: "Настройка Записи",
                topicLabel: "Тема Речи",
                topicPlaceholder: "О чем вы будете говорить?",
                typeLabel: "Тип Речи",
                typePlaceholder: "напр., интервью, презентация, дебаты",
                repeatLabel: "Это повторная попытка на ту же тему",
                startBtn: "Начать Запись (T)",
                cancelBtn: "Отменить (B)",
                recordingText: "Запись в Процессе",
                recordingSubtext: "Говорите четко в микрофон. Нажмите стоп когда закончите или отмените для отклонения.",
                stopRecordingBtn: "Остановить Запись (Enter)",
                cancelActiveBtn: "Отменить (X)",
                recordingsSection: "Ваши Записи",
                feedbackSection: "Обратная Связь и Анализ ИИ",
                transcriptionSection: "Транскрипция Речи",
                playbackSection: "Воспроизведение Записи",
                noRecordings: "Записи не найдены",
                noRecordingsSubtext: "Создайте свою первую запись для начала!",
                playRecBtn: "Воспроизвести",
                deleteBtn: "Удалить",
                feedbackLoadingText: "ИИ анализирует вашу речь"
            },
            ja: {
                title: "AI音声評価者",
                subtitle: "最先端のAI駆動フィードバックと分析で話すスキルを変革する",
                sessionText: "あなたのセッション:",
                languageLabel: "対象言語を選択してください:",
                languageSection: "言語選択",
                actionsSection: "クイックアクション",
                recordBtn: "音声録音 (R)",
                viewBtn: "録音を表示 (L)",
                playBtn: "録音を再生 (P)",
                stopBtn: "録音停止 (Enter)",
                setupSection: "録音設定",
                topicLabel: "スピーチトピック",
                topicPlaceholder: "何について話しますか？",
                typeLabel: "スピーチタイプ",
                typePlaceholder: "例：面接、プレゼンテーション、ディベート",
                repeatLabel: "これは同じトピックでの再試行です",
                startBtn: "録音開始 (T)",
                cancelBtn: "キャンセル (B)",
                recordingText: "録音中",
                recordingSubtext: "マイクに向かってはっきりと話してください。終了したら停止をクリック、または破棄するにはキャンセルをクリックしてください。",
                stopRecordingBtn: "録音停止 (Enter)",
                cancelActiveBtn: "キャンセル (X)",
                recordingsSection: "あなたの録音",
                feedbackSection: "AIフィードバック＆分析",
                transcriptionSection: "音声転写",
                playbackSection: "録音再生",
                noRecordings: "録音が見つかりません",
                noRecordingsSubtext: "始めるために最初の録音を作成してください！",
                playRecBtn: "再生",
                deleteBtn: "削除",
                feedbackLoadingText: "AIがあなたの音声を分析しています"
            },
            ko: {
                title: "AI 음성 평가자",
                subtitle: "최첨단 AI 기반 피드백과 분석으로 말하기 기술을 혁신하세요",
                sessionText: "당신의 세션:",
                languageLabel: "목표 언어를 선택하세요:",
                languageSection: "언어 선택",
                actionsSection: "빠른 작업",
                recordBtn: "음성 녹음 (R)",
                viewBtn: "녹음 보기 (L)",
                playBtn: "녹음 재생 (P)",
                stopBtn: "녹음 중지 (Enter)",
                setupSection: "녹음 설정",
                topicLabel: "연설 주제",
                topicPlaceholder: "무엇에 대해 말할 것인가요?",
                typeLabel: "연설 유형",
                typePlaceholder: "예: 면접, 발표, 토론",
                repeatLabel: "같은 주제에 대한 재시도입니다",
                startBtn: "녹음 시작 (T)",
                cancelBtn: "취소 (B)",
                recordingText: "녹음 진행 중",
                recordingSubtext: "마이크에 대고 명확히 말하세요. 완료되면 중지를 클릭하거나 삭제하려면 취소를 클릭하세요.",
                stopRecordingBtn: "녹음 중지 (Enter)",
                cancelActiveBtn: "취소 (X)",
                recordingsSection: "당신의 녹음",
                feedbackSection: "AI 피드백 & 분석",
                transcriptionSection: "음성 전사",
                playbackSection: "녹음 재생",
                noRecordings: "녹음을 찾을 수 없습니다",
                noRecordingsSubtext: "시작하려면 첫 번째 녹음을 만드세요!",
                playRecBtn: "재생",
                deleteBtn: "삭제",
                feedbackLoadingText: "AI가 당신의 음성을 분석하고 있습니다"
            },
            zh: {
                title: "AI语音评估器",
                subtitle: "通过尖端的AI驱动反馈和分析改造您的口语技能",
                sessionText: "您的会话:",
                languageLabel: "选择您的目标语言:",
                languageSection: "语言选择",
                actionsSection: "快速操作",
                recordBtn: "录制演讲 (R)",
                viewBtn: "查看录音 (L)",
                playBtn: "播放录音 (P)",
                stopBtn: "停止录音 (Enter)",
                setupSection: "录音设置",
                topicLabel: "演讲主题",
                topicPlaceholder: "您将谈论什么？",
                typeLabel: "演讲类型",
                typePlaceholder: "例如：面试、演示、辩论",
                repeatLabel: "这是同一主题的重复尝试",
                startBtn: "开始录音 (T)",
                cancelBtn: "取消 (B)",
                recordingText: "录音进行中",
                recordingSubtext: "请对着麦克风清楚地说话。完成后点击停止或取消以丢弃。",
                stopRecordingBtn: "停止录音 (Enter)",
                cancelActiveBtn: "取消 (X)",
                recordingsSection: "您的录音",
                feedbackSection: "AI反馈和分析",
                transcriptionSection: "语音转写",
                playbackSection: "录音回放",
                noRecordings: "未找到录音",
                noRecordingsSubtext: "创建您的第一个录音开始吧！",
                playRecBtn: "播放",
                deleteBtn: "删除",
                feedbackLoadingText: "AI正在分析您的语音"
            },
            ar: {
                title: "مقيم الكلام بالذكاء الاصطناعي",
                subtitle: "حول مهاراتك في التحدث بالتعليقات والتحليل المتطور المدعوم بالذكاء الاصطناعي",
                sessionText: "جلستك:",
                languageLabel: "اختر لغتك المستهدفة:",
                languageSection: "اختيار اللغة",
                actionsSection: "الإجراءات السريعة",
                recordBtn: "تسجيل الكلام (R)",
                viewBtn: "عرض التسجيلات (L)",
                playBtn: "تشغيل التسجيل (P)",
                stopBtn: "إيقاف التسجيل (Enter)",
                setupSection: "إعداد التسجيل",
                topicLabel: "موضوع الكلام",
                topicPlaceholder: "عن ماذا ستتحدث؟",
                typeLabel: "نوع الكلام",
                typePlaceholder: "مثل: مقابلة، عرض تقديمي، مناقشة",
                repeatLabel: "هذه محاولة متكررة لنفس الموضوع",
                startBtn: "بدء التسجيل (T)",
                cancelBtn: "إلغاء (B)",
                recordingText: "التسجيل جاري",
                recordingSubtext: "تحدث بوضوح في الميكروفون. انقر على إيقاف عند الانتهاء أو إلغاء للتجاهل.",
                stopRecordingBtn: "إيقاف التسجيل (Enter)",
                cancelActiveBtn: "إلغاء (X)",
                recordingsSection: "تسجيلاتك",
                feedbackSection: "التعليقات والتحليل بالذكاء الاصطناعي",
                transcriptionSection: "نسخ الكلام",
                playbackSection: "تشغيل التسجيل",
                noRecordings: "لم يتم العثور على تسجيلات",
                noRecordingsSubtext: "أنشئ تسجيلك الأول للبدء!",
                playRecBtn: "تشغيل",
                deleteBtn: "حذف",
                feedbackLoadingText: "الذكاء الاصطناعي يحلل كلامك"
            },
            hi: {
                title: "AI वाक् मूल्यांकनकर्ता",
                subtitle: "अत्याधुनिक AI-संचालित फीडबैक और विश्लेषण के साथ अपने बोलने के कौशल को बदलें",
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
                repeatLabel: "यह उसी विषय पर एक दोहराया प्रयास है",
                startBtn: "रिकॉर्डिंग शुरू करें (T)",
                cancelBtn: "रद्द करें (B)",
                recordingText: "रिकॉर्डिंग चल रही है",
                recordingSubtext: "अपने माइक्रोफोन में स्पष्ट रूप से बोलें। समाप्त होने पर रोकें क्लिक करें या रद्द करने के लिए रद्द करें।",
                stopRecordingBtn: "रिकॉर्डिंग रोकें (Enter)",
                cancelActiveBtn: "रद्द करें (X)",
                recordingsSection: "आपकी रिकॉर्डिंग",
                feedbackSection: "AI फीडबैक और विश्लेषण",
                transcriptionSection: "भाषण प्रतिलेखन",
                playbackSection: "रिकॉर्डिंग प्लेबैक",
                noRecordings: "कोई रिकॉर्डिंग नहीं मिली",
                noRecordingsSubtext: "शुरू करने के लिए अपनी पहली रिकॉर्डिंग बनाएं!",
                playRecBtn: "चलाएं",
                deleteBtn: "हटाएं",
                feedbackLoadingText: "AI आपके भाषण का विश्लेषण कर रहा है"
            },
            tr: {
                title: "AI Konuşma Değerlendiricisi",
                subtitle: "En gelişmiş AI destekli geri bildirim ve analiz ile konuşma becerilerinizi dönüştürün",
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
                typePlaceholder: "örn. mülakat, sunum, tartışma",
                repeatLabel: "Bu aynı konu için tekrar bir deneme",
                startBtn: "Kaydı Başlat (T)",
                cancelBtn: "İptal (B)",
                recordingText: "Kayıt Devam Ediyor",
                recordingSubtext: "Mikrofonunuza net bir şekilde konuşun. Bittiğinde durdur'a tıklayın veya atmak için iptal edin.",
                stopRecordingBtn: "Kaydı Durdur (Enter)",
                cancelActiveBtn: "İptal (X)",
                recordingsSection: "Kayıtlarınız",
                feedbackSection: "AI Geri Bildirim ve Analiz",
                transcriptionSection: "Konuşma Transkripti",
                playbackSection: "Kayıt Oynatma",
                noRecordings: "Kayıt bulunamadı",
                noRecordingsSubtext: "Başlamak için ilk kaydınızı oluşturun!",
                playRecBtn: "Oynat",
                deleteBtn: "Sil",
                feedbackLoadingText: "AI konuşmanızı analiz ediyor"
            },
            nl: {
                title: "AI Spraakevaluator",
                subtitle: "Transformeer je spreekvaardigheden met geavanceerde AI-aangedreven feedback en analyse",
                sessionText: "Jouw Sessie:",
                languageLabel: "Kies je doeltaal:",
                languageSection: "Taalselectie",
                actionsSection: "Snelle Acties",
                recordBtn: "Spraak Opnemen (R)",
                viewBtn: "Opnames Bekijken (L)",
                playBtn: "Opname Afspelen (P)",
                stopBtn: "Opname Stoppen (Enter)",
                setupSection: "Opname Instelling",
                topicLabel: "Spraak Onderwerp",
                topicPlaceholder: "Waarover ga je spreken?",
                typeLabel: "Spraak Type",
                typePlaceholder: "bijv. interview, presentatie, debat",
                repeatLabel: "Dit is een herhaalde poging van hetzelfde onderwerp",
                startBtn: "Opname Starten (T)",
                cancelBtn: "Annuleren (B)",
                recordingText: "Opname Bezig",
                recordingSubtext: "Spreek duidelijk in je microfoon. Klik op stoppen wanneer klaar of annuleer om te verwerpen.",
                stopRecordingBtn: "Opname Stoppen (Enter)",
                cancelActiveBtn: "Annuleren (X)",
                recordingsSection: "Jouw Opnames",
                feedbackSection: "AI Feedback & Analyse",
                transcriptionSection: "Spraak Transcriptie",
                playbackSection: "Opname Afspelen",
                noRecordings: "Geen opnames gevonden",
                noRecordingsSubtext: "Maak je eerste opname om te beginnen!",
                playRecBtn: "Afspelen",
                deleteBtn: "Verwijderen",
                feedbackLoadingText: "AI analyseert je spraak"
            },
            bn: {
                title: "AI বক্তৃতা মূল্যায়নকারী",
                subtitle: "অত্যাধুনিক AI-চালিত প্রতিক্রিয়া এবং বিশ্লেষণের সাথে আপনার কথা বলার দক্ষতা পরিবর্তন করুন",
                sessionText: "আপনার সেশন:",
                languageLabel: "আপনার লক্ষ্য ভাষা চয়ন করুন:",
                languageSection: "ভাষা নির্বাচন",
                actionsSection: "দ্রুত কর্ম",
                recordBtn: "বক্তৃতা রেকর্ড করুন (R)",
                viewBtn: "রেকর্ডিং দেখুন (L)",
                playBtn: "রেকর্ডিং চালান (P)",
                stopBtn: "রেকর্ডিং বন্ধ করুন (Enter)",
                setupSection: "রেকর্ডিং সেটআপ",
                topicLabel: "বক্তৃতার বিষয়",
                topicPlaceholder: "আপনি কী নিয়ে কথা বলবেন?",
                typeLabel: "বক্তৃতার ধরন",
                typePlaceholder: "যেমন: সাক্ষাৎকার, উপস্থাপনা, বিতর্ক",
                repeatLabel: "এটি একই বিষয়ে একটি পুনরাবৃত্ত প্রচেষ্টা",
                startBtn: "রেকর্ডিং শুরু করুন (T)",
                cancelBtn: "বাতিল করুন (B)",
                recordingText: "রেকর্ডিং চলমান",
                recordingSubtext: "আপনার মাইক্রোফোনে স্পষ্টভাবে কথা বলুন। শেষ হলে স্টপ ক্লিক করুন বা বাতিল করতে বাতিল করুন।",
                stopRecordingBtn: "রেকর্ডিং বন্ধ করুন (Enter)",
                cancelActiveBtn: "বাতিল করুন (X)",
                recordingsSection: "আপনার রেকর্ডিং",
                feedbackSection: "AI প্রতিক্রিয়া এবং বিশ্লেষণ",
                transcriptionSection: "বক্তৃতা প্রতিলিপি",
                playbackSection: "রেকর্ডিং প্লেব্যাক",
                noRecordings: "কোন রেকর্ডিং পাওয়া যায়নি",
                noRecordingsSubtext: "শুরু করতে আপনার প্রথম রেকর্ডিং তৈরি করুন!",
                playRecBtn: "চালান",
                deleteBtn: "মুছুন",
                feedbackLoadingText: "AI আপনার বক্তৃতা বিশ্লেষণ করছে"
            }
        };

        document.addEventListener('DOMContentLoaded', function() {
            initializeSession();
            setupKeyboardShortcuts();
            loadLanguages();
            checkHealth();
            setupBeforeUnload();
            updateLanguage(); // Initialize with default language
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

        document.getElementById('languageSelect').addEventListener('change', function() {
            currentLanguage = this.value;
            updateLanguage();
        });

        function updateLanguage() {
            console.log('Language changed to: ' + currentLanguage);
            
            const lang = translations[currentLanguage] || translations.en;
            
            // Update main content
            document.getElementById('mainTitle').textContent = lang.title;
            document.getElementById('mainSubtitle').textContent = lang.subtitle;
            document.getElementById('sessionText').textContent = lang.sessionText;
            
            // Update language selector
            document.getElementById('languageLabel').textContent = lang.languageLabel;
            document.getElementById('languageSectionTitle').textContent = lang.languageSection;
            
            // Update quick actions
            document.getElementById('actionsSectionTitle').textContent = lang.actionsSection;
            document.getElementById('recordBtnText').textContent = lang.recordBtn;
            document.getElementById('viewBtnText').textContent = lang.viewBtn;
            document.getElementById('playBtnText').textContent = lang.playBtn;
            document.getElementById('stopBtnText').textContent = lang.stopBtn;
            
            // Update recording setup
            document.getElementById('setupSectionTitle').textContent = lang.setupSection;
            document.getElementById('topicLabel').textContent = lang.topicLabel;
            document.getElementById('topicInput').placeholder = lang.topicPlaceholder;
            document.getElementById('typeLabel').textContent = lang.typeLabel;
            document.getElementById('speechTypeInput').placeholder = lang.typePlaceholder;
            document.getElementById('repeatLabel').textContent = lang.repeatLabel;
            document.getElementById('startBtnText').textContent = lang.startBtn;
            document.getElementById('cancelBtnText').textContent = lang.cancelBtn;
            
            // Update recording status
            document.getElementById('recordingText').textContent = lang.recordingText;
            document.getElementById('recordingSubtext').textContent = lang.recordingSubtext;
            document.getElementById('stopRecordingBtnText').textContent = lang.stopRecordingBtn;
            document.getElementById('cancelActiveBtnText').textContent = lang.cancelActiveBtn;
            
            // Update sections
            document.getElementById('recordingsSectionTitle').textContent = lang.recordingsSection;
            document.getElementById('feedbackSectionTitle').textContent = lang.feedbackSection;
            document.getElementById('transcriptionSectionTitle').textContent = lang.transcriptionSection;
            document.getElementById('playbackSectionTitle').textContent = lang.playbackSection;
            document.getElementById('feedbackLoadingText').textContent = lang.feedbackLoadingText;
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
                    // Try streaming first, with fallback
                    if (result.result.stream_url) {
                        startFeedbackStream(result.result.stream_url + '?language=' + currentLanguage);
                    } else {
                        // Fallback to regular feedback generation
                        generateFeedbackFallback(result.result);
                    }
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

            // Ensure the URL uses the same protocol as the current page
            let fullStreamUrl = streamUrl;
            if (streamUrl.startsWith('/')) {
                const protocol = window.location.protocol;
                const host = window.location.host;
                fullStreamUrl = `${protocol}//${host}${streamUrl}`;
            }

            console.log('Starting feedback stream with URL:', fullStreamUrl);

            try {
                feedbackEventSource = new EventSource(fullStreamUrl);
                
                feedbackEventSource.onopen = function(event) {
                    console.log('EventSource connection opened');
                };
                
                feedbackEventSource.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        
                        if (data.error) {
                            console.error('Stream error:', data.error);
                            showStatus('❌ Feedback generation failed: ' + data.error, 'error');
                            feedbackEventSource.close();
                            fallbackToPolling();
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
                    feedbackEventSource.close();
                    feedbackEventSource = null;
                    
                    // Fallback to polling method
                    fallbackToPolling();
                };
            } catch (error) {
                console.error('Failed to create EventSource:', error);
                fallbackToPolling();
            }
        }

        function fallbackToPolling() {
            console.log('Falling back to polling method for feedback');
            
            // Hide loading and show a simple message
            document.getElementById('feedbackLoading').style.display = 'none';
            document.getElementById('feedbackText').style.display = 'block';
            document.getElementById('feedbackText').innerHTML = '<span>Generating feedback... This may take a moment.</span>';
            
            // For now, show a placeholder message
            setTimeout(function() {
                const lang = translations[currentLanguage] || translations.en;
                document.getElementById('feedbackText').innerHTML = '<span>AI feedback generation is currently unavailable due to connection issues. Please try again later.</span>';
            }, 3000);
        }

        async function generateFeedbackFallback(recordingResult) {
            try {
                document.getElementById('feedbackLoading').style.display = 'none';
                document.getElementById('feedbackText').style.display = 'block';
                document.getElementById('feedbackText').innerHTML = '<span>Generating comprehensive feedback...</span>';
                
                const payload = {
                    topic: recordingResult.topic,
                    speech_type: recordingResult.speech_type,
                    transcription: recordingResult.transcription,
                    duration: recordingResult.duration,
                    language: currentLanguage,
                    is_repeat: false
                };

                const response = await fetch(API_BASE + '/feedback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Session-ID': sessionId
                    },
                    body: JSON.stringify(payload)
                });

                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('feedbackText').innerHTML = '<span>' + result.feedback.replace(/\n/g, '<br>') + '</span>';
                } else {
                    document.getElementById('feedbackText').innerHTML = '<span>Failed to generate feedback. Please try again.</span>';
                }
            } catch (error) {
                console.error('Fallback feedback generation failed:', error);
                document.getElementById('feedbackText').innerHTML = '<span>Unable to generate feedback at this time.</span>';
            }
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