import os
import json
import tempfile
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import base64

from speech_evaluator import SpeechEvaluator
from config_validator import ConfigValidator
from exceptions import *
from logger import setup_logger
from validator import Validator

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

logger = setup_logger(__name__)

# initialize speech evaluator
try:
    ConfigValidator.validate_all()
    speech_evaluator = SpeechEvaluator()
    logger.info("Speech evaluator initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize speech evaluator: {e}")
    speech_evaluator = None

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
    if speech_evaluator is None:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': 'Speech evaluator not initialized'
        }), 503
    
    return jsonify({
        'success': True,
        'status': 'healthy',
        'version': '1.0.0'
    })

@app.route('/api/validate-config', methods=['GET'])
def validate_configuration():
    """Validate system configuration"""
    try:
        results = ConfigValidator.validate_all()
        return jsonify({
            'success': True,
            'validation_results': results
        })
    except ConfigurationError as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'validation_results': {}
        }), 400

@app.route('/api/languages', methods=['GET'])
def get_languages():
    """Get available languages"""
    from config import LANGUAGES, LANGUAGE_DISPLAY
    return jsonify({
        'success': True,
        'languages': LANGUAGES,
        'display_options': LANGUAGE_DISPLAY
    })

@app.route('/api/recordings', methods=['GET'])
def list_recordings():
    """List all available recordings"""
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
        
        # Validate inputs
        clean_topic = Validator.sanitize_topic(topic)
        clean_speech_type = Validator.sanitize_speech_type(speech_type)
        Validator.validate_language(language)
        
        # Decode audio data
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Invalid audio data: {e}'
            }), 400
        
        # Save audio to temporary file and then to recordings directory
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name
        
        try:
            # Generate filename
            filename = speech_evaluator.audio_recorder.file_manager.generate_filename(
                clean_topic, include_timestamp=True
            )
            
            # Move to recordings directory
            import shutil
            shutil.move(temp_path, filename)
            
            # Calculate duration (approximate)
            duration = len(audio_bytes) / (44100 * 2)  # Approximate for 16-bit 44.1kHz
            
            # Transcribe audio
            transcription = speech_evaluator.transcription_service.transcribe_audio(
                filename, language, show_output=False
            )
            
            if not transcription:
                return jsonify({
                    'success': False,
                    'error': 'Could not transcribe audio'
                }), 400
            
            # Store transcription
            filename_key = os.path.basename(filename)
            speech_evaluator.data_manager.add_speech_data(
                filename_key, transcription, topic=clean_topic, speech_type=clean_speech_type
            )
            
            # Get previous transcription if repeat
            previous_transcription = None
            if is_repeat and previous_filename:
                previous_transcription = speech_evaluator.data_manager.get_previous_transcription(
                    previous_filename
                )
            
            # Generate feedback
            feedback = speech_evaluator.feedback_service.generate_feedback(
                clean_topic, clean_speech_type, transcription, duration, 
                language, is_repeat, previous_transcription
            )
            
            return jsonify({
                'success': True,
                'result': {
                    'filename': filename_key,
                    'transcription': transcription,
                    'feedback': feedback,
                    'duration': duration,
                    'topic': clean_topic,
                    'speech_type': clean_speech_type
                }
            })
            
        finally:
            # Clean up temp file if it still exists
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe_recording():
    """Transcribe an existing recording"""
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
        
        # Validate inputs
        clean_topic = Validator.sanitize_topic(topic)
        clean_speech_type = Validator.sanitize_speech_type(speech_type)
        Validator.validate_language(language)
        Validator.validate_duration(duration)
        
        # Generate feedback
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

@app.route('/api/session', methods=['DELETE'])
def clear_session():
    """Clear current session data"""
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
    if speech_evaluator is None:
        print("❌ Failed to initialize speech evaluator. Please check configuration.")
        exit(1)
    
    print("🚀 Starting AI Speech Evaluator Web API...")
    print("📱 Frontend will be available at: http://localhost:5000")
    print("🔧 API endpoints available at: http://localhost:5000/api/*")
    
    app.run(debug=True, host='0.0.0.0', port=5001)