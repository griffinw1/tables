"""One-off: research/candidates.json -> cities/boston/venues.json (+ specials.json, media.json) using resolve()."""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from resolve import resolve
B = HERE / "cities" / "boston"
places = json.loads((B / "research" / "candidates.json").read_text())["places"]
sp = {x["name"]: x for x in json.loads((B / "research" / "specials.json").read_text())["places"]}
ph = {x["name"]: x for x in json.loads((B / "research" / "photos.json").read_text())["places"]}
out, media, specials = [], {}, {}
for i, p in enumerate(places, 1):
    bk = p.get("booking") or {}
    plat, url = (bk.get("platform") or "unknown").lower(), bk.get("url")
    entry = {"name": p["name"], "kind": p.get("kind", "restaurant"), "beli_rank": None, "beli_avg": None,
             "hood": (p.get("neighborhood") or "").split(" (")[0], "platform": plat, "id": None, "url": url or p.get("website"),
             "phone": p.get("phone"), "notes": bk.get("notes", ""), "press_rank": i}
    if plat in ("resy", "opentable", "sevenrooms", "tock") and url:
        try:
            info = resolve(url); entry["platform"], entry["id"] = info["platform"], info["id"]
        except Exception as e:
            print("  ! resolve failed", p["name"], plat, e); entry["platform"] = "unknown"
        time.sleep(1)
    elif plat not in ("phone", "walkin"):
        entry["platform"] = "unknown"
    out.append(entry); print(f"{p['name']}: {entry['platform']} {entry['id']}")
    imgs = []
    for it in (ph.get(p["name"]) or {}).get("items", []):
        for c in [it.get("best")] + (it.get("runners_up") or []):
            if c and c.get("url"): imgs.append(c["url"])
    media[p["name"]] = {"website": p.get("website"), "cuisine": p.get("cuisine"), "images": list(dict.fromkeys(imgs))[:8], "img_src": "their site"}
    fam = [f["item"] for f in (sp.get(p["name"]) or {}).get("famous", [])][:2]
    if fam:
        kf = " and ".join(fam)
        specials[p["name"]] = {"known_for": kf if len(kf) <= 70 else fam[0]}
json.dump(out, open(B / "venues.json", "w"), indent=1, ensure_ascii=False)
json.dump(media, open(B / "media.json", "w"), indent=1, ensure_ascii=False)
json.dump(specials, open(B / "specials.json", "w"), indent=1, ensure_ascii=False)
print("wrote", len(out))
