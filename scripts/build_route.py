#!/usr/bin/env python3
"""Build the 6.5-day Ring Road itinerary, Reykjavik -> Reykjavik.

Every night lands at a campsite from data/iceland_campsites.csv (the
Utilegukortid card network), so the trip can be run on the card alone.

Driving distances and the map geometry are real road routing from OSRM, not
straight lines -- each day's waypoints are sent to the public OSRM server and
the returned geometry is stored in data/route.json for the site to draw.

For each night the three nearest card campsites are also recorded, so the site
can offer alternatives when the planned one is shut for the season.
"""

import csv
import json
import math
import sys
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OSRM = "https://router.project-osrm.org/route/v1/driving/"

REYKJAVIK = (64.1466, -21.9426)

# Stops that aren't in iceland_places.csv but the route needs.
EXTRA = {
    "Reykjavík": REYKJAVIK,
    "Húsavík harbour": (66.0455, -17.3410),
    "Húsavík Whale Museum": (66.0448, -17.3392),
    "Stuðlagil Canyon": (65.1651, -15.3153),
    "Skaftafell": (64.0166, -16.9666),
    "Vík í Mýrdal": (63.4187, -19.0060),
    "Kirkjubæjarklaustur": (63.7939, -18.0399),
    "Höfn": (64.2590, -15.2063),
    "Egilsstaðir": (65.2605, -14.4078),
    "Blönduós": (65.6602, -20.2759),
    "Deildartunguhver": (64.6634, -21.4114),
}

# stop = (name, kind). kind drives the icon/treatment on the site.
ITINERARY = [
    {
        "day": 1,
        "note": "Easiest day of the trip. If you land late, this is the one to compress.",
        "title": "Golden Circle",
        "summary": "An easy first day. Three headline stops, all paved, all within an hour of each other.",
        "stops": [
            ("Reykjavík", "start"),
            ("Þingvellir National Park", "sight"),
            ("Geysir Geothermal Area", "sight"),
            ("Strokkur Geyser", "sight"),
            ("Gullfoss", "sight"),
            ("Kerið", "optional"),
        ],
        "night": "At Faxi",
    },
    {
        "day": 2,
        "note": "Kleifarmörk is 37 km up a slow road off the ring — about an hour each way. It is the only card campsite between Vík and Djúpivogur, so the detour buys the card night. Camping at Vík instead saves roughly 73 km and 2 h across today and tomorrow.",
        "title": "South coast waterfalls to Vík",
        "summary": "The postcard stretch. Short walks, black sand, and the two waterfalls everyone knows.",
        "stops": [
            ("Seljalandsfoss", "sight"),
            ("Gljúfrafoss", "sight"),
            ("Skógafoss", "sight"),
            ("Dyrhólaey", "sight"),
            ("Reynisfjara Beach", "sight"),
            ("Vík í Mýrdal", "town"),
        ],
        "night": "Kleifarmörk",
    },
    {
        "day": 3,
        "note": "The long one. Leave by 08:00. The card network has no site for the 330 km between Vík and Djúpivogur, which is exactly why this day is oversized — a non-card site at Höfn would split it neatly if you would rather.",
        "title": "Glaciers and the lagoon",
        "summary": "The longest driving day, and the best one. Start early.",
        "stops": [
            ("Fjaðrárgljúfur", "sight"),
            ("Kirkjubæjarklaustur", "town"),
            ("Skaftafell", "sight"),
            ("Svartifoss waterfall (Parking)", "hike"),
            ("Jökulsárlón Glacial Lagoon", "sight"),
            ("Diamond Beach", "sight"),
            ("Höfn", "town"),
        ],
        "night": "Tjaldvæðið Bragðavöllum",
    },
    {
        "day": 4,
        "note": "Deliberately short to recover from day 3. Slack here if you want to add Petra\u2019s Stone Collection or a fjord swim.",
        "title": "East fjords to Stuðlagil",
        "summary": "Quiet fjord road, then inland to the basalt canyon.",
        "stops": [
            ("Fáskrúðsfjörður", "town"),
            ("Egilsstaðir", "town"),
            ("Stuðlagil Canyon", "sight"),
        ],
        "night": "Studlagil Canyon",
    },
    {
        "day": 5,
        "note": "Mývatn midges are gone by September but the smell at Hverir is not. Nature Baths take a booking.",
        "title": "Dettifoss and Mývatn",
        "summary": "Iceland's most powerful waterfall, then the geothermal lake district.",
        "stops": [
            ("Dettifoss", "sight"),
            ("Hverír", "sight"),
            ("Grjótagjá", "sight"),
            ("Dimmuborgir", "sight"),
            ("Myvatn Nature Baths", "optional"),
        ],
        "night": "Húsavík",
    },
    {
        "day": 6,
        "note": "Long transit after the whales. Whale watching (~3 h) versus the museum (~1.5 h) shifts your departure by over an hour — agree a regroup time at the harbour before you split.",
        "title": "Húsavík whales, then west",
        "summary": "Split the morning in Húsavík, regroup at the harbour, then the long transit west.",
        "split": {
            "where": "Húsavík harbour",
            "note": "Both options leave from the same harbour, about 100 m apart — regroup on the quay.",
            "options": [
                {"who": "Boat", "what": "Whale watching", "where": "Húsavík harbour",
                 "duration": "~3 h", "book": "Book ahead; sailings are weather-dependent."},
                {"who": "Museum", "what": "Húsavík Whale Museum", "where": "Hafnarstétt 1",
                 "duration": "~1.5 h", "book": "Walk in. Leaves time for the town and a coffee."},
            ],
        },
        "stops": [
            ("Húsavík harbour", "split"),
            ("Góðafoss", "sight"),
            ("Akureyri", "town"),
            ("Blönduós", "town"),
        ],
        "night": "Tjaldsvæðið búðardal",
    },
    {
        "day": 7,
        "note": "Kept short on purpose so it cannot threaten a flight. Both stops are optional if you are tight.",
        "title": "Half day back to Reykjavík",
        "summary": "Deliberately short so it can't threaten a flight. Two stops, then the city.",
        "half": True,
        "stops": [
            ("Hraunfossar & Barnafoss", "sight"),
            ("Deildartunguhver", "optional"),
            ("Reykjavík", "end"),
        ],
        "night": None,
    },
]


