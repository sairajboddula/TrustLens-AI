"""
KYC Application - Repositories Package

Repository layer implementing the Repository pattern for database access.
Each repository wraps async SQLAlchemy queries with a clean interface.

Repositories:
- BaseRepository: Generic CRUD operations for any SQLAlchemy model
- UserRepository: User-specific queries
- KYCRepository: KYC submission queries with workflow logic
- DocumentRepository: Document storage and retrieval
"""

from app.repositories.base import BaseRepository
from app.repositories.user_repository import UserRepository
from app.repositories.kyc_repository import KYCRepository
from app.repositories.document_repository import DocumentRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "KYCRepository",
    "DocumentRepository",
]
