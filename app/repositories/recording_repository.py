"""Recording repository for managing speech recordings."""
import os
import json
import base64
import psycopg2
from app.models import Recording, db
from .base import BaseRepository


def _row_to_recording(row, columns):
    """Convert a database row to a Recording object."""
    data = dict(zip(columns, row))
    recording = Recording()
    for key, value in data.items():
        if hasattr(recording, key):
            setattr(recording, key, value)
    return recording


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
        self._db_url = os.getenv('DATABASE_URL')

    def save_recording(self, session_id, filename, topic, speech_type, language,
                       audio_file_path=None, audio_data_base64=None, audio_url=None,
                       transcription=None, feedback=None, duration=None,
                       is_repeat=False, previous_recording_id=None, user_id=None,
                       recording_mode=None):
        """
        Save a recording to the database.

        Args:
            session_id: Session ID
            filename: Filename of the recording
            topic: Topic of the speech
            speech_type: Type of speech
            language: Language code
            audio_file_path: Path to audio file (for file/supabase storage mode)
            audio_data_base64: Base64 encoded audio (for base64 storage mode)
            audio_url: Public URL for Supabase Storage
            transcription: Transcription text
            feedback: Feedback text
            duration: Duration in seconds
            is_repeat: Whether this is a repeat attempt
            previous_recording_id: ID of previous recording (if repeat)
            user_id: Supabase auth user ID for persistent storage
            recording_mode: Mode of recording (standard, behavioral, improvement)

        Returns:
            Recording: Created recording instance
        """
        # Create recording with all storage options
        recording = self.create(
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            topic=topic,
            speech_type=speech_type,
            language=language,
            audio_data=audio_data_base64,
            file_path=audio_file_path,
            audio_url=audio_url,
            transcription=transcription,
            feedback=feedback,
            duration=duration,
            is_repeat=is_repeat,
            previous_recording_id=previous_recording_id,
            recording_mode=recording_mode or 'standard'
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
        """Get a recording by filename using raw SQL."""
        import sys

        if not self._db_url:
            return self.db.session.query(Recording).filter_by(filename=filename).first()

        try:
            conn = psycopg2.connect(self._db_url)
            conn.set_session(autocommit=True)
            cur = conn.cursor()

            cur.execute("""
                SELECT id, session_id, user_id, filename, topic, speech_type, language,
                       audio_data, file_path, audio_url, transcription, feedback, duration,
                       is_repeat, previous_recording_id, recording_mode, created_at, updated_at,
                       score_overall, score_content, score_organization, score_delivery, score_language
                FROM recordings
                WHERE filename = %s
            """, (filename,))

            columns = ['id', 'session_id', 'user_id', 'filename', 'topic', 'speech_type',
                      'language', 'audio_data', 'file_path', 'audio_url', 'transcription',
                      'feedback', 'duration', 'is_repeat', 'previous_recording_id',
                      'recording_mode', 'created_at', 'updated_at',
                      'score_overall', 'score_content', 'score_organization', 'score_delivery', 'score_language']

            row = cur.fetchone()
            cur.close()
            conn.close()

            if row:
                return _row_to_recording(row, columns)
            return None

        except Exception as e:
            print(f"[FETCH ERROR] get_by_filename: {str(e)}", file=sys.stderr, flush=True)
            return self.db.session.query(Recording).filter_by(filename=filename).first()

    def get_session_recordings(self, session_id):
        """Get all recordings for a session."""
        return self.db.session.query(Recording).filter_by(session_id=session_id).all()

    def get_user_recordings(self, user_id):
        """Get all recordings for a user (across all sessions) using raw SQL."""
        import sys
        print(f"[FETCH] Getting recordings for user_id={user_id}", file=sys.stderr, flush=True)

        if not self._db_url:
            print("[FETCH] No DATABASE_URL, falling back to SQLAlchemy", file=sys.stderr, flush=True)
            return self.db.session.query(Recording).filter_by(user_id=user_id).order_by(Recording.created_at.desc()).all()

        try:
            conn = psycopg2.connect(self._db_url)
            conn.set_session(autocommit=True)
            cur = conn.cursor()

            cur.execute("""
                SELECT id, session_id, user_id, filename, topic, speech_type, language,
                       audio_data, file_path, audio_url, transcription, feedback, duration,
                       is_repeat, previous_recording_id, recording_mode, created_at, updated_at,
                       score_overall, score_content, score_organization, score_delivery, score_language
                FROM recordings
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))

            columns = ['id', 'session_id', 'user_id', 'filename', 'topic', 'speech_type',
                      'language', 'audio_data', 'file_path', 'audio_url', 'transcription',
                      'feedback', 'duration', 'is_repeat', 'previous_recording_id',
                      'recording_mode', 'created_at', 'updated_at',
                      'score_overall', 'score_content', 'score_organization', 'score_delivery', 'score_language']

            rows = cur.fetchall()
            print(f"[FETCH] Found {len(rows)} recordings for user {user_id[:8] if user_id else 'None'}", file=sys.stderr, flush=True)

            recordings = [_row_to_recording(row, columns) for row in rows]

            cur.close()
            conn.close()

            return recordings

        except Exception as e:
            print(f"[FETCH ERROR] {str(e)}, falling back to SQLAlchemy", file=sys.stderr, flush=True)
            return self.db.session.query(Recording).filter_by(user_id=user_id).order_by(Recording.created_at.desc()).all()

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
