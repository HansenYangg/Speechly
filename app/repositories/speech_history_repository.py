"""Speech history repository for tracking speech evaluation history."""
import os
import json
from app.models import SpeechHistory, db
from .base import BaseRepository


class SpeechHistoryRepository(BaseRepository):
    """Repository for speech history management."""

    def __init__(self, db_session=None, legacy_json_file=None):
        """
        Initialize speech history repository.

        Args:
            db_session: Database session (optional)
            legacy_json_file: Legacy JSON file path for dual-write (optional)
        """
        super().__init__(SpeechHistory, db_session)
        self.legacy_json_file = legacy_json_file

    def add_history_entry(self, recording_id, score=None, extra_data=None):
        """
        Add a history entry for a recording.

        Args:
            recording_id: ID of the recording
            score: Overall score (optional)
            extra_data: Additional metadata dict (optional)

        Returns:
            SpeechHistory: Created history entry
        """
        entry = self.create(
            recording_id=recording_id,
            score=score,
            extra_data=extra_data
        )

        # Dual-write to legacy JSON if provided
        if self.legacy_json_file:
            self._write_to_legacy_json(entry)

        return entry

    def get_history_for_recording(self, recording_id):
        """Get all history entries for a recording."""
        return self.db.session.query(SpeechHistory).filter_by(
            recording_id=recording_id
        ).all()

    def get_recent_history(self, limit=100):
        """
        Get recent history entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            list: List of SpeechHistory instances
        """
        return self.db.session.query(SpeechHistory).order_by(
            SpeechHistory.created_at.desc()
        ).limit(limit).all()

    def _write_to_legacy_json(self, entry):
        """Write history entry to legacy JSON file for dual-write."""
        try:
            # Read existing data
            if os.path.exists(self.legacy_json_file):
                with open(self.legacy_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []

            # Add entry
            data.append(entry.to_dict())

            # Keep only last 100 entries (matching original behavior)
            if len(data) > 100:
                data = data[-100:]

            # Write back
            with open(self.legacy_json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            print(f"Warning: Could not write to legacy JSON: {e}")


__all__ = ['SpeechHistoryRepository']
