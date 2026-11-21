"""Resy: anonymous availability via Resy's JSON API with the public web api_key.

Lifted (read-only parts only) from resy-sniper/resy_sniper/client.py: GET /4/find.
No auth token, no /3/details, no /3/book, no cancel. The public key below is the one
resy.com's own site ships to every anonymous visitor.

Flow per venue: one /4/venue/calendar call (which dates have any reservation
inventory), then one /4/find per date that does.
"""

from __future__ import annotations

import urllib.parse

from .common import Query, VenueResult, err, finish, get_json, polite_sleep, retry

BASE = "https://api.resy.com"
PUBLIC_API_KEY = "VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"
HEADERS = {
    "Authorization": f'ResyAPI api_key="{PUBLIC_API_KEY}"',
    "Origin": "https://resy.com",
    "Referer": "https://resy.com/",
}


def _get(path: str, **params):
    return retry(lambda: get_json(f"{BASE}{path}?{urllib.parse.urlencode(params)}", HEADERS))


def calendar(venue_id: int, q: Query) -> dict[str, str]:
    j = _get("/4/venue/calendar", venue_id=venue_id, num_seats=q.party,
             start_date=min(q.dates), end_date=max(q.dates))
    return {d["date"]: d.get("inventory", {}).get("reservation", "") for d in j.get("scheduled", [])}


def find_times(venue_id: int, day: str, party: int) -> set[str]:
    j = _get("/4/find", lat=0, long=0, day=day, party_size=party, venue_id=venue_id)
    out = set()
    for v in j.get("results", {}).get("venues", []):
        for s in v.get("slots", []):
            start = (s.get("date") or {}).get("start", "")  # 'YYYY-MM-DD HH:MM:SS'
            if start[:10] == day:
                out.add(start[11:16])
    return out


def check(venue: dict, q: Query) -> VenueResult:
    res = VenueResult()
    vid = int(venue["id"])
    try:
        cal = calendar(vid, q)
        polite_sleep(q)
    except Exception as e:  # calendar is an optimisation; fall back to find on every date
        cal = {}
        print(f"    resy calendar failed ({err(e)}), checking every date")
    times: dict[str, set[str]] = {}
    for d in q.dates:
        state = cal.get(d)
        if state and state != "available":
            res.slots[d], res.status[d] = [], "none"
            if state in ("closed", "sold-out"):
                res.day_notes[d] = state
            continue
        try:
            times[d] = find_times(vid, d, q.party)
        except Exception as e:
            res.slots[d], res.status[d] = [], err(e)
        polite_sleep(q)
    finish(times, q, res)
    return res


def resolve(url_or_slug: str, location: str | None = None) -> dict:
    """resy.com venue URL (or slug) -> {'id', 'name', 'slug', 'location'}.

    URLs look like https://resy.com/cities/dallas-tx/venues/cbd-provisions (newer) or
    https://resy.com/cities/dfw/cbd-provisions (older). The API wants Resy's city code
    ('dfw' for Dallas-Fort Worth), so we try the URL's city then 'dfw'.
    """
    path = urllib.parse.urlparse(url_or_slug).path.strip("/").split("/")
    slug = path[-1]
    tries = [location] if location else []
    if "cities" in path:
        tries.append(path[path.index("cities") + 1])
    tries += ["dfw", "dallas-tx"]
    last = None
    for loc in [t for t in tries if t]:
        try:
            j = _get("/3/venue", url_slug=slug, location=loc)
            vid = (j.get("id") or {}).get("resy")
            if vid:
                return {"id": vid, "name": j.get("name"), "slug": slug, "location": loc}
        except Exception as e:
            last = e
    raise RuntimeError(f"Resy venue not found for slug {slug!r} ({last})")
