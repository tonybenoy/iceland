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
| Distance | 1,765 km | 2,045 km | **1,519 km** |
| Driving | 29.1 h | 34.3 h | **28.5 h** |
| Stops | 32 | **52** | 41 |
| Longest day | **10.0 h** | 11.7 h | 10.3 h |
| Snæfellsnes | no | no | **yes** |
| Jökulsárlón | yes | yes | **no** |
| Whales at Húsavík | yes | yes | **no** |

v1 nights: Hvolsvöllur, Kirkjubæjarklaustur, Berunes, Mývatn, Blönduós.

## Not card-only

Nights are placed where the driving wants them, using all **215 named campsites
in Iceland** from OpenStreetMap (`scripts/extract_osm_campsites.py`), with the
20 card sites flagged. That single change fixed the plan more than any amount of
re-routing: v1's worst day went from 500 km to 361 km, and no day now runs past
daylight.

The card set had made the country look emptier than it is. The stretch between
Vík and Djúpivogur that I called a "campsite desert" — the thing that forced a
400 km day — actually has **28 campsites**, including Skaftafell and Vestrahorn
open all year. Exactly one of them is on the card.

**Dates still matter, just less.** Four card sites shut before you arrive
(Kleifarmörk on 31 August — it was night 2 of an earlier draft, so the trip would
have reached a locked gate) and six more close on 15 September, mid-trip.
`build_route.py` parses every season, checks it against the actual date of each
night, and only offers alternatives open that night.

## Six days, three shapes

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
