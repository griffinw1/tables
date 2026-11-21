"""SevenRooms: the public booking widget's availability range API (no auth).

Same call as Aspen-Trip-deploy/.github/release-watch/watch.py. Only times whose
type == "book" are bookable; "request" (request-a-table) and others are ignored.
num_days is capped by SevenRooms (9 and 7 are rejected, 3 works), so dates are
fetched in chunks of 3.
"""

from __future__ import annotations

import datetime as dt
import urllib.parse

from .common import Query, VenueResult, err, finish, get_json, polite_sleep, retry

URL = "https://www.sevenrooms.com/api-yoa/availability/ng/widget/range"
CHUNK = 3


def fetch(slug: str, start: str, num_days: int, party: int) -> dict[str, set[str]]:
    params = {"venue": slug, "party_size": party, "halo_size_interval": 100,
              "start_date": start, "num_days": num_days,
              "channel": "SEVENROOMS_WIDGET", "exclude_pdr": "true"}
    j = retry(lambda: get_json(f"{URL}?{urllib.parse.urlencode(params)}"))
    if j.get("status") != 200 or "data" not in j:
        raise RuntimeError(f"SevenRooms status {j.get('status')}: {j.get('msg')}")
    out: dict[str, set[str]] = {}
    for date, shifts in (j["data"].get("availability") or {}).items():
        for shift in shifts or []:
            for t in shift.get("times") or []:
                if t.get("type") == "book" and t.get("time_iso"):
                    out.setdefault(date, set()).add(t["time_iso"][11:16])  # 'YYYY-MM-DD HH:MM:SS'
    return out


def check(venue: dict, q: Query) -> VenueResult:
    res = VenueResult()
    dates = sorted(q.dates)
    times: dict[str, set[str]] = {}
    i = 0
    while i < len(dates):
        start = dates[i]
        # contiguous run of up to CHUNK dates starting at `start`
        n = 1
        while (n < CHUNK and i + n < len(dates) and
               dt.date.fromisoformat(dates[i + n]) - dt.date.fromisoformat(start) == dt.timedelta(days=n)):
            n += 1
        try:
            got = fetch(venue["id"], start, n, q.party)
            for d in dates[i:i + n]:
                times[d] = got.get(d, set())
        except Exception as e:
            for d in dates[i:i + n]:
                res.slots[d], res.status[d] = [], err(e)
        i += n
        polite_sleep(q)
    finish(times, q, res)
    return res


def resolve(url_or_slug: str) -> dict:
    """SevenRooms URL -> slug. URLs look like
    https://www.sevenrooms.com/reservations/<slug> or
    https://www.sevenrooms.com/explore/<slug>/reservations/create/search."""
    p = urllib.parse.urlparse(url_or_slug)
    parts = [x for x in p.path.split("/") if x]
    qs = urllib.parse.parse_qs(p.query)
    if "venue" in qs:
        slug = qs["venue"][0]
    elif "reservations" in parts and parts.index("reservations") + 1 < len(parts) and parts[0] == "reservations":
        slug = parts[1]
    elif "explore" in parts:
        slug = parts[parts.index("explore") + 1]
    else:
        slug = parts[-1] if parts else url_or_slug
    today = dt.date.today().isoformat()
    fetch(slug, today, 1, 2)  # raises if the slug is unknown
    return {"id": slug}
