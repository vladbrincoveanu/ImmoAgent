#!/usr/bin/env bash
#
# Polls the co-op sources repeatedly for one "window", instead of relying on a
# GitHub cron tick per poll.
#
# Why this exists: a "*/5" schedule does NOT get delivered every 5 minutes.
# Measured on 2026-07-29, consecutive delivered runs of coop-fast-poll were 46 to
# 153 minutes apart (median ~80) with zero failures and zero cancellations —
# GitHub simply drops most ticks of a high-frequency schedule. So one delivered
# run now polls many times instead of once.
#
# Knobs (all optional):
#   POLL_INTERVAL_SECONDS  gap between polls                        (default 300)
#   POLL_WINDOW_MINUTES    how long to keep polling                  (default 55)
#   POLL_WINDOW_SECONDS    same, in seconds; overrides the minutes   (derived)
#   POLL_HARD_STOP_UTC     "HH:MM" after which the window ends       (default 21:00)
#   POLL_CMD               the poll command to run       (default python run_coop.py)
#
# Exit status: 0 if at least one poll succeeded, 1 only if every poll failed. A
# single flaky scrape must not abort the window, but a window that never once
# succeeded has to go red — a silently-green job that never scraped is how the
# /coop page went empty before.
set -uo pipefail

: "${POLL_INTERVAL_SECONDS:=300}"
: "${POLL_WINDOW_MINUTES:=55}"
: "${POLL_WINDOW_SECONDS:=$(( POLL_WINDOW_MINUTES * 60 ))}"
: "${POLL_HARD_STOP_UTC:=21:00}"
: "${POLL_CMD:=python run_coop.py}"

start=$(date -u +%s)
end=$(( start + POLL_WINDOW_SECONDS ))

# Keep a long window from pushing Telegram alerts deep into the night. The cron
# window ends at 20:00 UTC, so a run picked up at 20:5x plus a 55-minute loop
# would otherwise still be alerting at ~23:00 Vienna.
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
