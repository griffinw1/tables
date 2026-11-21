#!/usr/bin/env python3
"""Check open reservation slots for every venue in venues.json and write results.json.

READ-ONLY: this only looks up availability. It never books, holds, locks or cancels.

  python3 check.py                                  # every platform
  python3 check.py --platforms resy,sevenrooms      # subset (what the GitHub runner does)
  python3 check.py --only "Monarch"                 # venues whose name contains this text

When only some platforms run, rows for the other platforms are kept from the existing
results.json, so the cloud runner (Resy and SevenRooms) and the Mac (OpenTable and Tock)
can share one file.
"""

from __future__ import annotations

import argparse
import random
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

from platforms import opentable, resy, sevenrooms, tock
from platforms.common import Query, VenueResult, err

HERE = Path(__file__).resolve().parent
TZ = ZoneInfo("America/Chicago")  # replaced per city in main()


def load_city(slug: str) -> dict:
    for c in json.loads((HERE / "cities.json").read_text()):
        if c["slug"] == slug:
            return c
    raise SystemExit(f"unknown city {slug!r} (see cities.json)")


def city_dates(c: dict, today: dt.date) -> tuple[str, str]:
    """'YYYY-MM-DD..YYYY-MM-DD' (fixed trip window) or 'rolling:N' (today + N-1 days)."""
    d = c.get("dates", "rolling:9")
    if d.startswith("rolling:"):
        n = int(d.split(":")[1])
        return today.isoformat(), (today + dt.timedelta(days=n - 1)).isoformat()
    a, b = d.split("..")
    return a, b
API_PLATFORMS = {"resy": resy, "sevenrooms": sevenrooms}
BROWSER_PLATFORMS = {"opentable": opentable, "tock": tock}
CHECKABLE = set(API_PLATFORMS) | set(BROWSER_PLATFORMS)
ALL = sorted(CHECKABLE | {"phone", "walkin", "unknown"})


