#!/usr/bin/env bash
# Classify every local and remote branch against main so cleanup decisions are
# evidence-based rather than name-based.
#
# "unique" = commits on the branch whose patch-id is NOT already in main
# (`rev-list --cherry-pick --right-only`). This is what distinguishes a branch
# that was squash-merged (work landed, ancestry says "unmerged") from one that
# holds real unlanded work. Squash merges collapse N commits into 1, so even
# patch-id can miss them — hence the PR state column from gh is the tiebreak.
set -uo pipefail
MAIN=origin/main

printf '%-52s %-7s %-7s %-12s %s\n' BRANCH AHEAD UNIQUE LASTCOMMIT WORKTREE

# Which branches are checked out in some worktree (cannot be deleted).
git worktree list --porcelain | awk '/^branch /{sub("refs/heads/","",$2); print $2}' > /tmp/claude/wt-branches.txt 2>/dev/null \
  || git worktree list --porcelain | awk '/^branch /{sub("refs/heads/","",$2); print $2}' > "${TMPDIR:-/tmp}/wt-branches.txt"
WT_FILE=/tmp/claude/wt-branches.txt
[ -s "$WT_FILE" ] || WT_FILE="${TMPDIR:-/tmp}/wt-branches.txt"

classify() {
  local ref="$1" label="$2"
  local ahead unique last wt
  ahead=$(git rev-list --count "$MAIN..$ref" 2>/dev/null || echo '?')
  unique=$(git rev-list --cherry-pick --right-only --count "$MAIN...$ref" 2>/dev/null || echo '?')
  last=$(git log -1 --format=%cs "$ref" 2>/dev/null || echo '?')
  wt=''
  grep -qxF "$label" "$WT_FILE" 2>/dev/null && wt='CHECKED-OUT'
  printf '%-52s %-7s %-7s %-12s %s\n' "$label" "$ahead" "$unique" "$last" "$wt"
}

echo "--- LOCAL ---"
for b in $(git for-each-ref --format='%(refname:short)' refs/heads/); do
  classify "$b" "$b"
done

echo "--- REMOTE ---"
for b in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin/ | grep -v '^origin/HEAD$' | grep -v '^origin/main$'); do
  classify "$b" "$b"
done
