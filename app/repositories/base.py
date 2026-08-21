"""Base repository pattern."""
from app.models import db


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self, model_class, db_session=None):
        """
        Initialize base repository.

        Args:
            model_class: SQLAlchemy model class
            db_session: Database session (optional, uses default if not provided)
        """
        self.model_class = model_class
        self.db = db_session or db

    def get_by_id(self, id):
        """Get a record by ID."""
        return self.db.session.query(self.model_class).filter_by(id=id).first()

    def get_all(self):
        """Get all records."""
        return self.db.session.query(self.model_class).all()

    def create(self, **kwargs):
        """Create a new record."""
        instance = self.model_class(**kwargs)
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def update(self, instance):
        """Update an existing record."""
        self.db.session.add(instance)
        self.db.session.commit()
        return instance

    def delete(self, instance):
        """Delete a record."""
        self.db.session.delete(instance)
        self.db.session.commit()

    def commit(self):
        """Commit the current transaction."""
        self.db.session.commit()

    def rollback(self):
        """Rollback the current transaction."""
        self.db.session.rollback()


__all__ = ['BaseRepository']
