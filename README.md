# Iceland — 12–18 September

One road trip, everything in it. Plus 325 sights, 215 campsites and 31 fuel
stops on the same map.

**→ https://tonybenoy.github.io/iceland/**

Star anything and hit **Copy picks** — it copies a plain list to paste into the
chat. Picks live in your own browser only.

**Installable and works offline.** Open it on your phone and use "Add to Home
Screen"; a service worker precaches the app and all trip data, and caches map
tiles as you pan over them. Load the map over wifi the night before and the
route, campsites and fuel stops stay readable in the fjords where there is no
signal. Tiles you have never looked at will be blank — everything else works.

## The plan

Reykjavík is the 11th, before this. Day 1 is an early start from KEF on Saturday
the 12th. Six nights. Flight home **17:00 on Friday the 18th**, so the car is
back at Keflavík by 15:00.

**2,263 km · 38.4 h driving · 61 stops · longest day 11.7 h · no camping card.**

| Day | | km | 07:00 → | Night |
|---|---|---:|---|---|
| 1 Sat 12 | Golden Circle, then south | 301 | 16:23 | Hvolsvöllur |
| 2 Sun 13 | Every waterfall on the south coast | 263 | 18:24 | Skaftafell |
| 3 Mon 14 | Glacier lagoon and the south-east | 279 | 15:54 | Berunes |
| 4 Tue 15 | East fjords, Stuðlagil and Mývatn | 366 | 17:18 | Hlíð (Mývatn) |
| 5 Wed 16 | Dettifoss, the whales, then west | 387 | 17:36 | Blönduós |
| 6 Thu 17 | North coast to Snæfellsnes | 425 | 18:42 | Arnarstapi |
| 7 Fri 18 | Snæfellsnes south, then the plane | 241 | 12:06 | — |

Everything you asked for is in it: **south, east, north and west including all
of Snæfellsnes**, and the **Húsavík whale boat** on day 5. Nothing finishes after
dark (sunset is ~20:20 on the 12th, ~20:00 on the 18th).

### How it fits

Three things make it work:

- **Camping in Skaftafell on night 2** puts Svartifoss at your tent, so day 3
  starts with the hike before anyone else is there.
- **The Mývatn cluster moves to day 4 evening**, not day 5. Day 4 had slack; that
  one change cut day 6 from 581 km to 425.
- **Night 6 at Arnarstapi**, on the south side of Snæfellsnes. Grundarfjörður on
  the north side shut on 15 September anyway, and the south side leaves a
  241 km run to the airport — done by lunchtime.

### Booking now, not later

- **The whale trip.** September sailings fill and get cancelled for weather.
  The Whale Museum is the fallback and is on the same quay.
- **Nights 1, 4, 5 and 6.** OSM records opening hours for only about a third of
  campsites, and mid-September is exactly when small sites close quietly. Skaftafell
  (night 2) is all-year and Berunes (night 3) runs to 1 October.

### Why the Westfjords are not in it

They are not skipped for lack of merit — 27 sights, including Dynjandi — but the
detour does not fit. Day 6 runs Blönduós to Arnarstapi in **266 km**. Going
through the Westfjords instead:

```
Blönduós → Hólmavík → Ísafjörður          415 km   6.0 h
Ísafjörður → Dynjandi → Patreksfjörður    165 km   2.5 h
Patreksfjörður → Búðardalur → Arnarstapi  377 km   5.4 h
                                          957 km  13.9 h
```

That is **957 km against 266** — roughly two extra days on slow, winding fjord
roads, and it would cost you Snæfellsnes, which is on the way and is not.
The Westfjords are their own trip.

### What it costs

10 paid car parks (600–1,000 ISK each, **per car**, under ~10,000 ISK for the
whole week) and 2 per-person tickets. One whale trip for three costs more than
every car park combined — that is the only real money decision.

## Datasets

