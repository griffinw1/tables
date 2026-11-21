#!/usr/bin/env python3
"""cities/<slug>/ (results + venues + beli + media + vibes) -> <slug>/index.html, one page per city.

  python3 render.py            # every city in cities.json, plus index.html (city chooser)
  python3 render.py dallas     # one city

The page is one self-contained file: data is embedded as JSON and drawn by a small
script (page.js, inlined at render time), so every card can have its own day picker and deep-linked times.
Photos are hot-linked from each venue's own Resy/OpenTable/website listing (never copied).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

PLATFORM = {"resy": "Resy", "opentable": "OpenTable", "sevenrooms": "SevenRooms", "tock": "Tock",
            "phone": "Phone", "walkin": "Walk-in", "unknown": "Their site", "none": "Walk-in"}


def load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def load_cities() -> list[dict]:
    return load_json(HERE / "cities.json", [])


def build_data(city: dict, res: dict, cities: list[dict]) -> dict:
    cdir = HERE / "cities" / city["slug"]
    meta = {v["name"]: v for v in load_json(cdir / "venues.json", [])}
    coffee = {c["name"]: c for c in load_json(cdir / "coffee.json", []) if c["name"] not in meta}  # no booking; Beli + photos + hours
    meta.update(coffee)
    media = load_json(cdir / "media.json", {})
    vibes = load_json(cdir / "vibes.json", {})  # optional; keyed by exact venue name
    geo = (load_json(cdir / "geo.json", {}) or {}).get("venues", {})
    specials = load_json(cdir / "specials.json", {})  # optional: known_for / famous items (web research)
    more = load_json(cdir / "media_more.json", {})  # optional: extra tagged photos from official/platform listings
    beli = {}
    try:  # one line per venue from the phone pull; later lines win
        for line in (cdir / "beli.jsonl").read_text().splitlines():
            if line.strip():
                b = json.loads(line)
                beli[b["name"]] = b
    except FileNotFoundError:
        pass
    venues = []
    seen = {r["name"] for r in res["venues"]}
    rows = res["venues"] + [{"name": n, "kind": v.get("kind"), "platform": v.get("platform", "none")}
                            for n, v in meta.items() if n not in seen]
    for r in rows:
        m = dict(meta.get(r["name"], {}))
        b = beli.get(r["name"])
        if b and b.get("avg") is not None:
            m["beli_avg"] = b["avg"]
            m["beli_ratings"] = b.get("ratings")
            m["beli_dishes"] = [{"dish": d["dish"].replace("... (truncated)", "…"), "count": d.get("count")}
                                for d in (b.get("dishes") or []) if d.get("dish")]
            rt, note = b.get("ratings"), b.get("note") or ""
            shown = re.search(r"shown as (\d+k)", note)
            m["ratings_label"] = (shown.group(1) if shown else f"{rt // 1000}k" if "rounded" in note and rt
                                  else (f"{rt:,}" if rt else None))
            m["beli_type"] = b.get("beli_type")
        md = dict(media.get(r["name"], {}))
        if r["name"] in coffee:
            cf = coffee[r["name"]]
            md.update({"images": cf.get("photos") or [], "website": cf.get("website"), "img_src": "their site"})
        extra = [x["url"] for x in (more.get(r["name"], {}) or {}).get("photos", []) if x.get("url")]
        md["images"] = list(dict.fromkeys((md.get("images") or []) + extra))[:8]
        sp = specials.get(r["name"]) or {}
        vb = vibes.get(r["name"]) if isinstance(vibes, dict) else None
        vb = vb if isinstance(vb, dict) else {}
        venues.append({
            "name": r["name"],
            "kind": m.get("kind") or r.get("kind") or "restaurant",
            "platform": m.get("platform") or r.get("platform"),
            "id": m.get("id", r.get("id")),
            "url": m.get("url") or r.get("url"),
            "phone": m.get("phone") or r.get("phone"),
            "hood": m.get("hood") or r.get("hood"),
            "top25": m.get("beli_rank"),
            "avg": m.get("beli_avg"),
            "ratings": m.get("beli_ratings"),
            "ratings_label": m.get("ratings_label"),
            "dishes": m.get("beli_dishes") or [],
            "closed": (m.get("notes") or "").startswith("CLOSED"),
            "note": m.get("public_note") or "",
            "img": (md.get("images") or [None])[0],
            "imgs": md.get("images") or [],
            "img_src": md.get("img_src"),
            "website": md.get("website"),
            "menu": md.get("menu"),
            "cuisine": md.get("cuisine") or m.get("beli_type"),
            "blurb": md.get("blurb"),
            "known_for": sp.get("known_for") or m.get("known_for"),
            "hours": m.get("hours"),
            "ll": [geo[r["name"]]["lat"], geo[r["name"]]["lng"]] if r["name"] in geo else None,
            "press_rank": m.get("press_rank"),
            "status": r.get("status", {}),
            "slots": r.get("slots", {}),
            "day_notes": r.get("day_notes", {}),
            "skip": r.get("skip_reason"),
            "vibe": {k: vb[k] for k in ("food", "vibe", "tags", "crowd", "energy", "price", "dress", "good_for", "heads_up")
                     if vb.get(k)} or None,
            "checked": r.get("checked_at", ""),
        })
    # Other party sizes: results_p{N}.json from `check.py --party N --out results_pN.json`.
    by_size = {}
    for n in range(2, 9):
        if n == res.get("party", 4):
            continue
        rr = load_json(cdir / "results" / f"p{n}.json", None)
        if rr and rr.get("venues"):
            by_size[str(n)] = {"at": rr.get("generated_at", ""),
                               "v": {r["name"]: [r.get("slots", {}), r.get("status", {}), r.get("day_notes", {})]
                                     for r in rr["venues"]}}
    return {"generated_at": res["generated_at"], "party": res.get("party", 4), "by_size": by_size,
            "window": res.get("window", {}), "dates": res["dates"], "venues": venues,
            "platforms": PLATFORM, "pull_topic": PULL_TOPIC,
            "city": {k: city.get(k) for k in ("slug", "name", "state", "tz", "accent", "accent_dark", "tagline", "bbox")},
            "cities": [{"slug": c["slug"], "name": c["name"], "state": c.get("state"), "status": c.get("status"),
                        "accent": c.get("accent"), "tagline": c.get("tagline")} for c in cities]}


PULL_TOPIC = (HERE / "scripts" / "pull_topic.txt").read_text().strip()  # ntfy.sh topic the Mac listens on

CSS = r"""
:root{--bg:#f6f3ee;--paper:#fffdf9;--ink:#1c1a17;--soft:#6b655c;--faint:#a39c91;--line:#e7e1d6;
--accent:#a2382b;--accent-ink:#fff;--open:#1f6b46;--openbg:#e8f2ea;--chip:#f0ebe2;--shadow:0 1px 2px rgba(40,30,20,.06),0 8px 24px -12px rgba(40,30,20,.18);
--gold:#b0862f;--r:16px;
--k-surface:var(--paper);--k-ink:var(--ink);--k-soft:var(--soft);--k-line:var(--line);--k-shadow:var(--shadow);
--k-shadow-lift:0 2px 4px rgba(40,30,20,.06),0 18px 36px -16px rgba(40,30,20,.32);
--k-glow1:rgba(162,56,43,.15);--k-glow2:rgba(176,134,47,.17);--k-grain:.05}
@media (prefers-color-scheme:dark){:root{--bg:#121110;--paper:#1b1a18;--ink:#f1ece4;--soft:#aaa396;--faint:#6f695f;
--line:#2c2a26;--accent:#e0705d;--accent-ink:#1a0f0c;--open:#7fd3a4;--openbg:#18291f;--chip:#24221f;--shadow:0 1px 2px rgba(0,0,0,.3),0 10px 30px -14px rgba(0,0,0,.6);--gold:#d9b25e;
--k-shadow-lift:0 2px 4px rgba(0,0,0,.35),0 20px 40px -16px rgba(0,0,0,.75);--k-glow1:rgba(224,112,93,.11);--k-glow2:rgba(217,178,94,.09);--k-grain:.07}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 "Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:inherit}
.serif{font-family:"Instrument Serif","Iowan Old Style",Georgia,serif;font-weight:400;letter-spacing:-.01em}
.top{max-width:1240px;margin:0 auto;padding:40px 20px 8px}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--soft)}
h1{font-size:clamp(40px,7vw,68px);line-height:1;margin:8px 0 10px}
.lede{color:var(--soft);max-width:720px;margin:0}
.lede b{color:var(--ink);font-weight:600}
.pull{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;margin:14px 0 2px;font-size:13.5px;color:var(--soft)}
.pull b{color:var(--ink);font-weight:600}
.pdot{width:8px;height:8px;border-radius:50%;background:var(--open);flex:0 0 auto;box-shadow:0 0 0 3px var(--openbg)}
.pull.stale .pdot{background:var(--gold);box-shadow:0 0 0 3px color-mix(in srgb,var(--gold) 20%,transparent)}
.pull.busy .pdot{background:var(--accent);animation:pblink 1s ease-in-out infinite}
@keyframes pblink{50%{opacity:.25}}
.pbtn{display:inline-flex;align-items:center;gap:6px;height:32px;padding:0 13px;border:1px solid var(--line);border-radius:999px;background:var(--paper);color:var(--ink);font:inherit;font-size:13px;font-weight:600;cursor:pointer;box-shadow:var(--shadow)}
.pbtn:hover{border-color:var(--accent);color:var(--accent)}
.pbtn:disabled{opacity:.55;cursor:default;color:var(--soft);border-color:var(--line)}
.pull.busy .pbtn svg{animation:pspin 1.1s linear infinite}
@keyframes pspin{to{transform:rotate(360deg)}}
.pmsg{flex:1 1 100%;font-size:13px}.pmsg:empty{display:none}
.pmsg.err{color:var(--accent)}.pmsg.ok{color:var(--open)}
@media (prefers-reduced-motion:reduce){.pull.busy .pdot,.pull.busy .pbtn svg{animation:none}}
.bar{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:saturate(1.4) blur(12px);
-webkit-backdrop-filter:saturate(1.4) blur(12px);border-bottom:1px solid var(--line)}
.bar-in{max-width:1240px;margin:0 auto;padding:10px 20px;display:flex;flex-direction:column;gap:8px}
.row1,.row2{display:flex;flex-wrap:wrap;gap:8px 10px;align-items:center;min-width:0}
.seg{display:inline-flex;background:var(--chip);border-radius:999px;padding:3px}
.seg button{border:0;background:none;color:var(--soft);font:inherit;font-weight:500;padding:7px 14px;border-radius:999px;cursor:pointer}
.seg button.on{background:var(--paper);color:var(--ink);box-shadow:var(--shadow)}
.days{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;flex:1 1 380px;min-width:0}
.days::-webkit-scrollbar{display:none}
.days button{flex:0 0 auto;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:13px;
padding:6px 9px;border-radius:10px;cursor:pointer;line-height:1.1;text-align:center}
.days button small{display:block;color:var(--faint);font-size:11px}
.days button.on{background:var(--ink);color:var(--paper);border-color:var(--ink)}.days button.on small{color:inherit;opacity:.7}
.tog{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:var(--soft);cursor:pointer;user-select:none}
.tog input{accent-color:var(--accent);width:16px;height:16px}
.search{border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:13px;padding:7px 12px;border-radius:10px;width:160px;height:34px}
.search:focus,.sel:focus{outline:2px solid color-mix(in srgb,var(--accent) 45%,transparent);outline-offset:1px}
.seg.when button,.seg.vseg button{padding:5px 12px;font-size:13px}
.seg.party{align-items:center}.seg.party .plbl{font-size:12px;color:var(--soft);padding:0 6px 0 10px;letter-spacing:.02em}.seg.party button{padding:5px 10px;font-size:13px;font-variant-numeric:tabular-nums}
.pnote{margin:0 0 12px;font-size:13px;color:var(--soft)}
.vseg button{display:inline-flex;align-items:center;gap:6px}.vseg svg{fill:currentColor}
.vseg{margin-left:auto}
.sel{-webkit-appearance:none;appearance:none;border:1px solid var(--line);color:var(--ink);font:inherit;font-size:13px;height:34px;padding:0 30px 0 12px;
border-radius:10px;cursor:pointer;max-width:150px;text-overflow:ellipsis;
background-color:var(--paper);
background-image:linear-gradient(45deg,transparent 50%,var(--soft) 50%),linear-gradient(135deg,var(--soft) 50%,transparent 50%);
background-position:calc(100% - 16px) 15px,calc(100% - 11px) 15px;background-size:5px 5px,5px 5px;background-repeat:no-repeat}
.sortl{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--soft)}
.reset{border:0;background:none;color:var(--accent);font:inherit;font-size:13px;font-weight:600;cursor:pointer;padding:6px 8px;border-radius:8px}
.reset:hover{background:var(--chip)}
.fbtn{display:none;border:1px solid var(--line);background:var(--paper);color:var(--ink);font:inherit;font-size:13px;font-weight:500;height:34px;padding:0 12px;border-radius:10px;cursor:pointer;align-items:center;gap:6px}
.fbtn i{font-style:normal;background:var(--accent);color:var(--accent-ink);font-size:11px;font-weight:700;border-radius:999px;min-width:18px;height:18px;display:inline-grid;place-items:center;padding:0 5px}
.fbtn i:empty{display:none}
main{max-width:1240px;margin:0 auto;padding:8px 20px 40px}
.sec-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:34px 0 14px}
.sec-h h2{font-size:38px;margin:0}.sec-h span{color:var(--soft);font-size:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}
.card{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);display:flex;flex-direction:column;
transition:transform .18s ease,box-shadow .18s ease}
.card:hover{transform:translateY(-2px)}
.card.closed{opacity:.6}
.ph{position:relative;aspect-ratio:16/9;background:linear-gradient(135deg,#3b2a22,#7a4a33 55%,#c08a57);overflow:hidden}
.ph img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .5s ease}
.card:hover .ph img{transform:scale(1.04)}
.ph .mono{position:absolute;inset:0;display:grid;place-items:center;color:rgba(255,255,255,.85);font-size:56px}
.slides{position:absolute;inset:0;display:flex;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scrollbar-width:none;overscroll-behavior-x:contain}
.slides::-webkit-scrollbar{display:none}
.slides img{flex:0 0 100%;min-width:100%;scroll-snap-align:start;scroll-snap-stop:always}
.card:hover .slides img{transform:none}
.dots{position:absolute;top:15px;left:50%;transform:translateX(-50%);z-index:3;display:flex;gap:5px;pointer-events:none}
.dots i{width:6px;height:6px;border-radius:50%;background:rgba(255,255,255,.5);box-shadow:0 0 3px rgba(0,0,0,.4);transition:background .2s,transform .2s}
.dots i.on{background:#fff;transform:scale(1.25)}
.nav{position:absolute;top:50%;z-index:3;width:34px;height:34px;margin-top:-17px;border:0;border-radius:50%;background:rgba(255,255,255,.88);color:#1c1a17;
font-size:22px;line-height:1;display:grid;place-items:center;padding:0 0 3px;cursor:pointer;opacity:0;transition:opacity .2s;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.nav.prev{left:10px}.nav.next{right:10px}
@media (hover:hover){.ph:hover .nav{opacity:1}}
.nav:focus-visible{opacity:1}
.ph::after{pointer-events:none;z-index:1;content:"";position:absolute;inset:0;background:linear-gradient(to top,rgba(0,0,0,.55),rgba(0,0,0,0) 55%)}
.rank{position:absolute;left:12px;top:12px;z-index:2;background:rgba(0,0,0,.55);color:#fff;font-size:12px;font-weight:600;padding:4px 9px;border-radius:999px;backdrop-filter:blur(6px)}
.score{position:absolute;right:12px;bottom:12px;z-index:2;display:flex;align-items:center;gap:8px;color:#fff}
.score .n{width:52px;height:52px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:19px;
background:var(--sc,#2d6a4f);border:2px solid rgba(255,255,255,.9);box-shadow:0 4px 14px rgba(0,0,0,.35)}
.score .l{font-size:11px;line-height:1.2;text-align:right;text-shadow:0 1px 3px rgba(0,0,0,.6)}
.score .l b{display:block;font-size:12px}
.tag25{position:absolute;left:12px;bottom:12px;z-index:2;color:#fff;font-size:11px;letter-spacing:.06em;text-transform:uppercase;text-shadow:0 1px 3px rgba(0,0,0,.6)}
.body{padding:14px 16px 16px;display:flex;flex-direction:column;gap:10px;flex:1}
.name{font-size:27px;line-height:1.05;margin:0}
.sub{color:var(--soft);font-size:13px}
.blurb{color:var(--soft);font-size:13px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0}
.blurb[onclick]{cursor:pointer}.blurb.full{display:block;-webkit-line-clamp:unset;overflow:visible}
.dishes{display:flex;flex-wrap:wrap;gap:6px}
.dish{font-size:12px;background:var(--chip);border-radius:999px;padding:3px 9px;color:var(--ink)}
.dish i{font-style:normal;color:var(--faint);margin-left:4px}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));gap:4px}
.strip button{border:1px solid var(--line);background:none;border-radius:8px;padding:4px 0;font:inherit;font-size:11px;color:var(--faint);cursor:pointer;line-height:1.15}
.strip button b{display:block;font-size:13px;color:var(--soft)}
.strip button.has{background:var(--openbg);border-color:color-mix(in srgb,var(--open) 35%,transparent);color:var(--open)}
.strip button.has b{color:var(--open)}
.strip button.sel{outline:2px solid var(--ink);outline-offset:-1px}
.times{display:flex;flex-wrap:wrap;gap:6px;min-height:34px;align-items:center}
.time{display:inline-block;text-decoration:none;font-size:13px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--open);
border:1.5px solid var(--open);border-radius:9px;padding:6px 10px;transition:background .15s,color .15s}
.time:hover{background:var(--open);color:var(--paper)}
.time.stale{opacity:.55;border-style:dashed}
.empty{color:var(--faint);font-size:13px;font-style:italic}
.acts{display:flex;gap:8px;margin-top:auto;padding-top:4px}
.book{flex:1;display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;background:var(--accent);color:var(--accent-ink);
font-weight:650;font-size:15px;padding:12px 14px;border-radius:12px;transition:filter .15s,transform .15s}
.book:hover{filter:brightness(1.08)}.book:active{transform:scale(.98)}
.book.ghost{background:var(--chip);color:var(--ink)}
.sbtn{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;border:1px solid var(--line);color:var(--ink);font-size:13px;
font-weight:550;padding:0 13px;border-radius:12px;background:var(--paper)}
.sbtn:hover{border-color:var(--ink)}
.hide{display:none!important}
/* tactile pass */
.seg{position:relative}.seg button{position:relative;z-index:1;transition:color var(--dur-2) var(--ease-out),transform var(--dur-2) var(--ease-spring)}
.seg.kit-on button.on{background:none;box-shadow:none}
.seg .kit-ind{background:var(--paper);border-radius:999px;box-shadow:var(--shadow)}
.days{position:relative}.days button{position:relative;z-index:1;transition:color var(--dur-2) var(--ease-out),border-color var(--dur-2),transform var(--dur-2) var(--ease-spring)}
.days.kit-on button{background:transparent}.days.kit-on button.on{border-color:transparent}
.days .kit-ind{background:var(--ink);border-radius:10px;box-shadow:0 4px 12px -4px rgba(0,0,0,.35)}
.card,.row{transition:transform var(--dur-3) var(--ease-out),box-shadow var(--dur-3) var(--ease-out)}
.card:hover{transform:none}
@media (hover:hover){.card:hover,.row:hover{transform:translateY(-3px);box-shadow:var(--k-shadow-lift)}}
.time:hover{transform:translateY(-1px)}
.book:active{transform:scale(.97)}
.slides img,.r-th img{cursor:zoom-in}
.r-th{position:relative}
.n.kit-num,.pill.kit-num{font-variant-numeric:tabular-nums}
/* vibe profile */
.food{color:var(--ink);font-size:13.5px;font-weight:500;margin-top:3px}
.vmeta{display:flex;flex-wrap:wrap;gap:4px 10px;font-size:12px;color:var(--soft)}
.vmeta b{font-weight:650;color:var(--ink);letter-spacing:.03em}
.vmeta span+span::before{content:"·";margin-right:10px;color:var(--faint)}
.vtags{display:flex;flex-wrap:wrap;gap:5px}
.vtag{font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--gold);border:1px solid color-mix(in srgb,var(--gold) 40%,transparent);
border-radius:999px;padding:2px 8px}
.heads{margin:0;font-size:12px;color:var(--soft);font-style:italic;padding-left:9px;border-left:2px solid color-mix(in srgb,var(--accent) 45%,transparent)}
.r-vibe{color:var(--soft);font-size:12px;white-space:nowrap}
.list{display:flex;flex-direction:column;gap:8px}
.row{display:grid;grid-template-columns:26px 56px minmax(0,1fr) 40px auto 196px;grid-template-areas:"rk th mn sc dy ac";align-items:center;gap:12px;
background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:8px 12px;box-shadow:var(--shadow)}
.row.closed{opacity:.6}
.r-rank{grid-area:rk;color:var(--faint);font-size:13px;font-weight:600;text-align:center;font-variant-numeric:tabular-nums}
.r-th{grid-area:th;width:56px;height:56px;border-radius:10px;overflow:hidden;background:linear-gradient(135deg,#3b2a22,#7a4a33 55%,#c08a57);display:grid;place-items:center}
.r-th img{width:100%;height:100%;object-fit:cover;display:block}
.r-th .mono{color:rgba(255,255,255,.85);font-size:26px}
.r-main{grid-area:mn;min-width:0}
.r-name{font-size:21px;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r-main .sub{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.r-score{grid-area:sc}
.pill{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;font-weight:700;font-size:14px;color:#fff;background:var(--sc,#2d6a4f)}
.r-days{grid-area:dy;display:grid;grid-template-columns:repeat(9,30px);gap:3px}
.r-days .empty{grid-column:1/-1;text-align:center}
.mini{display:flex;flex-direction:column;align-items:center;justify-content:center;height:36px;border-radius:8px;border:1px solid var(--line);text-decoration:none;
font-size:13px;font-weight:600;color:var(--faint);font-variant-numeric:tabular-nums;line-height:1.05}
.mini small{font-size:9.5px;font-weight:500;letter-spacing:.02em;opacity:.8}
.mini.has{background:var(--openbg);border-color:color-mix(in srgb,var(--open) 35%,transparent);color:var(--open)}
a.mini.has:hover{background:var(--open);color:var(--paper)}
.r-act{grid-area:ac;display:flex}
.book.sm{font-size:13px;padding:9px 12px;border-radius:10px;white-space:nowrap}
.r-act .book.sm{flex:1}
@media (max-width:1000px){.row{grid-template-columns:26px 56px minmax(0,1fr) 40px;grid-template-areas:"rk th mn sc" "dy dy dy dy" "ac ac ac ac";row-gap:8px}
.r-days{grid-template-columns:repeat(9,minmax(0,1fr))}}
.none{color:var(--soft);padding:30px 0;text-align:center}
foot,footer{display:block;max-width:1240px;margin:0 auto;padding:10px 20px 50px;color:var(--faint);font-size:12px}
@media (max-width:640px){.top{padding:26px 16px 8px}.bar-in,main,footer{padding-left:16px;padding-right:16px}.grid{grid-template-columns:1fr}
.bar-in{padding-top:8px;padding-bottom:8px}.days{flex-basis:100%;order:-1}.fbtn{display:inline-flex;padding:0 10px}.lbl{display:none}
.row1{gap:8px 6px}.row1 .seg:first-of-type{flex:1 1 0;min-width:0}.row1 .seg:first-of-type button{flex:1;padding:6px 6px;font-size:13px}
.vseg{margin-left:0}.vseg button{padding:6px 9px}
.row2{display:none;padding-bottom:4px}.bar.open{position:static}.bar.open .row2{display:flex}.search{width:100%;order:-1}
.seg.party{flex:1 1 100%}.seg.party button{flex:1;padding:6px 0}.seg.when{flex:1 1 100%}.seg.when button{flex:1;padding:6px 4px}.sel{flex:1 1 40%;max-width:none}.tog{flex:1 1 40%}
.sortl{flex:1 1 55%}.sortl .sel{flex:1}.sec-h h2{font-size:32px}.sec-h span{flex-basis:100%}
.acts{flex-wrap:wrap}.acts .book{flex-basis:100%}.acts .sbtn{flex:1;padding:9px 0}
.row{padding:8px 10px;gap:10px}.r-th{width:48px;height:48px}.row{grid-template-columns:22px 48px minmax(0,1fr) 38px}.r-name{font-size:19px}}
"""


# Shared tactile layer. trip/index.html carries a verbatim copy between the kit:start / kit:end markers.
NEW_CSS = r"""
/* ---- multi-city / v2 ---- */
.brandrow{display:flex;align-items:center;gap:10px;margin:0 0 18px}
.brand{font:700 13px/1 Inter,system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;text-decoration:none;color:var(--ink);
padding:8px 12px 8px 0;border-right:1px solid var(--line)}
.citypick{display:inline-flex;align-items:center;gap:8px;height:34px;padding:0 14px;border:1px solid var(--line);border-radius:999px;
background:var(--paper);color:var(--ink);font:600 14px Inter,system-ui,sans-serif;cursor:pointer;box-shadow:var(--shadow)}
.citypick:hover{border-color:var(--city)}
.cdot{width:9px;height:9px;border-radius:50%;background:var(--city);box-shadow:0 0 0 3px color-mix(in srgb,var(--city) 22%,transparent)}
h1 em{font-style:italic;color:var(--city)}
.top{position:relative}
.top::after{content:"";position:absolute;left:20px;right:20px;bottom:-2px;height:3px;border-radius:3px;
background:linear-gradient(90deg,var(--city),color-mix(in srgb,var(--city) 30%,var(--gold)) 60%,transparent);opacity:.55}
/* city sheet */
.sheet{position:fixed;inset:0;z-index:90;display:flex;align-items:flex-end;justify-content:center;background:rgba(14,11,9,.45);
-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px)}
.sheet.hide{display:none}
.sheet-in{width:min(560px,100%);max-height:80vh;overflow:auto;background:var(--paper);border-radius:22px 22px 0 0;padding:18px 16px calc(18px + env(safe-area-inset-bottom));
box-shadow:0 -20px 60px -20px rgba(0,0,0,.5);animation:sheetup .26s cubic-bezier(.2,.8,.2,1)}
@media (min-width:700px){.sheet{align-items:center}.sheet-in{border-radius:22px}}
@keyframes sheetup{from{transform:translateY(40px);opacity:0}}
.sheet-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}.sheet-h b{font-size:26px;font-weight:400}
.sheet-x{border:0;background:var(--chip);color:var(--ink);width:34px;height:34px;border-radius:50%;font-size:20px;cursor:pointer}
.clist{display:grid;gap:10px}
.ccard{display:flex;align-items:center;gap:14px;padding:14px;border:1px solid var(--line);border-radius:16px;text-decoration:none;color:var(--ink);
background:linear-gradient(135deg,color-mix(in srgb,var(--cc) 14%,var(--paper)),var(--paper) 70%)}
.ccard:hover{border-color:var(--cc)}
.ccard .cm{width:44px;height:44px;border-radius:13px;background:var(--cc);color:#fff;display:grid;place-items:center;font:400 24px "Instrument Serif",Georgia,serif;flex:0 0 auto}
.ccard b{display:block;font:400 22px/1.1 "Instrument Serif",Georgia,serif}.ccard small{color:var(--soft)}
.ccard.cur{outline:2px solid var(--cc);outline-offset:-2px}.ccard .here{margin-left:auto;font-size:12px;font-weight:600;color:var(--cc)}
.sheet-note{color:var(--soft);font-size:13px;margin:12px 2px 0}
/* tonight */
.tonight{margin:22px 0 0}.tonight:empty,.hits:empty{display:none}
.tn-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.tn-big{font:400 44px/1 "Instrument Serif",Georgia,serif;color:var(--city);font-variant-numeric:tabular-nums}
.tn-l{font-weight:600}.tn-l small{display:block;font-weight:400;color:var(--soft)}
.tn-row{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(290px,1fr);gap:12px;overflow-x:auto;scroll-snap-type:x mandatory;padding:2px 2px 8px;scrollbar-width:none}
.tn-row::-webkit-scrollbar{display:none}
.tn{scroll-snap-align:start;display:flex;gap:12px;align-items:center;padding:12px;border:1px solid var(--line);border-radius:16px;background:var(--paper);box-shadow:var(--shadow);cursor:pointer;text-align:left;font:inherit;color:inherit}
.tn:hover{border-color:var(--city)}
.tn .th{width:64px;height:64px;border-radius:12px;overflow:hidden;flex:0 0 auto;background:var(--chip);display:grid;place-items:center;font:400 28px "Instrument Serif",Georgia,serif;color:var(--soft)}
.tn .th img{width:100%;height:100%;object-fit:cover}
.tn>div:nth-child(2){min-width:0;flex:1}.tn .tt{overflow:hidden}
.tn b{display:block;font:400 20px/1.1 "Instrument Serif",Georgia,serif}
.tn .tt{display:flex;gap:5px;flex-wrap:nowrap;margin-top:6px}
.tn .tt a{font-size:12px;font-weight:600;color:var(--open);border:1.5px solid var(--open);border-radius:8px;padding:3px 7px;text-decoration:none}
.tn .tt a:hover{background:var(--open);color:var(--paper)}
.tn .sc{margin-left:auto;align-self:flex-start;font-weight:700;font-size:13px;color:#fff;background:var(--sc);border-radius:999px;padding:3px 8px}
/* greatest hits */
.hits{margin:18px 0 0}
.hits h3{margin:0 0 8px;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--soft)}
.hrow{display:flex;gap:8px;overflow-x:auto;scrollbar-width:none;padding:2px 2px 6px}.hrow::-webkit-scrollbar{display:none}
.hit{flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-start;gap:2px;padding:9px 13px;border-radius:14px;border:1px solid var(--line);
background:var(--paper);cursor:pointer;font:inherit;color:inherit;text-align:left;max-width:220px}
.hit:hover{border-color:var(--gold)}
.hit b{font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:190px}
.hit small{color:var(--soft);font-size:12px}.hit small i{font-style:normal;color:var(--gold);font-weight:700}
/* order this */
.order{display:grid;gap:5px}
.order .oh{font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--soft)}
.od{position:relative;display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:10px;background:var(--chip);overflow:hidden;font-size:13.5px}
.od::before{content:"";position:absolute;inset:0 auto 0 0;width:var(--w);background:color-mix(in srgb,var(--gold) 20%,transparent)}
.od span{position:relative;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:500}
.od i{position:relative;font-style:normal;font-variant-numeric:tabular-nums;color:var(--soft);font-size:12px}
.od.first span::after{content:"Most ordered";margin-left:8px;font-size:10px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#fff;
background:var(--gold);border-radius:999px;padding:2px 7px;vertical-align:1px}
.known{margin:0;font-size:13.5px;color:var(--ink)}.known b{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--city);margin-right:6px}

.hrs{margin:0;font-size:13px;color:var(--soft);display:flex;align-items:center;gap:7px}
.hrs i{width:8px;height:8px;border-radius:50%;background:var(--faint)}.hrs i.on{background:var(--open);box-shadow:0 0 0 3px var(--openbg)}
/* kinds counters */
.seg.kinds button i{font-style:normal;margin-left:6px;font-size:11px;opacity:.6;font-variant-numeric:tabular-nums}
/* surprise */
.surprise{position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:40;border:0;border-radius:999px;padding:12px 18px;
background:var(--city);color:#fff;font:600 14px Inter,system-ui,sans-serif;cursor:pointer;box-shadow:0 10px 30px -10px color-mix(in srgb,var(--city) 70%,#000)}
.surprise:hover{filter:brightness(1.08)}.surprise span{display:inline-block;margin-right:4px}
.surprise.spin span{animation:spin .6s ease}
@keyframes spin{to{transform:rotate(360deg)}}
.card.picked{animation:picked 1.6s ease;outline:3px solid var(--city);outline-offset:3px}
@keyframes picked{0%{transform:scale(.96)}20%{transform:scale(1.02)}40%{transform:none}}
.confetti{position:fixed;width:8px;height:12px;border-radius:2px;z-index:95;pointer-events:none;animation:conf 1s cubic-bezier(.2,.7,.4,1) forwards}
@keyframes conf{to{transform:translate(var(--x),var(--y)) rotate(var(--r));opacity:0}}
.card.coffee .acts .book.ghost{background:var(--chip)}
@media (prefers-reduced-motion:reduce){.card.picked,.confetti,.surprise.spin span,.sheet-in{animation:none}}
/* ---- v3 site polish (cards keep their v2 look) ---- */
.top{padding-top:18px}
.topnav{position:relative;display:flex;align-items:center;gap:10px;padding:4px 0 30px}
.brandrow{display:none}
.pull{margin:0 0 0 auto;gap:8px;font-size:12.5px}
.pbtn{height:30px;padding:0 11px;font-size:12.5px;box-shadow:none}
.pmsg{position:absolute;right:0;top:44px;z-index:30;max-width:330px;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:10px 12px;
box-shadow:var(--k-shadow-lift);font-size:13px;line-height:1.4;flex:none;animation:sheetup .25s ease}
.pmsg:empty{display:none}
.hero{display:grid;gap:12px}
.hero h1{margin:0;font-size:clamp(46px,8vw,84px);letter-spacing:-.025em}
.stats{display:flex;flex-wrap:wrap;gap:8px}
.stats span{display:inline-flex;align-items:baseline;gap:5px;padding:6px 12px;border-radius:999px;background:color-mix(in srgb,var(--paper) 75%,transparent);
border:1px solid var(--line);font-size:13px;color:var(--soft)}
.stats b{color:var(--ink);font-weight:650;font-variant-numeric:tabular-nums}
.stats .dim{background:none;border-color:transparent;padding-left:4px}
.tonight{margin-top:30px}
.tn-big{font-size:38px}.tn-l{font-size:14px;color:var(--soft);font-weight:500}
.hits{margin-top:22px}
.step{display:inline-flex;align-items:center;gap:2px;background:var(--chip);border-radius:999px;padding:3px}
.step button{width:30px;height:30px;border:0;border-radius:50%;background:var(--paper);color:var(--ink);font:500 17px/1 Inter,system-ui,sans-serif;cursor:pointer;box-shadow:var(--shadow);
transition:transform .15s ease}
.step button:active{transform:scale(.9)}.step button:disabled{opacity:.35;cursor:default}
.step span{min-width:76px;text-align:center;font-size:13px;color:var(--soft);font-variant-numeric:tabular-nums}
.step b{color:var(--ink);font-size:15px;margin-right:4px;display:inline-block}
.step b.bump{animation:bump .28s ease}
@keyframes bump{40%{transform:translateY(-3px) scale(1.15)}}
.fbtn{display:inline-flex}
.row2{display:none;padding:4px 0 6px}.bar.open .row2{display:flex}
.bar{border-bottom-color:color-mix(in srgb,var(--line) 70%,transparent)}
.lede{font-size:15px}
.sec-h{margin-top:40px}
.sec-h span{font-variant-numeric:tabular-nums;font-size:13px;color:var(--faint)}
footer{font-size:12px!important;text-align:center}
@media (max-width:640px){.row1 .seg.kinds{flex:1 1 100%}.step{margin-right:auto}.topnav{padding-bottom:22px;gap:8px}.pull .ptxt{display:none}.pmsg{left:0;right:0;max-width:none}
.stats span{padding:5px 10px;font-size:12.5px}.step{flex:0 0 auto}}
@media (prefers-reduced-motion:reduce){.step b.bump,.pmsg{animation:none}}

/* ---- map view ---- */
.map-wrap{position:relative;margin-top:28px;border-radius:22px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--shadow);background:var(--chip)}
#map{height:min(72vh,760px);min-height:440px;width:100%}
.map-leg{position:absolute;left:12px;bottom:12px;z-index:500;display:flex;gap:12px;align-items:center;padding:7px 12px;border-radius:999px;
background:color-mix(in srgb,var(--paper) 88%,transparent);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);font-size:12px;color:var(--soft);box-shadow:var(--shadow)}
.map-leg span{display:inline-flex;align-items:center;gap:6px}.map-leg i{width:10px;height:10px;border-radius:50%}
.lg-open{background:var(--open);box-shadow:0 0 0 3px var(--openbg)}.lg-none{background:var(--faint)}
.pinm{background:none;border:0}
.pin{position:relative;display:grid;place-items:center;width:34px;height:34px;border-radius:50% 50% 50% 4px;transform:rotate(-45deg);
background:var(--sc);color:#fff;box-shadow:0 6px 14px -4px rgba(0,0,0,.55);border:2px solid #fff;transition:transform .15s ease}
.pin b{transform:rotate(45deg);font:700 11.5px Inter,system-ui,sans-serif;font-variant-numeric:tabular-nums}
.pin.off{filter:saturate(.25) brightness(1.05);opacity:.75}
.pin.open::after{content:"";position:absolute;inset:-6px;border-radius:inherit;border:2px solid var(--open);opacity:.8}
.pinm:hover .pin,.pin.hl{transform:rotate(-45deg) scale(1.18);z-index:1000}
.leaflet-popup-content-wrapper{border-radius:18px!important;padding:0!important;overflow:hidden;background:var(--paper)!important;color:var(--ink)!important;box-shadow:var(--k-shadow-lift)!important}
.leaflet-popup-content{margin:0!important;width:260px!important;font:13px/1.4 Inter,system-ui,sans-serif}
.leaflet-popup-tip{background:var(--paper)!important}
.leaflet-container a.leaflet-popup-close-button{color:#fff;top:8px;right:8px;width:24px;height:24px;border-radius:50%;background:rgba(0,0,0,.35);font-size:16px;line-height:22px}
.mp-ph{height:120px;background:var(--chip) center/cover no-repeat}
.mp-b{padding:12px 14px 14px;display:grid;gap:8px}
.mp-h{display:flex;align-items:flex-start;gap:8px}.mp-h b{flex:1;font:400 22px/1.05 "Instrument Serif",Georgia,serif}
.mp-sc{color:#fff;background:var(--sc);border-radius:999px;padding:2px 8px;font-weight:700;font-size:12px}
.mp-m{color:var(--soft);font-size:12px}
.mp-t{display:flex;gap:5px;flex-wrap:wrap}.mp-t a{font-size:12px;font-weight:600;color:var(--open)!important;border:1.5px solid var(--open);border-radius:999px;padding:3px 8px;text-decoration:none}
.mp-a{display:flex;gap:6px}.mp-a a,.mp-a button{flex:1;text-align:center;font:600 12.5px Inter,system-ui,sans-serif;padding:8px 10px;border-radius:12px;cursor:pointer;text-decoration:none}
.mp-a .go{background:var(--accent);color:var(--accent-ink)!important;border:0}.mp-a .see{background:var(--chip);color:var(--ink);border:0}
.leaflet-control-zoom a{background:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important}
.leaflet-control-attribution{font-size:10px!important;background:color-mix(in srgb,var(--paper) 80%,transparent)!important;color:var(--faint)!important}
.leaflet-control-attribution a{color:var(--soft)!important}
@media (max-width:640px){#map{height:66vh;min-height:380px}.map-wrap{border-radius:18px;margin-top:20px}.map-leg{right:12px;justify-content:center;flex-wrap:wrap;row-gap:2px}}

"""

KIT_CSS = r"""
/* kit:start — shared "premium" layer for the Dallas pages (render.py is the source; trip/index.html carries a copy) */
:root{--ease-out:cubic-bezier(.2,.8,.2,1);--ease-in-out:cubic-bezier(.65,0,.35,1);--ease-spring:cubic-bezier(.34,1.4,.64,1);
--dur-1:150ms;--dur-2:220ms;--dur-3:280ms}
body{isolation:isolate}
/* ambient header glow: two soft blobs drifting on the compositor (transform only) */
.kit-glow{position:absolute;top:0;left:0;right:0;height:560px;z-index:-1;overflow:hidden;pointer-events:none;
-webkit-mask-image:linear-gradient(#000 35%,transparent);mask-image:linear-gradient(#000 35%,transparent)}
.kit-glow::before,.kit-glow::after{content:"";position:absolute;width:780px;height:780px;border-radius:50%;will-change:transform}
.kit-glow::before{top:-430px;left:-240px;background:radial-gradient(closest-side,var(--k-glow1),transparent);animation:kitDriftA 26s var(--ease-in-out) infinite alternate}
.kit-glow::after{top:-470px;right:-300px;background:radial-gradient(closest-side,var(--k-glow2),transparent);animation:kitDriftB 34s var(--ease-in-out) infinite alternate}
@keyframes kitDriftA{to{transform:translate3d(220px,70px,0) scale(1.12)}}
@keyframes kitDriftB{to{transform:translate3d(-260px,90px,0) scale(.92)}}
/* static film grain */
.kit-grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:var(--k-grain,.05);mix-blend-mode:overlay;background-size:140px 140px;
background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
/* page switcher: Plan | Tables | Map (identical on every page) */
.switch{position:relative;display:inline-flex;gap:2px;padding:3px;margin:0 0 18px;border:1px solid var(--k-line);border-radius:999px;
background:var(--k-surface);box-shadow:var(--k-shadow);font:600 13px/1.2 Inter,system-ui,-apple-system,sans-serif}
.switch a{position:relative;z-index:1;padding:6px 16px;border-radius:999px;text-decoration:none;color:var(--k-soft);
transition:color var(--dur-2) var(--ease-out),transform var(--dur-2) var(--ease-spring)}
.switch a[aria-current="page"]{color:var(--k-surface)}
.switch:not(.kit-on) a[aria-current="page"]{background:var(--k-ink)}
.switch a:not([aria-current]):hover{color:var(--k-ink)}
.switch .kit-ind{background:var(--k-ink);border-radius:999px;box-shadow:0 2px 8px -2px rgba(0,0,0,.25)}
.switch:has(.kit-go) a[aria-current="page"]{color:var(--k-soft)}
.switch a.kit-go{color:var(--k-surface)}
/* sliding selection pill (generic) */
.kit-ind{position:absolute;left:0;top:0;z-index:0;pointer-events:none;opacity:0;
transition:transform var(--dur-3) var(--ease-spring),width var(--dur-3) var(--ease-spring),height var(--dur-3) var(--ease-spring),opacity var(--dur-1) linear}
/* press + hover */
.kit-tap{transition:transform var(--dur-2) var(--ease-spring),box-shadow var(--dur-2) var(--ease-out),background-color var(--dur-1),color var(--dur-1),border-color var(--dur-1),filter var(--dur-1)}
.kit-tap:active{transform:scale(.97);transition-duration:90ms}
@media (hover:hover){.kit-lift:hover{transform:translateY(-2px);box-shadow:var(--k-shadow-lift)}.kit-lift:active{transform:translateY(-1px) scale(.97)}}
/* staggered fade-up */
.kit-rv{animation:kitUp 340ms var(--ease-out) both;animation-delay:calc(var(--kit-i,0) * 28ms)}
@keyframes kitUp{from{opacity:0;transform:translate3d(0,10px,0)}}
/* photo skeleton shimmer + fade-in */
.kit-load::before{content:"";position:absolute;inset:0;z-index:0;pointer-events:none;
background:linear-gradient(100deg,transparent 30%,rgba(255,255,255,.16) 50%,transparent 70%);animation:kitShimmer 1.3s linear infinite}
@keyframes kitShimmer{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.kit-img{opacity:0;transition:opacity 420ms var(--ease-out)}
.kit-img.kit-in{opacity:1}
/* lightbox */
.kit-lb{position:fixed;inset:0;z-index:100;display:flex;flex-direction:column;background:rgba(14,11,9,.95);
opacity:0;visibility:hidden;transition:opacity var(--dur-3) var(--ease-out),visibility 0s linear var(--dur-3)}
.kit-lb.open{opacity:1;visibility:visible;transition:opacity var(--dur-3) var(--ease-out)}
.kit-lb-stage{position:relative;flex:1;min-height:0;transition:transform var(--dur-3) var(--ease-spring)}
.kit-lb-track{position:absolute;inset:0;display:flex;overflow-x:auto;overflow-y:hidden;scroll-snap-type:x mandatory;scrollbar-width:none;
overscroll-behavior:contain;touch-action:pan-x}
.kit-lb-track::-webkit-scrollbar{display:none}
.kit-lb-slide{flex:0 0 100%;min-width:100%;height:100%;scroll-snap-align:center;scroll-snap-stop:always;display:flex;align-items:center;justify-content:center;
padding:calc(60px + env(safe-area-inset-top)) 16px 8px}
.kit-lb-slide img{max-width:100%;max-height:100%;object-fit:contain;border-radius:10px;box-shadow:0 24px 70px -24px rgba(0,0,0,.85);
transform:scale(.97);transition:opacity 420ms var(--ease-out),transform var(--dur-3) var(--ease-out)}
.kit-lb-slide img.kit-in{transform:none}
.kit-lb-film{display:flex;gap:6px;justify-content:center;overflow-x:auto;scrollbar-width:none;padding:0 16px 10px}
.kit-lb-film::-webkit-scrollbar{display:none}.kit-lb-film:empty{display:none}
.kit-lb .kit-lb-film button{position:static;flex:0 0 auto;width:52px;height:52px;border-radius:9px;padding:0;overflow:hidden;opacity:.5;
background:rgba(255,255,255,.08);border:2px solid transparent;transition:opacity .15s,border-color .15s}
.kit-lb .kit-lb-film button.on{opacity:1;border-color:#f3eee6}.kit-lb .kit-lb-film button:hover{opacity:.85}
.kit-lb-film img{width:100%;height:100%;object-fit:cover;display:block}
.kit-lb-cap{color:#f3eee6;text-align:center;padding:12px 16px calc(18px + env(safe-area-inset-bottom));font:14px/1.45 Inter,system-ui,sans-serif}
.kit-lb-cap b{display:block;font:400 26px/1.1 "Instrument Serif",Fraunces,Georgia,serif;letter-spacing:-.01em}
.kit-lb-cap .n{font-variant-numeric:tabular-nums;color:rgba(243,238,230,.75);font-size:13px}
.kit-lb-cap small{display:block;margin-top:4px;color:rgba(243,238,230,.55);font-size:12px}
.kit-lb-cap a{color:inherit}
.kit-lb button{position:absolute;z-index:2;border:0;border-radius:50%;background:rgba(255,255,255,.13);color:#fff;cursor:pointer;
width:44px;height:44px;display:grid;place-items:center;font:400 26px/1 system-ui,sans-serif;padding:0 0 3px;
-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.kit-lb button:hover{background:rgba(255,255,255,.22)}
.kit-lb-x{top:calc(12px + env(safe-area-inset-top));right:12px}
.kit-lb-p,.kit-lb-n{top:50%;margin-top:-22px}.kit-lb-p{left:14px}.kit-lb-n{right:14px}
@media (hover:none){.kit-lb-p,.kit-lb-n{display:none}}
.kit-lb[data-one] .kit-lb-p,.kit-lb[data-one] .kit-lb-n{display:none}
html.kit-lock{overflow:hidden}
@media (prefers-reduced-motion:reduce){
.kit-glow::before,.kit-glow::after,.kit-load::before,.kit-rv{animation:none}
.kit-ind,.kit-lb-stage,.kit-lb-slide img{transition:none}
.kit-tap:active,.kit-lift:hover,.kit-lift:active{transform:none}}
/* kit:end */
"""

KIT_JS = r"""
// kit:start — shared tactile layer (render.py is the source; trip/index.html carries a copy)
(() => {
  const RM = matchMedia('(prefers-reduced-motion: reduce)');
  const still = () => RM.matches;
  const buzz = () => { try { navigator.vibrate && navigator.vibrate(8); } catch (e) {} };

  // Sliding selection pill. The indicator survives innerHTML re-renders: it is re-inserted at its old spot, then animated.
  function place(ind, p, anim) {
    if (!anim) ind.style.transition = 'none';
    ind.style.width = p.w + 'px'; ind.style.height = p.h + 'px';
    ind.style.transform = `translate3d(${p.x}px,${p.y}px,0)`; ind.style.opacity = 1;
    if (!anim) { void ind.offsetWidth; ind.style.transition = ''; }
  }
  function slide(box, target, anim = true) {
    if (!box) return;
    let ind = box._kInd;
    if (!ind) {
      ind = box._kInd = document.createElement('span');
      ind.className = 'kit-ind'; ind.setAttribute('aria-hidden', 'true');
      box.classList.add('kit-on');
      if ('ResizeObserver' in window) new ResizeObserver(() => slide(box, null, false)).observe(box);
    }
    if (ind.parentNode !== box) { box.prepend(ind); if (box._kPos) place(ind, box._kPos, false); }
    const a = target || box.querySelector('.kit-go') || box.querySelector('.on,[aria-current="page"],[aria-selected="true"]');
    if (!a) { ind.style.opacity = 0; box._kPos = null; return; }
    if (!a.offsetWidth) return;                       // hidden (collapsed filters); the ResizeObserver catches it later
    const p = {x: a.offsetLeft, y: a.offsetTop, w: a.offsetWidth, h: a.offsetHeight};
    place(ind, p, anim && !!box._kPos && !still());
    box._kPos = p;
    if (box.scrollWidth > box.clientWidth + 2) {     // keep the chosen chip in view in scrolling rows
      const l = box.scrollLeft, r = l + box.clientWidth;
      if (p.x < l || p.x + p.w > r) box.scrollTo({left: p.x - (box.clientWidth - p.w) / 2, behavior: still() ? 'auto' : 'smooth'});
    }
  }

  // Staggered fade-up.
  function reveal(els, cap = 12) {
    if (still()) return;
    let i = 0;
    for (const el of els) {
      el.style.setProperty('--kit-i', Math.min(i++, cap));
      el.classList.add('kit-rv');
      el.addEventListener('animationend', function done(e) { if (e.target === el) { el.classList.remove('kit-rv'); el.removeEventListener('animationend', done); } });
    }
  }

  // Count-up (text only, rAF, no layout reads).
  function count(el, to, {dec = 0, dur = 900, from = 0} = {}) {
    const fmt = x => dec ? x.toFixed(dec) : Math.round(x).toLocaleString('en-US');
    if (still()) { el.textContent = fmt(to); return; }
    const t0 = performance.now();
    const f = t => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(from + (to - from) * e); if (k < 1) requestAnimationFrame(f); };
    el.textContent = fmt(from); requestAnimationFrame(f);
  }
  const seen = new Set();
  const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => es.forEach(e => {
    if (!e.isIntersecting) return; io.unobserve(e.target);
    const el = e.target; count(el, +el.dataset.kitTo, {dec: +el.dataset.kitDec || 0, dur: 750});
  }), {threshold: .6}) : null;
  // Count once per key, the first time it scrolls into view (re-renders don't replay it).
  function countOnce(el, to, key, dec = 1) {
    if (!io || seen.has(key) || still()) return;
    seen.add(key); el.dataset.kitTo = to; el.dataset.kitDec = dec; io.observe(el);
  }

  // Photo fade-in once loaded; drops the shimmer from its frame.
  window.kitImg = img => { img.classList.add('kit-in'); const f = img.closest('.kit-load'); if (f) f.classList.remove('kit-load'); };

  // Lightbox: swipe / arrows between photos; Esc, Back, or swipe down closes.
  let lb, track, stage, cap, last = null, items = [], meta = {};
  function build() {
    lb = document.createElement('div'); lb.className = 'kit-lb'; lb.setAttribute('role', 'dialog'); lb.setAttribute('aria-modal', 'true'); lb.setAttribute('aria-label', 'Photos');
    lb.innerHTML = '<div class="kit-lb-stage"><div class="kit-lb-track"></div></div><div class="kit-lb-film"></div><div class="kit-lb-cap" aria-live="polite"></div>'
      + '<button class="kit-lb-x" aria-label="Close">×</button><button class="kit-lb-p" aria-label="Previous photo">‹</button><button class="kit-lb-n" aria-label="Next photo">›</button>';
    document.body.appendChild(lb);
    stage = lb.querySelector('.kit-lb-stage'); track = lb.querySelector('.kit-lb-track'); cap = lb.querySelector('.kit-lb-cap');
    lb.querySelector('.kit-lb-x').onclick = () => close();
    lb.querySelector('.kit-lb-p').onclick = () => go(-1);
    lb.querySelector('.kit-lb-n').onclick = () => go(1);
    track.addEventListener('scroll', () => { const i = idx(); if (i !== meta.i) { meta.i = i; caption(); } }, {passive: true});
    track.addEventListener('click', e => { if (e.target === track || e.target.classList.contains('kit-lb-slide')) close(); });
    let sy = null, sx = 0, dy = 0, vert = false;
    stage.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse') { sy = e.clientY; sx = e.clientX; dy = 0; vert = false; } });
    stage.addEventListener('pointermove', e => {
      if (sy == null) return;
      const y = e.clientY - sy, x = e.clientX - sx;
      if (!vert) { if (Math.abs(y) < 8 && Math.abs(x) < 8) return; if (Math.abs(x) > Math.abs(y)) { sy = null; return; } vert = true; }
      dy = Math.max(0, y); stage.style.transition = 'none';
      stage.style.transform = `translate3d(0,${dy}px,0) scale(${1 - Math.min(dy, 400) / 2400})`;
      lb.style.backgroundColor = `rgba(14,11,9,${(.95 * Math.max(.25, 1 - dy / 500)).toFixed(3)})`;
    });
    const end = () => {
      if (sy == null && !vert) return; sy = null;
      stage.style.transition = ''; if (vert && dy > 90) close(); else { stage.style.transform = ''; lb.style.backgroundColor = ''; }
      vert = false; dy = 0;
    };
    stage.addEventListener('pointerup', end); stage.addEventListener('pointercancel', end);
    document.addEventListener('keydown', e => {
      if (!lb.classList.contains('open')) return;
      if (e.key === 'Escape') { e.preventDefault(); close(); } else if (e.key === 'ArrowRight') go(1); else if (e.key === 'ArrowLeft') go(-1);
    });
    addEventListener('popstate', () => { if (lb.classList.contains('open')) close(true); });
  }
  const idx = () => Math.round(track.scrollLeft / (track.clientWidth || 1));
  const go = d => { const n = items.length; if (n < 2) return; const i = (idx() + d + n) % n; track.scrollTo({left: i * track.clientWidth, behavior: still() ? 'auto' : 'smooth'}); };
  const escH = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  function caption() {
    const n = items.length, cr = meta.credit ? `<small>Photo: ${meta.href ? `<a href="${escH(meta.href)}" target="_blank" rel="noopener">${escH(meta.credit)}</a>` : escH(meta.credit)}</small>` : '';
    cap.innerHTML = `<b>${escH(meta.title)}</b>${n > 1 ? `<span class="n">${(meta.i || 0) + 1} / ${n}</span>` : ''}${cr}`;
    lb.querySelectorAll('.kit-lb-film button').forEach((b, j) => { b.classList.toggle('on', j === (meta.i || 0)); if (j === (meta.i || 0)) b.scrollIntoView({block: 'nearest', inline: 'center'}); });
  }
  function open(srcs, i = 0, m = {}) {
    if (!srcs.length) return;
    if (!lb) build();
    items = srcs; meta = {...m, i}; last = document.activeElement;
    lb.toggleAttribute('data-one', srcs.length < 2);
    track.innerHTML = srcs.map((s, j) => `<div class="kit-lb-slide"><img class="kit-img" src="${escH(s)}" alt="${escH(m.title || '')} photo ${j + 1}" referrerpolicy="no-referrer" onload="kitImg(this)" ${Math.abs(j - i) > 1 ? 'loading="lazy"' : ''}></div>`).join('');
    const film = lb.querySelector('.kit-lb-film');
    film.innerHTML = srcs.length > 1 ? srcs.map((s, j) => `<button aria-label="Photo ${j + 1}"><img src="${escH(s)}" alt="" loading="lazy" referrerpolicy="no-referrer"></button>`).join('') : '';
    film.querySelectorAll('button').forEach((b, j) => b.onclick = e => { e.stopPropagation(); track.scrollTo({left: j * track.clientWidth, behavior: still() ? 'auto' : 'smooth'}); });
    stage.style.transform = ''; lb.style.backgroundColor = '';
    document.documentElement.classList.add('kit-lock');
    lb.classList.add('open'); caption();
    track.scrollLeft = i * track.clientWidth;
    try { history.pushState({kitLb: 1}, ''); } catch (e) {}
    lb.querySelector('.kit-lb-x').focus({preventScroll: true});
    buzz();
  }
  function close(fromPop) {
    if (!lb || !lb.classList.contains('open')) return;
    if (!fromPop && history.state && history.state.kitLb) { history.back(); return; }  // popstate finishes the close
    lb.classList.remove('open'); document.documentElement.classList.remove('kit-lock');
    setTimeout(() => { if (!lb.classList.contains('open')) { track.innerHTML = ''; stage.style.transform = ''; lb.style.backgroundColor = ''; } }, 300);
    if (last && last.focus) last.focus({preventScroll: true});
  }

  // Haptic tick on the taps that matter (phones that support it; silently nothing elsewhere).
  function buzzOn(sel) { document.addEventListener('click', e => { if (e.target.closest && e.target.closest(sel)) buzz(); }, true); }

  // Page switcher: the pill slides to the tapped page, then we go.
  function switcher() {
    document.querySelectorAll('.switch').forEach(sw => {
      slide(sw, null, false);
      sw.addEventListener('click', e => {
        const a = e.target.closest('a');
        if (!a || a.hasAttribute('aria-current') || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button) return;
        buzz(); if (still()) return;
        e.preventDefault();
        sw.querySelectorAll('a').forEach(x => x.classList.toggle('kit-go', x === a));
        slide(sw, a);
        setTimeout(() => { location.href = a.href; }, 180);
      });
    });
    addEventListener('pageshow', e => { if (e.persisted) document.querySelectorAll('.switch').forEach(sw => { sw.querySelectorAll('.kit-go').forEach(x => x.classList.remove('kit-go')); slide(sw, null, false); }); });
  }

  window.Kit = {slide, reveal, count, countOnce, open, close, buzz, buzzOn, still};
  const boot = () => {
    switcher();
    document.querySelectorAll('[data-count]').forEach(el => count(el, +el.dataset.count, {dur: 1100}));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
// kit:end
"""


def render(city: dict, res: dict, cities: list[dict]) -> str:
    data = build_data(city, res, cities)
    gen = dt.datetime.fromisoformat(res["generated_at"])
    dates = res["dates"]
    d0, d1 = dt.date.fromisoformat(dates[0]), dt.date.fromisoformat(dates[-1])
    total = sum(len(v["slots"].get(d, [])) for v in data["venues"] for d in dates)
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    name = city["name"]
    tzab = gen.strftime("%Z") or "local"
    acc, accd = city.get("accent") or "#a2382b", city.get("accent_dark") or "#e0705d"
    city_css = (f":root{{--city:{acc}}}@media (prefers-color-scheme:dark){{:root{{--city:{accd}}}}}")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name} Tables</title>
<meta name="description" content="Open tables at {name}'s best-rated restaurants, bars and coffee on Beli.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}{KIT_CSS}{NEW_CSS}{city_css}</style></head><body>
<div class="kit-glow" aria-hidden="true"></div><div class="kit-grain" aria-hidden="true"></div>
<header class="top">
<nav class="topnav"><a class="brand" href="../">Tables</a>
<button class="citypick" id="citypick" type="button" aria-haspopup="dialog" aria-expanded="false"><span class="cdot" aria-hidden="true"></span><span>{name}</span><svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
<div class="pull" id="pull"><span class="pdot" aria-hidden="true"></span><span class="ptxt" id="ptxt">Updated <b>{gen:%-I:%M %p}</b></span>
<button class="pbtn" id="pbtn" type="button" title="Pull fresh times now"><svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3h-3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg><span>Refresh</span></button>
<span class="pmsg" id="pmsg" role="status" aria-live="polite"></span></div></nav>
<div class="hero"><h1 class="serif">{name} <em>Tables</em></h1>
<div class="stats"><span><b>{len([d for d in dates if d >= dt.date.today().isoformat()]) or len(dates)}</b> nights</span><span><b data-count="{total}">{total:,}</b> open times</span><span>for <b id="pnum">{data['party']}</b></span><span class="dim">{d0:%b} {d0.day}–{d1:%b} {d1.day}</span></div></div>
<section class="tonight" id="tonight" aria-label="Tonight"></section>
<section class="hits" id="hits" aria-label="Most ordered dishes"></section>
</header>
<div class="sheet hide" id="sheet" role="dialog" aria-modal="true" aria-label="Choose a city"><div class="sheet-in"><div class="sheet-h"><b class="serif">Pick a city</b><button class="sheet-x" id="sheetx" aria-label="Close">×</button></div><div class="clist" id="clist"></div><p class="sheet-note">More cities are on the way. Each one needs its Beli scores pulled first.</p></div></div>
<div class="bar"><div class="bar-in">
<div class="row1">
<div class="seg kinds" role="group" aria-label="Show"><button data-k="restaurant">Restaurants<i id="c-restaurant"></i></button><button data-k="bar">Bars<i id="c-bar"></i></button><button data-k="coffee">Coffee<i id="c-coffee"></i></button></div>
<div class="step" role="group" aria-label="Party size"><button data-pd="-1" aria-label="Fewer people">−</button><span><b id="pval">4</b><small>guests</small></span><button data-pd="1" aria-label="More people">+</button></div>
<div class="days" id="days"></div>
<button class="fbtn" id="fbtn" aria-expanded="false" aria-controls="filters" aria-label="Filters"><svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path d="M2 3h12M4.5 8h7M7 13h2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" fill="none"/></svg><span class="lbl">Filters</span><i id="fcount"></i></button>
<div class="seg vseg" role="group" aria-label="View"><button data-view="cards" title="Cards" aria-label="Cards"><svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/></svg><span class="lbl">Cards</span></button><button data-view="list" title="List" aria-label="List"><svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><rect x="2" y="2.5" width="12" height="3" rx="1"/><rect x="2" y="6.5" width="12" height="3" rx="1"/><rect x="2" y="10.5" width="12" height="3" rx="1"/></svg><span class="lbl">List</span></button><button data-view="map" title="Map" aria-label="Map"><svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true"><path d="M8 14.5s4.5-4.2 4.5-8A4.5 4.5 0 0 0 3.5 6.5c0 3.8 4.5 8 4.5 8z" fill="none" stroke="currentColor" stroke-width="1.6"/><circle cx="8" cy="6.5" r="1.6"/></svg><span class="lbl">Map</span></button></div>
</div>
<div class="row2" id="filters">
<div class="seg when" role="group" aria-label="Time of night"><button data-when="any">Any time</button><button data-when="early" title="5–7 PM">Early</button><button data-when="prime" title="7–8:30 PM">Prime</button><button data-when="late" title="8:30 PM on">Late</button></div>
<select id="hood" class="sel" aria-label="Area"></select>
<select id="cuisine" class="sel" aria-label="Food"></select>
<select id="vibe" class="sel hide" aria-label="Vibe"></select>
<label class="tog"><input type="checkbox" id="only"> Open only</label>
<label class="tog"><input type="checkbox" id="onl"> Book online</label>
<input class="search" id="q" type="search" placeholder="Search name or dish" aria-label="Search">
<label class="sortl">Sort <select id="sort" class="sel"><option value="score">Beli score</option><option value="open">Most open</option><option value="soonest">Soonest</option><option value="top25">Top 25 rank</option><option value="name">A–Z</option></select></label>
<button id="reset" class="reset hide">Reset</button>
</div>
</div></div>
<main>
<section id="s-map" class="hide"><div class="map-wrap"><div id="map" role="region" aria-label="Map of places"></div><div class="map-leg"><span><i class="lg-open"></i>Table tonight</span><span><i class="lg-none"></i>Nothing tonight</span><span id="map-n"></span></div></div></section>
<section id="s-restaurant"><div class="sec-h"><h2 class="serif">Restaurants</h2><span id="n-restaurant"></span></div>
<div class="grid" id="g-restaurant"></div><div class="none hide" id="e-restaurant">Nothing matches these filters. Try another day, a wider time, or Reset.</div></section>
<section id="s-bar"><div class="sec-h"><h2 class="serif">Bars</h2><span id="n-bar"></span></div>
<div class="grid" id="g-bar"></div><div class="none hide" id="e-bar">Nothing matches these filters. Try another day, a wider time, or Reset.</div></section>
<section id="s-coffee"><div class="sec-h"><h2 class="serif">Coffee</h2><span id="n-coffee"></span></div>
<div class="grid" id="g-coffee"></div><div class="none hide" id="e-coffee">No coffee shops for {name} yet. They're next on the list: once their Beli scores are pulled they'll show up here.</div></section>
</main>
<button class="surprise" id="surprise" type="button"><span aria-hidden="true">✦</span> Surprise me</button>
<footer>Beli community averages · times refresh every few hours · photos from each venue's own listings · nothing here books for you</footer>
<script id="data" type="application/json">{blob}</script>
<script>{KIT_JS}</script>
<script>{(HERE / "page.js").read_text()}</script></body></html>
"""


def render_home(cities: list[dict]) -> str:
    """Root page: send people to their last city (or the first live one)."""
    first = next((c["slug"] for c in cities if c.get("status") == "live"), cities[0]["slug"])
    links = "".join(f'<li><a href="{c["slug"]}/">{c["name"]}</a></li>' for c in cities)
    slugs = json.dumps([c["slug"] for c in cities])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tables</title><style>body{{font:16px/1.5 -apple-system,system-ui,sans-serif;margin:40px 16px;background:#f6f3ee;color:#1c1a17}}
@media (prefers-color-scheme:dark){{body{{background:#121110;color:#f1ece4}}a{{color:#e8875a}}}}</style>
<script>try{{var c=localStorage.getItem('tablesCity');if({slugs}.indexOf(c)<0)c={json.dumps(first)};location.replace(c+'/'+location.hash)}}catch(e){{location.replace({json.dumps(first)}+'/')}}</script></head>
<body><h1>Tables</h1><ul>{links}</ul></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cities", nargs="*", help="slugs (default: every city in cities.json)")
    a = ap.parse_args()
    cities = load_cities()
    for c in cities:
        if a.cities and c["slug"] not in a.cities:
            continue
        cdir = HERE / "cities" / c["slug"]
        res = load_json(cdir / "results" / f"p{c.get('party', 4)}.json", None)
        if not res:
            print(f"skip {c['slug']}: no results yet")
            continue
        out = HERE / c["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(c, res, cities))
        print(f"wrote {out}")
    (HERE / "index.html").write_text(render_home(cities))


if __name__ == "__main__":
    main()
