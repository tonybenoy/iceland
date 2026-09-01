# Iceland — 12–17 September

Three six-day road trips from Keflavík, plus 325 sights, 30 campsites and 31
fuel stops on one map.

**→ https://tonybenoy.github.io/iceland/**

Star anything you fancy and hit **Copy picks** — it copies a plain list you can
paste into the chat. Picks live in your own browser only.

## The shape of the trip

Day 1 starts at KEF on the morning of the 12th (collect the car, pick up the
third of you). The flight home is **17:00 on day 6**, so the car is back at the
airport by 15:00. Five nights: 12, 13, 14, 15, 16 September. Reykjavík is
handled separately, before day 1.

| | v1 ring | v2 ring, max stops | v3 west & south |
|---|---|---|---|
| Distance | 1,817 km | 2,010 km | **1,514 km** |
| Driving | 29.7 h | 33.3 h | **28.4 h** |
| Stops | 32 | **52** | 41 |
| Longest day | 9.9 h | **13.1 h** | 10.3 h |
| Nights off the card | 1 | 1 | **0** |
| Snæfellsnes | no | no | **yes** |
| Jökulsárlón | yes | yes | **no** |
| Whales at Húsavík | yes | yes | **no** |

## Two things the dates changed

**Four campsites are already shut when you arrive.** Kleifarmörk closed
31 August, Skjól and Möðrudalur on 10 September, Svartiskógur on the 12th.
Kleifarmörk was night 2 of the original plan — the trip would have arrived at a
locked gate. Húsavík, Bragðavellir, Grundarfjörður, Akranes, Stokkseyri and
Skagaströnd all close on **15 September**, mid-trip. `build_route.py` now parses
every campsite's season, checks it against the actual date of each night, and
only ever offers alternatives that are open that night.

**Six days is not enough for the ring and Snæfellsnes.** v1 and v2 do the whole
loop but never linger, and both need one night off the card, because no card
site between Vík and Djúpivogur is open in mid-September. v3 drops the north and
east entirely to do Reykjanes, the Golden Circle, the south coast and all of
Snæfellsnes properly — 300 km less driving, more stops, every night on the card.
The trade is Jökulsárlón and the Húsavík whales.

### Day length, not distance

Each day shows real OSRM driving time plus an estimate of time on the ground
(15 min roadside, 35–45 a proper sight, 90 a hike, 180 the whale boat), and a
finish time from an 08:30 start. Iceland gives ~13 h of daylight on 12 September
and ~11.5 h by the 17th, so anything ending after ~20:00 is flagged.

v2's day 4 runs to 13.1 h and ends at 21:00 — that is the honest cost of adding
20 stops to a loop this tight.

### What things cost

Stops carry a badge: `free`, `car park` (per car, 600–1,000 ISK), or `ticket pp`.
All the car parks together come to under ~10,000 ISK for the whole trip. The
per-person tickets are where the money is — one whale trip for three costs more
than every car park combined.

## Datasets

| File | Rows | Source |
|---|---|---|
| `data/iceland_places_ranked.csv` / `.json` | 325 | adventures.com map + hand-curated notes |
| `data/iceland_places.csv` / `.json` | 332 | [adventures.com map of Iceland](https://adventures.com/information/map-of-iceland/) (raw) |
| `data/iceland_campsites.csv` / `.json` | 30 | [utilegukortid.is](https://utilegukortid.is/all-camping-sites/?lang=en) |
| `data/iceland_gas_stations.csv` / `.json` | 31 | [Google My Map](https://www.google.com/maps/d/u/0/viewer?mid=1wTIeHwmiHN2QQcL_ySY7_rmLaxHkan6o) |
| `data/routes.json` | 2 routes | built from the above + OSRM |

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
