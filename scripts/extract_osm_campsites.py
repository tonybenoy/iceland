#!/usr/bin/env python3
"""All Iceland campsites from OpenStreetMap, not just the 30 on the camping card.

The Utilegukortid card covers ~30 sites and several shut in mid-September, which
made the itinerary look far more constrained than it is. OSM has the full
network (~215 named), so nights can be placed where the driving wants them.

Card membership is matched back on by proximity, so `on_card` still shows which
nights the card would pay for.

Writes data/iceland_campsites_all.csv / .json.
"""

import csv
import json
import math
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:90];
area["ISO3166-1"="IS"][admin_level=2]->.a;
(node["tourism"="camp_site"](area.a);way["tourism"="camp_site"](area.a););
out center tags;
"""


def haversine(a, b):
    r = 6371.0
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def main():
    req = urllib.request.Request(
        OVERPASS, data=urllib.parse.urlencode({"data": QUERY}).encode(),
        headers={"User-Agent": "iceland-data/1.0"})
    with urllib.request.urlopen(req, timeout=120) as f:
        elements = json.load(f)["elements"]

    card = []
    with open(DATA / "iceland_campsites.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["lat"]:
                card.append((r["name"], (float(r["lat"]), float(r["lon"])), r["open"]))

    rows = []
    for e in elements:
        t = e.get("tags", {})
        name = t.get("name")
        if not name:
            continue
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None:
            continue
        match = min(((haversine((lat, lon), p), n, o) for n, p, o in card), default=None)
        on_card = match is not None and match[0] <= 1.5
        rows.append({
            "name": name,
            "lat": round(lat, 6), "lon": round(lon, 6),
            "on_card": "yes" if on_card else "",
            "card_name": match[1] if on_card else "",
            "card_open": match[2] if on_card else "",
            "opening_hours": t.get("opening_hours", ""),
            "seasonal": t.get("seasonal", ""),
            "operator": t.get("operator", ""),
            "website": t.get("website", "") or t.get("contact:website", ""),
            "phone": t.get("phone", "") or t.get("contact:phone", ""),
            "shower": t.get("shower", ""),
            "toilets": t.get("toilets", ""),
            "drinking_water": t.get("drinking_water", ""),
            "power_supply": t.get("power_supply", ""),
            "osm": f"https://www.openstreetmap.org/{e['type']}/{e['id']}",
        })
    rows.sort(key=lambda r: r["name"])

    cols = list(rows[0])
    with (DATA / "iceland_campsites_all.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    (DATA / "iceland_campsites_all.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} named campsites ({sum(1 for r in rows if r['on_card'])} on the card)")


if __name__ == "__main__":
    main()
