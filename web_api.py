import os
import json
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import base64
import openai
from dotenv import load_dotenv

# Try to import local modules, but handle production gracefully
try:
    from speech_evaluator import SpeechEvaluator
    from config_validator import ConfigValidator
    from exceptions import *
    from logger import setup_logger
    from validator import Validator
    PRODUCTION_MODE = False
    print("🏠 Development mode: All modules loaded")
except ImportError as e:
    # Production mode - create mock classes
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

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

logger = setup_logger(__name__)

# Initialize OpenAI client for production
if PRODUCTION_MODE:
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize speech evaluator or use production mode
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
    """Global error handler"""
    logger.error(f"API Error: {error}", exc_info=True)
    return jsonify({
        'success': False,
        'error': str(error),
        'type': type(error).__name__
    }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'version': '1.0.0',
        'mode': 'production' if PRODUCTION_MODE else 'development'
    })

@app.route('/api/validate-config', methods=['GET'])
def validate_configuration():
    """Validate system configuration"""
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
    """Get available languages"""
    if PRODUCTION_MODE:
        # Production: Use simple language list
        LANGUAGES = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi', 'tr', 'nl', 'bn']
        LANGUAGE_DISPLAY = [f"{code}: {code.upper()}" for code in LANGUAGES]
    else:
        # Development: Use config file
        from config import LANGUAGES, LANGUAGE_DISPLAY
    
    return jsonify({
        'success': True,
        'languages': LANGUAGES,
        'display_options': LANGUAGE_DISPLAY
    })

