"""Custom scenario model for user-defined practice scenarios."""
from datetime import datetime
from .database import db


class CustomScenario(db.Model):
    """
    Model for user-defined custom practice scenarios.

    Users can create their own scenarios for quick access across sessions.
    """

    __tablename__ = 'custom_scenarios'

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # User who created this scenario
    user_id = db.Column(db.String(36), nullable=False, index=True)

    # Scenario type: 'practice' or 'behavioral'
    scenario_type = db.Column(db.String(20), nullable=False, default='practice')

    # Scenario content
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    topic = db.Column(db.String(500), nullable=False)
    speech_type = db.Column(db.String(100), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<CustomScenario {self.title}>'

    def to_dict(self):
        """Convert scenario to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'scenario_type': self.scenario_type,
            'title': self.title,
            'description': self.description,
            'topic': self.topic,
            'speech_type': self.speech_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


__all__ = ['CustomScenario']
