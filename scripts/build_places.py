#!/usr/bin/env python3
"""Build the ranked places table from the scraped map plus hand-curated notes.

Replaces the earlier rank_iceland_places.py. Same 43 curated assessments (now
held in data/curated_places.json), but four corrections:

1. Confidence is explicit. Only 43 of 300-odd places were ever assessed; the
   rest previously received defaults that were indistinguishable from real
   judgements -- "Moderate (2WD/Gravel)" and "Yes - Fully Open" on 244 and 273
   rows respectively. Anything unassessed now says so, and the optimistic
   defaults are gone. Herdubreid and Eldgja sit on F-roads and used to read as
   2WD-drivable and fully open in September, which is the one error that could
   actually put someone in a river.
2. Duplicates are collapsed. The source map lists Gullfoss, Myvatn,
   Landmannalaugar, Drangsnes, Snaefellsjokull, Akranes and Hellissandur twice.
3. Regions come from OpenStreetMap (Nominatim `state_district`), giving the
   eight official Icelandic regions instead of 17 overlapping guessed labels.
4. Linear features (The Ring Road, Golden Circle Route) are marked as routes
   rather than pinned to a point in Reykjavik that skewed the density counts.

Writes data/iceland_places_ranked.csv and .json.
"""

import csv
import json
import math
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
GEO_CACHE = DATA / "geo_cache.json"

NOT_ASSESSED = "Not assessed"

# Curated names arrived NFD-normalised from the original script while the scraped
# CSV is NFC, so accented names compared unequal. Match on a normalised key.
def nkey(s):
    s = unicodedata.normalize("NFC", s).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).casefold().strip()

# Typos in the curated data, mapped to the scraped name they meant.
ALIASES = {nkey("Kirkjefellsfoss"): nkey("Kirkjufellsfoss")}

DUPLICATE_RADIUS_KM = 2.0

# Nominatim's state_district, in English. These are the eight official regions --
# one consistent taxonomy for every row, curated or not.
REGION_EN = {
    "Höfuðborgarsvæðið": "Capital",
    "Suðurnes": "Reykjanes",
    "Vesturland": "West",
    "Vestfirðir": "Westfjords",
    "Norðurland vestra": "Northwest",
    "Norðurland eystra": "Northeast",
    "Austurland": "East",
    "Suðurland": "South",
}

# Named linear features on the source map -- they have no meaningful single point.
ROUTES = {"The Ring Road", "Golden Circle Route", "Laugavegur trail", "Fimmvörðuháls trail"}

# Effort inferred from the map layer. Genuinely a guess, and labelled as one.
HIKE_BY_CATEGORY = {
    "Hikes / Places to Hike": "Some walking (inferred from category)",
    "Points of Interest": "Little or none (inferred from category)",
    "Waterfalls": "Little or none (inferred from category)",
    "Caves": "Short walk (inferred from category)",
    "Hot springs": "Little or none (inferred from category)",
    "Cultural Centres & Museums": "None (inferred from category)",
    "Tours and activities": NOT_ASSESSED,
    "Game of Thrones filming locations": NOT_ASSESSED,
}

COLUMNS = [
    "name", "category", "attraction_type", "region", "tourist_area", "locality", "municipality",
    "tier", "popularity", "accessibility", "open_in_september", "best_season",
    "needs_hiking", "duration", "tickets", "photography",
    "confidence", "spots_within_25km", "spots_within_50km",
    "is_route", "lat", "lon", "maps_url",
]


