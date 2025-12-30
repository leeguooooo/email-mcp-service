"""
Service layer for MCP Email Service
Provides clean interfaces to business logic and reduces coupling
"""
from .email_service import EmailService
from .communication_service import CommunicationService
from .folder_service import FolderService
from .system_service import SystemService
from .daily_digest_service import DailyDigestService

__all__ = [
    'EmailService',
    'CommunicationService', 
    'FolderService',
    'SystemService',
    'DailyDigestService'
]
