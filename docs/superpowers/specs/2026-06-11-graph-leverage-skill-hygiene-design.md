# Spec: Graph-First Skills + Long-Term Skill Hygiene

**Date:** 2026-06-11
**Status:** approved (B + commit graph.json)
**Owner:** user (vladbrincoveanu) + agent
**Scope:** global + all 14 projects + 35+ skills
**Goal:** minimize token usage, maximize smartness/completeness; relentless skill hygiene

## Problem

Current state:
- 35+ skills in `~/.claude/skills/`; some stale, some duplicate, some broken
- Skills re-read code via grep (5-30k tokens/query) — 83% token waste vs. graph query
- Graph built once, not reused across skills
- No institutional memory of "why was this skill added, when verified, by whom"
- No periodic recheck → broken skills persist
- Brainstorming, code-review, playwright = core; not always being improved
- Future UI work may need new skills; no plan for them

## Goal (B approach + hygiene overlay)

### Token economics target
- Build cost: 600k-1.2M LLM tokens, 5-7 min wall (one-shot per project)
- Per-query cost: 2-5k tokens (vs. 30k naive)
- **Savings: 83%** at 100 queries/session
- Break-even: ~30-50 queries

### Hygiene targets
- All skills: audited, rechecked, faulty removed
- Past NVIDIA security audit for skills: re-run, act on findings
- Core skills (brainstorming, code-review, playwright): actively improved each session
- Future UI skills: deferred until concrete need (no pre-build)

## Architecture

### Layer 1: Graph as first-class artifact
- **Commit `graphify-out/graph.json` to each repo** (currently gitignored)
- Per-project `.graphify/` directory: `graph.json`, `cost.json`, `manifest.json`, `.needs_update`
- `.gitignore` pattern: keep `.graphify/` committed, ignore `graphify-out/cache/` (extract subagent transcripts)

### Layer 2: Skills consume graph (don't re-explore)

| Skill | Upgrade |
|-------|---------|
| `grill-me` | `graphify query "dependents of X"` + community labels as context |
| `verification-before-completion` | `graphify query "tests for X"` + freshness check |
| `subagent-driven-development` | Pass `graph-context-pack` (1-2k tokens) not file dumps |
| `finishing-a-development-branch` | `graphify query "untested changes"` + `graphify path` |
| `pr-review-expert` | (done) graph-first blast radius |
| `comprehensive-code-review` | (done) graph-first import verification |
| `brainstorming` Step 2 | (done) graph-first explore |
| `multi-architect` | `graphify explain + query` for arch decisions |
| `mcp-server-builder` | `graphify query` for server scope |
| `database-designer` | `graphify query "where is X stored"` |

### Layer 3: New skills to design

#### Module: `graph-context-pack` skill
- **Responsibility:** produce a 1-2k token subagent context (god nodes + top communities + active edges) from current graph
- **Interface:** `Skill graph-context-pack --for-subagent <task-description>` → returns context string
- **Dependencies:** `graphify-out/graph.json` (must be fresh)
- **Size target:** 150 lines (single-purpose)

#### Module: `graph-staleness-check` skill
- **Responsibility:** report mtime + commit-since-graph + node-count-drift; pre-flight for any graph-using skill
- **Interface:** returns `{fresh: true/false, age_days, drift_pct, recommended_action}`
- **Dependencies:** git, graph.json
- **Size target:** 100 lines

#### Module: `graph-blast-radius` skill
- **Responsibility:** given file/symbol → dependents + breaking-change risk score
- **Interface:** `Skill graph-blast-radius <file-or-symbol>` → structured report
- **Dependencies:** graph.json
- **Size target:** 120 lines

#### Module: `graph-rationale-write` skill
- **Responsibility:** write `rationale_for` edge to graph; used by brainstorming, verification, code-review
- **Interface:** `Skill graph-rationale-write --target <node-id> --reason "<text>"`
- **Dependencies:** graph.json
- **Size target:** 80 lines

### Layer 4: Skills write back to graph
- `brainstorming` (Step 9) → on design approval, write `rationale_for` edges
- `verification-before-completion` → mark nodes `verified: true`
- `code-reviewer` → add `review_issue` edges with severity
- `finishing-a-development-branch` → mark nodes `shipped: true`

### Layer 5: Memory ↔ graph cross-pollination
- `daily-memory-digest` → write graph rationales to memory
- `caveman`/`compress` → compress graph state to memory on session end
- New helper: `graph-to-memory` (one-shot)

### Layer 6: Skill hygiene (parallel to graph work)

#### Module: `skill-audit` (recurring task)
- **Responsibility:** scan `~/.claude/skills/*/SKILL.md` for staleness, broken refs, missing frontmatter, duplicate coverage
- **Interface:** returns `{deprecated: [...], to_improve: [...], missing_coverage: [...]}`
- **Dependencies:** `~/.claude/skills/`, `graphify-out/` (if exists for skills dir)
- **Size target:** 200 lines

#### Module: `nvidia-security-recheck` (one-shot)
- **Responsibility:** re-run the past NVIDIA security audit on all skills; act on findings
- **Interface:** invokes the audit methodology, diffs against past results
- **Dependencies:** past audit report (find it in `~/.claude/memory/` or git history)
- **Size target:** 150 lines

#### Module: `skill-deprecate` (helper)
- **Responsibility:** move faulty skill to `_deprecated/` with a one-line reason; log to feedback memory
- **Interface:** `Skill skill-deprecate <skill-name> --reason "<text>"`
- **Dependencies:** filesystem
- **Size target:** 50 lines

