# Tables

Open reservations at each city's best-rated restaurants, bars and coffee on Beli.
Live: https://griffinw1.github.io/tables/ (redirects to your last city, e.g. `/tables/dallas/`).

- `cities.json`: the city list (slug, time zone, window, dates `A..B` or `rolling:N`, status `live|soon|paused`, accent colour).
- `cities/<slug>/`: `venues.json`, `beli.jsonl` (Beli community averages + most-recommended dishes, from the Beli app),
  `media.json` (+ optional `media_more.json`), `vibes.json`, `specials.json` (known-for lines), `results/p<N>.json` (availability by party size).
- `check.py --city <slug>`: read-only availability check (Resy, SevenRooms API; OpenTable, Tock via headless Chrome).
- `render.py`: writes `<slug>/index.html` for every city with results, plus the root redirect.
- `scripts/publish.sh`: check every live city, render, commit, push (launchd every 3 h: `scripts/com.tables.local.plist`).
- `scripts/pull_listener.py`: the "Pull again" button (ntfy.sh topic in `scripts/pull_topic.txt`), launchd `scripts/com.tables.pull.plist`.

Read-only: nothing here ever books, holds or joins a waitlist. Beli member photos are never published.
Plan for more cities and features: `PLAN.md`.
