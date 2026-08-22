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

    # Foreign keys
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False)
    user_id = db.Column(db.String(36), nullable=True, index=True)  # Supabase auth user ID

    # Recording metadata
    filename = db.Column(db.String(255), unique=True, nullable=False, index=True)
    topic = db.Column(db.String(500), nullable=False)
    speech_type = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(10), nullable=False)

    # Audio data - stored differently based on AUDIO_STORAGE config
    # For cloud: audio_data contains base64 encoded audio
    # For local: file_path contains path to file on disk
    # For supabase: file_path contains Supabase Storage path, audio_url contains public URL
    audio_data = db.Column(db.Text, nullable=True)  # Base64 encoded audio
    file_path = db.Column(db.String(500), nullable=True)  # Local file path or Supabase path
    audio_url = db.Column(db.String(1000), nullable=True)  # Supabase Storage public URL

    # Processing results
    transcription = db.Column(db.Text, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Float, nullable=True)  # Duration in seconds

    # Extracted scores for analytics (parsed from feedback)
    score_overall = db.Column(db.Integer, nullable=True)  # Overall score out of 100
    score_content = db.Column(db.Integer, nullable=True)  # Content & Relevance out of 25
    score_organization = db.Column(db.Integer, nullable=True)  # Organization & Clarity out of 25
    score_delivery = db.Column(db.Integer, nullable=True)  # Delivery & Confidence out of 25
    score_language = db.Column(db.Integer, nullable=True)  # Language & Expression out of 25

    # Recording mode (for analytics filtering)
    recording_mode = db.Column(db.String(20), nullable=True, default='standard')  # 'standard', 'behavioral', 'improvement'

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

    @staticmethod
    def extract_scores_from_feedback(feedback):
        """
        Extract all scores from feedback text with validation.

        Returns:
            dict: Dictionary with score_overall, score_content, score_organization,
                  score_delivery, score_language (all integers or None)
        """
        import re

        scores = {
            'score_overall': None,
            'score_content': None,
            'score_organization': None,
            'score_delivery': None,
            'score_language': None
        }

        if not feedback:
            return scores

        # Extract Overall Score: X/100
        overall_match = re.search(r'Overall Score:\s*(\d+)/100', feedback, re.IGNORECASE)
        if overall_match:
            scores['score_overall'] = min(int(overall_match.group(1)), 100)  # Cap at 100

        # Extract Content & Relevance (Score: X/25)
        content_match = re.search(r'Content\s*[&]\s*Relevance\s*\([^)]*Score:\s*(\d+)/25', feedback, re.IGNORECASE)
        if not content_match:
            content_match = re.search(r'Content\s*[&]\s*Relevance\s*\(Previous:[^→]*→\s*New:\s*(\d+)/25', feedback, re.IGNORECASE)
        if content_match:
            scores['score_content'] = min(int(content_match.group(1)), 25)  # Cap at 25

        # Extract Organization & Clarity (Score: X/25)
        org_match = re.search(r'Organization\s*[&]\s*Clarity\s*\([^)]*Score:\s*(\d+)/25', feedback, re.IGNORECASE)
        if not org_match:
            org_match = re.search(r'Organization\s*[&]\s*Clarity\s*\(Previous:[^→]*→\s*New:\s*(\d+)/25', feedback, re.IGNORECASE)
        if org_match:
            scores['score_organization'] = min(int(org_match.group(1)), 25)  # Cap at 25

        # Extract Delivery & Confidence (Score: X/25)
        delivery_match = re.search(r'Delivery\s*[&]\s*Confidence\s*\([^)]*Score:\s*(\d+)/25', feedback, re.IGNORECASE)
        if not delivery_match:
            delivery_match = re.search(r'Delivery\s*[&]\s*Confidence\s*\(Previous:[^→]*→\s*New:\s*(\d+)/25', feedback, re.IGNORECASE)
        if delivery_match:
            scores['score_delivery'] = min(int(delivery_match.group(1)), 25)  # Cap at 25

        # Extract Language & Expression (Score: X/25)
        lang_match = re.search(r'Language\s*[&]\s*Expression\s*\([^)]*Score:\s*(\d+)/25', feedback, re.IGNORECASE)
        if not lang_match:
            lang_match = re.search(r'Language\s*[&]\s*Expression\s*\(Previous:[^→]*→\s*New:\s*(\d+)/25', feedback, re.IGNORECASE)
        if lang_match:
            scores['score_language'] = min(int(lang_match.group(1)), 25)  # Cap at 25

        # Validate: If we have all category scores, recalculate overall from them
        # This fixes cases where AI gives inconsistent scores
        category_scores = [
            scores['score_content'],
            scores['score_organization'],
            scores['score_delivery'],
            scores['score_language']
        ]
        if all(s is not None for s in category_scores):
            calculated_overall = sum(category_scores)
            # If there's a mismatch, use the calculated value (more reliable)
            if scores['score_overall'] is None or abs(scores['score_overall'] - calculated_overall) > 2:
                scores['score_overall'] = calculated_overall

        return scores

    def extract_and_save_scores(self):
        """Extract scores from feedback and save to the model."""
        scores = self.extract_scores_from_feedback(self.feedback)
        self.score_overall = scores['score_overall']
        self.score_content = scores['score_content']
        self.score_organization = scores['score_organization']
        self.score_delivery = scores['score_delivery']
        self.score_language = scores['score_language']

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
            'user_id': self.user_id,
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
            'audio_url': self.audio_url,  # Supabase Storage URL if available
            # Analytics scores
            'score_overall': self.score_overall,
            'score_content': self.score_content,
            'score_organization': self.score_organization,
            'score_delivery': self.score_delivery,
            'score_language': self.score_language,
            'recording_mode': self.recording_mode,
        }

        if include_audio:
            data['audio_data'] = self.audio_data
            data['file_path'] = self.file_path

        return data


__all__ = ['Recording']
