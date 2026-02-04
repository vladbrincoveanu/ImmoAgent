#!/usr/bin/env python3
"""
Automated Outreach Script - Sends templated offer emails to top listings.

This script:
1. Fetches top listings from MongoDB (same logic as run_top5.py)
2. Extracts contact information (email) from each listing page
3. Sends a German offer email with a configurable discount (default: 30% below asking)

Configuration required in config.json under "outreach" section:
{
    "outreach": {
        "enabled": true,
        "smtp_provider": "gmail",
        "smtp_user": "your-email@gmail.com",
        "smtp_password": "your-app-password",
        "sender_name": "Max Mustermann",
        "offer_discount": 30,
        "max_emails_per_run": 5,
        "delay_between_emails": 10
    }
}

For Gmail: You need to use an App Password, not your regular password.
Create one at: https://myaccount.google.com/apppasswords
"""

import argparse
import sys
import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Robust config.json search logic
def ensure_config_json_on_path():
    possible_paths = [
        os.path.join(project_root, 'config.json'),
        os.path.join(os.path.dirname(project_root), 'config.json'),
        os.path.join(project_root, 'Project', 'config.json'),
        os.path.join(project_root, '..', 'config.json'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.chdir(os.path.dirname(path))
            print(f"✅ Found config.json at: {path}")
            break

ensure_config_json_on_path()

from Application.helpers.utils import load_config
from Application.helpers.listing_validator import filter_valid_listings
from Application.outreach.contact_extractor import ContactExtractor, ContactType
from Application.outreach.email_sender import EmailSender, OutreachMessage
from Integration.mongodb_handler import MongoDBHandler
import json


def setup_logging():
    """Setup logging configuration."""
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('log/outreach.log')
        ]
    )


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Send automated offer emails to top property listings"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of top listings to process (default: 5)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=30.0,
        help="Minimum listing score to consider (default: 30.0)"
    )
    parser.add_argument(
        "--discount",
        type=int,
        help="Discount percentage to offer (overrides config, default: 30)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract contacts and format messages but don't send emails"
    )
    parser.add_argument(
        "--test-smtp",
        action="store_true",
        help="Only test SMTP connection and exit"
    )
    parser.add_argument(
        "--send-test-email",
        type=str,
        metavar="EMAIL",
        help="Send a test email to the specified email address to verify email sending works"
    )
    parser.add_argument(
        "--skip-sent",
        action="store_true",
        default=True,
        help="Skip listings that have already received an outreach email (default: True)"
    )
    parser.add_argument(
        "--no-skip-sent",
        action="store_false",
        dest="skip_sent",
        help="Include listings even if they already received an outreach email"
    )
    return parser.parse_args()


