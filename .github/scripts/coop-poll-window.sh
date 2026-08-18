#!/usr/bin/env bash
#
# Polls the co-op sources once for automated triggers or repeatedly for a manual
# "window", instead of relying on a GitHub cron tick per poll.
#
# Why this exists: the former "*/5" schedule did NOT get delivered every five
# minutes.
# Measured on 2026-07-29, consecutive delivered runs of coop-fast-poll were 46 to
# 153 minutes apart (median ~80) with zero failures and zero cancellations —
# GitHub simply drops most ticks of a high-frequency schedule. So one delivered
# run used to poll many times instead of once; automated runs now stay one-shot.
#
# Knobs (all optional):
#   POLL_INTERVAL_SECONDS  gap between polls                        (default 300)
#   POLL_WINDOW_MINUTES    how long to keep polling      (default 0 on schedule/
#                                                         dispatch, otherwise 55)
#   POLL_WINDOW_SECONDS    manual-window seconds; overrides minutes (derived)
#   POLL_HARD_STOP_UTC     "HH:MM" after which the window ends       (default 21:00)
#   POLL_CMD               the poll command to run       (default python run_coop.py)
#
# Exit status: 0 if at least one poll succeeded, 1 only if every poll failed. A
# single flaky scrape must not abort the window, but a window that never once
# succeeded has to go red — a silently-green job that never scraped is how the
# /coop page went empty before.
set -uo pipefail

: "${POLL_INTERVAL_SECONDS:=300}"

# repository_dispatch and schedule runs are ONE poll and exit. The external
# trigger owns minutely cadence, while the fallback shares the same concurrency
# group; a fallback window would occupy the only running slot and block dispatch.
# Only workflow_dispatch keeps its operator-selected window.
#
# This lives in bash rather than in a workflow `${{ }}` expression on purpose.
# The obvious expression — `event_name == 'repository_dispatch' && '0' || '55'`
# — is a trap: GitHub casts the string '0' to falsy, so the `||` swallows it and
# every dispatched run would quietly loop for 55 minutes instead of exiting.
: "${GITHUB_EVENT_NAME:=}"
if [ "$GITHUB_EVENT_NAME" = "repository_dispatch" ] ||
   [ "$GITHUB_EVENT_NAME" = "schedule" ]; then
  # Automated runs are always one poll. This also prevents test/debug overrides
  # from accidentally turning the real fallback or dispatch path into a window.
  POLL_WINDOW_MINUTES=0
  POLL_WINDOW_SECONDS=0
else
  : "${POLL_WINDOW_MINUTES:=55}"
  : "${POLL_WINDOW_SECONDS:=$(( POLL_WINDOW_MINUTES * 60 ))}"
fi
: "${POLL_HARD_STOP_UTC:=21:00}"
: "${POLL_CMD:=python run_coop.py}"

start=$(date -u +%s)
end=$(( start + POLL_WINDOW_SECONDS ))

# Keep a long manual window from pushing Telegram alerts deep into the night.
# Automated schedule and dispatch runs are one poll, so only manual operation can
# reach this long-window clamp.
#
# Deliberately arithmetic on H/M/S rather than `date -d`: `-d` is GNU-only, and
# this script has to be runnable (and testable) on macOS too. `10#` forces
# base 10 so "08"/"09" aren't parsed as invalid octal.
now_hms=$(date -u +"%H %M %S")
read -r now_h now_m now_s <<EOF
$now_hms
EOF
stop_h=${POLL_HARD_STOP_UTC%%:*}
stop_m=${POLL_HARD_STOP_UTC##*:}
secs_now=$(( 10#$now_h * 3600 + 10#$now_m * 60 + 10#$now_s ))
secs_stop=$(( 10#$stop_h * 3600 + 10#$stop_m * 60 ))
if [ "$secs_stop" -gt "$secs_now" ]; then
  hard_stop=$(( start + secs_stop - secs_now ))
  if [ "$end" -gt "$hard_stop" ]; then
    echo "Clamping poll window to ${POLL_HARD_STOP_UTC} UTC."
    end=$hard_stop
  fi
fi
# Already past the cutoff (or triggered manually at night): no clamp, the
# operator asked for this run explicitly.

polls=0
failures=0
while : ; do
  polls=$(( polls + 1 ))
  echo "--- poll #${polls} at $(date -u +%H:%M:%SZ) ---"
  # Unquoted on purpose: POLL_CMD is a command line, not a single filename.
  # shellcheck disable=SC2086
  if $POLL_CMD; then
    echo "poll #${polls} ok"
  else
    failures=$(( failures + 1 ))
    echo "::warning::co-op poll #${polls} failed (continuing the window)"
  fi
  now=$(date -u +%s)
  # Only sleep when a further full interval still fits inside the window.
  if [ $(( now + POLL_INTERVAL_SECONDS )) -ge "$end" ]; then
    break
  fi
  sleep "$POLL_INTERVAL_SECONDS"
done

echo "window complete: ${polls} polls, ${failures} failed"
if [ "$polls" -eq "$failures" ]; then
  echo "::error::all ${polls} co-op polls in this window failed"
  exit 1
fi
