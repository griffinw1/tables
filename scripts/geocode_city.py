#!/usr/bin/env python3
"""Fill cities/<slug>/geo.json with lat/lng for every venue (venues.json + coffee.json) that lacks one.

  python3 scripts/geocode_city.py boston
Sources: a street address (research/candidates.json, coffee_candidates.json, venues.json "address")
-> OpenStreetMap Nominatim, else "<name>, <city>, <state>". Hits must fall inside the city's bbox
(cities.json "bbox": [south, west, north, east]). Nominatim: max 1 request/second, generic User-Agent.
"""
import json, sys, time, urllib.parse, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
UA = "tables-site/1.0 (geocoding public business addresses)"

def nominatim(q, bbox):
    s, w, n, e = bbox
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": q, "format": "json", "limit": 1, "viewbox": f"{w},{n},{e},{s}", "bounded": 1})
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20) as r:
        j = json.load(r)
    time.sleep(1.1)
    return (float(j[0]["lat"]), float(j[0]["lon"])) if j else None

def main(slug):
    city = next(c for c in json.loads((HERE / "cities.json").read_text()) if c["slug"] == slug)
    cdir = HERE / "cities" / slug
    gp = cdir / "geo.json"
    geo = json.loads(gp.read_text()) if gp.exists() else {"generated_by": "scripts/geocode_city.py", "venues": {}}
    addr = {}
    for f, key in ((cdir / "research" / "candidates.json", "places"), (cdir / "coffee_candidates.json", None), (cdir / "venues.json", None)):
        if f.exists():
            d = json.loads(f.read_text()); d = d[key] if key else d
            for x in d:
                if x.get("address"): addr.setdefault(x["name"], x["address"])
    names = [v["name"] for v in json.loads((cdir / "venues.json").read_text())]
    if (cdir / "coffee.json").exists():
        names += [v["name"] for v in json.loads((cdir / "coffee.json").read_text())]
    bbox = city["bbox"]
    for n in names:
        if n in geo["venues"]:
            continue
        hit, src = None, None
        for q, s in ((addr.get(n), "osm-address"), (f"{n}, {city['name']}, {city.get('state', '')}", "osm-name")):
            if not q:
                continue
            try:
                hit = nominatim(q, bbox)
            except Exception as e:
                print("  !", n, e); time.sleep(2)
            if hit:
                src = s; break
        if hit:
            geo["venues"][n] = {"lat": round(hit[0], 6), "lng": round(hit[1], 6), "src": src}
            print(f"{n}: {hit} ({src})")
        else:
            print(f"{n}: not found")
        gp.write_text(json.dumps(geo, indent=1, ensure_ascii=False) + "\n")
    print("done", sum(1 for n in names if n in geo["venues"]), "/", len(names))

if __name__ == "__main__":
    main(sys.argv[1])
