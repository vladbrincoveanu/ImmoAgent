"""
Outreach module for automated contact extraction and message sending.
"""

from .contact_extractor import ContactExtractor, ContactInfo, ContactType
from .email_sender import EmailSender, OutreachMessage

__all__ = [
    'ContactExtractor',
    'ContactInfo', 
    'ContactType',
    'EmailSender',
    'OutreachMessage'
]





