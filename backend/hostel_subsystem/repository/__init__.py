"""
Repository package for Student Sync - Hostel subsystem.
Provides persistence abstractions and storage implementations.
"""
from repository.base import BaseHostelRepository, HostelRepository
from repository.in_memory import InMemoryHostelRepository
from repository.mongo import MongoHostelRepository

__all__ = [
    "BaseHostelRepository",
    "HostelRepository",
    "InMemoryHostelRepository",
    "MongoHostelRepository",
]
