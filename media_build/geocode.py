#!/usr/bin/env python3
"""venues.json -> map/geo.json (lat/lng per venue for the Map page).

  python3 media_build/geocode.py            # geocode every venue, write map/geo.json
  python3 media_build/geocode.py --only "Nuri Steakhouse" "Stillwell's"   # redo just these, merge into geo.json

Sources, in order:
  1. Resy venues: Resy's public venue API (location.latitude/longitude).
  2. A known street address (ADDR below, taken from venues.json notes or the venue's own site)
     -> OpenStreetMap Nominatim.
  3. The venue name -> Nominatim ("<name>, Dallas, Texas").
Every hit must land inside Dallas (lat 32.6-33.1, lng -97.0 to -96.5). If it is far from the
venue's `hood` centre (HOODS below) it is kept but flagged "approx": true. Nominatim is called at
most once a second with a generic User-Agent and nothing but the place query.
"""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "map" / "geo.json"
UA = "dallas-res-watch/1.0"
RESY_KEY = "VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"

# Street addresses (venues.json notes / official sites). Only used for non-Resy venues.
ADDR = {
    "Shoyo": "1916 Greenville Ave",
    "Uchi": "2817 Maple Ave",
    "Uchiba": "2817 Maple Ave",
    "Mamani": "2681 Howell St",
    "Mister Charles": "3229 Knox St",
    "Naminohana": "5521 Greenville Ave",
    "Norman's Japanese Grill": "4002 Oak Lawn Ave",
    "Town Hearth": "1617 Market Center Blvd",
    "Bar Sardine": "6805 Snider Plaza",
    "Jack & Harry's": "6833 Snider Plaza",
    "Bowen House": "2614 Boll St",
    "Al Biernat's": "4217 Oak Lawn Ave",
    "il Bracco": "8416 Preston Center Plaza",
    "El Molino": "6818 Snider Plaza",
    "Quarter Acre": "2023 Greenville Ave",
    "Sushi by Scratch Restaurants: Dallas": "1321 Commerce St",
    "MĀBO": "6109 Berkshire Ln",
    "Sushi Kozy": "2000 Ross Ave",
    "Mot Hai Ba": "6047 Lewis St",
    "Namo": "3699 McKinney Ave",
    "Koryo Korean BBQ": "2560 Royal Ln",
    "Yujo": "12835 Preston Rd",
    "Marlowe Lounge": "2912 McKinney Ave",
    "Triumphs Espresso & Whiskey": "141 Manufacturing St",
    "Katy Trail Ice House": "3127 Routh St",
    "Lounge Here": "9028 Garland Rd",
    "SILO": "1340 Manufacturing St",
    "Nobu Dallas": "400 Crescent Ct",
    "The Mansion Bar": "2821 Turtle Creek Blvd",
    "Nick & Sam's": "3008 Maple Ave",
    "Apothecary": "1922 Greenville Ave",
    "Georgie": "4514 Travis St",
    "Hillstone": "8300 Preston Rd",
    "Stillwell's": "2575 McKinnon St",  # Hotel Swexan, 7th floor
    "Bar Colette": "3699 McKinney Ave",
    "Otaru Sushi & Handroll Bar": "408 W 8th St",
    "Kilmac's": "814 W Davis St",
    "Mike's Gemini Twin Lounge": "1906 S Harwood St",
    "Clifton Club Bar & Lounge": "3333 N Fitzhugh Ave",
    "Tatsu Dallas": "3309 Elm St",  # Continental Gin Building, Suite 120 (Michelin guide)
    "Purepecha and Revolver Taco Lounge": "2701 Main St",  # Suite 120 (OpenTable)
    "Nuri Steakhouse": "2401 Cedar Springs Rd",  # Suite 120 (nuristeakhouse.com)
}

# Addresses recalled from memory, not confirmed on the venue's own page: flagged approx.
# (Nov 19: Tatsu, Purepecha, Stillwell's, Apothecary and Nuri confirmed against official/listing pages.)
UNVERIFIED: set[str] = set()

