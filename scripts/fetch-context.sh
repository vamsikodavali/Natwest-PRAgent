#!/usr/bin/env bash
# Usage: scripts/fetch-context.sh <github-url> [<github-url> ...]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p context/repos context/prs

# Reads JSON on stdin; writes merged PR array to $OUT, or exits 1 on API error.
# Args: pulls.json comments.json out.json
MERGE='
const fs=require("fs");
const [pf,cf,out]=process.argv.slice(1);
const pulls=JSON.parse(fs.readFileSync(pf,"utf8"));
const cmts=JSON.parse(fs.readFileSync(cf,"utf8"));
for (const [n,d] of [["pulls",pulls],["comments",cmts]])
  if (!Array.isArray(d)) { console.error("GitHub API error ("+n+"): "+(d&&d.message||"unexpected response")); process.exit(1); }
const res=pulls.map(p=>({
  number:p.number,title:p.title,body:p.body,
  state:p.merged_at?"MERGED":p.state==="open"?"OPEN":"CLOSED",
  comments:cmts.filter(c=>c.pull_request_url===p.url).map(c=>({author:{login:c.user&&c.user.login},body:c.body,path:c.path})),
  files:[],reviews:[],url:p.html_url}));
fs.writeFileSync(out,JSON.stringify(res,null,2));
console.log(res.length);
'

use_gh=0
gh auth status >/dev/null 2>&1 && use_gh=1

for url in "$@"; do
  url=${url%/}; url=${url%.git}
  name=${url##*/}; slug=$(echo "${url%/*}/$name" | sed -E 's#^.*github\.com[/:]##')
  if [ -d "context/repos/$name/.git" ]; then
    git -C "context/repos/$name" pull --quiet
  else
    git clone --quiet "$url" "context/repos/$name"
  fi

  out="context/prs/$name.json"; tmp=$(mktemp -d)
  if [ $use_gh = 1 ]; then
    gh pr list --repo "$slug" --state all --limit 100 --json number,title,body,state,files,reviews,comments > "$tmp/o.json"
    n=$(node -e 'console.log(JSON.parse(require("fs").readFileSync(process.argv[1],"utf8")).length)' "$tmp/o.json")
    mv "$tmp/o.json" "$out"; method=gh
  else
    api="https://api.github.com/repos/$slug"
    curl -sSL -H "User-Agent: curl" "$api/pulls?state=all&per_page=100" > "$tmp/p.json"
    curl -sSL -H "User-Agent: curl" "$api/pulls/comments?per_page=100&sort=created&direction=desc" > "$tmp/c.json"
    n=$(node -e "$MERGE" "$tmp/p.json" "$tmp/c.json" "$tmp/o.json") || { rm -rf "$tmp"; exit 1; }
    mv "$tmp/o.json" "$out"; method=curl
  fi
  rm -rf "$tmp"
  echo "$name: $n PRs written ($method)"
done
