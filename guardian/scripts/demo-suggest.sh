#!/usr/bin/env bash
# Demo part 1: code suggestion for a ticket, live in out/live-blueprint.md.
#   scripts/demo-suggest.sh                      # demo/ticket.md
#   scripts/demo-suggest.sh demo/ticket-drift.md # or any ticket file / text
#   scripts/demo-suggest.sh --offline            # no model, <1 s (backup)
set -euo pipefail
cd "$(dirname "$0")/.."
ticket="demo/ticket.md"; extra=()
for a in "$@"; do if [ "$a" = "--offline" ]; then extra+=(--offline); else ticket="$a"; fi; done
exec scripts/live.sh blueprint "$ticket" ${extra[@]+"${extra[@]}"}
