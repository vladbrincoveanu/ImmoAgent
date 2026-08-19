# Sentry-style CI Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add free-tier-friendly, blocking GitHub Actions validation for the Python scraper and Next.js dashboard, plus deterministic security checks, without changing scheduled production jobs.

**Architecture:** Add two independent workflows. `ci.yml` runs parallel Python and dashboard validation on pull requests, pushes to `main`, and manual dispatch. `security.yml` runs CodeQL plus Python and npm dependency audits on code changes and weekly. Preserve the existing operational workflows and make one minimal analyzer compatibility fix required by the current test contract.

**Tech Stack:** GitHub Actions, Python 3.11, pytest, pip-audit, Node 20, npm, Jest, TypeScript, Next.js, CodeQL.

---

## File Map

| File | Responsibility |
|---|---|
| `Project/Application/analyzer.py` | Preserve the existing `StructuredAnalyzer` timeout configuration value. |
| `tests/test_analyzer_configuration.py` | Fast regression test for the public constructor configuration contract. |
| `.github/workflows/ci.yml` | Blocking Python and dashboard test/build jobs. |
| `.github/workflows/security.yml` | CodeQL and dependency audit jobs. |
| `graphify-out/*` | Generated graph state refreshed after source changes; stage only if `graphify update .` changes tracked outputs. |

Do not modify `.github/workflows.yaml` or the existing files under
`.github/workflows/`; they are scheduled production operations and are outside
this plan.

### Task 1: Preserve Analyzer Configuration Contract

**Files:**
- Create: `tests/test_analyzer_configuration.py`
- Modify: `Project/Application/analyzer.py:645-647`

- [ ] **Step 1: Write the failing regression test**

Create `tests/test_analyzer_configuration.py`:

```python
from Project.Application.analyzer import StructuredAnalyzer


def test_structured_analyzer_preserves_outlines_wait_timeout():
    analyzer = StructuredAnalyzer(outlines_wait_timeout=1.75)

    assert analyzer.outlines_wait_timeout == 1.75
```

- [ ] **Step 2: Run the focused test and verify the baseline failure**

Run:

```bash
PYTHONPATH=. pytest -q tests/test_analyzer_configuration.py
```

Expected: FAIL with `AttributeError: 'StructuredAnalyzer' object has no attribute 'outlines_wait_timeout'`.

- [ ] **Step 3: Implement the minimal fix**

In `StructuredAnalyzer.__init__`, keep the existing lightweight analyzer
selection and store the already-supported argument before constructing the
lightweight analyzer:

```python
def __init__(self, model_name: str = "microsoft/DialoGPT-medium", outlines_wait_timeout: float = 0.5, **kwargs):
    self.outlines_wait_timeout = outlines_wait_timeout
    self.lightweight_analyzer = LightweightAnalyzer()
```

Do not load an Outlines model, change model selection, or add a new provider.

- [ ] **Step 4: Run focused and existing startup tests**

Run:

```bash
PYTHONPATH=. pytest -q tests/test_analyzer_configuration.py tests/test_fast_startup.py
```

Expected: all tests in both files pass, including
`TestFastStartup.test_fast_startup` and `TestFastStartup.test_outlines_speed`.

- [ ] **Step 5: Commit the compatibility fix**

```bash
git add Project/Application/analyzer.py tests/test_analyzer_configuration.py
git commit -m "fix: preserve analyzer timeout setting"
```

### Task 2: Add Python and Dashboard CI Workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the blocking CI workflow**

