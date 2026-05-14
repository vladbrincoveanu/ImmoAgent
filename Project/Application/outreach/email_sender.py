"""
Email sender module for sending outreach messages to property listings.
Supports SMTP with SSL/TLS for Gmail, Outlook, and other providers.
"""

import smtplib
import logging
import time
import os
import ssl
import socket
import hashlib
import secrets
import base64
import bleach
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import re
import email.utils
from Application.helpers.utils import smart_sleep


UNSUBSCRIBE_BASE_URL = "https://immo-scouter.com/unsubscribe"


def _generate_unsubscribe_token(recipient_email: str) -> str:
    """Generate a one-time unsubscribe token for GDPR compliance."""
    token_data = f"{recipient_email}:{secrets.token_hex(16)}"
    return base64.urlsafe_b64encode(token_data.encode()).decode()


def _verify_unsubscribe_token(token: str, recipient_email: str) -> bool:
    """Verify unsubscribe token matches recipient."""
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        return decoded.startswith(f"{recipient_email}:")
    except Exception:
        return False


def _is_valid_email(email_addr: str) -> bool:
    parsed = email.utils.parseaddr(email_addr)
    return bool(parsed[1] and '@' in parsed[1] and '.' in parsed[1].split('@')[1])


@dataclass(slots=True)
class OutreachMessage:
    """Represents an outreach message to be sent."""
    to_email: str
    subject: str
    body_html: str
    body_text: str
    listing_url: str
    listing_price: float
    offer_price: float
    sent_at: Optional[datetime] = None
    success: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "to_email": self.to_email,
            "subject": self.subject,
            "listing_url": self.listing_url,
            "listing_price": self.listing_price,
            "offer_price": self.offer_price,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "success": self.success,
            "error_message": self.error_message
        }


