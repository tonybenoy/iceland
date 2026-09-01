# Iceland — 6.5 days

A browsable trip plan for three people: a Ring Road route, 325 sights, 30
campsites and 31 fuel stops, all on one map.

**→ https://tonybenoy.github.io/iceland/**

Star anything you fancy and hit **Copy picks** — it copies a plain list you can
paste straight into the chat. Picks live in your own browser only; nobody else
sees them and nothing is sent anywhere.

## Two routes — pick one on the site

Both start and end in Reykjavík and put every night on an Útilegukortið campsite.

| | Counter-clockwise (v1) | Clockwise (v2) |
|---|---|---|
| Distance | 1,928 km | 1,957 km |
| Driving | 32.2 h | 33.3 h |
| Worst day | 403 km / 6.6 h | 414 km / 7.0 h |
| Final half day | 226 km / 3.4 h | 248 km / **5.6 h** |
| Golden Circle | yes | **no** |
| Reykjavík day | no | yes (free, no driving) |
| Paid car parks | 9 | 8 |
| Per-person tickets | 2 | 2 |

Clockwise buys a relaxed whale day (162 km), a free Reykjavík day, and Ásbyrgi,
Hvítserkur and the Herring Museum. It costs the Golden Circle — Þingvellir,
Geysir, Gullfoss, three of them free — and its last day isn't a half day, which
matters if you're flying out that evening.

| Day | | km | Driving | Night |
|---|---|---:|---:|---|
| 1 | Golden Circle | 222 | 3.5 h | At Faxi |
| 2 | South coast waterfalls to Vík | 221 | 5.1 h | Kleifarmörk |
| 3 | Glaciers and the lagoon | 403 | 6.6 h | Bragðavellir |
| 4 | East fjords to Stuðlagil | 225 | 3.5 h | Stuðlagil |
| 5 | Dettifoss and Mývatn | 275 | 4.8 h | Húsavík |
| 6 | Húsavík whales, then west | 356 | 5.3 h | Búðardalur |
| 6½ | Back to Reykjavík | 226 | 3.4 h | — |

Distances are real road routing from OSRM, not straight lines. **Driving hours
exclude every stop** — budget 30–60 min per sight on top.

### What things cost

Stops carry a cost badge from the curated `tickets` field: `free`, `car park`
(per car), or `ticket pp` (per person).

Car-park fees are 600–1,000 ISK **per car** and total under ~10,000 ISK across
the whole trip. That's not where the money goes. The per-person tickets are:
Mývatn Nature Baths, Kerið, whale watching, and the Blue Lagoon if you add it.
**One whale-watching trip for three people costs more than every car park on the
route combined** — so that's the decision worth having, not the parking.

Day 6 splits in Húsavík: whale watching (~3 h) or the Whale Museum (~1.5 h).
Both leave from the same harbour about 100 m apart, so regrouping is easy —
but the two options finish over an hour apart, so agree a time first.

### Two honest warnings

**Day 3 is oversized.** The card network has no campsite for the 330 km between
Vík and Djúpivogur, which is exactly why. A non-card site at Höfn would split it
neatly.

**Kleifarmörk costs you.** It's 37 km up a slow road off the ring — about an
hour each way, roughly +73 km and +2 h across days 2 and 3. It buys a card
night; camping at Vík instead buys back an afternoon.

## Datasets

| File | Rows | Source |
|---|---|---|
| `data/iceland_places_ranked.csv` / `.json` | 325 | adventures.com map + hand-curated notes |
| `data/iceland_places.csv` / `.json` | 332 | [adventures.com map of Iceland](https://adventures.com/information/map-of-iceland/) (raw) |
| `data/iceland_campsites.csv` / `.json` | 30 | [utilegukortid.is](https://utilegukortid.is/all-camping-sites/?lang=en) |
| `data/iceland_gas_stations.csv` / `.json` | 31 | [Google My Map](https://www.google.com/maps/d/u/0/viewer?mid=1wTIeHwmiHN2QQcL_ySY7_rmLaxHkan6o) |
| `data/route.json` | 7 days | built from the above + OSRM |

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