Create `.github/workflows/ci.yml` with immutable action references:

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  python-tests:
    name: Python tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: Project/requirements.txt

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r Project/requirements.txt
          python -m pip install pytest pytest-asyncio

      - name: Compile Python sources
        run: python -m compileall -q Project tests

      - name: Run non-live tests
        env:
          PYTHONPATH: .
        run: |
          mkdir -p artifacts
          python -m pytest -m "not smoke" -q --junitxml=artifacts/python-junit.xml

      - name: Upload Python diagnostics
        if: ${{ failure() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: python-test-results
          path: artifacts/python-junit.xml
          if-no-files-found: ignore

  dashboard-tests:
    name: Dashboard tests and build
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - name: Set up Node
        uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: dashboard/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run Jest
        run: npm test -- --runInBand

      - name: Type check
        run: npx tsc --noEmit

      - name: Build production bundle
        env:
          MONGODB_URI: mongodb://127.0.0.1:27017/immo
          NEXT_TELEMETRY_DISABLED: "1"
        run: npm run build

      - name: Upload dashboard diagnostics
        if: ${{ failure() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: dashboard-build-diagnostics
          path: |
            dashboard/.next/trace
            dashboard/tsconfig.tsbuildinfo
          if-no-files-found: ignore
```

The two jobs must not receive MongoDB, Telegram, SMTP, or model-provider
secrets. `cancel-in-progress` cancels only superseded pull-request runs;
`main` pushes and manual runs remain independently visible.

- [ ] **Step 2: Validate workflow syntax before running application commands**

Run:

```bash
actionlint .github/workflows/ci.yml
```

Expected: no diagnostics. If `actionlint` is unavailable locally, record that
fact and use the GitHub Actions parser on the next pushed branch; do not replace
the check with a YAML parser that cannot validate Actions expressions.

- [ ] **Step 3: Run local equivalents of both CI jobs**

Run the Python commands from the repository root:

```bash
PYTHONPATH=. python -m compileall -q Project tests
PYTHONPATH=. pytest -m "not smoke" -q
```

Run the dashboard commands from `dashboard` after installing the lockfile:

```bash
npm ci
npm test -- --runInBand
npx tsc --noEmit
MONGODB_URI=mongodb://127.0.0.1:27017/immo NEXT_TELEMETRY_DISABLED=1 npm run build
```

Expected: all commands exit zero. The Python run must include the focused
timeout regression test and the existing startup tests; it must not silently
skip unmarked tests.

- [ ] **Step 4: Commit the CI workflow**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Python and dashboard gates"
```

### Task 3: Add CodeQL and Dependency Security Workflow

**Files:**
- Create: `.github/workflows/security.yml`

- [ ] **Step 1: Create the security workflow**

Create `.github/workflows/security.yml`:

```yaml
name: Security

on:
  pull_request:
  push:
    branches:
      - main
  schedule:
    - cron: "23 4 * * 1"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: security-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  codeql:
    name: CodeQL (${{ matrix.language }})
    runs-on: ubuntu-latest
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language:
          - python
          - javascript-typescript
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - name: Initialize CodeQL
        uses: github/codeql-action/init@60168efe1c415ce0f5521ea06d5c2062adbeed1b # v3.28.17
        with:
          languages: ${{ matrix.language }}

      - name: Analyze
        uses: github/codeql-action/analyze@60168efe1c415ce0f5521ea06d5c2062adbeed1b # v3.28.17
        with:
          category: /language:${{ matrix.language }}

  python-audit:
    name: Python dependency audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.11"

      - name: Install pip-audit
        run: python -m pip install --upgrade pip pip-audit

      - name: Audit Python requirements
        run: |
          mkdir -p artifacts
          pip-audit --requirement Project/requirements.txt --format json --output artifacts/pip-audit.json

      - name: Upload Python audit report
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: python-audit-report
          path: artifacts/pip-audit.json
          if-no-files-found: ignore

  npm-audit:
    name: Dashboard dependency audit
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: dashboard
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2

      - name: Set up Node
        uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version: "20"

      - name: Audit dashboard lockfile
        run: |
          mkdir -p artifacts
          npm audit --package-lock-only --omit=dev --audit-level=high --json > artifacts/npm-audit.json

      - name: Upload npm audit report
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2
        with:
          name: npm-audit-report
          path: dashboard/artifacts/npm-audit.json
          if-no-files-found: ignore
```

`pip-audit` has no severity threshold, so any reported Python advisory is
blocking. `npm audit --audit-level=high` blocks high and critical npm findings
while still reporting lower severities. Neither audit job installs application
secrets or calls external model APIs.

- [ ] **Step 2: Validate the security workflow syntax**

Run:

```bash
actionlint .github/workflows/security.yml
```

Expected: no diagnostics.

- [ ] **Step 3: Run dependency audits locally**

Run from the repository root:

```bash
mkdir -p artifacts
pip-audit --requirement Project/requirements.txt --format json --output artifacts/pip-audit.json
cd dashboard
npm audit --package-lock-only --omit=dev --audit-level=high --json > artifacts/npm-audit.json
```

Expected: both commands exit zero. If either reports a vulnerability, keep the
report, identify the dependency/version constraint responsible, and update the
dependency contract in a separate change rather than weakening the workflow.

- [ ] **Step 4: Commit the security workflow**

```bash
git add .github/workflows/security.yml
git commit -m "ci: add CodeQL and dependency audits"
```

### Task 4: Final Repository Verification and Graph Refresh

**Files:**
- Modify: tracked `graphify-out/*` files only if `graphify update .` regenerates them from the intended source changes.

- [ ] **Step 1: Run the complete local validation set**

Run:

```bash
actionlint .github/workflows/ci.yml .github/workflows/security.yml
PYTHONPATH=. python -m compileall -q Project tests
PYTHONPATH=. pytest -m "not smoke" -q
cd dashboard
npm test -- --runInBand
npx tsc --noEmit
MONGODB_URI=mongodb://127.0.0.1:27017/immo NEXT_TELEMETRY_DISABLED=1 npm run build
cd ..
git diff --check
```

Expected: every command exits zero. The browser suite is not part of this
gate, so do not start Playwright or a live MongoDB service for this plan.

- [ ] **Step 2: Refresh the project graph**

Run from the repository root:

```bash
graphify update .
```

Inspect the result:

```bash
git status --short graphify-out
git diff --name-only -- graphify-out
git diff --check
```

Stage only graph files generated by this source change. Do not stage unrelated
worktree changes, caches, secrets, `.env` files, or runtime data.

- [ ] **Step 3: Commit graph refresh, if tracked outputs changed**

```bash
git add --update -- graphify-out
git commit -m "chore: refresh code graph"
```

Skip this commit only when `graphify update .` leaves tracked graph outputs
unchanged.

- [ ] **Step 4: Confirm final branch state**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected: only intentional commits are present on
`relentless/implement-free-model-pipelines`; no secrets or unrelated changes
are staged.
