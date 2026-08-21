"""Session repository for managing user sessions."""
from datetime import datetime
from app.models import Session, db
from .base import BaseRepository


class SessionRepository(BaseRepository):
    """Repository for session management with dual-write capability."""

    def __init__(self, db_session=None, legacy_sessions_dict=None):
        """
        Initialize session repository.

        Args:
            db_session: Database session (optional)
            legacy_sessions_dict: Legacy in-memory sessions dict for dual-write (optional)
        """
        super().__init__(Session, db_session)
        self.legacy_sessions = legacy_sessions_dict  # For backward compatibility during migration

    def get_or_create(self, session_id):
        """
        Get existing session or create new one.

        Args:
            session_id: Session ID (UUID string)

        Returns:
            Session: Session instance
        """
        session = self.get_by_id(session_id)

        if not session:
            session = self.create(id=session_id)

            # Dual-write to legacy dict if provided
            if self.legacy_sessions is not None:
                self.legacy_sessions[session_id] = []

        # Update last accessed time
        session.update_access_time()
        self.update(session)

        return session

    def get_recordings(self, session_id):
        """
        Get all recordings for a session.

        Args:
            session_id: Session ID

        Returns:
            list: List of Recording instances
        """
        session = self.get_or_create(session_id)
        return session.recordings.all()

    def delete_session(self, session_id):
        """
        Delete a session and all its recordings.

        Args:
            session_id: Session ID

        Returns:
            bool: True if deleted, False if not found
        """
        import os

        session = self.get_by_id(session_id)
        if session:
            # Delete all audio files for recordings in this session before deleting the session
            for recording in session.recordings.all():
                if recording.file_path and os.path.exists(recording.file_path):
                    try:
                        os.remove(recording.file_path)
                    except Exception as e:
                        print(f"Warning: Could not delete file {recording.file_path}: {e}")

            self.delete(session)

            # Dual-write to legacy dict if provided
            if self.legacy_sessions is not None and session_id in self.legacy_sessions:
                del self.legacy_sessions[session_id]

            return True
        return False

    def cleanup_old_sessions(self, max_age_hours=24):
        """
        Clean up sessions older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            int: Number of sessions deleted
        """
        import os
        from datetime import timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        old_sessions = self.db.session.query(Session).filter(
            Session.last_accessed < cutoff_time
        ).all()

        count = len(old_sessions)
        for session in old_sessions:
            # Delete all audio files for recordings in this session
            for recording in session.recordings.all():
                if recording.file_path and os.path.exists(recording.file_path):
                    try:
                        os.remove(recording.file_path)
                    except Exception as e:
                        print(f"Warning: Could not delete file {recording.file_path}: {e}")

            self.delete(session)

        return count


__all__ = ['SessionRepository']
