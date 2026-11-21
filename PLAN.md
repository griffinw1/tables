# Plan: Cities, Coffee, and a Sleeker "Tables" Page

Status: proposal only. No code has been changed. Written Nov 21, 2026.
Today the site is Dallas-only: one `venues.json` (57 venues, restaurant or bar), one `results.json` (plus `results_p2…p8.json`), one `beli_avgs.jsonl` (26 lines, most with no dishes yet), `media.json`, `vibes.json`. `render.py` bakes everything into `site/index.html`, and `page.js` runs it. Several values are Dallas-specific and hard-coded: the `America/Chicago` time zone (check.py, platforms/common.py, page.js), the trip dates `2026-11-20…28`, the Resy city fallbacks `dfw`/`dallas-tx`, and the "Dallas Tables" title.

---

## 1. Data layout per city

```
cities.json                      # the city list: slug, name, tz, resy_city, window, dates mode, status
cities/<slug>/venues.json        # same schema as today + "kind": restaurant | bar | coffee
cities/<slug>/beli.jsonl         # was beli_avgs.jsonl (later lines win, as now)
cities/<slug>/media.json         # photos / menu / website per venue
cities/<slug>/vibes.json         # optional
cities/<slug>/geo.json           # map pins (moves from map/geo.json)
cities/<slug>/results/p4.json    # availability; p2…p8 alongside
```

- **Dallas moves first** to `cities/dallas/` with no behaviour change (a one-time `git mv`). Old paths stay readable for one release so `trip/` (which fetches `../results.json`) keeps working; then point trip at `../cities/dallas/results/p4.json`.
- **`cities.json` entry** example: `{"slug":"austin","name":"Austin","tz":"America/Chicago","resy_city":"austin-tx","window":"17:00-22:00","dates":"rolling:9","status":"live"}`. `dates` is either a fixed trip window (Dallas: `2026-11-20..2026-11-28`) or `rolling:N` (next N days). Cities without a trip default to rolling.
- **Coffee venues** carry `"platform": "none"` and are skipped by the checker entirely. They get `hours` (optional, from the official site) instead of slots.
- **Stable venue ids.** Add an `id`-like `slug` per venue (e.g. `lucia`) and key media/vibes/beli by slug, not display name. Names collide across cities and get edited ("St. Martin's" vs "St Martin's").
- `~/BeliData/<city>/` already uses this shape (`dallas-tx/`, `aspen-co/`); keep those folder names and map them in `cities.json` (`"beli_dir":"dallas-tx"`).

## 2. Beli collection: making the slow part go further

At 2–4 minutes a place by iPhone Mirroring, 50 places is ~2–3 hours of an untouched Mac. Cap the work and order it:

1. **Seed from Beli lists, not one-by-one.** Each city starts from Beli's "Top 25 Restaurants / Bars / Coffee in <city>" list screens. One pass over a list screen gives names + rank for 25 places in ~5 minutes; that's enough to publish a city with ranks before any averages exist.
2. **Priority queue** (`cities/<slug>/beli_queue.txt`, generated): (a) places with live availability and no average, (b) Top-10 in each category, (c) everything else, (d) re-checks older than 90 days. Coffee sits behind restaurants because it has no availability to pair with.
3. **Batch runs of 15 places** (~45 min), one city per run, started on demand ("run the Austin batch") while the Mac is idle. The skill already resumes from `~/BeliData/<city>/`; add a "skip if pulled < 90 days ago" check.
4. **Dishes are the payoff.** Capture the full most-recommended list with counts on the same screen visit (no second trip). Today many lines have `"dishes": []`; backfill Dallas Top-25 first.
5. **Page degrades gracefully:** no average → show Beli list rank ("#4 on Beli's Austin list"); no dishes → hide the section, never show an empty box.

Rough budget for a new city: 30 min to seed lists, then 2–3 batches (~2 h of idle Mac) for the top ~40.

## 3. Checker / publisher across cities

