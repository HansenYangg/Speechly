"""Session model for user sessions."""
from datetime import datetime
from .database import db


class Session(db.Model):
    """
    Model for user sessions.

    Each session represents a user's interaction period and can contain
    multiple recordings.
    """

    __tablename__ = 'sessions'

    # Primary key
    id = db.Column(db.String(36), primary_key=True)  # UUID as string

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    recordings = db.relationship(
        'Recording',
        back_populates='session',
        cascade='all, delete-orphan',
        lazy='dynamic'
    )

    def __repr__(self):
        return f'<Session {self.id}>'

    def to_dict(self):
        """Convert session to dictionary."""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'recording_count': self.recordings.count()
        }

    def update_access_time(self):
        """Update the last accessed timestamp."""
        self.last_accessed = datetime.utcnow()


__all__ = ['Session']
