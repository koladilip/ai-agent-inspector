"""
Storage module for Agent Inspector.

Provides SQLite-based persistent storage with efficient querying,
batch operations, and automatic schema migrations.
"""

from .database import Database

__all__ = ["Database"]
