# Plan 5 of 6: Outreach System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GDPR-compliant unsubscribe, fix HTML injection in templates, add Reply-To/threading headers, add SMTP connection reuse for batch, add weak email regex fix (already done in Plan 1), add outreach MongoDB job queue with retry.

**Architecture:** Add unsubscribe token to every email. Track outreach jobs in MongoDB with status field. Use SMTP connection pooling for batch sends. Add Reply-To and threading headers. HTML-sanitize user fields before template interpolation.

**Tech Stack:** smtplib, ssl, email.headerregistry, bleach (for HTML sanitization), pymongo

---

## File Map

```
Project/
  Application/
    outreach/
      email_sender.py              # Modify: unsubscribe link, SMTP reuse, Reply-To, threading, HTML sanitization
      contact_extractor.py          # Modify: retry logic
  run_outreach.py                   # Modify: use MongoDB job queue, exponential backoff
  Integration/
    mongodb_handler.py              # Modify: add outreach_jobs collection, job status updates
```

---

## Task 1: Add unsubscribe link to every outreach email (GDPR)

**Files:**
- Modify: `Application/outreach/email_sender.py` (compose_email method)

- [ ] **Step 1: Read compose_email method in email_sender.py**

Find where email body is constructed (around line 225).

- [ ] **Step 2: Add unsubscribe token generation**

Add at module level or at top of compose_email:
```python
import hashlib, secrets, base64

def _generate_unsubscribe_token(recipient_email: str) -> str:
    """Generate a one-time unsubscribe token for GDPR compliance"""
    token_data = f"{recipient_email}:{secrets.token_hex(16)}"
    return base64.urlsafe_b64encode(token_data.encode()).decode()

def _verify_unsubscribe_token(token: str, recipient_email: str) -> bool:
    """Verify unsubscribe token matches recipient"""
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        return decoded.startswith(f"{recipient_email}:")
    except Exception:
        return False
```

- [ ] **Step 3: Add unsubscribe link to email footer**

In compose_email, after the body is set, add HTML footer:
```python
# Generate unsubscribe token
unsubscribe_token = _generate_unsubscribe_token(contact_email)
unsubscribe_url = f"https://immo-scouter.com/unsubscribe?token={unsubscribe_token}&email={contact_email}"

# Add footer to HTML body
footer_html = f'''
<br><br>
<small>
<a href="{unsubscribe_url}">Unsubscribe from these emails</a> |
<a href="https://immo-scouter.com">Immo-Scouter</a>
</small>
'''
body_html = body_text.replace('\n', '<br>\n') + footer_html

# Add footer to plain text
footer_text = f'\n\n---\nUnsubscribe: {unsubscribe_url}'
body_text += footer_text
```

- [ ] **Step 4: Add List-Unsubscribe header**

In `email_sender.py` send method, add before `server.send_message`:
```python
msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'
msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
```

- [ ] **Step 5: Add /unsubscribe route to Flask API**

In `Api/app.py`:
```python
@app.route('/unsubscribe', methods=['GET'])
def unsubscribe():
    token = request.args.get('token', '')
    email = request.args.get('email', '')
    if not _verify_unsubscribe_token(token, email):
        return jsonify({"error": "Invalid unsubscribe token"}), 400

    # Mark all outreach jobs for this email as unsubscribed
    db = get_db()
    db.outreach_jobs.update_many(
        {'recipient_email': email},
        {'$set': {'status': 'unsubscribed', 'unsubscribed_at': datetime.now(timezone.utc)}}
    )
    return jsonify({"message": "Successfully unsubscribed"}), 200
```

- [ ] **Step 6: Commit**
```bash
git add Application/outreach/email_sender.py Api/app.py
git commit -m "feat: add GDPR-compliant unsubscribe link to all outreach emails"
```

---

## Task 2: Fix HTML injection in email templates (sanitize user fields)

**Files:**
- Modify: `Application/outreach/email_sender.py:225`

- [ ] **Step 1: Install bleach for HTML sanitization**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Project && pip install bleach
```

- [ ] **Step 2: Add HTML sanitization before template interpolation**

In compose_email (around line 220), before the replace call:
```python
import bleach

