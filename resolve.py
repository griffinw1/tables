#!/usr/bin/env python3
"""Turn a booking-page URL into a venues.json entry (platform + id), read-only.

  python3 resolve.py https://resy.com/cities/dallas-tx/venues/cbd-provisions
  python3 resolve.py https://www.opentable.com/r/walkers-dallas
  python3 resolve.py https://www.sevenrooms.com/reservations/monarchdallas
  python3 resolve.py https://www.exploretock.com/mos-italian-bistro-dallas
  python3 resolve.py URL --name "Monarch" --kind restaurant --beli 8.9 --ratings 1200 --add

With --add the entry is appended to venues.json (or replaces an entry of the same name).
OpenTable /r/<slug> URLs start a headless Chrome to read the rid; the others need no browser.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from platforms import opentable, resy, sevenrooms, tock

HERE = Path(__file__).resolve().parent


def detect(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "resy.com" in host:
        return "resy"
    if "opentable." in host:
        return "opentable"
    if "sevenrooms.com" in host:
        return "sevenrooms"
    if "exploretock.com" in host or "tock.com" in host:
        return "tock"
    return "unknown"


def resolve(url: str) -> dict:
    p = detect(url)
    if p == "resy":
        info = resy.resolve(url)
    elif p == "sevenrooms":
        info = sevenrooms.resolve(url)
    elif p == "tock":
        info = tock.resolve(url)
    elif p == "opentable":
        from urllib.parse import parse_qs
        pu = urlparse(url)
        if "rid" in parse_qs(pu.query) or "/restaurant/profile/" in pu.path:
            info = opentable.resolve(url, None)
        else:
            from platforms.browser import headless_chrome
            with headless_chrome() as b:
                info = opentable.resolve(url, b)
    else:
        raise SystemExit(f"Don't recognise the platform for {url}. Use platform phone/walkin/unknown by hand.")
    return {"platform": p, **info}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--name")
    ap.add_argument("--kind", choices=["restaurant", "bar"], default="restaurant")
    ap.add_argument("--beli", type=float)
    ap.add_argument("--ratings", type=int)
    ap.add_argument("--phone")
    ap.add_argument("--notes", default="")
    ap.add_argument("--add", action="store_true", help="write into venues.json")
    a = ap.parse_args()
    info = resolve(a.url)
    entry = {"name": a.name or info.get("name") or info["id"], "kind": a.kind, "beli_avg": a.beli,
             "beli_ratings": a.ratings, "platform": info["platform"], "id": info["id"], "url": a.url,
             "phone": a.phone, "notes": a.notes}
    print(json.dumps(entry, indent=1))
    if a.add:
        path = HERE / "venues.json"
        venues = json.loads(path.read_text())
        venues = [v for v in venues if v["name"] != entry["name"]] + [entry]
        path.write_text("[\n" + ",\n".join(" " + json.dumps(v, ensure_ascii=False) for v in venues) + "\n]\n")
        print(f"saved to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