def haversine(a, b):
    r = 6371.0
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def main():
    curated_file = json.loads((DATA / "curated_places.json").read_text(encoding="utf-8"))
    curated = {ALIASES.get(nkey(k), nkey(k)): v for k, v in curated_file["places"].items()}
    coord_fixes = {k: tuple(v) for k, v in curated_file["coord_fixes"].items()}
    geo = json.loads(GEO_CACHE.read_text(encoding="utf-8")) if GEO_CACHE.exists() else {}

    rows, kept = [], []
    duplicates = 0
    for r in csv.DictReader(open(DATA / "iceland_places.csv", encoding="utf-8")):
        name = r["name"].strip()
        lat = float(r["lat"]) if r["lat"] else None
        lon = float(r["lon"]) if r["lon"] else None
        # coord_fixes wins outright: it covers both the linear features that have
        # no point at all, and names the geocoder resolved to the wrong real place.
        if name in coord_fixes:
            lat, lon = coord_fixes[name]

        # The source map pins several places twice, up to ~1.1 km apart.
        k = nkey(name)
        if any(k == pk and (lat is None or haversine((lat, lon), pp) <= DUPLICATE_RADIUS_KM)
               for pk, pp in kept):
            duplicates += 1
            continue
        kept.append((k, (lat, lon) if lat else (0.0, 0.0)))

        c = curated.get(k, {})
        g = geo.get(f"{round(lat, 5)},{round(lon, 5)}", {}) if lat else {}
        is_route = name in ROUTES

        rows.append({
            "name": name,
            "category": r["category"],
            "attraction_type": c.get("attraction_type", r["category"]),
            "region": REGION_EN.get(g.get("region", ""), g.get("region") or NOT_ASSESSED),
            "tourist_area": c.get("region", ""),
            "locality": g.get("locality", ""),
            "municipality": g.get("county", ""),
            "tier": c.get("tier", "Unranked"),
            "popularity": c.get("popularity", NOT_ASSESSED),
            "accessibility": c.get("accessibility", NOT_ASSESSED),
            "open_in_september": c.get("open_in_september", NOT_ASSESSED),
            "best_season": c.get("best_season", NOT_ASSESSED),
            "needs_hiking": c.get("needs_hiking") or HIKE_BY_CATEGORY.get(r["category"], NOT_ASSESSED),
            "duration": c.get("duration", NOT_ASSESSED),
            "tickets": c.get("tickets", NOT_ASSESSED),
            "photography": c.get("photography", NOT_ASSESSED),
            "confidence": "curated" if k in curated else "not assessed",
            "is_route": "yes" if is_route else "",
            "lat": lat if lat else "",
            "lon": lon if lon else "",
            "maps_url": f"https://www.google.com/maps?q={lat},{lon}" if lat else "",
        })

    # Density counts over real points only -- routes have no meaningful location.
    pts = [(i, (r["lat"], r["lon"])) for i, r in enumerate(rows) if r["lat"] and not r["is_route"]]
    for i, a in pts:
        n25 = n50 = 0
        for j, b in pts:
            if i == j:
                continue
            d = haversine(a, b)
            n25 += d <= 25
            n50 += d <= 50
        rows[i]["spots_within_25km"], rows[i]["spots_within_50km"] = n25, n50
    for r in rows:
        r.setdefault("spots_within_25km", "")
        r.setdefault("spots_within_50km", "")

    tier_rank = {"Tier 1 (S-Tier)": 0, "Tier 2 (A-Tier)": 1, "Tier 3 (B-Tier)": 2,
                 "Tier 4 (C-Tier)": 3, "Unranked": 4}
    rows.sort(key=lambda r: (tier_rank.get(r["tier"], 9), r["category"], r["name"]))

    with (DATA / "iceland_places_ranked.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in COLUMNS} for r in rows)
    (DATA / "iceland_places_ranked.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    assessed = sum(1 for r in rows if r["confidence"] == "curated")
    located = sum(1 for r in rows if r["region"] != NOT_ASSESSED and r["region"])
    print(f"{len(rows)} places ({duplicates} duplicates collapsed)")
    print(f"  curated: {assessed}   not assessed: {len(rows) - assessed}")
    print(f"  region resolved: {located}/{len(rows)}")


if __name__ == "__main__":
    main()