| File | Rows | Source |
|---|---|---|
| `data/iceland_places_ranked.csv` / `.json` | 325 | adventures.com map + hand-curated notes |
| `data/iceland_places.csv` / `.json` | 332 | [adventures.com map of Iceland](https://adventures.com/information/map-of-iceland/) (raw) |
| `data/iceland_campsites.csv` / `.json` | 30 | [utilegukortid.is](https://utilegukortid.is/all-camping-sites/?lang=en) |
| `data/iceland_gas_stations.csv` / `.json` | 31 | [Google My Map](https://www.google.com/maps/d/u/0/viewer?mid=1wTIeHwmiHN2QQcL_ySY7_rmLaxHkan6o) |
| `data/routes.json` | 3 routes | built from the above + OSRM |
| `data/route_stops.csv` | 125 rows | every stop in every route, flat, for sorting |
| `data/iceland_campsites_all.csv` / `.json` | 215 | OpenStreetMap (Overpass) |

### Read `confidence` before you trust a row

Only **43 of 325** places have been assessed by a human. Every other row says
`Not assessed` rather than guessing, and the table view dims those cells.

This matters more than it sounds. An earlier version of the ranking filled the
gaps with cheerful defaults — `Moderate (2WD/Gravel)` on 244 rows and
`Yes - Fully Open` on 273 — which were indistinguishable from real judgements.
The effect was that **Herðubreið, Eldgjá and Ófærufoss all read as 2WD-drivable
and fully open in September** when they sit on F-roads with river crossings that
typically shut in late September. Curated neighbours like Landmannalaugar and
Askja carried the correct warnings, so the file looked trustworthy while being
wrong in exactly the places that could put someone in a river.

The rule now: an unassessed field says so. For anything highland or F-road,
check [road.is](https://road.is) and [safetravel.is](https://safetravel.is) on
the day — no static dataset can answer that question.

## Reproducing

```sh
python3 scripts/extract_mymaps.py                       # sights + fuel
python3 scripts/extract_mymaps.py gas_stations --geocode # + localities
python3 scripts/extract_campsites.py                    # campsites
python3 scripts/build_places.py                         # ranked table
python3 scripts/build_route.py                          # itinerary + geometry
python3 -m http.server                                  # then open localhost:8000
```

Stdlib Python 3 only, no dependencies. `--geocode` and `build_route.py` contact
OpenStreetMap's Nominatim and OSRM respectively, both throttled and both
optional to re-run — their output is committed.

## How the sources actually work

All three pages render client-side, so none of the data is in the served HTML:

- **Google My Maps** exposes placemarks as KML at `/maps/d/kml?mid=<id>`;
  `forcekml=1` returns XML rather than KMZ. Large maps get split across
  `NetworkLink` elements, so the script aborts rather than emit a partial file.
- **utilegukortid.is** is WordPress behind Divi's AJAX pagination, so the script
  queries the REST API and checks `X-WP-Total` to confirm nothing is missing.
- **Campsite coordinates** come from embedded Google Maps URLs, which encode
  position in the `pb` parameter as `!2d<lon>!3d<lat>` — longitude first.
- **Campsite amenities** are untitled icons, but each `<img>` carries a bilingual
  `alt` (`"Salerni / Toilets"`); the half after the slash is the English name.
- **Regions** come from Nominatim's `state_district`, giving the eight official
  Icelandic regions instead of guessing from latitude and longitude.

## Remaining quirks

- `iceland_places.csv` is the raw scrape and still holds the source map's seven
  duplicate pins; `build_places.py` collapses them (same name within 2 km).
- The fuel map is a hand-curated subset, **not** every filling station in
  Iceland. Don't plan a range off it — use OSM's `amenity=fuel` for that.
- Campsites are the ~30 the Útilegukortið card covers, not all ~170 in Iceland.
- Nine fuel points are rural enough that Nominatim returns no locality.

Data belongs to the respective sources; this repo is the extraction and the plan.
