# src/auth_context/infrastructure/__init__.py
from .user_repository import MongoUserRepository

__all__ = ["MongoUserRepository"]