# Rough neighbourhood centres + how far (km) a pin may sit from them before it is "approx".
HOODS = {
    "Lower Greenville": (32.8135, -96.7700, 3.0), "Uptown": (32.7980, -96.8010, 3.0),
    "Bishop Arts": (32.7490, -96.8285, 3.0), "Knox/Henderson": (32.8215, -96.7900, 3.0),
    "Old East Dallas": (32.7990, -96.7720, 3.5), "Oak Lawn": (32.8100, -96.8150, 3.5),
    "Design District": (32.7960, -96.8250, 3.0), "Park Cities": (32.8450, -96.7950, 5.0),
    "Cityplace": (32.8060, -96.7930, 2.5), "NW Dallas": (32.8900, -96.8800, 7.0),
    "North Dallas": (32.9300, -96.8000, 8.0), "Oak Cliff": (32.7400, -96.8300, 5.0),
    "Cedars": (32.7700, -96.7950, 2.5), "Little Forest Hills": (32.8250, -96.7160, 3.0),
    "Downtown": (32.7810, -96.7980, 2.5), "Peak's Suburban Addition": (32.7950, -96.7750, 2.5),
}


def get(url: str, headers: dict) -> object:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def in_dallas(lat: float, lng: float) -> bool:
    return 32.6 <= lat <= 33.1 and -97.0 <= lng <= -96.5


def km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def resy(vid) -> tuple | None:
    d = get(f"https://api.resy.com/3/venue?id={vid}", {
        "Authorization": f'ResyAPI api_key="{RESY_KEY}"', "Accept": "application/json",
        "Origin": "https://resy.com", "User-Agent": "Mozilla/5.0"})
    loc = d.get("location") or {}
    if loc.get("latitude") and loc.get("longitude"):
        return float(loc["latitude"]), float(loc["longitude"])
    return None


_last = [0.0]


def nominatim(q: str) -> list:
    wait = 1.1 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"format": "json", "q": q, "limit": 5, "countrycodes": "us"})
    try:
        return get(url, {"User-Agent": UA, "Accept": "application/json"}) or []
    except Exception as e:  # noqa: BLE001
        print("   nominatim error:", e)
        return []


def pick(hits: list, hood) -> tuple | None:
    pts = [(float(h["lat"]), float(h["lon"])) for h in hits]
    pts = [p for p in pts if in_dallas(*p)]
    if not pts:
        return None
    if hood in HOODS:
        pts.sort(key=lambda p: km(p, HOODS[hood][:2]))
    return pts[0]


def main() -> None:
    import sys
    venues = json.loads((ROOT / "venues.json").read_text())
    out, missing = {}, []
    only = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None
    if only:  # keep every other venue as it is
        prev = json.loads(OUT.read_text())
        out = {k: r for k, r in prev["venues"].items() if k not in only}
        missing = [n for n in prev.get("missing", []) if n not in only]
        venues = [v for v in venues if v["name"] in only]
    for v in venues:
        name, hood = v["name"], v.get("hood")
        pt, src = None, None
        if v.get("platform") == "resy" and v.get("id"):
            try:
                pt, src = resy(v["id"]), "resy"
            except Exception as e:  # noqa: BLE001
                print("   resy error:", e)
            if pt and not in_dallas(*pt):
                pt = None
        if not pt and name in ADDR:
            pt, src = pick(nominatim(f"{ADDR[name]}, Dallas, Texas"), hood), "osm-address"
            if not pt:  # University Park / Highland Park addresses are not "Dallas" to OSM
                pt = pick(nominatim(f"{ADDR[name]}, Texas"), hood)
        if not pt:
            base = name.replace(": Dallas", "").replace(" Dallas", "")
            pt, src = pick(nominatim(f"{base}, Dallas, Texas"), hood), "osm-name"
            if not pt and " " in base:  # e.g. "Nuri Steakhouse" -> "Nuri, Dallas"
                pt = pick(nominatim(f"{base.split()[0]} restaurant, Dallas, Texas"), hood)
        if not pt:
            missing.append(name)
            print(f"MISS  {name}")
            continue
        rec = {"lat": round(pt[0], 6), "lng": round(pt[1], 6), "src": src}
        if hood in HOODS:
            d = km(pt, HOODS[hood][:2])
            if d > HOODS[hood][2]:
                rec["approx"] = True
            rec["hood_km"] = round(d, 1)
        if name in UNVERIFIED and src == "osm-address":
            rec["approx"] = True
        out[name] = rec
        print(f"{'APPROX' if rec.get('approx') else 'ok    '} {name:40s} {rec}")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generated_by": "media_build/geocode.py", "venues": out, "missing": missing},
                              ensure_ascii=False, indent=1) + "\n")
    print(f"\n{len(out)} placed, {sum(1 for r in out.values() if r.get('approx'))} approx, missing: {missing}")


if __name__ == "__main__":
    main()