The binding limit is OpenTable (Akamai rate-limits bursts; today it already gets only one extra party size per 3-hour run). Adding cities must not multiply OpenTable traffic.

- **One loop, one lock.** `publish.sh` iterates `cities.json` inside the existing lock and commits once per run (one push, fewer rebase races). `check.py` gains `--city <slug>` and reads tz/dates/resy_city from `cities.json`.
- **A fixed OpenTable budget per run** (e.g. 40 page loads total, shared across all cities), filled round-robin: party of 4 for each city's top OpenTable venues first, then extra party sizes. Anything not reached keeps its last good row, shown faded as "older check" (existing behaviour).
- **Rotate cities on the extra work.** Party sizes 2/3/5–8 rotate by (run number) across *city × size*, so each city gets each size roughly once a day.
- **Tiering:** a city has `status`: `live` (every run), `light` (party of 4 only, every other run), `paused` (render only). Only cities with an upcoming trip need `live`.
- **Resy / SevenRooms / Tock** are API-ish and cheap; they can run every city every time, with the existing per-request delay.
- **GitHub Actions** cron (Resy + SevenRooms) loops cities the same way; OpenTable stays on the Mac.
- `diff.py` reports per city; the ntfy "Pull again" button gets a city argument.

## 4. URLs and the city picker

- **`/site/?city=austin`** served by one `site/index.html` that fetches `../cities/<slug>/data.json` (a small per-city bundle `render.py` writes). One page to maintain; city switching is instant; `#d=2026-11-24` keeps working for trip links.
- **Also emit `/c/<slug>/index.html`** as a tiny static shell (title, description, social preview image) that loads the same page with that city preset. Clean shareable links; good link previews in iMessage.
- Default city = last chosen (localStorage), else the city with the soonest trip, else Dallas.
- **Picker:** the eyebrow line becomes a tappable pill, "Dallas ▾". It opens a bottom sheet on phones (popover on desktop) with city cards: name, a small skyline/photo tile, "57 places · 12 open tonight", trip dates if any. Cities still being seeded show "Coming soon" in a muted style.

## 5. Category tabs: Restaurants / Bars / Coffee

- Replace the Restaurants / Bars / Both switch with three sliding pills (the existing pill component): **Restaurants · Bars · Coffee**, plus a counter on each.
- **Coffee cards drop the booking block** (no 9-day strip, no time chips, no "Book" button). Instead: Beli score, photos, top dishes/drinks, hours today ("Open till 6"), "Walk-in" tag, Map · Site · Menu buttons.
- Filters adapt per tab: time-of-night and "Open only" hide on Coffee; add "Open now" (from hours) and "Has food" there. Sort on Coffee: Beli score · A–Z · Nearest (if location is granted on tap).

## 6. Popular dishes, front and centre

- **"Order this" strip** on every card, right under the name: the top 3 dishes as chips with a small bar showing share of recommendations (e.g. "Beef wellington · 133"). The #1 dish gets a gold "Most ordered" badge.
- **Tap a chip** → the dish's own photo if the venue/menu has one, else nothing (no Beli member photos, ever).
- **"Dishes" search mode:** search "tartare" and get a ranked list of dishes across the city (venue, count), with jump-to-card.
- **City "Greatest hits" row** at the top: the 8 dishes with the highest counts in the city, horizontally scrollable.
- Clean truncated names at collection time (the "… (truncated)" strings) by opening the dish row in Beli during the same visit.

## 7. More photos

- Target **5–8 photos per venue**, tagged `room | food | drink | exterior | menu`, from allowed sources only: Resy/OpenTable/SevenRooms/Tock listing photos, the official site, official Instagram embeds (linked, not copied), Google Maps "by owner" photos only when clearly the venue's own. Store as `{"url","tag","credit","src"}` in `media.json`; credit line stays.
- Card shows the carousel with a small tag label ("Food", "Room"); the lightbox gets a filmstrip and tag filter.
- A **per-venue photo page** (lightbox "All photos" grid) rather than heavier cards.
- Run the existing `media_build/` pipeline per city; add a Chrome-assisted pass for coffee shops (mostly official sites / Instagram).