@app.route('/api/recordings', methods=['GET'])
def list_recordings():
    """List all available recordings"""
    if PRODUCTION_MODE:
        # Production: No persistent recordings
        return jsonify({
            'success': True,
            'recordings': []
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
    """Download a specific recording"""
    if PRODUCTION_MODE:
        return jsonify({
            'success': False,
            'error': 'Recording downloads not available in production'
        }), 404
    
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
    """Delete a specific recording"""
    if PRODUCTION_MODE:
        return jsonify({
            'success': False,
            'error': 'Recording deletion not available in production'
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

@app.route('/api/record', methods=['POST'])
def process_recording():
    """Process uploaded audio recording and generate feedback"""
    try:
        # Get form data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Validate required fields
        topic = data.get('topic', '').strip()
        speech_type = data.get('speech_type', '').strip()
        language = data.get('language', 'en')
        audio_data = data.get('audio_data')  # Base64 encoded audio
        is_repeat = data.get('is_repeat', False)
        previous_filename = data.get('previous_filename')
        
        if not topic or not speech_type or not audio_data:
            return jsonify({
                'success': False,
                'error': 'Missing required fields: topic, speech_type, or audio_data'
            }), 400
        
        # Simple validation for production
        if PRODUCTION_MODE:
            # Basic sanitization
            import re
            topic = re.sub(r'[^\w\s-]', '', topic)[:100]
            speech_type = re.sub(r'[^\w\s-]', '', speech_type)[:50]
            
            valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh', 'ar', 'hi', 'tr', 'nl', 'bn']
            if language not in valid_languages:
                language = 'en'
        else:
            # Development: Use validator
            topic = Validator.sanitize_topic(topic)
            speech_type = Validator.sanitize_speech_type(speech_type)
            Validator.validate_language(language)
        
        # Decode audio data
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Invalid audio data: {e}'
            }), 400
        
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        try:
            # Replace the feedback generation section in your web_api.py /api/record route with this:

            if PRODUCTION_MODE:
                # Production: Use OpenAI directly with improved prompting
                print(f"🌐 Processing with OpenAI - Topic: {topic}, Language: {language}")
                
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
                
                # Calculate approximate duration (rough estimate)
                duration = len(audio_bytes) / (44100 * 2)  # Approximate for 16-bit 44.1kHz
                
                # Constants for duration thresholds
                MIN_RECORDING_DURATION = 5  # 5 seconds
                SHORT_RECORDING_THRESHOLD = 30  # 30 seconds
                
                # Check if recording is too short
                if duration <= MIN_RECORDING_DURATION:
                    return jsonify({
                        'success': False,
                        'error': 'Speech was too short to generate feedback for (<5 seconds). Please try again.'
                    }), 400
                
                # Build sophisticated prompt based on duration and context
                def build_feedback_prompt(topic, speech_type, transcription_text, duration, language, is_repeat, previous_transcription=None):
                    # Base prompt components
                    grading_instruction = (
                        "First, give a grading on a strict scale of 1-100 on the speech. "
                        "Don't always have scores in increments of 5, use more varied/granular scores. "
                        "You can choose to give separate scores for certain things, like 18/20 for structure, 17.5/20 for conclusion, etc., and please but clear spacing in between each (clearly separate them as if they were paragraphs).\n"
                    )
                    
                    feedback_instruction = (
                        "Comment on things such as their structure of the speech, clarity, volume, confidence, intonation, pauses, etc. "
                        "Note good things they did and things they can improve on, and don't be overly nice. "
                    )
                    
                    context = f"For context, the speech was '{topic}' for a {speech_type}."
                    
                    repeat_context = ""
                    if is_repeat and previous_transcription:
                        repeat_context = f"Also, the user has already done a speech on this topic. Here is the original transcription: {previous_transcription}. Compare the two and note improvements."
                    
                    language_instruction = f"Try to tailor to their specific speech style. Make sure to do this in {language}."
                    
                    # Different prompts based on recording duration
                    if MIN_RECORDING_DURATION < duration < SHORT_RECORDING_THRESHOLD:
                        prompt = (
                            f"The following speech is pretty short and may lack sufficient content. "
                            f"Please evaluate and critique it given the following topic and type of the speech. "
                            f"Give appropriate feedback accordingly based on these:\n\n"
                            f"Speech topic: '{topic}'\n"
                            f"Speech type: {speech_type}\n"
                            f"Transcription: '{transcription_text}'\n\n"
                            f"{repeat_context}\n"
                            f"Please grade on a scale of 1-100 considering the potential lack of content and give constructive feedback without being overly nice. "
                            f"You can choose to give separate scores for certain things, like 18/20 for structure, 20/20 for conclusion, etc. "
                            f"Don't always have scores in increments of 5, use more varied/granular scores. \n"
                            f"please but clear spacing in between each (clearly separate them as if they were paragraphs)\n" 
                            f"{language_instruction}"
                        )
                    else:
                        prompt = (
                            f"{grading_instruction} "
                            f"{feedback_instruction} "
                            f"{context} "
                            f"{repeat_context} "
                            f"In {language}, give specific feedback tailored towards this topic and type of speech and preferably cite specific things they said. Please put adequate spacing and indentation where needed.\n"
                            f"The speech is:\n\n{transcription_text}\n\nFeedback:"
                        )
                    
                    return prompt
                
                # Generate the sophisticated prompt
                feedback_prompt = build_feedback_prompt(
                    topic, speech_type, transcription_text, duration, language, is_repeat
                )
                
                # Generate feedback with improved model and settings
                feedback_response = client.chat.completions.create(
                    model="gpt-4o-mini",  # Use the same model as your original
                    messages=[
                        {"role": "user", "content": feedback_prompt}
                    ],
                    max_tokens=500,  # Increased for more detailed feedback
                    temperature=0.7
                )
                
                feedback = feedback_response.choices[0].message.content
                
                return jsonify({
                    'success': True,
                    'result': {
                        'transcription': transcription_text,
                        'feedback': feedback,
                        'topic': topic,
                        'speech_type': speech_type,
                        'duration': round(duration, 1),
                        'score_type': 'short' if duration < SHORT_RECORDING_THRESHOLD else 'full'
                    }
                })
            
        finally:
            # Clean up temp file if it still exists
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe_recording():
    """Transcribe an existing recording"""
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
        
        # Transcribe the audio
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
    """Generate feedback for a transcription"""
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
            # Production: Use OpenAI
            feedback_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{
                    "role": "user", 
                    "content": f"Provide speech feedback for topic '{topic}' of type '{speech_type}'. Transcription: {transcription}"
                }],
                max_tokens=300
            )
            feedback = feedback_response.choices[0].message.content
        else:
            # Development: Use speech_evaluator
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
    """Get current session data"""
    if PRODUCTION_MODE:
        return jsonify({
            'success': True,
            'session_data': {
                'speech_count': 0,
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
    """Serve frontend in production"""
    if PRODUCTION_MODE:
        # Serve the complete frontend HTML
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

        .select-wrapper {
            position: relative;
            margin-top: 10px;
        }

        .select-wrapper select {
            width: 100%;
            padding: 18px 24px;
            background: rgba(255,255,255,0.1);
            border: 2px solid rgba(255,255,255,0.2);
            border-radius: 16px;
            font-size: 16px;
            color: white;
            cursor: pointer;
            transition: all 0.3s ease;
            appearance: none;
        }

        .select-wrapper select:focus {
            outline: none;
            border-color: rgba(255,255,255,0.4);
            background: rgba(255,255,255,0.15);
        }

        .select-wrapper::after {
            content: '\\f107';
            font-family: 'Font Awesome 6 Free';
            font-weight: 900;
            position: absolute;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
            color: rgba(255,255,255,0.7);
            pointer-events: none;
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
            min-width: auto;
        }

        .feedback-section {
            display: none;
            margin-top: 40px;
        }

        .feedback-section.active {
            display: block;
            animation: slideInUp 0.5s ease-out;
        }

        .feedback-content {
            background: rgba(255,255,255,0.9);
            border-left: 4px solid #4facfe;
            padding: 30px;
            border-radius: 16px;
            margin-top: 20px;
            backdrop-filter: blur(10px);
            color: #2d3748;
            line-height: 1.6;
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

        <div class="glass-card">
            <div class="section-title">
                <div class="section-icon">
                    <i class="fas fa-globe"></i>
                </div>
                <span>Language Selection</span>
            </div>
            
            <div class="language-selector">
                <label for="languageSelect" style="color: white; font-weight: 600;">Choose your target language:</label>
                <div class="select-wrapper">
                    <select id="languageSelect">
                        <option value="en">English</option>
                        <option value="ko">Korean</option>
                        <option value="zh-CN">Chinese (Simplified)</option>
                        <option value="it">Italian</option>
                        <option value="ja">Japanese</option>
                        <option value="pt">Portuguese</option>
                        <option value="ru">Russian</option>
                        <option value="ar">Arabic</option>
                        <option value="hi">Hindi</option>
                        <option value="tr">Turkish</option>
                        <option value="nl">Dutch</option>
                        <option value="fr">French</option>
                        <option value="es">Spanish</option>
                        <option value="de">German</option>
                        <option value="bn">Bengali</option>
                        <option value="zh">Mandarin Chinese</option>
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
                <div class="status-subtext">Speak clearly into your microphone. Click stop when finished.</div>
                <button class="btn btn-stop" onclick="stopRecording()">
                    <i class="fas fa-stop"></i>
                    Stop Recording (Enter)
                </button>
            </div>

            <div class="recordings-list" id="recordingsList">
                <div class="section-title">
                    <div class="section-icon">
                        <i class="fas fa-folder-open"></i>
                    </div>
                    <span>Your Recordings</span>
                </div>
                <div class="recordings-grid" id="recordingsContainer">
                    <!-- Recordings will be populated here -->
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
                    <!-- Feedback will appear here -->
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
                    <!-- Transcription will appear here -->
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
        // Global variables
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        let currentLanguage = 'en';
        let recordedBlob = null;
        let recordings = [];

        // API base URL - IMPORTANT: This now points to the production server
        const API_BASE = 'https://speakeasyy.onrender.com/api';

        // Initialize the app
        document.addEventListener('DOMContentLoaded', function() {
            setupKeyboardShortcuts();
            loadLanguages();
            checkHealth();
        });

        // Language change handler
        document.getElementById('languageSelect').addEventListener('change', function() {
            currentLanguage = this.value;
            updateLanguage();
        });

        function updateLanguage() {
            console.log('Language changed to: ' + currentLanguage);
        }

        // API helper function
        async function apiCall(endpoint, options = {}) {
            try {
                const response = await fetch(API_BASE + endpoint, {
                    headers: {
                        'Content-Type': 'application/json',
                        ...options.headers
                    },
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

        // Check backend health
        async function checkHealth() {
            try {
                const result = await apiCall('/health');
                if (result.success) {
                    showStatus('✓ Connected to backend successfully', 'success');
                }
            } catch (error) {
                showStatus('❌ Cannot connect to backend. Please start the API server.', 'error');
            }
        }

        // Load available languages from backend
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

        // Show status message
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

        // Keyboard shortcuts
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

        // Start recording process
        function startRecording() {
            if (isRecording) {
                showStatus('Already recording!', 'error');
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

        // Get supported MIME type
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

        // Convert WebM to WAV for better backend compatibility
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
                    processRecording();
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
                    },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    throw new Error('HTTP ' + response.status + ': ' + errorText);
                }

                const result = await response.json();

                if (result.success) {
                    displayResults(result.result);
                    showStatus('✅ Recording processed successfully!', 'success');
                } else {
                    showStatus('❌ Processing failed: ' + result.error, 'error');
                }

            } catch (error) {
                console.error('Processing error:', error);
                showStatus('❌ Failed to process recording: ' + error.message, 'error');
            }
        }

        function displayResults(result) {
            const hasTranscription = result.transcription && result.transcription.trim().length > 0;
            const hasFeedback = result.feedback && result.feedback.trim().length > 0;
            
            if (hasTranscription) {
                document.getElementById('transcriptionContent').textContent = result.transcription;
                document.getElementById('transcriptionSection').classList.remove('hidden');
            }

            if (hasFeedback) {
                document.getElementById('feedbackContent').innerHTML = result.feedback.replace(/\\\\n/g, '<br>');
            } else {
                document.getElementById('feedbackContent').innerHTML = '<div style="text-align: center; padding: 20px;"><i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 15px; color: #f9ca24;"></i><h3 style="color: #f9ca24; margin-bottom: 10px;">Recording Too Short</h3><p style="color: #2d3748;">Sorry! The recording was too short to generate feedback for. Please try again with a longer speech.</p></div>';
            }
            
            document.getElementById('feedbackSection').classList.add('active');

            if (recordedBlob) {
                const audioURL = URL.createObjectURL(recordedBlob);
                document.getElementById('audioPlayer').src = audioURL;
                document.getElementById('audioControls').classList.remove('hidden');
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
    
            if (recordings.length === 0) {
                container.innerHTML = '<div class="recording-item" style="background: rgba(255,255,255,0.9);"><div class="recording-info"><h4 style="color: #2d3748;">📁 No recordings found</h4><div class="recording-meta" style="color: #2d3748;">Create your first recording to get started!</div></div></div>';
                return;
            }

            const recordingItems = recordings.map(function(recording) {
                const safeFilename = recording.filename.replace(/'/g, "\\\\'");
                return '<div class="recording-item"><div class="recording-info"><h4 style="color: #2d3748;"><i class="fas fa-file-audio"></i> ' + recording.filename + '</h4><div class="recording-meta">Size: ' + formatFileSize(recording.size) + ' | Created: ' + formatDate(recording.created) + '</div></div><div class="recording-actions"><button class="btn btn-play btn-small" onclick="playRecording(\\'' + safeFilename + '\\')"><i class="fas fa-play"></i> Play</button><button class="btn btn-stop btn-small" onclick="deleteRecording(\\'' + safeFilename + '\\')" style="background: var(--danger-gradient);"><i class="fas fa-trash"></i> Delete</button></div></div>';
            });

            container.innerHTML = recordingItems.join('');
        }

        async function playRecording(filename) {
            try {
                showStatus('▶️ Loading ' + filename + '...', 'info');
                const response = await fetch(API_BASE + '/recordings/' + filename);
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
    """Clear current session data"""
    if PRODUCTION_MODE:
        return jsonify({
            'success': True,
            'message': 'Session data cleared (production mode)'
        })
    
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