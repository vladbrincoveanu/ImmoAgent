---
name: handoff
description: Write a session handoff before /clear. Use at any task boundary, when context exceeds ~70%, or when the user says "handoff", "checkpoint", or "wrap up the session".
---

# Session handoff

1. Write `.claude/handoffs/<YYYY-MM-DD-HHMM>.md` (use `date +%F-%H%M`) with EXACTLY this structure, <=10 lines total:

   - **Goal:** one line
   - **Done:** what is finished and verified
   - **Next:** the single next concrete action
   - **Risks/open:** unknowns, failing tests, traps
   - **Files/cmds:** key paths and the command to resume

2. No prose beyond the file. Reply with one line only:
   "Handoff written → run /clear; it autoloads next session (context-guard)."

Rules: never start new work after writing a handoff; never exceed 10 lines; overwrite is fine — newest file wins.
