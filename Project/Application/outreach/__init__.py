"""
Outreach module for automated contact extraction and message sending.
"""

from .contact_extractor import ContactExtractor, ContactInfo, ContactType

__all__ = [
    'ContactExtractor',
    'ContactInfo', 
    'ContactType',
    'EmailSender',
    'OutreachMessage'
]


def __getattr__(name):
    """Load the SMTP sender only for callers that use outreach email."""
    if name in {'EmailSender', 'OutreachMessage'}:
        from .email_sender import EmailSender, OutreachMessage

        globals().update({
            'EmailSender': EmailSender,
            'OutreachMessage': OutreachMessage,
        })
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")




