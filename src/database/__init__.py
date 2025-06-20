"""
Email database module for local caching and synchronization
"""
from .email_database import EmailDatabase
from .sync_manager import SyncManager

__all__ = ['EmailDatabase', 'SyncManager']