## 8. Sleeker and more fun (concrete)

- **Per-city accent** from `cities.json` (Dallas: burnt orange, Austin: live-oak green, NYC: subway yellow) feeding the existing CSS tokens; headers get a subtle city skyline SVG line drawing at the top.
- **"Tonight" hero:** big number "14 tables open tonight for 4" with the three best (score × openings) as swipeable cards; one tap to the time chips.
- **Score rings** that fill on scroll (reuse count-up), coloured by band (9+ gold, 8.5+ green).
- **"Surprise me"** button: picks a highly rated place with an open table tonight (or an open coffee shop now), flips the card in with a small confetti burst. Read-only, it just scrolls to the card.
- **Card flip** for vibe: front = photos + dishes, back = vibe sentence, tags, price · energy, dress.
- **Sticky mini-map toggle** on desktop (right column pins that highlight as you scroll), hidden on phones behind a "Map" pill.
- **Collect stamps:** tap "Been here" to stamp a card (localStorage only); a city "passport" counter in the picker. Fun, private, no accounts.
- Tighter type scale, fewer borders, more whitespace; skeleton shimmer while a city bundle loads.
- All motion stays `prefers-reduced-motion` guarded; every new surface gets dark-mode tokens.

## 9. Phased order of work

| Phase | What | Effort |
|---|---|---|
| 0 | Move Dallas into `cities/dallas/`, add `cities.json`, slugs, keep old paths working; no visual change | ½ day |
| 1 | `check.py --city`, tz/dates/resy_city from config, `publish.sh` city loop + shared OpenTable budget | 1 day |
| 2 | Per-city `data.json`, `?city=` routing, `/c/<slug>/` shells, city picker | 1 day |
| 3 | Category tabs + coffee card variant + `platform: none` | ½–1 day |
| 4 | Popular dishes: "Order this" strip, Greatest hits, dish search; Dallas dish backfill (Mac time) | ½ day code + ~1 h Beli |
| 5 | Photos: tagged media schema, 5–8 per venue, lightbox filmstrip | 1 day + collection |
| 6 | Design/fun pass: city accent, Tonight hero, Surprise me, card flip, stamps | 1–2 days |
| 7 | Second city end-to-end (seed lists → venues → platforms → photos → Beli batches) | ~1 day + ~2–3 h idle Mac |

Each phase ships on its own and keeps the 3-hourly job green. Acceptance per phase (as in REQUIREMENTS 1.7): headless screenshots at 390px and 1300px, light and dark, no overlap or sideways scroll, no script errors, deep links spot-checked per platform, and every outside link `target="_blank" rel="noopener"`.

## 10. Guardrails (unchanged)

- Read-only: no booking, holds, waitlists or automation on any platform.
- Public pages: first names only, no private addresses (the trip plan's lakehouse stays location-free).
- Beli member photos are never republished; only venue/official/platform photos, with credit.
- Every outside link opens in a new tab.
- Works at 390px and in dark mode.

## 11. Open questions for Griffin

1. Which cities, in what order? Any with trip dates (fixed window) vs always-on rolling?
2. Keep `/site/` as Dallas forever (and add `/c/…`), or rename the repo/site to something city-neutral?
3. Coffee: also bakeries / cafés with food, or strictly coffee? Want "Open now" hours (needs per-shop collection)?
4. Default party size for new cities: still 4?
5. How much idle-Mac time per week can go to Beli batches?
6. Should `trip/` and `map/` become per-city too, or stay Dallas-only?
7. "Been here" stamps: device-only is fine, or synced (e.g. via the same Firebase approach as the Aspen site)?
8. OK to drop a city to `light`/`paused` after its trip to save OpenTable budget?
