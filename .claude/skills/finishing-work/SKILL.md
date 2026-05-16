---
name: finishing-work
description: Use when implementation is complete and you're tempted to say "all done" — enforces verification before declaring done. Step 1: Run project tests. Step 2: Live smoke test (actually run the feature, not just unit tests). Step 3: Fix loop (brainstorm before patching). Step 4: Code review. Step 5: Simplify. Loop until clean.
---

# Finishing Work

## Overview

Every implementation is only done when it survives real-world verification, not just unit tests. This skill enforces a mandatory post-implementation loop: unit tests → live smoke test → fix failures via brainstorming → repeat until clean → code review → simplify.

**Core principle: "Done" means verified, not implemented.**

---

## When to Use

- All planned tasks in a session are marked `completed`
- You are tempted to say "all tests pass, we're done"
- You ran `pytest` once and it passed
- You implemented a fix but didn't re-run the live smoke test
- A feature worked in the unit test but failed in the live pipeline

**Trigger phrases that mean you MUST use this skill:**
- "tests pass" (without live verification)
- "implementation is complete"
- "all tasks done"
- "let me summarize what we did"

---

## Mandatory Completion Checklist

After every implementation session, complete ALL steps before declaring done.

### Step 1: Unit Test Suite

**Run the project's test suite — whatever that project uses:**

```bash
# Detect and run the correct test command for this project
# Python
pytest -v --tb=short
# Node/JS
npm test / npm run test
# Go
go test ./...
# Rust
cargo test
# Ruby
rspec
# Generic (if you can't detect)
find . -name "*test*" -type f | head -5  # inspect before running
```

- **All tests must pass.** If any fail → go to Step 3 (Fix Loop) first.
- **Do NOT skip this step** even if you "know the tests pass."
- If project has no tests → note that explicitly, then skip to Step 2.

### Step 2: Live Smoke Test

**Actually run the feature** — not unit tests, but the real code path:

- **Web app**: start dev server, curl endpoints, verify HTML renders
- **API**: make real requests to endpoints, check responses
- **Script/tool**: run it with real input, verify output
- **Background job**: trigger it, check it actually runs
- **Frontend component**: verify it mounts without errors

```bash
# Example patterns by project type:
# Flask/Express API
python run.py &
curl -s http://localhost:5000/health
# Next.js app
npm run dev &
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/
# Python scraper
python run.py --dry-run
# Background worker
python run_outreach.py --dry-run --limit=1
```

**Pass criteria:**
- No crashes (exit code 0)
- No uncaught exceptions in logs
- Output is non-empty and reasonable
- HTTP responses are 2xx (not 500)

**If live test fails** → go to Step 3 (Fix Loop).

### Step 3: Fix Loop

**NEVER patch failures without understanding them first. ALWAYS use brainstorming.**

1. Identify the failure type — don't guess
2. Invoke brainstorming for each failing component
3. Implement the brainstormed fix (not a guess)
4. Re-run smoke test for ONLY the failed part
5. Re-run full test suite
6. Repeat until clean

**Do not ad-hoc patch.** Brainstorm first.

### Step 4: Code Review

After all tests pass and smoke test is clean:

Run code review on changed files. Address all HIGH and MEDIUM findings. SKIP is valid only with explicit reason.

### Step 5: Simplify

After code review fixes:

1. Scan for dead code, redundant state, over-engineering
2. Apply refactoring suggestions
3. Ensure no obvious improvements remain

---

## Loop Until Clean

```
Implement → Unit Tests → Live Smoke Test → [Fail? → Brainstorm Fix → Re-test] → Code Review → Simplify → DONE
```

**Loop does NOT exit after one pass.** Repeat until:

- ✅ All unit tests pass
- ✅ Live smoke test passes (no crashes, correct output)
- ✅ No HIGH/MEDIUM issues in code review
- ✅ Code simplified (no obvious improvements remaining)

---

## Common Rationalizations — STOP HERE

These mean you are NOT done:

| Rationalization | Reality |
|----------------|---------|
| "Unit tests pass, that's enough" | Unit tests don't catch integration failures, network issues, or runtime crashes |
| "It worked last time, probably fine" | Each run can have different failure modes; retest every time |
| "I'll just patch the failing test" | Patching tests without understanding = technical debt; brainstorm first |
| "One test failure is minor" | Any failure means verification is incomplete; loop until clean |
| "The live test took too long" | Skipping live verification means shipped features are unverified |
| "We can review later" | Code review after live verification catches different issues |
| "No tests, so we're done after smoke test" | Unit tests are Step 1; smoke test is Step 2; both required |

**If you catch yourself saying any of these: you are not done. Return to Step 1.**

---

## Project-Specific Notes

**Immo-Scouter (this project):**
- Python: `cd Project && pytest Tests/ -v`
- Dashboard: `cd dashboard && npm run dev` → curl routes
- No separate smoke test script — run the actual scripts (`run.py`, `run_top5.py`, etc.)

**Other projects**: adapt test commands to whatever that project uses. The skill pattern is the same; the commands are project-specific.

---

## Integration

**Called by:**
- **executing-plans** — after all tasks complete
- **subagent-driven-development** — after all batches complete
- Any time you catch yourself about to say "all done"

**Required sub-skills (when needed):**
- **brainstorming** — for any fix in Step 3
- **code-review** or **pr-review-expert** — for Step 4