"""Recording repository for managing speech recordings."""
import os
import json
import base64
from app.models import Recording, db
from .base import BaseRepository


class RecordingRepository(BaseRepository):
    """Repository for recording management with dual-write capability."""

    def __init__(self, db_session=None, config=None, legacy_sessions_dict=None, legacy_json_file=None):
        """
        Initialize recording repository.

        Args:
            db_session: Database session (optional)
            config: Configuration object (optional)
            legacy_sessions_dict: Legacy in-memory sessions dict for dual-write (optional)
            legacy_json_file: Legacy JSON file path for dual-write (optional)
        """
        super().__init__(Recording, db_session)
        self.config = config
        self.legacy_sessions = legacy_sessions_dict
        self.legacy_json_file = legacy_json_file

    def save_recording(self, session_id, filename, topic, speech_type, language,
                       audio_file_path=None, audio_data_base64=None, transcription=None,
                       feedback=None, duration=None, is_repeat=False, previous_recording_id=None):
        """
        Save a recording to the database.

        Args:
            session_id: Session ID
            filename: Filename of the recording
            topic: Topic of the speech
            speech_type: Type of speech
            language: Language code
            audio_file_path: Path to audio file (for file storage mode)
            audio_data_base64: Base64 encoded audio (for base64 storage mode)
            transcription: Transcription text
            feedback: Feedback text
            duration: Duration in seconds
            is_repeat: Whether this is a repeat attempt
            previous_recording_id: ID of previous recording (if repeat)

        Returns:
            Recording: Created recording instance
        """
        # Determine storage mode from config
        if self.config:
            audio_storage = self.config.AUDIO_STORAGE
        else:
            audio_storage = 'file'  # Default

        # Create recording
        recording = self.create(
            session_id=session_id,
            filename=filename,
            topic=topic,
            speech_type=speech_type,
            language=language,
            audio_data=audio_data_base64 if audio_storage == 'base64' else None,
            file_path=audio_file_path if audio_storage == 'file' else None,
            transcription=transcription,
            feedback=feedback,
            duration=duration,
            is_repeat=is_repeat,
            previous_recording_id=previous_recording_id
        )

        # Dual-write to legacy in-memory dict if provided
        if self.legacy_sessions is not None and session_id in self.legacy_sessions:
            legacy_record = {
                'filename': filename,
                'topic': topic,
                'speech_type': speech_type,
                'language': language,
                'transcription': transcription,
                'feedback': feedback,
                'duration': duration,
                'is_repeat': is_repeat
            }
            self.legacy_sessions[session_id].append(legacy_record)

        # Dual-write to legacy JSON file if provided
        if self.legacy_json_file and os.path.exists(os.path.dirname(self.legacy_json_file)):
            self._write_to_legacy_json(recording)

        return recording

    def get_by_filename(self, filename):
        """Get a recording by filename."""
        return self.db.session.query(Recording).filter_by(filename=filename).first()

    def get_session_recordings(self, session_id):
        """Get all recordings for a session."""
        return self.db.session.query(Recording).filter_by(session_id=session_id).all()

    def delete_recording(self, recording_id):
        """Delete a recording by ID."""
        recording = self.get_by_id(recording_id)
        if recording:
            # Delete associated file if exists
            if recording.file_path and os.path.exists(recording.file_path):
                try:
                    os.remove(recording.file_path)
                except Exception as e:
                    print(f"Warning: Could not delete file {recording.file_path}: {e}")

            self.delete(recording)
            return True
        return False

    def delete_by_filename(self, filename):
        """Delete a recording by filename."""
        recording = self.get_by_filename(filename)
        if recording:
            return self.delete_recording(recording.id)
        return False

    def _write_to_legacy_json(self, recording):
        """Write recording to legacy JSON file for dual-write."""
        try:
            # Read existing data
            if os.path.exists(self.legacy_json_file):
                with open(self.legacy_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}

            # Add recording to session
            if recording.session_id not in data:
                data[recording.session_id] = []

            data[recording.session_id].append(recording.to_dict())

            # Write back
            with open(self.legacy_json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Warning: Could not write to legacy JSON: {e}")


__all__ = ['RecordingRepository']
