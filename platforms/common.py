"""Shared helpers: polite HTTP with retries, time-window filtering, time formatting.

READ-ONLY. Nothing in this project books, holds, locks, or cancels anything.
Every request here is an anonymous availability lookup.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")


@dataclass
class Query:
    party: int
    dates: list[str]          # 'YYYY-MM-DD', venue-local
    start: str = "17:00"      # 'HH:MM' inclusive, venue-local (America/Chicago)
    end: str = "22:00"        # 'HH:MM' inclusive
    min_delay: float = 1.0
    max_delay: float = 2.0


@dataclass
class VenueResult:
    slots: dict[str, list[str]] = field(default_factory=dict)   # date -> ['5:30 PM', ...]
    status: dict[str, str] = field(default_factory=dict)        # date -> ok|none|error:...|skipped
    day_notes: dict[str, str] = field(default_factory=dict)     # date -> e.g. 'closed'


class Transient(Exception):
    """Worth retrying (5xx, 429, network)."""


def polite_sleep(q: Query) -> None:
    time.sleep(random.uniform(q.min_delay, q.max_delay))


def retry(fn, *, attempts: int = 3, base: float = 2.0):
    """Call fn(); on Transient, back off base, 2*base, ... and retry."""
    for i in range(attempts):
        try:
            return fn()
        except Transient:
            if i == attempts - 1:
                raise
            time.sleep(base * (2 ** i) + random.uniform(0, 1))


def get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 25.0):
    """GET a JSON URL. Raises Transient for 429/5xx/network, RuntimeError for other HTTP errors."""
    # Caller headers FIRST. Resy's edge answers HTTP 500 when Accept precedes
    # Authorization (verified 2026-11-18: 4/4 fail vs 4/4 succeed by header order alone).
    hdrs = dict(headers or {})
    hdrs.setdefault("User-Agent", UA)
    hdrs.setdefault("Accept", "application/json, text/plain, */*")
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        if e.code == 429 or e.code >= 500:
            raise Transient(f"HTTP {e.code}") from e
        raise RuntimeError(f"HTTP {e.code}: {body}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise Transient(f"network: {e}") from e


def in_window(hhmm: str, q: Query) -> bool:
    return q.start <= hhmm <= q.end


def fmt12(hhmm: str) -> str:
    """'17:30' -> '5:30 PM'."""
    h, m = (int(x) for x in hhmm.split(":")[:2])
    return f"{(h % 12) or 12}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def finish(times_by_date: dict[str, set[str]], q: Query, res: VenueResult) -> None:
    """Window-filter + sort 'HH:MM' sets into res.slots/res.status for dates not already set."""
    for d in q.dates:
        if d in res.status:
            continue
        times = sorted(t for t in times_by_date.get(d, set()) if in_window(t, q))
        res.slots[d] = [fmt12(t) for t in times]
        res.status[d] = "ok" if times else "none"


def err(e: Exception) -> str:
    msg = str(e).splitlines()[0] if str(e) else ""
    return f"error:{type(e).__name__}:{msg}"[:160]