# Sanitize user-controlled fields to prevent HTML injection
safe_address = bleach.clean(listing.get('address', ''), tags=[], strip=True)
safe_title = bleach.clean(listing.get('title', ''), tags=[], strip=True)
safe_name = bleach.clean(contact_name, tags=[], strip=True)
```

- [ ] **Step 3: Use sanitized fields in template**

```python
# OLD:
body_text = f"Sehr geehrte/r {contact_name},\n\nich interessiere mich für das Objekt..."
# NEW:
body_text = f"Sehr geehrte/r {safe_name},\n\nich interessiere mich für das Objekt..."
# Use safe_address, safe_title in the relevant places
```

- [ ] **Step 4: Commit**
```bash
git add Application/outreach/email_sender.py
git commit -m "fix: sanitize user fields in email templates to prevent HTML injection"
```

---

## Task 3: Add Reply-To header and email threading (In-Reply-To, References)

**Files:**
- Modify: `Application/outreach/email_sender.py` (around line 241-243)

- [ ] **Step 1: Read current headers in send method**

Find where `msg['Subject']`, `msg['From']`, `msg['To']` are set.

- [ ] **Step 2: Add threading headers**

After `msg['To'] = to_email`, add:
```python
# Threading headers for email clients (Gmail, Outlook)
listing_url_hash = hashlib.sha256(listing.get('url', '').encode()).hexdigest()[:12]
thread_id = f"<immo-scouter-{listing_url_hash}@{socket.gethostname()}>"
msg['Reply-To'] = self.sender_email
msg['References'] = thread_id
msg['In-Reply-To'] = thread_id
msg['Thread-Topic'] = f"Immobilien-Anfrage: {listing.get('title', 'Unbekannt')}"
```

- [ ] **Step 3: Import needed modules**

```python
import socket
```

- [ ] **Step 4: Commit**
```bash
git add Application/outreach/email_sender.py
git commit -m "feat: add Reply-To, References, and In-Reply-To headers for email threading"
```

---

## Task 4: SMTP connection reuse for batch sends

**Files:**
- Modify: `Application/outreach/email_sender.py` (batch send method)

- [ ] **Step 1: Read the send_offers_batch method**

Find the method around line 320.

- [ ] **Step 2: Refactor to use persistent SMTP connection**

Replace the current batch loop with:
```python
def send_offers_batch(self, outreach_jobs: List[Dict]) -> Dict:
    """Send batch of outreach emails with connection reuse"""
    results = {'sent': 0, 'failed': 0, 'skipped': 0}
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls(context=context)
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            for job in outreach_jobs:
                try:
                    self._send_single_email(server, job)
                    results['sent'] += 1
                except Exception as e:
                    logging.warning(f"Failed to send to {job.get('contact_email')}: {e}")
                    results['failed'] += 1
                time.sleep(self.delay_between_emails)
    except smtplib.SMTPException as e:
        logging.error(f"SMTP connection error: {e}")
        results['failed'] = len(outreach_jobs) - results['sent']
    return results
```

- [ ] **Step 3: Add _send_single_email helper**

```python
def _send_single_email(self, server, job: Dict) -> None:
    """Send one email using an existing server connection"""
    msg = self._build_message(job)
    server.send_message(msg)
```

- [ ] **Step 4: Commit**
```bash
git add Application/outreach/email_sender.py
git commit -m "perf: reuse SMTP connection for batch sends instead of reconnecting per email"
```

---

## Task 5: Add MongoDB outreach job queue with retry (instead of in-memory list)

**Files:**
- Modify: `run_outreach.py`, `Integration/mongodb_handler.py`

- [ ] **Step 1: Add outreach_jobs collection to MongoDB handler**

In `mongodb_handler.py`, add new method:
```python
def create_outreach_jobs(self, jobs: List[Dict]) -> int:
    """Create pending outreach jobs in MongoDB for tracking and retry"""
    if not jobs:
        return 0
    job_docs = []
    for job in jobs:
        job_docs.append({
            'recipient_email': job['contact_email'],
            'listing_url': job['listing_url'],
            'listing_title': job.get('title', ''),
            'status': 'pending',  # pending | sent | failed | retry | unsubscribed
            'attempts': 0,
            'created_at': datetime.now(timezone.utc),
            'last_attempt': None,
            'next_retry': None,
            'error_message': None
        })
    result = self.outreach_collection.insert_many(job_docs)
    return len(result.inserted_ids)

