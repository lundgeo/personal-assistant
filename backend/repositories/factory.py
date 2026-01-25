"""Factory for creating the appropriate repository based on environment."""
import os
from typing import Optional
from .base import ToolRepository


_repository_instance: Optional[ToolRepository] = None


def get_repository(app=None) -> ToolRepository:
    """
    Get the appropriate repository implementation based on environment.

    Uses DATABASE_TYPE environment variable to determine implementation:
    - 'dynamodb': Uses DynamoDB (for AWS Lambda deployment)
    - 'sqlite' (default): Uses SQLite with Flask-SQLAlchemy

    Args:
        app: Flask application instance (required for SQLite, ignored for DynamoDB)

    Returns:
        ToolRepository implementation
    """
    global _repository_instance

    database_type = os.environ.get('DATABASE_TYPE', 'sqlite').lower()

    if database_type == 'dynamodb':
        if _repository_instance is None or not isinstance(_repository_instance, _get_dynamodb_class()):
            from .dynamodb_repository import DynamoDBToolRepository
            _repository_instance = DynamoDBToolRepository()
        return _repository_instance

    else:  # sqlite (default)
        if _repository_instance is None or not isinstance(_repository_instance, _get_sqlite_class()):
            from .sqlite_repository import SQLiteToolRepository
            _repository_instance = SQLiteToolRepository(app)
        elif app and hasattr(_repository_instance, 'app') and _repository_instance.app is None:
            _repository_instance.init_app(app)
        return _repository_instance


def _get_dynamodb_class():
    """Lazy import for DynamoDB repository class."""
    from .dynamodb_repository import DynamoDBToolRepository
    return DynamoDBToolRepository


def _get_sqlite_class():
    """Lazy import for SQLite repository class."""
    from .sqlite_repository import SQLiteToolRepository
    return SQLiteToolRepository


def reset_repository():
    """Reset the repository instance (useful for testing)."""
    global _repository_instance
    _repository_instance = None
