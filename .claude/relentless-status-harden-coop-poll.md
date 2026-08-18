---
task: Harden co-op poll runtime
branch: relentless/harden-coop-poll
current_step: complete
status: completed
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
- [x] Verify and deploy

## Known Evidence
- `TELEGRAM_COOP_CHANNEL_ID` and `TELEGRAM_PRIVATE_COOP_CHANNEL_ID` are optional channel secrets.
- GitHub runner logs first showed `No module named 'selenium'`, then exposed the eager `EmailSender` import through `Application.outreach.__init__` as `No module named 'bleach'`.
- Latest dispatch runtime is about 2m25s.
- The focused co-op suite passes: `244 passed` and workflow-window tests `11 passed`.
- PR #41 merged as `8d7a455e6a6bbd2947d19a724a499d1e0962dcc5`.
- Live run `32131488795` succeeded in 1m59s on that merge SHA.
- Live logs show no Selenium or bleach import errors; Willhaben considered 10 of 16 newest URLs.
- Telegram channel IDs remain intentionally unconfigured and produce warnings only.
