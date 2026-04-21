# Global Skill Feedback Memory Loop — Design

**Date:** 2026-04-21
**Status:** Approved

---

## Overview

A layered system where key skills write feedback after completing their workflow, a periodic digest consolidates patterns, and `~/.claude/CLAUDE.md` stays current as the single source of truth for all projects.

**Key principle:** Skills write *observations*, not instructions. The digest distills those into usable memory.

---

## Architecture

### Override Strategy

Each overridden skill lives in `~/.claude/skills/<skill-name>/SKILL.md` and extends the original with a feedback step. Plugin updates don't overwrite these — they're local to your Claude config.

**Skills to override:**

| Skill | Override path | Feedback trigger |
|-------|--------------|-----------------|
| brainstorming | `~/.claude/skills/brainstorming/SKILL.md` | After user approves design |
| writing-plans | `~/.claude/skills/writing-plans/SKILL.md` | After plan written |
| verification-before-completion | `~/.claude/skills/verification-before-completion/SKILL.md` | After verification passes |
| finishing-a-development-branch | `~/.claude/skills/finishing-a-development-branch/SKILL.md` | After merge/PR/abandon |

**New skills:**

| Skill | Purpose |
|-------|---------|
| `~/.claude/skills/daily-memory-digest/SKILL.md` | Weekly review + CLAUDE.md update |

---

## Feedback Format

Written after each skill completes its workflow:

```markdown
---
name: <skill>-feedback-<timestamp>
type: feedback
---

## <Skill> Feedback

**Session:** <project name>
**Date:** <ISO date>
**Outcome:** <approved|rejected|modified|abandoned>

### What worked
- <bullet>

### What didn't work
- <bullet>

### Next time try
- <bullet>

### Energy level (1-5)
<number>
```

**Storage location:** `~/.claude/memory/feedback/<skill>-<date>.md`

---

## Modules

### Module: BrainstormingFeedbackWriter
- **Responsibility:** After a design is approved, write a structured feedback note to `~/.claude/memory/feedback/`
- **Interface:** Receives skill outcome (approved/rejected/modified), project name, brief notes on what worked/didn't. Outputs a `.md` file.
- **Dependencies:** `~/.claude/memory/feedback/` directory
- **Size target:** ~50 lines

### Module: WritingPlansFeedbackWriter
- **Responsibility:** After plan is written and saved, write feedback about the planning process itself
- **Interface:** Receives plan path, whether it was approved/modified/abandoned. Outputs feedback file.
- **Dependencies:** `~/.claude/memory/feedback/`
- **Size target:** ~50 lines

### Module: VerificationFeedbackWriter
- **Responsibility:** After verification passes, note any recurring failure patterns observed
- **Interface:** Receives verification outcome and any flaky/persistent issues noted
- **Dependencies:** `~/.claude/memory/feedback/`
- **Size target:** ~40 lines

### Module: FinishingFeedbackWriter
- **Responsibility:** After merge/PR/abandon, note the state of the branch and what wrapping issues occurred
- **Interface:** Receives outcome (merged/pr/abandoned), any refactoring gate issues, branch cleanliness
- **Dependencies:** `~/.claude/memory/feedback/`
- **Size target:** ~40 lines

### Module: MemoryDigestGenerator
- **Responsibility:** Scan feedback files, identify patterns across skills, generate CLAUDE.md delta
- **Interface:**
  - Input: scan `~/.claude/memory/feedback/` since last digest
  - Output: diff of proposed changes to `~/.claude/CLAUDE.md`
- **Dependencies:** `~/.claude/memory/metadata/last-digest-date`
- **Size target:** ~120 lines

### Module: FeedbackStore
- **Responsibility:** Append-only store of feedback files on disk
- **Interface:** `write_feedback(skill_name, outcome, notes)` → creates `~/.claude/memory/feedback/<skill>-<timestamp>.md`
- **Dependencies:** None (filesystem only)
- **Size target:** ~30 lines

---

## Data Flow

### Writing feedback (in-session, after each skill)

```
[Skill workflow completes]
    ↓
BrainstormingFeedbackWriter / WritingPlansFeedbackWriter / etc.
    ↓
FeedbackStore.write_feedback()
    → writes ~/.claude/memory/feedback/<skill>-<timestamp>.md
    ↓
[Session continues normally]
```

### Digest cycle (triggered weekly or on-demand)

```
[User runs daily-memory-digest skill]
    ↓
MemoryDigestGenerator.scan_feedback(last_digest_date)
    → reads all ~/.claude/memory/feedback/*.md since last digest
    ↓
MemoryDigestGenerator.identify_patterns()
    → groups by skill, extracts what_worked/what_didnt patterns
    ↓
MemoryDigestGenerator.generate_delta()
    → produces diff: lines to add/remove from ~/.claude/CLAUDE.md
    ↓
[Presents delta to user for approval]
    ↓
[On approval] → Edit tool updates ~/.claude/CLAUDE.md
    ↓
MemoryDigestGenerator.update_last_digest_date()
    → writes new date to ~/.claude/memory/metadata/last-digest-date
```

---

## File Structure

```
~/.claude/
├── CLAUDE.md                          # Global memory (updated by digest)
├── memory/
│   ├── feedback/                     # Feedback files written by skills
│   │   ├── brainstorming-2026-04-21.md
│   │   ├── writing-plans-2026-04-21.md
│   │   └── ...
│   └── metadata/
│       └── last-digest-date           # ISO date of last digest run
└── skills/
    ├── brainstorming/
    │   └── SKILL.md                  # Override + feedback step
    ├── writing-plans/
    │   └── SKILL.md                  # Override + feedback step
    ├── verification-before-completion/
    │   └── SKILL.md                  # Override + feedback step
    ├── finishing-a-development-branch/
    │   └── SKILL.md                  # Override + feedback step
    └── daily-memory-digest/
        └── SKILL.md                  # New: digest + CLAUDE.md update
```

---

## Error Handling

| Failure | Handling |
|---------|----------|
| Feedback write fails (disk full, permissions) | Log warning, continue session. Does not block skill completion. |
| No feedback files since last digest | Report "Nothing to digest — no new feedback". Exit gracefully. |
| Digest user rejects all changes | Skill exits. Feedback files persist for next cycle. |
| Feedback file corrupted | Skip file, log warning, continue with others. |

---

## Implementation Order

1. Create `~/.claude/memory/feedback/` directory
2. Create `~/.claude/memory/metadata/last-digest-date`
3. Create `~/.claude/skills/daily-memory-digest/SKILL.md` (digest skill first — basis for testing)
4. Create `~/.claude/skills/brainstorming/SKILL.md` (most commonly used)
5. Create `~/.claude/skills/writing-plans/SKILL.md`
6. Create `~/.claude/skills/verification-before-completion/SKILL.md`
7. Create `~/.claude/skills/finishing-a-development-branch/SKILL.md`
8. Run first digest manually to populate initial CLAUDE.md structure
