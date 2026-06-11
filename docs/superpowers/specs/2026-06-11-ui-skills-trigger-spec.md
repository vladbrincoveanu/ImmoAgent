# Spec: UI Skills — Trigger Conditions + Candidate Set

**Date:** 2026-06-11
**Status:** deferred (per user: "maybe UI skills in the future")
**Purpose:** document WHEN to build UI skills + WHICH skills to build, so the decision is data-driven not ad-hoc.

## Why deferred (not pre-built)

Pre-building UI skills without a concrete UI task wastes effort and creates orphan skills. The brainstorming skill's hard-gate principle: design first, build second, with a real use case. This spec captures the design for the FUTURE trigger.

## Trigger conditions (build UI skills when ANY of these is true)

1. **First concrete UI task** in a project — e.g., a design system request, accessibility audit, or component library work. The user explicitly asks for "UI skills" OR a project requires sustained UI work across 3+ sessions.
2. **Visual regression incident** — a Playwright snapshot diff fails twice in a row for the same component, suggesting a need for a dedicated visual-regression skill.
3. **Accessibility blocker** — a WCAG audit is requested or an a11y issue blocks a release.
4. **Design system drift** — the same component is implemented 3+ different ways across the codebase, suggesting a design-token or component-spec skill is needed.

When trigger fires: re-brainstorm per `brainstorming` skill. Use this spec as the starting menu, not a fait accompli.

## Candidate UI skills (build only what's needed)

### 1. `visual-companion-bridge`
- **Responsibility:** wrap the `~/.claude/skills/brainstorming/visual-companion.md` browser-based mockup server; auto-start it when brainstorming touches UI topics
- **When to build:** if `visual-companion.md` is missing OR broken (the brainstorming skill currently references it but the file is absent in some plugin caches per recent audit)
- **Dependencies:** existing brainstorming skill
- **Size target:** 100 lines

### 2. `accessibility-auditor`
- **Responsibility:** scan a frontend codebase for WCAG 2.2 AA violations; report severity + remediation; integrate with axe-core / Pa11y
- **When to build:** trigger condition 3
- **Dependencies:** axe-core CLI or Pa11y; graphify for component discovery
- **Size target:** 200 lines

### 3. `design-token-sync`
- **Responsibility:** keep design tokens (colors, spacing, typography) in sync between Figma export, Tailwind config, and component library. Detect drift.
- **When to build:** trigger condition 4
- **Dependencies:** Style Dictionary, Figma API token
- **Size target:** 250 lines

### 4. `screenshot-regression`
- **Responsibility:** Playwright-based visual regression for the dashboard; pixel-diff on every commit; integrate with `playwright-pro` and `ci-cd-pipeline-builder`
- **When to build:** trigger condition 2
- **Dependencies:** `@playwright/test` visual comparisons (built-in since Playwright 1.40)
- **Size target:** 150 lines

### 5. `component-spec-generator`
- **Responsibility:** from a Figma frame or screenshot, generate a typed React/Vue/Svelte component spec (props, slots, events, a11y notes). Reverse-engineer a Storybook story.
- **When to build:** first concrete UI task that requires shipping components from a design source
- **Dependencies:** Figma API or vision model; Storybook 8+
- **Size target:** 300 lines

## Pre-build cost estimate

If all 5 candidates were built upfront: ~1,000 lines of skill code + ~5 audit/hygiene cycles. Realistic value: each is used maybe 5-10 times in a project lifetime. **Pre-building is net-negative unless 3+ triggers are imminent.**

## Re-evaluation cadence

Re-read this spec every 90 days. If a trigger condition has been hit and a candidate skill is still unbuilt, prioritize it in the next planning session.

## Cross-references

- [[2026-06-11-graph-leverage-skill-hygiene-design]] — main graph-leverage design (B approach)
- [[long-term-skill-hygiene-goal]] — long-term audit/cleanup posture
- [[skill-audit-2026-06-11]] — current skill inventory + audit
