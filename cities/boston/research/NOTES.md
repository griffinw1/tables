# Boston research notes (2026-11-21)

Files in this folder:
- `candidates.json`: 49 open places (38 restaurants, 11 bars). Each has its address, booking platform and URL, the sources that named it, and `source_count`. `dropped` lists the one closed place.
- `specials.json`: for each place, the famous items (with evidence and mention counts), tips, reservation difficulty and warnings.
- `photos.json`: the scoring rubric at the top, then the best photo plus up to 2 runners-up for each place's top 1–3 items.

## Method

1. **Candidate pool.** I took every restaurant and bar named on the source lists below, then counted for each place how many independent lists named it (`source_count`). The places were sorted by that count. Where counts tied, I kept the order they had in the lists: Michelin, Boston Magazine and NYT ranks, then Eater and Infatuation.
2. **Geography.** The scope is Boston proper plus Cambridge and Somerville (`"area": "core"`). Three Brookline places scored too high to leave out: Mahaniyom (6 sources), Bar Vlaha (4) and Blossom Bar (3). They're kept but marked `"area": "adjacent"`; drop them if you want strict borders. Strong places outside the area were left out: Lê Madeline (Quincy, 5 sources), Nightshade Noodle Bar (Lynn, 4), Iru (Brookline), and McGonagle's and Bánh Mì Ba Lẹ (Dorchester, NYT only).
3. **Per-place research.** Five parallel research passes covered about 10 places each. For each place they:
   - checked the official site and that it is still open;
   - recorded the booking URL the restaurant's own site links to;
   - gathered "famous items" from Eater, Infatuation, the Globe, Boston Magazine, Time Out, NYT and the Resy blog, all paraphrased;
   - picked photos using the rubric in `photos.json`.
4. **Photo check.** Every kept photo URL was re-checked at the end with a plain GET. All 79 returned HTTP 200 with an image content type.

## Sources (restaurants)

| Key | Source | Date |
|---|---|---|
| MICH | Michelin Guide Northeast Cities, Boston selection: 1 star, 6 Bib Gourmand, 19 Recommended | Nov 2025; the 2026 edition is not yet announced |
| E38 | Eater Boston 38: https://boston.eater.com/maps/best-restaurants-boston-38 | updated Oct 8, 2026 |
| INF25 | Infatuation Top 25: https://www.theinfatuation.com/boston/guides/best-restaurants-in-boston-greatest-hits-list | Sep 18, 2026 |
| INFNEW | Infatuation Best New of 2026 | Nov 9, 2026 |
| BM50 | Boston Magazine Top 50: https://www.bostonmagazine.com/best-restaurants-in-boston/ | Oct 27, 2026; Mooncusser is #1 |
| BMNEW | Boston Magazine Best of Boston 2026 (Best New Restaurant: Fallow Kin; Best Restaurant, South: Dalia) | Jun 2026 |
| NYT | NYT "Where to Eat" Boston, 27 places, via the Boston.com recap | Sep 30, 2026 |
| TO | Time Out 29 Best Restaurants | Aug 2026 |
| RESY | Resy Hit List Boston | Nov 2026 |
| RBELI | Resy × Beli "Top Ranked Resy Restaurants in Boston": Tonino, Sarma, Wa Shin, Oleana, KAVA, Avra, Field & Vine, La Padrona, Darling, Iru | Oct 30, 2026 |
| JB | James Beard 2026 semifinalists (O Ya, Comfort Kitchen, Tonino, La Padrona, Lenox Sophia, Zurito, Spoke, Koji Club…) | Jan 2026 |

## Sources (bars)

| Key | Source | Date |
|---|---|---|
| INFBARS | Infatuation Best Bars | Nov 13, 2026 |
| TOBARS | Time Out Best Bars | Apr 2026 |
| TOCOCK | Time Out Best Cocktail Bars | Oct 2024; older |
| NA50 | North America's 50 Best Bars 2026, extended 51–100 list (Hecate, The Wig Shop) | 2026 |
| BOB | Boston Magazine Best of Boston "Best Cocktail Bar" archive: Hecate 2022, Farmacia 2023, Good Company 2024, Backbar 2017 | archive |
| EBARS / EHEAT | Eater new cocktail bars heatmap and restaurant heatmap | Aug and Nov 2026 |
| JB | James Beard 2026 semifinalists (Koji Club beverage professional) | Jan 2026 |

## Uncertain or worth knowing

- **Reddit was unreachable.** reddit.com is blocked for both WebSearch and WebFetch, and curl gets a block page. So r/boston, r/BostonFood and r/Cambridge are **not** in the source counts or the evidence. If you want Reddit signal, read the threads by hand.
- **Mention counts are conservative.** The shared WebSearch quota ran out partway through the per-place passes. The later places were researched by fetching known pages directly, so many `mentions` values are 1–2 and should be read as lower bounds.
- **No platform-listing photos.** Resy, OpenTable and Tock pages render with JavaScript or block bots, so almost no photos come from booking platforms. Most come from official sites, plus a few press photos credited "courtesy of".
- **Address and listing corrections found:**
  - Urban Hearth moved to **1281 Cambridge St, Inman Square**; Eater and Time Out still show the old address.
  - Dalia is at **429 W Broadway**; the Boston.com NYT recap says 629.
  - Dalia books through **DoorDash Reservations** (`platform: "other"`).
  - Toro now books on **OpenTable**; older guides still say walk-in only.
  - 311 Omakase also goes by "Three 1 One" and books on Tock. Reservations open on the 15th of each month.
