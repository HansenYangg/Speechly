"""Speech history model for tracking speech records."""
from datetime import datetime
from .database import db


class SpeechHistory(db.Model):
    """
    Model for speech history tracking.

    Stores historical records of speech evaluations for analytics and
    tracking purposes.
    """

    __tablename__ = 'speech_history'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to recording
    recording_id = db.Column(db.Integer, db.ForeignKey('recordings.id'), nullable=False)

    # Historical metadata
    score = db.Column(db.Float, nullable=True)  # Overall score if extracted from feedback
    extra_data = db.Column(db.JSON, nullable=True)  # Additional extensible metadata (renamed from metadata to avoid SQLAlchemy conflict)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    recording = db.relationship('Recording', backref='history_entries', lazy=True)

    def __repr__(self):
        return f'<SpeechHistory {self.id} for Recording {self.recording_id}>'

    def to_dict(self):
        """Convert speech history entry to dictionary."""
        return {
            'id': self.id,
            'recording_id': self.recording_id,
            'score': self.score,
            'extra_data': self.extra_data,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


__all__ = ['SpeechHistory']