def haversine(a, b):
    r = 6371.0
    dlat, dlon = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a[0])) * math.cos(math.radians(b[0])) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def load(path, key="name"):
    rows = {}
    for r in csv.DictReader(open(DATA / path, encoding="utf-8")):
        if r.get("lat") and r["name"] not in rows:
            rows[r["name"]] = r
    return rows


def simplify(pts, tol=0.0004):
    """Douglas-Peucker. OSRM returns ~4k points per leg; at country zoom a ~40 m
    tolerance is invisible and cuts route.json from 1.2 MB to under 150 KB."""
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    span = math.hypot(dx, dy)
    worst, idx = -1.0, 0
    for i, (x, y) in enumerate(pts[1:-1], 1):
        d = (abs(dy * x - dx * y + x2 * y1 - y2 * x1) / span if span
             else math.hypot(x - x1, y - y1))
        if d > worst:
            worst, idx = d, i
    if worst <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def osrm(points):
    coords = ";".join(f"{lon},{lat}" for lat, lon in points)
    url = f"{OSRM}{coords}?overview=full&geometries=geojson"
    req = urllib.request.Request(url, headers={"User-Agent": "iceland-data/1.0"})
    with urllib.request.urlopen(req, timeout=60) as f:
        out = json.load(f)
    if out.get("code") != "Ok":
        raise SystemExit(f"OSRM: {out.get('code')} {out.get('message','')}")
    route = out["routes"][0]
    return {
        "km": round(route["distance"] / 1000, 1),
        "hours": round(route["duration"] / 3600, 1),
        "geometry": simplify([[round(lat, 5), round(lon, 5)]
                              for lon, lat in route["geometry"]["coordinates"]]),
    }


def main():
    # simplify() recurses once per polyline split; OSRM legs are ~4k points deep.
    sys.setrecursionlimit(20000)
    places = load("iceland_places.csv")
    camps = load("iceland_campsites.csv")
    camp_pts = {n: (float(c["lat"]), float(c["lon"])) for n, c in camps.items()}

    def coord(name):
        if name in EXTRA:
            return EXTRA[name]
        if name in places:
            return (float(places[name]["lat"]), float(places[name]["lon"]))
        raise SystemExit(f"no coordinates for stop: {name!r}")

    days, cursor = [], REYKJAVIK
    for spec in ITINERARY:
        stops = []
        for name, kind in spec["stops"]:
            lat, lon = coord(name)
            src = places.get(name, {})
            stops.append({"name": name, "kind": kind, "lat": lat, "lon": lon,
                          "category": src.get("category", "")})

        waypoints = [cursor] + [(s["lat"], s["lon"]) for s in stops]
        night = camps.get(spec["night"]) if spec["night"] else None
        if night:
            waypoints.append(camp_pts[spec["night"]])

        leg = osrm(waypoints)
        time.sleep(1.0)  # be polite to the public OSRM server

        end = waypoints[-1]
        nearby = sorted(
            ({"name": n, "km": round(haversine(end, p), 1),
              "open": camps[n]["open"], "lat": p[0], "lon": p[1]}
             for n, p in camp_pts.items()),
            key=lambda c: c["km"],
        )[:4]

        days.append({
            **{k: v for k, v in spec.items() if k not in ("stops", "night")},
            "stops": stops,
            "km": leg["km"],
            "driving_hours": leg["hours"],
            "geometry": leg["geometry"],
            "night": ({"name": night["name"], "lat": float(night["lat"]),
                       "lon": float(night["lon"]), "open": night["open"],
                       "tel": night["tel"], "website": night["website"],
                       "facilities": night["facilities"], "page": night["page"]}
                      if night else None),
            "nearby_campsites": nearby,
        })
        days[-1]["long_day"] = leg["km"] > 300 or leg["hours"] > 5.0
        cursor = end
        print(f"day {spec['day']}: {leg['km']:>6.1f} km  {leg['hours']:>4.1f} h  "
              f"-> {spec['night'] or 'Reykjavík'}")

    out = {
        "title": "Iceland Ring Road — 6.5 days",
        "start": "Reykjavík",
        "end": "Reykjavík",
        "direction": "counter-clockwise (south coast first)",
        "total_km": round(sum(d["km"] for d in days), 1),
        "total_driving_hours": round(sum(d["driving_hours"] for d in days), 1),
        "days": days,
    }
    (DATA / "route.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ntotal {out['total_km']} km / {out['total_driving_hours']} h driving")
    print(f"written to {DATA / 'route.json'}")


if __name__ == "__main__":
    main()