def date_range(a: str, b: str) -> list[str]:
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    return [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def key(v: dict) -> tuple[str, str]:
    return (v["name"], v.get("platform", "unknown"))


def row(v: dict, res: VenueResult | None, q: Query, skip_reason: str | None = None) -> dict:
    out = {k: v.get(k) for k in ("name", "kind", "platform", "id", "url", "phone", "beli_rank", "beli_avg", "beli_ratings", "hood", "notes")}
    if res is None:
        out["slots"] = {d: [] for d in q.dates}
        out["status"] = {d: "skipped" for d in q.dates}
        out["skip_reason"] = skip_reason
    else:
        out["slots"] = {d: res.slots.get(d, []) for d in q.dates}
        out["status"] = {d: res.status.get(d, "error:missing") for d in q.dates}
        if res.day_notes:
            out["day_notes"] = res.day_notes
    out["checked_at"] = dt.datetime.now(TZ).isoformat(timespec="seconds")
    return out


def check_venue(v: dict, q: Query, browser) -> VenueResult:
    p = v["platform"]
    if p in API_PLATFORMS:
        return API_PLATFORMS[p].check(v, q)
    return BROWSER_PLATFORMS[p].check(v, q, browser)


def summarize(r: dict) -> str:
    n = sum(len(s) for s in r["slots"].values())
    errs = sum(1 for s in r["status"].values() if s.startswith("error"))
    return f"{n} slots" + (f", {errs} date errors" if errs else "")


def merge_rows(base: dict | None, fresh: dict[tuple, dict], venues: list[dict], q: Query) -> list[dict]:
    """venues.json order; fresh rows win, otherwise keep the previous row if dates match."""
    prev = {key(r): r for r in (base or {}).get("venues", [])}
    out = []
    for v in venues:
        k = key(v)
        if k in fresh:
            r = fresh[k]
            old = prev.get(k)
            if old:  # a failed check never wipes the last good answer for that date
                for d in q.dates:
                    if r["status"].get(d, "").startswith("error") and \
                            old.get("status", {}).get(d) in ("ok", "none"):
                        r["slots"][d] = old.get("slots", {}).get(d, [])
                        r["status"][d] = old["status"][d]
                        when = (old.get("good_at", {}) or {}).get(d) or old.get("checked_at", "")
                        r.setdefault("good_at", {})[d] = when
                        r.setdefault("day_notes", {})[d] = f"stale: last good check {when[5:16].replace('T', ' ')}"
                    elif r["status"].get(d) in ("ok", "none"):
                        r.setdefault("good_at", {})[d] = r["checked_at"]
            out.append(r)
        elif k in prev:
            r = dict(prev[k])
            # refresh static metadata from venues.json, keep the old availability
            r.update({f: v.get(f) for f in ("kind", "id", "url", "phone", "beli_rank", "beli_avg", "beli_ratings", "hood", "notes")})
            r["slots"] = {d: r.get("slots", {}).get(d, []) for d in q.dates}
            r["status"] = {d: r.get("status", {}).get(d, "error:not checked yet") for d in q.dates}
            out.append(r)
        else:
            out.append(row(v, VenueResult(status={d: "error:not checked yet" for d in q.dates}), q))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", default="dallas", help="slug from cities.json")
    ap.add_argument("--venues", help="default cities/<city>/venues.json")
    ap.add_argument("--out", help="default cities/<city>/results/p<party>.json")
    ap.add_argument("--platforms", default=",".join(ALL), help=f"comma list from {ALL}")
    ap.add_argument("--start-date", help="default from cities.json")
    ap.add_argument("--end-date", help="default from cities.json")
    ap.add_argument("--party", type=int, help="default from cities.json (4)")
    ap.add_argument("--window", help="HH:MM-HH:MM, city-local, inclusive; default from cities.json")
    ap.add_argument("--only", help="only venues whose name contains this (case-insensitive)")
    ap.add_argument("--delay", default="1.0-2.0", help="seconds between requests, min-max")
    ap.add_argument("--merge-from", help="(publish helper) copy rows for --platforms from this results "
                                          "file into --out without checking anything")
    a = ap.parse_args()
    global TZ
    city = load_city(a.city)
    TZ = ZoneInfo(city.get("tz", "America/Chicago"))
    cdir = HERE / "cities" / a.city
    a.party = a.party or city.get("party", 4)
    a.window = a.window or city.get("window", "17:00-22:00")
    d0, d1 = city_dates(city, dt.datetime.now(TZ).date())
    a.start_date, a.end_date = a.start_date or d0, a.end_date or d1
    a.venues = a.venues or str(cdir / "venues.json")
    a.out = a.out or str(cdir / "results" / f"p{a.party}.json")

    platforms = {p.strip() for p in a.platforms.split(",") if p.strip()}
    bad = platforms - set(ALL)
    if bad:
        ap.error(f"unknown platforms {sorted(bad)}")
    start, end = a.window.split("-")
    dmin, dmax = (float(x) for x in a.delay.split("-"))
    today = dt.datetime.now(TZ).date().isoformat()
    dates = [d for d in date_range(a.start_date, a.end_date)]
    q = Query(party=a.party, dates=dates, start=start, end=end, min_delay=dmin, max_delay=dmax)
    venues = json.loads(Path(a.venues).read_text())
    out_path = Path(a.out)
    base = json.loads(out_path.read_text()) if out_path.exists() else None

    if a.merge_from:
        theirs = json.loads(Path(a.merge_from).read_text())
        fresh = {key(r): r for r in theirs.get("venues", []) if r.get("platform") in platforms}
        result = dict(base or theirs)
        result["generated_at"] = max(result.get("generated_at", ""), theirs.get("generated_at", ""))
        result["venues"] = merge_rows(base, fresh, venues, q)
        out_path.write_text(json.dumps(result, indent=1) + "\n")
        print(f"merged {len(fresh)} rows for {sorted(platforms)} from {a.merge_from}")
        return 0

    selected = [v for v in venues if v.get("platform", "unknown") in platforms
                and (not a.only or a.only.lower() in v["name"].lower())]
    fresh: dict[tuple, dict] = {}
    past = [d for d in dates if d < today]

    def run_one(v, browser=None):
        p = v.get("platform", "unknown")
        if p not in CHECKABLE:
            reason = {"phone": "call", "walkin": "walk-in"}.get(p, "unknown platform")
            fresh[key(v)] = row(v, None, q, reason)
            print(f"  - {v['name']} [{p}] skipped ({reason})")
            return
        t0 = time.time()
        try:
            qq = Query(**{**q.__dict__, "dates": [d for d in dates if d >= today]})
            res = check_venue(v, qq, browser) if qq.dates else VenueResult()
            for d in past:
                res.slots[d], res.status[d] = [], "skipped"
                res.day_notes[d] = "past"
        except Exception as e:  # per-venue isolation
            traceback.print_exc(limit=2)
            res = VenueResult(status={d: err(e) for d in dates})
        r = row(v, res, q)
        fresh[key(v)] = r
        print(f"  - {v['name']} [{p}] {summarize(r)} ({time.time() - t0:.0f}s)")

    for p in sorted(platforms & set(API_PLATFORMS)) + sorted(platforms - CHECKABLE):
        group = [v for v in selected if v.get("platform", "unknown") == p]
        if group:
            print(f"[{p}] {len(group)} venues")
        for v in group:
            run_one(v)

    browser_group = [v for v in selected if v.get("platform") in BROWSER_PLATFORMS]
    if browser_group:
        print(f"[browser] {len(browser_group)} venues ({', '.join(sorted({v['platform'] for v in browser_group}))})")
        try:
            from platforms.browser import headless_chrome
            blocked_until_reset = False
            with headless_chrome() as browser:
                for v in browser_group:
                    if blocked_until_reset and v["platform"] == "opentable":
                        fresh[key(v)] = row(v, VenueResult(status={d: "error:opentable rate-limited this run" for d in dates}), q)
                        print(f"  - {v['name']} [opentable] skipped (rate-limited this run)")
                        continue
                    run_one(v, browser)
                    st = fresh[key(v)]["status"].values()
                    if v["platform"] == "opentable" and st and all("403" in s for s in st if s != "skipped"):
                        print("  ! OpenTable 403 - cooling off 120 s, then one retry")
                        time.sleep(120)
                        run_one(v, browser)
                        st = fresh[key(v)]["status"].values()
                        if all("403" in s for s in st if s != "skipped"):
                            print("  ! still 403 - skipping the rest of OpenTable this run (last good data kept)")
                            blocked_until_reset = True
                    elif v["platform"] == "opentable":
                        time.sleep(random.uniform(4, 9))  # space out page loads; Akamai rate-limits bursts
        except Exception as e:  # platform-level isolation: browser failed to start, etc.
            traceback.print_exc(limit=3)
            for v in browser_group:
                if key(v) not in fresh:
                    fresh[key(v)] = row(v, VenueResult(status={d: err(e) for d in dates}), q)

    result = {
        "generated_at": dt.datetime.now(TZ).isoformat(timespec="seconds"),
        "party": a.party,
        "city": a.city,
        "window": {"start": start, "end": end, "tz": city.get("tz", "America/Chicago")},
        "dates": dates,
        "platforms_checked_this_run": sorted(platforms),
        "venues": merge_rows(base, fresh, venues, q),
    }
    out_path.write_text(json.dumps(result, indent=1) + "\n")
    total = sum(sum(len(s) for s in r["slots"].values()) for r in fresh.values())
    print(f"wrote {out_path} ({len(fresh)} venues checked, {total} open slots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
