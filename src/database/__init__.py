"""
Email database module for local caching and synchronization
"""
from .email_database import EmailDatabase
from .sync_manager import SyncManager
from .email_sync_db import EmailSyncDatabase

__all__ = ['EmailDatabase', 'SyncManager', 'EmailSyncDatabase']