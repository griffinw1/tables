#!/usr/bin/env python3
"""Print slots that are open in the NEW results.json but were not in the OLD one.

  python3 diff.py OLD.json NEW.json            # human-readable lines; exit 0
  python3 diff.py OLD.json NEW.json --json     # machine-readable list
  python3 diff.py OLD.json NEW.json --markdown # for $GITHUB_STEP_SUMMARY

Optional push notification: set NTFY_TOPIC (and optionally NTFY_SERVER, default
https://ntfy.sh) and newly opened slots are posted there. Nothing is sent unless you
set it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def slots(res: dict) -> dict[tuple[str, str], dict[str, set[str]]]:
    out = {}
    for v in res.get("venues", []):
        out[(v["name"], v.get("platform", ""))] = {d: set(ts) for d, ts in (v.get("slots") or {}).items()
                                                  if (v.get("status") or {}).get(d) == "ok"}
    return out


def new_openings(old: dict, new: dict) -> list[dict]:
    o, n = slots(old), slots(new)
    meta = {(v["name"], v.get("platform", "")): v for v in new.get("venues", [])}
    found = []
    for k, days in n.items():
        for d in sorted(days):
            added = days[d] - o.get(k, {}).get(d, set())
            if added:
                v = meta[k]
                found.append({"name": k[0], "platform": k[1], "date": d, "url": v.get("url"),
                              "beli_avg": v.get("beli_avg"),
                              "times": sorted(added, key=lambda t: (t[-2:], int(t.split(":")[0]) % 12, t))})
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()
    old = json.loads(Path(a.old).read_text()) if Path(a.old).exists() else {}
    new = json.loads(Path(a.new).read_text())
    found = new_openings(old, new)
    if a.json:
        print(json.dumps(found, indent=1))
    elif a.markdown:
        print(f"### Newly opened slots ({len(found)} venue-days)\n")
        for f in found:
            print(f"- **{f['name']}** {f['date']}: {', '.join(f['times'])}" + (f" ([book]({f['url']}))" if f["url"] else ""))
        if not found:
            print("_none_")
    else:
        for f in found:
            print(f"NEW  {f['date']}  {f['name']} [{f['platform']}]  {', '.join(f['times'])}  {f['url'] or ''}")
        if not found:
            print("no newly opened slots")
    topic = os.environ.get("NTFY_TOPIC")
    if topic and found:
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        text = "\n".join(f"{f['date'][5:]} {f['name']}: {', '.join(f['times'][:6])}" for f in found[:20])
        try:
            urllib.request.urlopen(urllib.request.Request(f"{server}/{topic}", data=text.encode(),
                                   headers={"Title": f"{len(found)} new table openings"}), timeout=15)
        except Exception as e:
            print(f"ntfy failed: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
