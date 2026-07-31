#!/usr/bin/env python3
"""Tests for .github/scripts/coop-poll-window.sh.

That script is what makes the co-op poller poll often despite GitHub dropping
most ticks of a high-frequency cron. Its loop, its window clamp and its
"fail only if EVERY poll failed" rule are real logic that CI would otherwise
exercise unverified, so they are pinned here rather than trusted.

Each test injects a stub via POLL_CMD instead of running the real scraper, and
uses second-scale windows so the suite stays fast.

On the odd location: `tests/run_tests.py` does `discover('tests', ...)`, so this
`tests/tests/` subdirectory is the ONLY path the documented `cd tests && python
run_tests.py` command actually executes. The ~40 legacy `test_*.py` files sit in
`tests/` itself and that runner never picks them up. Putting this file next to
them would look conventional while never running — so it lives here instead.

(Git tracks the directory lower-case as `tests/`; CLAUDE.md's `cd Tests` only
resolves because macOS is case-insensitive. On Linux use `cd tests`.)
"""
import os
import stat
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "coop-poll-window.sh"


class CoopPollWindowTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), f"missing script: {SCRIPT}")
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _stub(self, name, body):
        """Write an executable stub and return its path."""
        p = self.tmp / name
        p.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body))
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
        return p

    def _run(self, env_extra, timeout=60):
        env = dict(os.environ)
        # Keep the real scraper and the real 5-minute cadence out of the tests.
        env.update({"POLL_INTERVAL_SECONDS": "1", "POLL_WINDOW_SECONDS": "0"})
        env.update(env_extra)
        return subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True, text=True, env=env, timeout=timeout,
        )

    def test_single_poll_when_window_is_zero(self):
        ok = self._stub("ok.sh", 'echo scraped; exit 0')
        r = self._run({"POLL_CMD": str(ok)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("window complete: 1 polls, 0 failed", r.stdout)
        self.assertIn("scraped", r.stdout)

    def test_polls_repeatedly_across_the_window(self):
        # A 3-second window at a 1-second interval must poll more than once --
        # this is the whole point of the script.
        counter = self.tmp / "count"
        ok = self._stub("count.sh", f'echo x >> "{counter}"; exit 0')
        r = self._run({"POLL_CMD": str(ok), "POLL_WINDOW_SECONDS": "3"})
        self.assertEqual(r.returncode, 0, r.stderr)
        polls = counter.read_text().count("x")
        self.assertGreaterEqual(polls, 2, f"expected repeated polls, got {polls}")
        self.assertIn(f"window complete: {polls} polls, 0 failed", r.stdout)

    def test_fails_loudly_only_when_every_poll_failed(self):
        bad = self._stub("bad.sh", 'echo boom >&2; exit 1')
        r = self._run({"POLL_CMD": str(bad)})
        self.assertEqual(r.returncode, 1, "an all-failed window must go red")
        self.assertIn("::error::all 1 co-op polls in this window failed", r.stdout)

    def test_survives_a_flaky_poll_when_a_later_one_succeeds(self):
        # Fails the first time, succeeds afterwards. The window must finish green:
        # one flaky scrape is not a reason to abandon the remaining polls.
        marker = self.tmp / "seen"
        flaky = self._stub("flaky.sh", f'''
            if [ -e "{marker}" ]; then exit 0; fi
            touch "{marker}"; exit 1
        ''')
        r = self._run({"POLL_CMD": str(flaky), "POLL_WINDOW_SECONDS": "3"})
        self.assertEqual(r.returncode, 0, "a partially-failed window must stay green")
        self.assertIn("::warning::co-op poll #1 failed", r.stdout)
        self.assertNotIn("::error::", r.stdout)

    def test_clamps_the_window_to_the_hard_stop(self):
        # A huge window must be cut short by POLL_HARD_STOP_UTC so a late run
        # cannot keep firing Telegram alerts through the night.
        now = time.gmtime()
        if now.tm_hour == 23 and now.tm_min >= 58:
            self.skipTest("UTC midnight rollover would make the cutoff ambiguous")
        stop = time.strftime("%H:%M", time.gmtime(time.time() + 120))
        ok = self._stub("ok.sh", 'exit 0')
        r = self._run({
            "POLL_CMD": str(ok),
            "POLL_WINDOW_SECONDS": "86400",  # 24h, far past the cutoff
            "POLL_HARD_STOP_UTC": stop,
            # An interval longer than the clamped window: the run must poll once
            # and then stop, rather than idling until the cutoff. Also pins the
            # "only sleep if a full interval still fits" rule.
            "POLL_INTERVAL_SECONDS": "3600",
        })
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"Clamping poll window to {stop} UTC.", r.stdout)
        self.assertIn("window complete: 1 polls, 0 failed", r.stdout)

    def test_no_clamp_once_past_the_hard_stop(self):
        # Manually dispatched at night: the operator asked for it, so the window
        # is honoured rather than clamped to zero.
        past = time.strftime("%H:%M", time.gmtime(time.time() - 3600))
        if past == "00:00" or time.gmtime().tm_hour == 0:
            self.skipTest("an hour ago was yesterday in UTC; cutoff not comparable")
        ok = self._stub("ok.sh", 'exit 0')
        r = self._run({"POLL_CMD": str(ok), "POLL_HARD_STOP_UTC": past})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("Clamping", r.stdout)

    def test_derives_the_window_from_minutes(self):
        # POLL_WINDOW_MINUTES is what the workflow actually sets; make sure the
        # seconds derivation works and a 0-minute window still polls once.
        ok = self._stub("ok.sh", 'exit 0')
        env = {"POLL_CMD": str(ok), "POLL_WINDOW_MINUTES": "0"}
        env["POLL_WINDOW_SECONDS"] = ""  # force the minutes path
        r = subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True, timeout=60,
            env={**os.environ, **env, "POLL_INTERVAL_SECONDS": "1"},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("window complete: 1 polls, 0 failed", r.stdout)


    # --- dispatch vs fallback default ----------------------------------------
    #
    # Cadence comes from an external trigger firing repository_dispatch every ~2
    # minutes, so a dispatched run must do ONE poll and exit. If it looped, each
    # run would still be polling when the next dispatch arrived and would be
    # cancelled mid-poll by `cancel-in-progress`.

    def _run_bare(self, env_extra, timeout=60):
        """Like `_run`, but WITHOUT the POLL_WINDOW_SECONDS override, so the
        script's own default logic is what gets exercised."""
        env = {**os.environ, "POLL_INTERVAL_SECONDS": "1",
               "POLL_WINDOW_SECONDS": "", "POLL_WINDOW_MINUTES": ""}
        env.update(env_extra)
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True,
                              text=True, env=env, timeout=timeout)

    def test_a_dispatched_run_polls_exactly_once(self):
        ok = self._stub("ok.sh", 'exit 0')
        r = self._run_bare({"POLL_CMD": str(ok),
                            "GITHUB_EVENT_NAME": "repository_dispatch"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("window complete: 1 polls, 0 failed", r.stdout)

    def test_a_scheduled_run_keeps_the_fallback_window(self):
        """The fallback must still loop — it is what covers a dead trigger."""
        ok = self._stub("ok.sh", 'exit 0')
        r = self._run_bare({"POLL_CMD": str(ok), "GITHUB_EVENT_NAME": "schedule",
                            # Clamp it so the test does not actually run 55 min.
                            "POLL_WINDOW_SECONDS": "3"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("window complete: 1 polls", r.stdout)

    def test_an_explicit_window_overrides_the_dispatch_default(self):
        """Debugging a dispatched run must still be possible."""
        ok = self._stub("ok.sh", 'exit 0')
        r = self._run_bare({"POLL_CMD": str(ok),
                            "GITHUB_EVENT_NAME": "repository_dispatch",
                            "POLL_WINDOW_SECONDS": "3"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("window complete: 1 polls", r.stdout)


if __name__ == "__main__":
    unittest.main()
