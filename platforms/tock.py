"""Tock: read the venue's availability calendar that the Tock page loads by itself.

One headless page load of https://www.exploretock.com/<slug>/search?... makes Tock's
app fetch POST /api/consumer/calendar/full/v2 (protobuf) once. That single response
holds inventory for every date on the calendar, so there is one page load per venue
and no API calls of our own. Nothing is selected, locked, or booked. The lock and
unlock code in resy-sniper was deliberately not copied.

Calendar layout (from resy-sniper/docs/tock.md, re-verified 2026-11-18):
  days at 1.1.60686.1; each day: 1 = 'YYYY-MM-DD'; slot records at 2.1.2.2 with
  3 = 'HH:MM', 4 = capacity (table size, or seats in a shared seating),
  6 = held seats, 7 = booked seats, 19 = max party size, 13 = {1: experience_id, 2: price_cents}.
  A slot is open for a party of N when (4 - 6 - 7) >= N and 19 >= N.
  Cross-checked against the rendered page: Tatsu (sold out) has 0 free on every slot;
  Mo's, Centennial and Dunston's show "Book" exactly where free 4-tops exist.
Offerings (POST /api/consumer/offerings) at 1.1.60249.1: 1 = experience_id, 3 = name.
Pickup/to-go/delivery experiences are excluded by name. A venue can pin experiences
with "tock_experiences": [ids] in venues.json.
"""

from __future__ import annotations

import re
import time

from .common import Query, VenueResult, err, finish, polite_sleep
from .tockproto import first_fields, messages

NON_DINING = re.compile(r"to[- ]?go|pick[- ]?up|delivery|takeout|take[- ]out|gift|merch|shipping|curbside", re.I)


def experience_names(offerings: bytes | None) -> dict[int, str]:
    out: dict[int, str] = {}
    if not offerings:
        return out
    try:
        for entry in messages(offerings, 1, 1, 60249, 1):
            f = first_fields(entry)
            if isinstance(f.get(1), int) and isinstance(f.get(3), bytes):
                out[f[1]] = f[3].decode("utf-8", "replace")
    except ValueError:
        pass
    return out


def parse_calendar(cal: bytes, party: int, allowed: set[int] | None, names: dict[int, str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for day in messages(cal, 1, 1, 60686, 1):
        date = first_fields(day).get(1)
        if not isinstance(date, bytes):
            continue
        d = date.decode()
        out.setdefault(d, set())
        for slot in messages(day, 2, 1, 2, 2):
            f = first_fields(slot)
            t = f.get(3)
            if not isinstance(t, bytes):
                continue
            exp = None
            if isinstance(f.get(13), bytes):
                exp = first_fields(f[13]).get(1)
            if allowed is not None and exp not in allowed:
                continue
            if allowed is None and exp in names and NON_DINING.search(names[exp]):
                continue
            cap, held, booked, maxp = (f.get(k, 0) for k in (4, 6, 7, 19))
            if not all(isinstance(x, int) for x in (cap, held, booked, maxp)):
                continue
            if cap - held - booked >= party and (maxp or cap) >= party:
                out[d].add(t.decode()[:5])
    return out


def check(venue: dict, q: Query, browser) -> VenueResult:
    res = VenueResult()
    slug = venue["id"]
    first = min(q.dates)
    allowed = set(venue["tock_experiences"]) if venue.get("tock_experiences") else None
    pg = browser.page()
    got: dict[str, object] = {}   # Response objects; bodies are read after the page settles

    def on_resp(r):
        for key in ("/api/consumer/calendar/full/v2", "/api/consumer/offerings"):
            if key in r.url and r.status == 200:
                got[key] = r
    pg.on("response", on_resp)
    try:
        for attempt in range(2):
            r = pg.goto(f"https://www.exploretock.com/{slug}/search?date={first}&size={q.party}&time=19%3A00",
                        wait_until="domcontentloaded", timeout=45000)
            title = pg.title().lower()
            if any(s in title for s in ("just a moment", "attention required", "verify you are human")):
                raise RuntimeError("Cloudflare challenge page (blocked)")
            if r is not None and r.status in (429,) or (r is not None and r.status >= 500):
                time.sleep(5 * (attempt + 1))
                continue
            if r is not None and r.status >= 400:
                raise RuntimeError(f"HTTP {r.status}")
            deadline = time.time() + 25
            while "/api/consumer/calendar/full/v2" not in got and time.time() < deadline:
                pg.wait_for_timeout(500)
            pg.wait_for_timeout(800)  # let offerings land too
            if "/api/consumer/calendar/full/v2" in got:
                break
        if "/api/consumer/calendar/full/v2" not in got:
            raise RuntimeError("no calendar response (venue has no reservable experiences, or page changed)")
        cal = got["/api/consumer/calendar/full/v2"].body()
        try:
            off = got["/api/consumer/offerings"].body() if "/api/consumer/offerings" in got else None
        except Exception:
            off = None
        names = experience_names(off)
        times = parse_calendar(cal, q.party, allowed, names)
        for d in q.dates:
            if d not in times:
                res.slots[d], res.status[d] = [], "none"
                res.day_notes[d] = "not on calendar"
        finish(times, q, res)
    except Exception as e:
        for d in q.dates:
            res.slots.setdefault(d, [])
            res.status.setdefault(d, err(e))
    finally:
        pg.close()
        polite_sleep(q)
    return res


def resolve(url: str) -> dict:
    """exploretock.com URL -> slug: https://www.exploretock.com/<slug>[/...]."""
    from urllib.parse import urlparse
    parts = [x for x in urlparse(url).path.split("/") if x]
    if not parts:
        raise RuntimeError("no slug in Tock URL")
    return {"id": parts[0]}
