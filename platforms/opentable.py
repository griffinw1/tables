"""OpenTable: the site's own `RestaurantsAvailability` GraphQL query, run inside a
headless Chrome tab that has loaded the restaurant's profile page.

- Loading /restaurant/profile/<rid> sets the cookies and window.__CSRF_TOKEN__ that the
  query needs. Akamai blocks plain HTTP clients, so the query has to run in the browser.
- One query with forwardDays=N covers N+1 consecutive days. Each day returns at most
  ~5 slots nearest the anchor time, so we query a few anchors across the window and
  merge them. That is ~5 requests per venue for the whole 9-day range.
- Read-only: this is the same query the profile page fires on load. No slot is
  selected, locked or booked.
- Blocked from GitHub Actions (HTTP 403), so run it on the Mac.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse

from .common import Query, VenueResult, err, finish, polite_sleep

PERSISTED_HASH = "9d41be178447f0688ceebc509e9e1d8b68c48c02e37a6a5fe313a8231975a4a0"  # seen 2026-11-18
ANCHORS = ["17:30", "18:45", "20:00", "21:15", "22:00"]  # each returns ~±30 min of slots

_JS = """async ({rid, date, time, fd, party, hash}) => {
 const body = {operationName:"RestaurantsAvailability", variables:{onlyPop:false,forwardDays:fd,requireTimes:false,
   requireTypes:["Standard","Experience"],privilegedAccess:[],includeGuestTagAccessRules:false,includeAvailableSpaces:false,
   includeMetaSearchListingSlots:false,includeSlotTypes:false,restaurantIds:[rid],date,time,partySize:party,
   databaseRegion:"NA",restaurantAvailabilityTokens:[],loyaltyRedemptionTiers:[],correlationId:crypto.randomUUID(),
   forwardMinutes:150,backwardMinutes:150},
   extensions:{persistedQuery:{version:1,sha256Hash:hash}}};
 const r = await fetch('/dapi/fe/gql?optype=query&opname=RestaurantsAvailability',{method:'POST',credentials:'include',
   headers:{'content-type':'application/json','x-csrf-token':window.__CSRF_TOKEN__||'',
            'ot-page-type':'restprofilepage','ot-page-group':'rest-profile'},body:JSON.stringify(body)});
 return {status:r.status, text:await r.text()};
}"""


def _add(hhmm: str, minutes: int) -> tuple[int, str]:
    """('19:30', +45) -> (day_shift, '20:15')."""
    h, m = map(int, hhmm.split(":"))
    total = h * 60 + m + minutes
    return total // 1440, f"{(total % 1440) // 60:02d}:{total % 60:02d}"


def check(venue: dict, q: Query, browser) -> VenueResult:
    res = VenueResult()
    rid = int(venue["id"])
    dates = sorted(q.dates)
    first = dt.date.fromisoformat(dates[0])
    span = (dt.date.fromisoformat(dates[-1]) - first).days
    pg = browser.page()
    try:
        r = pg.goto(f"https://www.opentable.com/restaurant/profile/{rid}", wait_until="domcontentloaded",
                    timeout=45000)
        if r is not None and r.status >= 400:
            raise RuntimeError(f"profile page HTTP {r.status} ({pg.title()[:40]})")
        pg.wait_for_function("() => !!window.__CSRF_TOKEN__", timeout=20000)
        times: dict[str, set[str]] = {d: set() for d in dates}
        seen_days: set[str] = set()
        closed: dict[str, int] = {}
        failures = []
        for anchor in ANCHORS:
            out = None
            for attempt in range(3):
                out = pg.evaluate(_JS, {"rid": rid, "date": dates[0], "time": anchor, "fd": span,
                                        "party": q.party, "hash": PERSISTED_HASH})
                if out["status"] not in (429,) and out["status"] < 500:
                    break
                pg.wait_for_timeout(2000 * (2 ** attempt))
            if out["status"] != 200:
                failures.append(f"HTTP {out['status']}")
                polite_sleep(q)
                continue
            j = json.loads(out["text"])
            if j.get("errors") and not j.get("data"):
                failures.append(f"gql: {j['errors'][0].get('message', '')[:80]}")
                continue
            avail = (j.get("data") or {}).get("availability") or []
            for day in (avail[0].get("availabilityDays") if avail else []) or []:
                d = (first + dt.timedelta(days=day.get("dayOffset", 0))).isoformat()
                seen_days.add(d)
                if "NoTimesExist" in (day.get("noTimesReasons") or []):
                    closed[d] = closed.get(d, 0) + 1
                for sl in day.get("slots") or []:
                    if sl.get("isAvailable") and sl.get("timeOffsetMinutes") is not None:
                        shift, hhmm = _add(anchor, sl["timeOffsetMinutes"])
                        if shift == 0 and d in times:
                            times[d].add(hhmm)
            polite_sleep(q)
        if failures and not seen_days:
            raise RuntimeError("; ".join(failures))
        for d in dates:
            if d not in seen_days:
                res.slots[d], res.status[d] = [], "error:no data for date"
            elif closed.get(d) == len(ANCHORS) - len(failures) and not times[d]:
                res.day_notes[d] = "no times"
        finish(times, q, res)
    except Exception as e:
        for d in dates:
            res.slots.setdefault(d, [])
            res.status.setdefault(d, err(e))
    finally:
        pg.close()
    return res


def resolve(url: str, browser) -> dict:
    """OpenTable URL -> rid. Accepts /restaurant/profile/<rid>, ?rid=<rid>, or /r/<slug>
    (loads the page headlessly and reads the rid from the page's own availability query)."""
    p = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(p.query)
    if "rid" in qs:
        return {"id": int(qs["rid"][0])}
    m = re.search(r"/restaurant/profile/(\d+)", p.path)
    if m:
        return {"id": int(m.group(1))}
    pg = browser.page()
    rids: list[int] = []

    def on_req(r):
        if "opname=RestaurantsAvailability" in r.url and r.post_data:
            try:
                rids.extend(json.loads(r.post_data)["variables"]["restaurantIds"])
            except Exception:
                pass
    pg.on("request", on_req)
    try:
        r = pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        if r is not None and r.status >= 400:
            raise RuntimeError(f"HTTP {r.status}")
        pg.wait_for_timeout(6000)
        if not rids:
            html = pg.content()
            m = re.search(r'"rid"\s*:\s*(\d+)', html) or re.search(r'restaurantId"?\s*:\s*"?(\d+)', html)
            if m:
                rids.append(int(m.group(1)))
        if not rids:
            raise RuntimeError("could not find rid on page")
        return {"id": int(rids[0]), "name": pg.title().split(" | ")[0]}
    finally:
        pg.close()