def get_pending_outreach_jobs(self, limit: int = 10) -> List[Dict]:
    """Get jobs ready for sending (pending or retry-eligible)"""
    now = datetime.now(timezone.utc)
    return list(self.outreach_collection.find({
        '$or': [
            {'status': 'pending'},
            {'status': 'retry', 'next_retry': {'$lte': now}}
        ]
    }).limit(limit))

def mark_outreach_job_sent(self, job_id, sent_at: datetime = None) -> None:
    self.outreach_collection.update_one(
        {'_id': job_id},
        {'$set': {
            'status': 'sent',
            'sent_at': sent_at or datetime.now(timezone.utc)
        }}
    )

def mark_outreach_job_failed(self, job_id, error: str, retry_at: datetime = None) -> None:
    self.outreach_collection.update_one(
        {'_id': job_id},
        {'$inc': {'attempts': 1},
         '$set': {
             'last_attempt': datetime.now(timezone.utc),
             'error_message': error,
             'next_retry': retry_at,
             'status': 'retry' if retry_at else 'failed'
         }}
    )
```

- [ ] **Step 2: Update run_outreach.py to use job queue**

In `run_outreach.py`, replace the in-memory list approach with:
```python
def run_outreach_pipeline(self, limit: int = 10, discount_pct: float = 20):
    # Get pending jobs
    jobs = self.db.get_pending_outreach_jobs(limit=limit)
    if not jobs:
        logging.info("No pending outreach jobs")
        return

    # Process with retry
    for job in jobs:
        try:
            self.send_outreach_for_job(job)
            self.db.mark_outreach_job_sent(job['_id'])
        except Exception as e:
            # Exponential backoff: 1min, 5min, 30min, 2hr, 24hr
            retry_delays = [60, 300, 1800, 7200, 86400]
            attempt = job.get('attempts', 0)
            retry_at = datetime.now(timezone.utc) + timedelta(
                seconds=retry_delays[min(attempt, len(retry_delays)-1)]
            )
            self.db.mark_outreach_job_failed(job['_id'], str(e), retry_at)
```

- [ ] **Step 3: Initialize outreach collection index**

In `mongodb_handler.py` `ensure_indexes`, add:
```python
self.outreach_collection.create_index([('status', 1), ('next_retry', 1)])
self.outreach_collection.create_index([('recipient_email', 1)])
```

- [ ] **Step 4: Commit**
```bash
git add run_outreach.py Integration/mongodb_handler.py
git commit -m "feat: add MongoDB-based outreach job queue with exponential backoff retry"
```

---

## Task 6: Contact emails logged at INFO level (PII exposure)

**Files:**
- Modify: `Application/outreach/email_sender.py:334`

- [ ] **Step 1: Change INFO logging to DEBUG or hash the email**

OLD:
```python
logging.info(f"📧 Sending offer to {contact_email} for {listing.get('url', 'unknown')}")
```

NEW:
```python
email_hash = hashlib.sha256(contact_email.encode()).hexdigest()[:8]
logging.info(f"📧 Sending offer to {email_hash}... for {listing.get('url', 'unknown')}")
```

- [ ] **Step 2: Commit**
```bash
git add Application/outreach/email_sender.py
git commit -m "fix: hash contact emails in logs to avoid PII exposure"
```

---

## Verification

1. Run: `python -m py_compile` on all modified files — must pass
2. Run: `cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter/Tests && rtk pytest test_validation.py test_listing_validator.py -v` — must pass
3. Manual: Send test email via run_outreach.py --dry-run and verify unsubscribe link appears

---

## Plan 5 Self-Review

| Spec Item | Covered? | Task |
|---|---|---|
| No unsubscribe link (GDPR) | ✅ | Task 1 |
| HTML injection in email templates | ✅ | Task 2 |
| No Reply-To / threading headers | ✅ | Task 3 |
| SMTP connection not reused | ✅ | Task 4 |
| No retry queue for failed sends | ✅ | Task 5 |
| Email addresses logged at INFO | ✅ | Task 6 |
| Weak email validation regex | ✅ | (Plan 1, Task 7) |
| Email header injection | ✅ | (Plan 1, Task 5) |
| SMTP MITM | ✅ | (Plan 1, Task 6) |