### Layer 7: Apply to all projects (per user request)
- Each project: `git checkout -b relentless/graph-first`; commit `graph.json`; append Codebase Exploration section (done for 14)
- Per-project verification: graph builds, `graphify query` returns expected

## Rollout sequence (5-10 sessions)

### Session 1 (now): foundation
- [x] Build immo-scouter graph (done, this session)
- [x] Add global CLAUDE.md §Graph-First (done)
- [x] Add project CLAUDE.md + AGENTS.md references (done, 14 + 11)
- [x] Update 3 skills (brainstorming, pr-review, code-review)
- [x] Generate callflow HTML (done)
- [ ] Save graph-leverage feedback memory (in progress)
- [ ] Write this design spec (in progress)
- [ ] Find past NVIDIA security audit report
- [ ] First `skill-audit` run; list faulty skills
- [ ] Commit immo-scouter `graph.json` to git on `relentless/graph-first` branch

### Sessions 2-4: core skill upgrades
- [ ] Build `graph-context-pack`, `graph-staleness-check` (new skills)
- [ ] Upgrade `grill-me`, `verification-before-completion` to graph-first
- [ ] Upgrade `subagent-driven-development` to use `graph-context-pack`
- [ ] Upgrade `finishing-a-development-branch` to graph-first
- [ ] First `nvidia-security-recheck`; act on findings
- [ ] First `skill-deprecate` pass; remove N faulty skills

### Sessions 5-7: write-back + cross-pollination
- [ ] Build `graph-rationale-write`, `graph-blast-radius`
- [ ] Wire `brainstorming` → `graph-rationale-write` on approval
- [ ] Wire `verification-before-completion` → mark verified
- [ ] Wire `code-reviewer` → review_issue edges
- [ ] Build `graph-to-memory` helper
- [ ] Wire `daily-memory-digest` → memory↔graph

### Sessions 8-10: rollout to all projects
- [ ] Build graph for each of 14 projects
- [ ] Commit `graph.json` per project
- [ ] Per-project verification: queries work, build is reproducible
- [ ] Update per-project CLAUDE.md with project-specific graph notes
- [ ] Decision: keep per-project graphs in repo, or centralize

### Future (deferred)
- [ ] UI skills when first concrete UI task triggers
- [ ] `engineering` skill consolidation (currently 4 sub-skills)
- [ ] `comprehensive-code-review` ↔ `code-reviewer` ↔ `pr-review-expert` dedup

## Risks

| Risk | Mitigation |
|------|-----------|
| INFERRED edge noise ~30% | verification step in every graph-using skill |
| Stale graphs mislead | `graph-staleness-check` pre-flight |
| Build cost high for small projects | lazy build (only on first query) |
| Graph.json merge complexity | start with single-developer model; add merge-driver when needed |
| Skill deprecation breaks workflows | deprecation candidates get 2-week deprecation warning in skill frontmatter |
| Cross-pollination creates circular writes | strict ownership: graph owns rationale, memory owns insight |
| Audit paralysis | ship in phases, each phase independently useful |

## Module Design Blocks

### Module: graph-context-pack
- **Responsibility:** produce optimal subagent context from current graph
- **Interface:** CLI + skill invocation; takes task description
- **Dependencies:** `~/.claude/skills/graphify/` for graph query
- **Size target:** 150 lines

### Module: graph-staleness-check
- **Responsibility:** pre-flight freshness check
- **Interface:** returns structured `{fresh, age_days, drift_pct, action}`
- **Dependencies:** git, filesystem stat
- **Size target:** 100 lines

### Module: graph-blast-radius
- **Responsibility:** dependents + breaking-change risk
- **Interface:** CLI; takes file or symbol
- **Dependencies:** `graphify-out/graph.json`
- **Size target:** 120 lines

### Module: graph-rationale-write
- **Responsibility:** write rationale edge to graph
- **Interface:** CLI; takes target node-id + reason
- **Dependencies:** graph.json (mutable, requires write)
- **Size target:** 80 lines

### Module: skill-audit
- **Responsibility:** scan skills for staleness, broken refs, duplicates
- **Interface:** CLI; returns list of issues
- **Dependencies:** `~/.claude/skills/`, optional `graphify-out/`
- **Size target:** 200 lines

### Module: skill-deprecate
- **Responsibility:** move faulty skill to _deprecated/ with reason
- **Interface:** CLI; takes skill name + reason
- **Dependencies:** filesystem
- **Size target:** 50 lines

## Success criteria

- 83% token reduction at 100-query session in graphified project
- All 14 projects have `graph.json` committed
- All core skills (brainstorming, code-review, playwright) audited + improved
- 0 critical findings from `nvidia-security-recheck`
- 0 broken references in any skill
- 3+ new skills shipped (graph-context-pack, graph-staleness-check, graph-blast-radius)
- Memory ↔ graph cross-pollination working (round-trip: write to graph → appears in memory digest)

## Open questions for next session

1. Where is the past NVIDIA security audit report? (search `~/.claude/memory/`, `git log`, or reconstruct methodology)
2. Which 3 skills are the most "faulty" candidates for first deprecation? (need `skill-audit` first)
3. Per-project graph: commit to each repo separately, or centralize in `~/.claude/graphs/<project>.json`?
4. Memory ↔ graph: write to memory file system or to a graph node with `type: memory_ref`?

## Why this design

User chose B over A (conservative) and C (revolutionary). B captures 70-83% savings, manageable risk, builds foundation for C. Folding in the new hygiene goal (audit, security recheck, deprecate, improve cores, defer UI) without expanding scope to C.
