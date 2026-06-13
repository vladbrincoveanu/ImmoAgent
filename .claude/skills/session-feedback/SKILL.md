---
name: session-feedback
description: Capture post-session feedback (what worked, what didn't, energy rating) into auto-memory after a skill run, especially /brainstorming. Triggers on /session-feedback or /sf.
---

# Session Feedback Capture

Capture what worked and what didn't after any substantial skill invocation. Writes to auto-memory so future sessions can adjust without re-asking the user.

## When to run

- After `/brainstorming`, `/caveman`, `/writing-plans`, `/code-reviewer`, `/compress`, or any skill that took meaningful cognitive effort
- Manual: `/session-feedback [skill-name]` or `/sf [skill-name]`
- Optional hook-based auto-trigger at SessionEnd if a skill was used in the last 30 minutes

## Inputs

- `skill-name` (optional) — name of the skill that was just run. If omitted, prompt the user.

## Steps

1. **Identify the skill that was just run.** If not provided, ask: "Which skill did you just run?" with options covering the common ones.
2. **Prompt for three things (in this order):**
   - **What worked** — concrete specifics ("the multi-perspective challenge pass caught a real ambiguity" — not "was good")
   - **What didn't** — concrete friction ("took 4 turns to settle on a goal" — vague is OK if it's an honest signal)
   - **Energy rating** — 1-5 scale (1 = drained, 5 = energized)
3. **One optional follow-up:** "Anything to lock in or change for next time?" (one line, optional — skip if user wants to stop)
4. **Write a feedback memory** at the auto-memory path:

```
<project-memory-dir>/feedback-<skill>-<YYYY-MM-DD>.md
```

Using this format:

```markdown
---
name: feedback-<skill>-<date>
description: <skill> feedback on <YYYY-MM-DD> — what worked, what didn't, energy <N>/5
metadata:
  type: feedback
---

**Skill:** <skill-name>
**Date:** <YYYY-MM-DD>
**Energy:** <N>/5

**What worked:**
- <bullet>
- <bullet>

**What didn't:**
- <bullet>
- <bullet>

**Lock in / change:**
- <bullet or "none">

**Why:** user feedback after <skill> run.
**How to apply:** <one-line guidance for future <skill> sessions>.
```

5. **Append a one-line pointer to MEMORY.md** under the existing feedback entries (keep the index tight, ≤150 chars per line).
6. **Confirm** to the user: "Saved feedback to `feedback-<skill>-<date>.md` (energy <N>/5)."

## Auto-trigger (optional, hook-based)

If a SessionEnd hook is configured, it can call this skill automatically. The hook checks:
- Was any skill invoked in the last 30 minutes? (track via tool history)
- If yes, prompt the user with the three questions before clearing context

Without a hook, the user invokes manually with `/session-feedback` (or `/sf` shorthand).

## Anti-patterns

- **Don't run for trivial sessions.** A 1-step `/compress` only needs energy + what didn't. Skip the "what worked" prompt.
- **Don't accept vague answers.** "Was fine" is not useful — ask for one specific example.
- **Don't auto-trigger without confirmation.** A pop-up before each /clear is annoying.
- **Don't replace the global CLAUDE.md "Recent Skill Feedback Patterns" section.** Both can coexist: CLAUDE.md is the live digest, `memory/feedback-*.md` is the persistent archive.

## Why this skill

- The CLAUDE.md "Recent Skill Feedback Patterns" section is hand-maintained and gets stale fast. Per-skill feedback files persist and don't drift.
- Energy ratings surface when a skill is consistently draining (≤2) so it can be revised or replaced.
- "What worked / didn't" catches issues that grill-me would miss because they only show up over multiple runs.

## Related

- [[brainstorming]] — primary use case
- [[caveman]] — also captures energy/style
- [[compress]] — sometimes run alongside
- Auto-memory format: see existing entries in `memory/feedback-*.md`
