"""Recording model for speech recordings."""
from datetime import datetime
from .database import db


class Recording(db.Model):
    """
    Model for speech recordings.

    Each recording represents a single speech recording with its associated
    metadata, transcription, and feedback.
    """

    __tablename__ = 'recordings'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False)

    # Recording metadata
    filename = db.Column(db.String(255), unique=True, nullable=False, index=True)
    topic = db.Column(db.String(500), nullable=False)
    speech_type = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(10), nullable=False)

    # Audio data - stored differently based on AUDIO_STORAGE config
    # For cloud: audio_data contains base64 encoded audio
    # For local: file_path contains path to file on disk
    audio_data = db.Column(db.Text, nullable=True)  # Base64 encoded audio
    file_path = db.Column(db.String(500), nullable=True)  # Local file path

    # Processing results
    transcription = db.Column(db.Text, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Float, nullable=True)  # Duration in seconds

    # Repeat functionality
    is_repeat = db.Column(db.Boolean, default=False, nullable=False)
    previous_recording_id = db.Column(db.Integer, db.ForeignKey('recordings.id'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    session = db.relationship('Session', back_populates='recordings')
    previous_recording = db.relationship(
        'Recording',
        remote_side=[id],
        backref='repeat_recordings',
        lazy=True
    )

    def __repr__(self):
        return f'<Recording {self.filename}>'

    def to_dict(self, include_audio=False):
        """
        Convert recording to dictionary.

        Args:
            include_audio: Whether to include audio data in the response

        Returns:
            Dictionary representation of the recording
        """
        import os

        # Calculate size
        size = 0
        if self.file_path and os.path.exists(self.file_path):
            size = os.path.getsize(self.file_path)
        elif self.audio_data:
            # Approximate size from base64 (base64 is ~1.33x original size)
            size = int(len(self.audio_data) * 0.75)

        data = {
            'id': self.id,
            'session_id': self.session_id,
            'filename': self.filename,
            'topic': self.topic,
            'speech_type': self.speech_type,
            'language': self.language,
            'transcription': self.transcription,
            'feedback': self.feedback,
            'duration': self.duration,
            'is_repeat': self.is_repeat,
            'previous_recording_id': self.previous_recording_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'size': size,
            'created': int(self.created_at.timestamp()) if self.created_at else 0,
        }

        if include_audio:
            data['audio_data'] = self.audio_data
            data['file_path'] = self.file_path

        return data


__all__ = ['Recording']
