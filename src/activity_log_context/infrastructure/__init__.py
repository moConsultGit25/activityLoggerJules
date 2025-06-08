# src/activity_log_context/infrastructure/__init__.py

from .activity_repository import MongoActivityRepository

__all__ = [
    "MongoActivityRepository",
]
