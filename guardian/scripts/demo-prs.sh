#!/usr/bin/env bash
# Demo part 2: review the correct PR, then the blocker PR, on ONE live page:
# out/live-prs.md. The first result stays on top while the second runs below it.
#   scripts/demo-prs.sh                          # PR #9 (correct) then PR #8 (blocker)
#   scripts/demo-prs.sh <PR URL or .diff> ...    # any PRs or local diffs, in order
set -euo pipefail
cd "$(dirname "$0")/.."
repo="https://github.com/vamsikodavali/Natwest-PRAgent/pull"
if [ $# -eq 0 ]; then set -- "$repo/9" "$repo/8"; fi
page="out/live-prs.md"; done_so_far="out/.live-prs-done.md"; mkdir -p out
if [ -f "$page" ] && grep -qE "Generated live|OpenHands review" "$page"; then   # keep the previous result
  mkdir -p out/backup && cp "$page" "out/backup/live-prs-$(date +%Y%m%d-%H%M%S).md" && echo "(saved the previous result to out/backup/)"
fi
: > "$done_so_far"
start=$(date +%s); n=0
for target in "$@"; do
  n=$((n + 1))
  echo "=================== review $n of $#: $target"
  if [ -s "$done_so_far" ]; then
    LIVE_OUT="$page" LIVE_PREFIX="$done_so_far" scripts/live.sh pr-review "$target"
  else
    LIVE_OUT="$page" scripts/live.sh pr-review "$target"
  fi
  cp "$page" "$done_so_far"
done
rm -f "$done_so_far"
echo "=================== all $# reviews done in $(( $(date +%s) - start ))s → $page"
