#!/usr/bin/env bash
# Check every live city in cities.json, render, commit and push (one push per run).
#
#   scripts/publish.sh                      # all platforms, every live city
#   CITIES=dallas scripts/publish.sh        # one city
#   NO_SIZES=1 / PULL_SIZES="5" / NO_PUSH=1 as before
#
# OpenTable rate-limits hard: party of 4 every run, plus ONE extra party size per run
# (rotating every 3 h). Resy / SevenRooms / Tock run every size every time.
set -euo pipefail
cd "$(dirname "$0")/.."
LOCK="$HOME/.tables/run.lock"; mkdir -p "$HOME/.tables"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +60 2>/dev/null)" ]; then rmdir "$LOCK"; mkdir "$LOCK"; else echo "another run is in progress"; exit 75; fi
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT
PY="${PYTHON:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"
OWN="${PLATFORMS:-resy,sevenrooms,opentable,tock,phone,walkin,unknown}"
HAS_REMOTE=$(git remote | head -1 || true)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
[ -n "$HAS_REMOTE" ] && [ -z "${NO_PUSH:-}" ] && { git pull -q --rebase --autostash || true; }

CITIES="${CITIES:-$("$PY" -c 'import json;print(" ".join(c["slug"] for c in json.load(open("cities.json")) if c.get("status")=="live"))')}"
for city in $CITIES; do
  echo "== $city"
  R="cities/$city/results"; mkdir -p "$R"
  [ -f "$R/p4.json" ] && cp "$R/p4.json" .prev.json || echo '{}' > .prev.json
  "$PY" check.py --city "$city" --platforms "$OWN" "$@"
  if [ -z "${NO_SIZES:-}" ]; then
    SIZES=(2 3 5 6 7 8); OTS=${SIZES[$(( ($(date +%s) / 10800) % 6 ))]}
    [ -n "${PULL_SIZES:-}" ] && { read -ra SIZES <<< "$PULL_SIZES"; OTS=all; }
    for n in "${SIZES[@]}"; do
      PL=$(echo "$OWN" | tr ',' '\n' | grep -vx opentable | paste -sd, - || true)
      { [ "$n" = "$OTS" ] || [ "$OTS" = all ]; } && PL="$OWN"
      [ -n "$PL" ] && { "$PY" check.py --city "$city" --platforms "$PL" --party "$n" --delay 0.4-0.9 "$@" | tail -1 || true; }
    done
  fi
  "$PY" diff.py .prev.json "$R/p4.json" || true
done
"$PY" render.py
git add cities/*/results/*.json */index.html index.html 2>/dev/null || true
git commit -qm "availability: $CITIES $(date -u +%FT%H:%MZ)" || { echo "nothing changed"; exit 0; }
{ [ -z "$HAS_REMOTE" ] || [ -n "${NO_PUSH:-}" ]; } && { echo "committed locally (no push)"; exit 0; }
for i in 1 2 3 4; do
  git push -q origin "$BRANCH" && { echo "pushed"; exit 0; }
  echo "push raced; rebasing (attempt $i)"; git pull -q --rebase -X theirs || { git rebase --abort; exit 1; }
  sleep $((i * 5))
done
echo "push failed after retries"; exit 1