def main():
    """Main function to run the outreach process."""
    setup_logging()
    args = parse_cli_args()
    
    print("📧 Starting Automated Outreach")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    if not config:
        logging.error("❌ Failed to load configuration")
        return False
    
    # Get outreach configuration
    outreach_config = config.get('outreach', {})
    
    if not outreach_config.get('enabled', False):
        logging.error("❌ Outreach is not enabled in config.json")
        logging.info("💡 Add 'outreach' section with 'enabled: true' to config.json")
        print("\n📝 Example configuration to add to config.json:")
        print('''
    "outreach": {
        "enabled": true,
        "smtp_provider": "gmail",
        "smtp_user": "your-email@gmail.com",
        "smtp_password": "your-app-password",
        "sender_name": "Your Name",
        "sender_email": "your-email@gmail.com",
        "offer_discount": 30,
        "max_emails_per_run": 5,
        "delay_between_emails": 10,
        "subject_template": "Anfrage zu Ihrer Immobilie - {address}"
    }
        ''')
        return False
    
    # Load secrets from secrets.json if it exists
    secrets = {}
    secrets_path = os.path.join(project_root, 'secrets.json')
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, 'r') as f:
                secrets = json.load(f)
                logging.info("✅ Loaded credentials from secrets.json")
        except Exception as e:
            logging.warning(f"⚠️ Could not load secrets.json: {e}")
    
    # Validate required config (check secrets.json, environment variables, then config.json)
    smtp_user = secrets.get('smtp_user') or os.getenv('SMTP_USER') or outreach_config.get('smtp_user')
    smtp_password = secrets.get('smtp_password') or os.getenv('SMTP_PASSWORD') or outreach_config.get('smtp_password')
    
    missing = []
    if not smtp_user:
        missing.append('smtp_user (or SMTP_USER env var)')
    if not smtp_password:
        missing.append('smtp_password (or SMTP_PASSWORD env var)')
    
    if missing:
        logging.error(f"❌ Missing required outreach config: {', '.join(missing)}")
        logging.info("💡 You can set environment variables:")
        logging.info("   export SMTP_USER='your-email@gmail.com'")
        logging.info("   export SMTP_PASSWORD='your-app-password'")
        logging.info("💡 Or add them to config.json (less secure)")
        return False
    
    # Update outreach_config with credentials from secrets.json (priority order: secrets.json > env > config)
    if smtp_user:
        outreach_config['smtp_user'] = smtp_user
    if smtp_password:
        outreach_config['smtp_password'] = smtp_password
    
    # Apply CLI overrides
    if args.discount:
        outreach_config['offer_discount'] = args.discount
    
    # Initialize email sender
    try:
        email_sender = EmailSender(outreach_config)
    except ValueError as e:
        logging.error(f"❌ Email sender configuration error: {e}")
        return False
    
    # Test SMTP if requested
    if args.test_smtp:
        print("🔌 Testing SMTP connection...")
        success = email_sender.test_connection()
        return success
    
    # Send test email if requested
    if args.send_test_email:
        print(f"📧 Sending test email to {args.send_test_email}...")
        test_subject = "Test Email from Immo-Scouter"
        test_body_text = """This is a test email from Immo-Scouter.

If you receive this email, it means your email sending configuration is working correctly!

You can now use the outreach feature to send offer emails to property listings.

Configuration:
- SMTP Provider: {provider}
- Sender: {sender_name} <{sender_email}>
- SMTP Host: {smtp_host}:{smtp_port}
""".format(
            provider=outreach_config.get('smtp_provider', 'unknown'),
            sender_name=email_sender.sender_name,
            sender_email=email_sender.sender_email,
            smtp_host=email_sender.smtp_host,
            smtp_port=email_sender.smtp_port
        )
        test_body_html = f"<html><body><p>{test_body_text.replace(chr(10), '<br>')}</p></body></html>"
        
        success = email_sender.send_email(
            to_email=args.send_test_email,
            subject=test_subject,
            body_text=test_body_text,
            body_html=test_body_html
        )
        
        if success:
            print(f"✅ Test email sent successfully to {args.send_test_email}!")
            print("💡 Check your inbox (and spam folder) to confirm receipt.")
        else:
            print(f"❌ Failed to send test email to {args.send_test_email}")
        
        return success
    
    # Initialize MongoDB handler
    mongo_uri = config.get('mongodb_uri', 'mongodb://localhost:27017/')
    mongo = MongoDBHandler(uri=mongo_uri)
    
    if not mongo.client:
        logging.error("❌ Failed to connect to MongoDB")
        return False
    
    # Initialize contact extractor
    contact_extractor = ContactExtractor(config=config, use_selenium=True)
    
    print(f"📊 Fetching top {args.limit} listings...")
    print(f"🎯 Minimum score: {args.min_score}")
    print(f"💰 Offer discount: {outreach_config.get('offer_discount', 30)}%")
    
    # Fetch top listings from MongoDB
    top5_config = config.get('top5', {})
    excluded_districts = top5_config.get('excluded_districts', [])
    min_rooms = top5_config.get('min_rooms', 0)
    
    listings = mongo.get_top_listings(
        limit=args.limit * 3,  # Fetch extra in case some don't have contacts
        min_score=args.min_score,
        days_old=365,
        excluded_districts=excluded_districts,
        min_rooms=min_rooms,
        exclude_recently_sent=args.skip_sent,
        recently_sent_days=30  # Skip if outreach sent in last 30 days
    )
    
    # Filter valid listings
    valid_listings = [
        l for l in listings
        if isinstance(l.get('price_total'), (int, float)) and l.get('price_total', 0) > 0
    ]
    valid_listings = filter_valid_listings(valid_listings)
    
    if not valid_listings:
        logging.warning("⚠️ No valid listings found")
        return True
    
    print(f"✅ Found {len(valid_listings)} valid listings")
    
    # Extract contacts for each listing
    listings_with_contacts = []
    for i, listing in enumerate(valid_listings[:args.limit * 2], 1):
        if len(listings_with_contacts) >= args.limit:
            break
            
        url = listing.get('url', '')
        price = listing.get('price_total', 0)
        source = listing.get('source', 'unknown')
        
        print(f"\n[{i}] Processing: {url[:60]}...")
        print(f"    💰 Price: €{price:,.0f} | Source: {source}")
        
        # Check if already contacted
        if args.skip_sent and mongo.collection is not None:
            existing = mongo.collection.find_one({
                'url': url,
                'outreach_sent': True
            })
            if existing:
                print(f"    ⏭️ Already contacted - skipping")
                continue
        
        # Extract contact
        contact = contact_extractor.extract_contact(listing)
        
        if contact.contact_type == ContactType.EMAIL and contact.email:
            offer_price = email_sender.calculate_offer_price(price)
            print(f"    📧 Found email: {contact.email}")
            print(f"    💵 Offer: €{offer_price:,.0f} ({outreach_config.get('offer_discount', 30)}% below asking)")
            
            listings_with_contacts.append({
                'listing': listing,
                'contact_email': contact.email,
                'contact_info': contact.to_dict()
            })
        elif contact.contact_type == ContactType.CONTACT_FORM:
            print(f"    📝 Has contact form (not supported yet): {contact.contact_form_url or 'on page'}")
        elif contact.phone:
            print(f"    📞 Phone only: {contact.phone}")
        else:
            print(f"    ❌ No contact found")
        
        # Small delay between page loads
        time.sleep(1)
    
    contact_extractor.cleanup()
    
    if not listings_with_contacts:
        logging.warning("⚠️ No listings with valid email contacts found")
        print("\n💡 Most listings use contact forms instead of direct emails.")
        print("   Consider implementing contact form automation for better coverage.")
        return True
    
    print(f"\n{'='*50}")
    print(f"📧 Ready to send {len(listings_with_contacts)} emails")
    
    if args.dry_run:
        print("\n🔍 DRY RUN - Showing what would be sent:\n")
        for item in listings_with_contacts:
            listing = item['listing']
            email = item['contact_email']
            formatted = email_sender.format_message(listing)
            
            print(f"To: {email}")
            print(f"Subject: {formatted['subject']}")
            print(f"Listing: {listing.get('url', 'N/A')}")
            print(f"Original Price: €{formatted['listing_price']:,.0f}")
            print(f"Offer Price: €{formatted['offer_price']:,.0f}")
            print("-" * 40)
            print(formatted['body_text'][:500] + "..." if len(formatted['body_text']) > 500 else formatted['body_text'])
            print("=" * 50 + "\n")
        
        print("✅ Dry run complete. Use without --dry-run to actually send emails.")
        return True
    
    # Send emails
    print("\n📤 Sending emails...")
    results = email_sender.send_offers_batch(listings_with_contacts)
    
    # Update MongoDB to mark listings as contacted
    success_count = 0
    for result, item in zip(results, listings_with_contacts):
        if result.success:
            success_count += 1
            listing = item['listing']
            
            # Mark as contacted in MongoDB
            if mongo.collection is not None:
                mongo.collection.update_one(
                    {'url': listing.get('url')},
                    {
                        '$set': {
                            'outreach_sent': True,
                            'outreach_sent_at': time.time(),
                            'outreach_email': item['contact_email'],
                            'outreach_offer_price': result.offer_price
                        }
                    }
                )
    
    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Outreach Summary")
    print(f"{'='*50}")
    print(f"✅ Emails sent successfully: {success_count}/{len(results)}")
    print(f"❌ Failed: {len(results) - success_count}")
    
    if success_count > 0:
        print(f"\n💰 Total potential savings if offers accepted:")
        total_savings = sum(
            r.listing_price - r.offer_price 
            for r in results if r.success
        )
        print(f"   €{total_savings:,.0f}")
    
    return success_count > 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