- **Kinds changed from the source lists:**
  - **Liars** (Somerville, opened Aug 2026) is a bistro from the Spoke team, not a cocktail bar, so it's classed as a restaurant.
  - **Spoke Wine Bar** is classed as a restaurant: it's food-led, though James Beard listed it under Outstanding Bar.
  - **Yvonne's** is classed as a bar; it's a supper club with cocktails.
- **Bars with weak data:**
  - **Backbar:** its site backbarunion.com shows a Wix error. The Field & Vine team bought it in 2025, and its cofounder left at the end of 2025. Re-check before publishing.
  - **Farmacia:** sources disagree on the exact address. The research used 5 North Square, but the brief had it upstairs at Mare.
- **Closed:** **Drink** (Fort Point) shut in January 2024 and was dropped.
- **Seasonal or retired items** are flagged in `specials.json` warnings:
  - Puritan's crab cavatelli
  - Fallow Kin's squid
  - Baleia's cataplana
  - Yvonne's pitas and popcorn brûlée
  - Blossom Bar's Gloria and Angie Valencia
  - La Royal's scallops
- **Jahunger photos** are the restaurant's official menu illustrations, not photographs. They score 11 on the rubric, but you may prefer to hide them.
- **Lower-authority photos.** Dalia (11 and 10), Brassica (9) and Grill 23 (ribeye, 9) use editorial photos credited to the restaurant (authority 1). These are allowed, but they come from press sites (Boston.com, Time Out, Boston Magazine), so their links may break.

## Photo stats

- 97 famous items got a photo search. 52 have an allowed `best` photo, and **49 of those score ≥10 out of 13**.
- 29 places have at least one photo scoring ≥10.
- Items with no allowed photo have `best: null` and a `photo_note`. Usually that's because the only dish shots are Instagram, uncredited, or by staff photographers.

## Beli pull shortlist (in this order)

Type the search text into Beli and filter to Boston, MA.

### Top 25 restaurants

| # | Place | Area | Beli search text |
|---|---|---|---|
| 1 | La Padrona | Back Bay (Raffles) | `La Padrona` |
| 2 | Sarma | Somerville | `Sarma` |
| 3 | Mooncusser | Back Bay | `Mooncusser` |
| 4 | Mahaniyom | Brookline (adjacent) | `Mahaniyom` |
| 5 | Field & Vine | Somerville | `Field Vine` |
| 6 | Comfort Kitchen | Dorchester | `Comfort Kitchen` |
| 7 | Neptune Oyster | North End | `Neptune Oyster` |
| 8 | O Ya | Leather District | `O Ya` (pick 9 East St) |
| 9 | Tonino | Jamaica Plain | `Tonino` |
| 10 | Urban Hearth | Cambridge | `Urban Hearth` |
| 11 | 311 Omakase | South End | `311` or `Three 1 One` |
| 12 | Oleana | Cambridge | `Oleana` |
| 13 | Giulia | Cambridge | `Giulia` |
| 14 | Pammy's | Cambridge | `Pammy` |
| 15 | Moëca | Cambridge | `Moeca` |
| 16 | Lenox Sophia | South Boston | `Lenox Sophia` |
| 17 | Spoke Wine Bar | Somerville | `Spoke Wine` |
| 18 | Dalia | South Boston | `Dalia` (check that it's 429 W Broadway) |
| 19 | Bar Vlaha | Brookline (adjacent) | `Bar Vlaha` |
| 20 | Wa Shin | Bay Village | `Wa Shin` |
| 21 | Kaia | South End | `Kaia` |
| 22 | Celeste | Somerville | `Celeste` (Union Sq, not other cities) |
| 23 | Jahunger | Cambridge | `Jahunger` |
| 24 | Sumiao Hunan Kitchen | Kendall | `Sumiao` |
| 25 | Brassica Kitchen + Café | Jamaica Plain | `Brassica` |

Next if there's time: Fallow Kin, Grill 23, Puritan & Co, Somaek, Via Cannuccia, Woods Hill Pier 4, La Royal, Zurito, Liars, Toro, Fox & the Knife, Row 34, Baleia.

### Top 8 bars

| # | Place | Area | Beli search text |
|---|---|---|---|
| 1 | Hecate | Back Bay | `Hecate` |
| 2 | Yvonne's | Downtown Crossing | `Yvonne` |
| 3 | haley.henry | Downtown Crossing | `haley henry` |
| 4 | Backbar | Somerville | `Backbar` |
| 5 | Blossom Bar | Brookline (adjacent) | `Blossom Bar` (it's inside Sichuan Garden; it may be listed under that name) |
| 6 | The Wig Shop | Downtown Crossing | `Wig Shop` |
| 7 | Farmacia | North End | `Farmacia` |
| 8 | Trina's Starlite Lounge | Somerville | `Trina` |

Then: The Koji Club (`Koji Club`), Extra Dirty Cocktail Club (`Extra Dirty`), Wusong Road (`Wusong`).
