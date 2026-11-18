#!/usr/bin/env bash
# Usage: scripts/fetch-context.sh <github-url> [<github-url> ...]
#
# Clones each repo into $GUARDIAN_CONTEXT/repos/<name> (default: guardian/context)
# and exports its last 100 pull requests to $GUARDIAN_CONTEXT/prs/<name>.json.
#
# Needs git and curl only. Uses `gh` when it is logged in (richer data: files and
# reviews); otherwise the public REST API. Set GITHUB_TOKEN to lift the anonymous
# limit of 60 API calls an hour (each repo costs 4 calls).
set -euo pipefail
cd "$(dirname "$0")/.."
ctx="${GUARDIAN_CONTEXT:-context}"
mkdir -p "$ctx/repos" "$ctx/prs"

use_gh=0
gh auth status >/dev/null 2>&1 && use_gh=1

auth=()
[ -n "${GITHUB_TOKEN:-}" ] && auth=(-H "Authorization: Bearer $GITHUB_TOKEN")
get() { curl -sSL -H "User-Agent: openhands-guardian" -H "Accept: application/vnd.github+json" ${auth[@]+"${auth[@]}"} "$1"; }

for url in "$@"; do
  url=${url%/}; url=${url%.git}
  name=${url##*/}; slug=$(echo "${url%/*}/$name" | sed -E 's#^.*github\.com[/:]##')
  if [ -d "$ctx/repos/$name/.git" ]; then
    git -C "$ctx/repos/$name" pull --quiet
  else
    # history is kept (depth 300) because "Who to ask" ranks people by recent commits
    git clone --quiet --depth 300 "$url" "$ctx/repos/$name"
  fi

  out="$ctx/prs/$name.json"; tmp=$(mktemp -d)
  if [ $use_gh = 1 ]; then
    gh pr list --repo "$slug" --state all --limit 100 \
      --json number,title,body,state,author,mergedAt,closedAt,files,reviews,comments,url > "$tmp/o.json"
    n=$(./bin/guardian import-prs --gh "$tmp/o.json" -o "$out") || { rm -rf "$tmp"; exit 1; }
    method=gh
  else
    api="https://api.github.com/repos/$slug"
    get "$api/pulls?state=all&per_page=100" > "$tmp/p.json"
    get "$api/pulls/comments?per_page=100&sort=created&direction=desc" > "$tmp/c.json"
    # conversation comments: where "closing because ..." is usually written
    get "$api/issues/comments?per_page=100&sort=created&direction=desc&page=1" > "$tmp/i1.json"
    get "$api/issues/comments?per_page=100&sort=created&direction=desc&page=2" > "$tmp/i2.json"
    n=$(./bin/guardian import-prs --pulls "$tmp/p.json" --review-comments "$tmp/c.json" \
          --issue-comments "$tmp/i1.json" --issue-comments "$tmp/i2.json" -o "$out") || { rm -rf "$tmp"; exit 1; }
    method=curl
  fi
  rm -rf "$tmp"
  echo "$name: $n PRs written ($method)"
done