class EmailSender:
    """Send outreach emails via SMTP."""
    
    # Common SMTP configurations
    SMTP_CONFIGS = {
        'gmail': {
            'host': 'smtp.gmail.com',
            'port': 587,
            'use_tls': True
        },
        'outlook': {
            'host': 'smtp-mail.outlook.com',
            'port': 587,
            'use_tls': True
        },
        'yahoo': {
            'host': 'smtp.mail.yahoo.com',
            'port': 587,
            'use_tls': True
        },
        'gmx': {
            'host': 'mail.gmx.net',
            'port': 587,
            'use_tls': True
        },
        'custom': {
            'host': None,
            'port': 587,
            'use_tls': True
        }
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize email sender with configuration.
        
        Expected config keys:
            - smtp_provider: 'gmail', 'outlook', 'yahoo', 'gmx', or 'custom'
            - smtp_host: (required if provider is 'custom')
            - smtp_port: (optional, defaults based on provider)
            - smtp_user: email address for authentication
            - smtp_password: password or app-specific password
            - sender_email: email address to send from (usually same as smtp_user)
            - sender_name: display name for sender
            - offer_discount: percentage discount to offer (default: 30)
        """
        self.config = config
        
        # Get SMTP settings
        provider = config.get('smtp_provider', 'gmail').lower()
        smtp_config = self.SMTP_CONFIGS.get(provider, self.SMTP_CONFIGS['custom'])
        
        self.smtp_host = config.get('smtp_host') or smtp_config['host']
        self.smtp_port = config.get('smtp_port') or smtp_config['port']
        self.use_tls = config.get('smtp_use_tls', smtp_config['use_tls'])
        
        # Prefer environment variables for sensitive data
        self.smtp_user = os.getenv('SMTP_USER') or config.get('smtp_user')
        self.smtp_password = os.getenv('SMTP_PASSWORD') or config.get('smtp_password')
        self.sender_email = os.getenv('SENDER_EMAIL') or config.get('sender_email') or self.smtp_user
        self.sender_name = os.getenv('SENDER_NAME') or config.get('sender_name', 'Immobilien Interessent')
        
        # Offer settings
        self.offer_discount = config.get('offer_discount', 40)  # 40% below asking
        
        # Rate limiting
        self.delay_between_emails = config.get('delay_between_emails', 5)  # seconds
        self.max_emails_per_run = config.get('max_emails_per_run', 10)
        
        # Templates
        self.subject_template = config.get('subject_template', 
            'Anfrage zu Ihrer Immobilie - {address}')
        
        self.message_template = config.get('message_template') or self._default_german_template()
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate that required configuration is present."""
        if not self.smtp_host:
            raise ValueError("SMTP host is required. Set smtp_host or use a known smtp_provider.")
        if not self.smtp_user:
            raise ValueError("SMTP user (smtp_user or SMTP_USER env var) is required for authentication.")
        if not self.smtp_password:
            raise ValueError("SMTP password (smtp_password or SMTP_PASSWORD env var) is required for authentication.")
        if not self.sender_email:
            raise ValueError("Sender email (sender_email or SENDER_EMAIL env var) is required.")
    
    def _default_german_template(self) -> str:
        """Return default German offer template with aggressive negotiation tactics."""
        return """Sehr geehrte Damen und Herren,

Ihre Immobilie in {address} hat meine Aufmerksamkeit erregt, da sie exakt meinem Suchprofil entspricht.

<b>Objekt:</b> {title}
<b>Lage:</b> {address}
<b>Ihr Angebotspreis:</b> €{listing_price:,.0f}

Als langjähriger Immobilienkäufer in Wien habe ich die aktuelle Marktlage genau analysiert. Die drastisch gestiegenen Zinssätze (aktuell 4-5% für Immobilienkredite), verschärfte Kreditvergaberichtlinien der KIM-Verordnung sowie die erhöhten Sanierungs- und Nebenkosten haben den Markt fundamental verändert{renovation_note}{altbau_note}.

Unter Berücksichtigung meiner Finanzierungskosten, der monatlichen Belastung durch Kredit und Betriebskosten sowie dem aktuellen Marktwert kann ich Ihnen folgendes realistisches Kaufangebot unterbreiten:

<b>Mein Kaufangebot: €{offer_price:,.0f}</b>

<b>Was Sie von mir erwarten können:</b>
• Bereits genehmigte Bankfinanzierung mit sofortiger Zusage
• Kaufvertrag innerhalb von 21 Tagen möglich
• Keine Maklerkette, direkte und unkomplizierte Abwicklung
• Professionelle Kaufabwicklung über renommierte Rechtsanwaltskanzlei
• Flexible Übernahme nach Ihren Zeitvorstellungen
• Seriöser, verlässlicher Käufer mit nachweisbarer Bonität

Ich habe in den letzten 24 Monaten bereits drei Immobilien in Wien erworben und weiß, worauf es bei einem reibungslosen Verkauf ankommt. Mein Angebot reflektiert den realistischen Marktwert unter Berücksichtigung aller Nebenkosten (Grunderwerbsteuer 3,5%, Eintragungsgebühr 1,1%, Makler, notwendige Investitionen) sowie der aktuellen Finanzierungskonditionen.

<b>Dieses Angebot gilt für 7 Tage.</b> Bei Interesse können wir bereits diese Woche einen Besichtigungstermin vereinbaren und alle Details persönlich besprechen.

Ich freue mich auf Ihre rasche Rückmeldung.

Mit freundlichen Grüßen,
{sender_name}

---
Direktkontakt: {sender_email}
Objektreferenz: {listing_url}
"""
    
    def calculate_offer_price(self, listing_price: float) -> float:
        """Calculate offer price based on configured discount."""
        discount_factor = 1 - (self.offer_discount / 100)
        return round(listing_price * discount_factor, -2)  # Round to nearest 100
    
    def format_message(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Format the email message for a listing with smart negotiation context."""
        listing_price = float(listing.get('price_total', 0))
        offer_price = self.calculate_offer_price(listing_price)
        
        # Determine if Altbau (old building) - typically built before 1945
        year_built = listing.get('year_built')
        is_altbau = year_built and year_built < 1945
        
        # Check condition for renovation needs
        condition = (listing.get('condition') or '').lower()
        needs_renovation = any(word in condition for word in ['sanierung', 'renovierung', 'renovierungsbedürftig'])
        
        # Build contextual notes for negotiation
        renovation_note = ""
        altbau_note = ""
        
        if needs_renovation or not condition:
            renovation_note = ". Zusätzlich kalkuliere ich Renovierungskosten von ca. €20.000-40.000 ein"
        
        if is_altbau:
            altbau_note = ". Bei Altbauten sind erfahrungsgemäß erhöhte Instandhaltungskosten sowie potenzielle versteckte Mängel einzukalkulieren"
        
        # Build template variables
        safe_title = bleach.clean(listing.get('title', '') or '', tags=[], strip=True)
        safe_address = bleach.clean(listing.get('address', '') or '', tags=[], strip=True)
        safe_sender_name = bleach.clean(self.sender_name, tags=[], strip=True)

        template_vars = {
            'title': safe_title,
            'address': safe_address,
            'listing_price': listing_price,
            'offer_price': offer_price,
            'source': listing.get('source', 'Ihrer Webseite').title(),
            'listing_url': listing.get('url', ''),
            'sender_name': safe_sender_name,
            'sender_email': self.sender_email,
            'area_m2': listing.get('area_m2', 'N/A'),
            'rooms': listing.get('rooms', 'N/A'),
            'bezirk': listing.get('bezirk', 'Wien'),
            'discount_percent': self.offer_discount,
            'renovation_note': renovation_note,
            'altbau_note': altbau_note
        }
        
        # Format subject
        subject = self.subject_template.format(**template_vars)
        
        # Format body
        body_text = self.message_template.format(**template_vars)
        
        # Convert to HTML (simple conversion)
        body_html = body_text.replace('\n', '<br>\n')
        body_html = f"<html><body>{body_html}</body></html>"
        
        return {
            'subject': subject,
            'body_text': body_text,
            'body_html': body_html,
            'listing_price': listing_price,
            'offer_price': offer_price
        }
    
    def send_email(self, to_email: str, subject: str, body_text: str, body_html: str,
                   listing: Dict[str, Any] = None, unsubscribe_url: str = None) -> bool:
        """Send an email via SMTP."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            safe_sender_name = self.sender_name.replace('\n', '').replace('\r', '')
            msg['From'] = f"{safe_sender_name} <{self.sender_email}>"
            msg['To'] = to_email

            if listing:
                listing_url = listing.get('url', '')
                listing_url_hash = hashlib.sha256(listing_url.encode()).hexdigest()[:12]
                thread_id = f"<immo-scouter-{listing_url_hash}@{socket.gethostname()}>"
                msg['Reply-To'] = self.sender_email
                msg['References'] = thread_id
                msg['In-Reply-To'] = thread_id

            if unsubscribe_url:
                msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

            part1 = MIMEText(body_text, 'plain', 'utf-8')
            part2 = MIMEText(body_html, 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            email_hash = hashlib.sha256(to_email.encode()).hexdigest()[:8]
            logging.info(f"📤 Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")

            if not self.smtp_user or not self.smtp_password:
                raise ValueError("SMTP credentials are missing. Set SMTP_USER and SMTP_PASSWORD environment variables.")

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls(context=ssl.create_default_context())
                server.login(str(self.smtp_user), str(self.smtp_password))
                server.sendmail(str(self.sender_email), to_email, msg.as_string())

            logging.info(f"✅ Email sent successfully to {email_hash}...")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            email_hash = hashlib.sha256(to_email.encode()).hexdigest()[:8]
            logging.error(f"❌ SMTP Auth failed for {email_hash}...: {e}")
            logging.error("💡 For Gmail: Use an App Password (https://myaccount.google.com/apppasswords)")
            return False
        except smtplib.SMTPException as e:
            email_hash = hashlib.sha256(to_email.encode()).hexdigest()[:8]
            logging.error(f"❌ SMTP error for {email_hash}...: {e}")
            return False
        except Exception as e:
            email_hash = hashlib.sha256(to_email.encode()).hexdigest()[:8]
            logging.error(f"❌ Failed to send to {email_hash}...: {e}")
            return False
    
    def send_offer(self, listing: Dict[str, Any], contact_email: str) -> OutreachMessage:
        """Send an offer email for a listing."""
        formatted = self.format_message(listing)

        unsub_token = _generate_unsubscribe_token(contact_email)
        unsub_url = f"{UNSUBSCRIBE_BASE_URL}?token={unsub_token}&email={contact_email}"

        footer_html = f'<br><br><small><a href="{unsub_url}">Unsubscribe</a> | <a href="https://immo-scouter.com">Immo-Scouter</a></small>'
        footer_text = f'\n\n---\nUnsubscribe: {unsub_url}'

        formatted['body_html'] = formatted['body_html'].replace('</body></html>', f'{footer_html}</body></html>')
        formatted['body_text'] += footer_text

        message = OutreachMessage(
            to_email=contact_email,
            subject=formatted['subject'],
            body_html=formatted['body_html'],
            body_text=formatted['body_text'],
            listing_url=listing.get('url', ''),
            listing_price=formatted['listing_price'],
            offer_price=formatted['offer_price']
        )

        success = self.send_email(
            to_email=contact_email,
            subject=formatted['subject'],
            body_text=formatted['body_text'],
            body_html=formatted['body_html'],
            listing=listing,
            unsubscribe_url=unsub_url
        )

        message.sent_at = datetime.now()
        message.success = success
        if not success:
            message.error_message = "Failed to send email"

        return message
    
    def send_offers_batch(self, listings_with_contacts: List[Dict[str, Any]]) -> List[OutreachMessage]:
        """
        Send offer emails to a batch of listings with SMTP connection reuse.
        """
        results = []
        sent_count = 0

        if not listings_with_contacts:
            return results

        context = ssl.create_default_context()

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls(context=context)
                server.login(str(self.smtp_user), str(self.smtp_password))

                for item in listings_with_contacts:
                    if sent_count >= self.max_emails_per_run:
                        logging.warning(f"⚠️ Reached max emails per run ({self.max_emails_per_run})")
                        break

                    listing = item.get('listing', {})
                    contact_email = item.get('contact_email')

                    if not contact_email:
                        logging.warning(f"⚠️ No contact email for listing: {listing.get('url', 'unknown')}")
                        continue

                    if not _is_valid_email(contact_email):
                        logging.warning(f"⚠️ Invalid email format")
                        continue

                    email_hash = hashlib.sha256(contact_email.encode()).hexdigest()[:8]
                    logging.info(f"📧 Sending offer to {email_hash}... for {listing.get('url', 'unknown')}")

                    unsub_token = _generate_unsubscribe_token(contact_email)
                    unsub_url = f"{UNSUBSCRIBE_BASE_URL}?token={unsub_token}&email={contact_email}"

                    result = self._send_single_email_via_server(server, listing, contact_email, unsub_url)
                    results.append(result)

                    if result.success:
                        sent_count += 1

                    if sent_count < len(listings_with_contacts):
                        smart_sleep(self.delay_between_emails)

        except smtplib.SMTPException as e:
            logging.error(f"❌ SMTP connection error: {e}")

        logging.info(f"📊 Batch complete: {sent_count}/{len(listings_with_contacts)} emails sent")
        return results

    def _send_single_email_via_server(self, server, listing: Dict[str, Any], contact_email: str, unsubscribe_url: str) -> OutreachMessage:
        """Send one email using an existing SMTP server connection."""
        formatted = self.format_message(listing)

        footer_html = f'<br><br><small><a href="{unsubscribe_url}">Unsubscribe</a> | <a href="https://immo-scouter.com">Immo-Scouter</a></small>'
        footer_text = f'\n\n---\nUnsubscribe: {unsubscribe_url}'
        formatted['body_html'] = formatted['body_html'].replace('</body></html>', f'{footer_html}</body></html>')
        formatted['body_text'] += footer_text

        message = OutreachMessage(
            to_email=contact_email,
            subject=formatted['subject'],
            body_html=formatted['body_html'],
            body_text=formatted['body_text'],
            listing_url=listing.get('url', ''),
            listing_price=formatted['listing_price'],
            offer_price=formatted['offer_price']
        )

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = formatted['subject']
            safe_sender_name = self.sender_name.replace('\n', '').replace('\r', '')
            msg['From'] = f"{safe_sender_name} <{self.sender_email}>"
            msg['To'] = contact_email

            listing_url = listing.get('url', '')
            listing_url_hash = hashlib.sha256(listing_url.encode()).hexdigest()[:12]
            thread_id = f"<immo-scouter-{listing_url_hash}@{socket.gethostname()}>"
            msg['Reply-To'] = self.sender_email
            msg['References'] = thread_id
            msg['In-Reply-To'] = thread_id
            msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'
            msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

            part1 = MIMEText(formatted['body_text'], 'plain', 'utf-8')
            part2 = MIMEText(formatted['body_html'], 'html', 'utf-8')
            msg.attach(part1)
            msg.attach(part2)

            server.sendmail(str(self.sender_email), contact_email, msg.as_string())

            message.sent_at = datetime.now()
            message.success = True
            email_hash = hashlib.sha256(contact_email.encode()).hexdigest()[:8]
            logging.info(f"✅ Email sent successfully to {email_hash}...")
        except Exception as e:
            message.sent_at = datetime.now()
            message.success = False
            message.error_message = str(e)
            email_hash = hashlib.sha256(contact_email.encode()).hexdigest()[:8]
            logging.error(f"❌ Failed to send to {email_hash}...: {e}")

        return message
    
    def test_connection(self) -> bool:
        """Test SMTP connection without sending an email."""
        try:
            logging.info(f"🔌 Testing SMTP connection to {self.smtp_host}:{self.smtp_port}...")
            
            # Ensure credentials are not None
            if not self.smtp_user or not self.smtp_password:
                raise ValueError("SMTP credentials are missing. Set SMTP_USER and SMTP_PASSWORD environment variables.")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                server.login(str(self.smtp_user), str(self.smtp_password))
                server.noop()  # No-operation command to verify connection
            
            logging.info("✅ SMTP connection test successful!")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logging.error("❌ SMTP Authentication failed!")
            logging.error("💡 For Gmail: Enable 2FA and create an App Password")
            logging.error("   https://myaccount.google.com/apppasswords")
            return False
        except Exception as e:
            logging.error(f"❌ SMTP connection test failed: {e}")
            return False


