"""Database initialization and setup."""
from flask_sqlalchemy import SQLAlchemy

# Initialize SQLAlchemy instance
db = SQLAlchemy()


def init_db(app):
    """
    Initialize database with Flask app.

    Args:
        app: Flask application instance
    """
    db.init_app(app)

    with app.app_context():
        # Import all models to ensure they're registered with SQLAlchemy
        from . import session, recording, speech_history  # noqa

        # Create all tables
        db.create_all()


__all__ = ['db', 'init_db']
