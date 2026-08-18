---
task: Harden co-op poll runtime
branch: relentless/harden-coop-poll
current_step: verifying optional dependency fix and live run
status: in_progress
---

## End State
- Current co-op workflow runs without misleading ERROR logs for optional Telegram channels.
- Coop runner has all dependencies needed for the configured Willhaben path.
- Automated polls process only the intended newest feed and complete within the cadence budget.
- Tests and a live GitHub Actions run verify the changes.

## Security
- A Telegram bot token was pasted into chat and must be revoked/rotated.
- Never commit or set the exposed token. User must add the replacement to GitHub Actions secrets.

## Progress
- [x] Create isolated branch
- [x] Trace runtime errors and poll scope
- [x] Add failing tests
- [x] Implement fixes
- [ ] Verify and deploy

## Known Evidence
- `TELEGRAM_COOP_CHANNEL_ID` and `TELEGRAM_PRIVATE_COOP_CHANNEL_ID` are optional channel secrets.
- GitHub runner logs first showed `No module named 'selenium'`, then exposed the eager `EmailSender` import through `Application.outreach.__init__` as `No module named 'bleach'`.
- Latest dispatch runtime is about 2m25s.
- The focused co-op suite passes: `244 passed` and workflow-window tests `11 passed`.
