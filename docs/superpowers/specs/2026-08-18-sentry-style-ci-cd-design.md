---
title: "Sentry-style CI validation for Immo-Scouter"
date: 2026-08-18
status: approved
ui_scope: false
graph_scope: true
test_scope: true
---

# Sentry-style CI validation for Immo-Scouter

## Goal

Add a free-tier-friendly, blocking GitHub Actions validation layer modeled on the useful parts
of [Sentry .NET's build workflow](https://github.com/getsentry/sentry-dotnet):
separate build/test concerns, dependency caching, concurrency control, failure
diagnostics, and scheduled security analysis.

The repository already has operational scheduled workflows for scraping,
reports, migrations, outreach, revalidation, and co-op polling. This design
does not change their cadence or production side effects.

## Verified starting state

| Claim | Evidence |
|---|---|
| Python runtime is the scraper and integration-test stack | `Project/`, `Project/requirements.txt`, and `tests/` |
| Dashboard is a separate Next.js stack | `dashboard/package.json` and `dashboard/package-lock.json` |
| Existing scheduled jobs use GitHub-hosted Ubuntu runners | `.github/workflows/*.yml` |
| Existing test configuration defines a `smoke` marker | `pytest.ini` |
| Dashboard has Jest, TypeScript, production-build, and Playwright configuration | `dashboard/package.json`, `dashboard/tsconfig.json`, `dashboard/playwright.config.ts` |
| `TestFastStartup` expects `StructuredAnalyzer.outlines_wait_timeout` | `tests/test_fast_startup.py:36` |
| The implementation currently accepts but discards that constructor value | `Project/Application/analyzer.py:645-647` |
| Sentry separates build/test work from security and uses caching/concurrency | Sentry `.github/workflows/build.yml`, `codeql-analysis.yml`, and `vulnerabilities.yml` |

## Scope

### In scope

1. Add `.github/workflows/ci.yml` for pull requests, pushes to `main`, and
   manual dispatch.
2. Add `.github/workflows/security.yml` for CodeQL and dependency audits.
3. Validate Python and dashboard code in separate parallel jobs.
4. Use immutable action references, dependency caches, and failure artifacts.
5. Preserve `StructuredAnalyzer.outlines_wait_timeout` so the existing startup
   contract is honored and the baseline test can pass.

### Out of scope

- Rewriting or consolidating existing scheduled production workflows.
- Adding a Vercel, Docker, MongoDB, or Telegram deployment step without a
  named target and approved credentials.
- Running scraper, alert, outreach, migration, or notification side effects
  from pull-request validation.
- Calling OpenAI, Fireworks, MiniMax, or any other paid model/API from CI.
- Adding an AI code-review workflow; this slice uses deterministic checks only.
- Adding an operating-system matrix before the Linux validation path is stable.

## Architecture

```text
pull_request / push main / manual dispatch
                    |
              ci.yml
          ________|________
         /                 \
   python-tests       dashboard-tests
         \                 /
          test/build diagnostics

push / pull_request / weekly schedule
                    |
             security.yml
          ________|________
         /                 \
      CodeQL         dependency audits
```

### `ci.yml`

The workflow uses a concurrency group keyed by workflow and ref. Newer pull
request runs cancel superseded runs; pushes to `main` and manual runs do not
cancel one another. Jobs use Ubuntu hosted runners and official GitHub actions
pinned to full commit SHAs with version comments.

#### Python job

- Set up Python 3.11, matching the repository's documented CI/runtime path.
- Restore pip cache using `Project/requirements.txt` as the dependency key.
- Install the existing project requirements rather than creating a second
  production dependency contract.
- Run Python compilation checks.
- Run the non-live pytest suite with `PYTHONPATH=.` and exclude only tests
  explicitly marked `smoke`.
- Emit a JUnit XML report and upload it when the job fails.

No MongoDB, Telegram, SMTP, scraper, or external model credentials are set in
this job.

#### Dashboard job

- Set up the repository's supported Node runtime.
- Run `npm ci` from `dashboard` using the committed lockfile.
- Run Jest serially for deterministic resource use.
- Run `tsc --noEmit`.
- Run the production Next.js build with a loopback MongoDB URI reserved for
  build configuration; the build must not contact MongoDB.
- Upload the Next.js build log or diagnostics when the job fails.

Playwright is not part of the first blocking gate because its current
configuration starts a production server and contains environment-dependent
browser flows. It remains a separate follow-up once a service-free smoke
fixture contract is defined.

### `security.yml`

- Run CodeQL for Python and JavaScript/TypeScript on code pushes, pull
  requests, and a weekly schedule.
- Run `pip-audit` against `Project/requirements.txt`.
- Run `npm audit` against the dashboard lockfile.
- Treat every `pip-audit` advisory as blocking because that tool does not
  expose severity filtering. Treat npm high and critical findings as blocking;
  lower npm severities remain visible without blocking this initial gate.
- Grant only read access plus the CodeQL security-events permission required by
  the official action. Never use `pull_request_target` or secrets for code from
  forks.

## Failure handling

- Core Python tests, dashboard tests, type checking, builds, CodeQL, every
  Python advisory, and npm high/critical dependency findings fail the relevant
  check.
- No core validation step uses `continue-on-error`.
- Upload diagnostics with `if: failure()` so failures remain inspectable after
  runner teardown.
- Cache misses are normal and cause a dependency install, not a skipped check.
- Scheduled operational jobs remain independent; a CI failure does not trigger
  a scraper, notification, or migration run.

## Compatibility fix

`StructuredAnalyzer.__init__` already accepts `outlines_wait_timeout`, and the
existing startup test treats the value as observable configuration. Store the
provided value on `self.outlines_wait_timeout` without changing analyzer
selection or runtime behavior. The existing test then protects the contract.

## Verification

Before implementation is considered complete:

1. Run workflow syntax validation with `actionlint` when available.
2. Run the Python compile check and non-live test command locally.
3. Run the focused startup test and confirm the timeout attribute failure is
   gone.
4. Run dashboard Jest, TypeScript, and production build checks locally after
   installing from the lockfile.
5. Run `git diff --check` and inspect workflow permissions, triggers, paths,
   cache keys, and environment blocks for secret leakage.
6. Run `graphify update .` and confirm the worktree contains only the intended
   spec, workflow, compatibility, and test changes before each milestone
   commit.

Success means the new PR gate validates both application stacks without paid
   services or production side effects, security checks are visible and
   blocking at the stated threshold, and existing scheduled workflows remain
   unchanged.
