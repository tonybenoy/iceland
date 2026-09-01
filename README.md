# Iceland trip data

Structured datasets scraped from three public sources, with the scripts that
produce them. Everything is stdlib Python 3 — no dependencies.

## Datasets

| File | Rows | Source |
|---|---|---|
| `data/iceland_places.csv` / `.json` | 332 | [adventures.com map of Iceland](https://adventures.com/information/map-of-iceland/) |
| `data/iceland_campsites.csv` / `.json` | 30 | [utilegukortid.is camping sites](https://utilegukortid.is/all-camping-sites/?lang=en) |
| `data/iceland_gas_stations.csv` / `.json` | 31 | [Google My Map: gas stations](https://www.google.com/maps/d/u/0/viewer?mid=1wTIeHwmiHN2QQcL_ySY7_rmLaxHkan6o) |

### `iceland_places` — sights and tours

`category, name, lat, lon`. Categories are the map's own layers:

| Layer | Count | Layer | Count |
|---|---|---|---|
| Points of Interest | 135 | Hot springs | 19 |
| Hikes / Places to Hike | 46 | Caves | 13 |
| Cultural Centres & Museums | 42 | Game of Thrones filming locations | 7 |
| Tours and activities | 36 | The Ultimate Golden Circle Route | 4 |
| Waterfalls | 28 | The Ring Road | 2 |

### `iceland_campsites` — Útilegukortið camping card network

`name, region, address, zip_town, tel, email, website, open, km_from_reykjavik,
km_from_seydisfjordur, lat, lon, facilities, maps_url, page`.

Regions: West Iceland (4), Westfjords (6), North Iceland (9), East Iceland (4),
South Iceland (7). `facilities` is a `; `-separated list drawn from a controlled
vocabulary of 42 amenities (Toilets, Electricity, Hot tubs, Swimming pool, …).

### `iceland_gas_stations`

`brand, layer, lat, lon, locality`. Pins carry only brand names (`N1` ×15), so
`locality` is filled in by reverse geocoding — see `--geocode` below.

## Reproducing

```sh
python3 scripts/extract_mymaps.py                      # places + gas stations
python3 scripts/extract_mymaps.py gas_stations --geocode
python3 scripts/extract_campsites.py
```

`--geocode` is opt-in because it contacts OpenStreetMap's Nominatim (throttled
to ~1 req/s per their usage policy); without it no external service is used
beyond the map export itself.

## How the sources actually work

All three pages render their data client-side, so none of it is in the served
HTML. The scripts go to the underlying feeds instead:

- **Google My Maps** exposes every layer's placemarks as KML at
  `/maps/d/kml?mid=<id>`; `forcekml=1` returns plain XML instead of a zipped
  KMZ. Genuinely large maps get split across `NetworkLink` elements, so
  `extract_mymaps.py` aborts rather than silently emitting a partial export.
- **utilegukortid.is** is WordPress. The listing page renders 30 posts behind
  Divi's AJAX pagination, so `extract_campsites.py` queries the REST API
  (`/wp-json/wp/v2/posts?categories=46`) and checks the `X-WP-Total` header to
  confirm nothing is missing.
- **Coordinates** for campsites come out of the embedded Google Maps URLs,
  which encode position in the `pb` parameter as `!2d<lon>!3d<lat>` —
  longitude first.
- **Campsite amenities** are icon images with no text, but each `<img>` carries
  a bilingual `alt` (`"Salerni / Toilets"`); the half after the slash gives a
  clean English vocabulary.

## Known data quirks

These come from the sources and are preserved as-is rather than silently fixed:

- `iceland_places` contains the map owner's duplicates (Akranes, Ólafsvík,
  Drangsnes, Landmannalaugar, Snæfellsjökull, Gullfoss, Hellissandur each appear
  twice), some non-places (`Point 19`, `Hot-dog stand`), and inconsistent
  transliteration (`Seyðisfjörður` vs `Seydisfjordur`). Its "Tours and
  activities" layer lists activities rather than places.
- `iceland_campsites` is the ~30 sites the Útilegukortið camping card covers,
  **not** every campsite in Iceland (there are ~170 nationwide). Þorlákshöfn's
  opening season isn't stated parseably on its page; 5 sites omit zip/town and
  6 omit a website. Akranes lists `48,5` km — an Icelandic decimal comma.
- `iceland_gas_stations` has one duplicated pin (`64.3098, -20.3017`), and 9
  rural ring-road points that Nominatim can't resolve to a locality. It is a
  hand-curated subset, not all Icelandic filling stations.

Data belongs to the respective sources; this repo is just the extraction.
