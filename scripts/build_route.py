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
import unicodedata
import math
import re
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
    "Borgarnes": (64.5383, -21.9224),
    "Siglufjörður": (66.1496, -18.9127),
    "Skagaströnd": (65.8292, -20.3147),
    "Möðrudalur": (65.3682, -15.9177),
    "Fáskrúðsfjörður": (64.9333, -14.0167),
    "Reykjavík city walk": (64.1426, -21.9264),
}

# stop = (name, kind). kind drives the icon/treatment on the site.
COUNTERCLOCKWISE = [
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


CLOCKWISE = [
    {
        "day": 0,
        "title": "Reykjavík on foot",
        "summary": "Your spare day. The core is walkable and costs nothing but coffee.",
        "note": "Hallgrímskirkja → Sun Voyager → Harpa is about 2 km along the shore. Grótta at low "
                "tide or the Videy ferry fills an afternoon. None of it needs a car.",
        "free_day": True,
        "stops": [
            ("Reykjavík city walk", "start"),
            ("Hallgrimskirkja", "sight"),
            ("Sólfarið (Sun Voyager)", "sight"),
            ("Harpa Concert Hall and Conference Centre", "sight"),
            ("Grótta Island Lighthouse", "optional"),
            ("Videy", "optional"),
        ],
        "night": None,
        "no_drive": True,
    },
    {
        "day": 1,
        "title": "North through Borgarfjörður",
        "summary": "Out of the city the quiet way, up the west coast.",
        "note": "Hraunfossar charges for parking; Deildartunguhver itself is free to look at "
                "(the Krauma spa next to it is not).",
        "stops": [
            ("Reykjavík", "start"),
            ("Borgarnes", "town"),
            ("Deildartunguhver", "sight"),
            ("Hraunfossar & Barnafoss", "sight"),
        ],
        "night": "Tjaldsvæðið búðardal",
    },
    {
        "day": 2,
        "title": "Vatnsnes and the north coast",
        "summary": "Empty road, seals, and the horse-shaped sea stack.",
        "note": "Everything today is free. Longest stretch without a fuel stop on either plan.",
        "stops": [
            ("Hvitserkur", "sight"),
            ("Blönduós", "town"),
            ("Skagaströnd", "town"),
            ("Síldarminjasafn Íslands - The Herring Era Museum", "optional"),
        ],
        "night": "Siglufjörður",
    },
    {
        "day": 3,
        "title": "Akureyri, Goðafoss and the whales",
        "summary": "Short driving day, built around the Húsavík split.",
        "split": {
            "where": "Húsavík harbour",
            "note": "Both leave from the same harbour, about 100 m apart — regroup on the quay.",
            "options": [
                {"who": "Boat", "what": "Whale watching", "where": "Húsavík harbour",
                 "duration": "~3 h", "book": "The single most expensive stop on the trip. Book ahead; weather-dependent."},
                {"who": "Museum", "what": "Húsavík Whale Museum", "where": "Hafnarstétt 1",
                 "duration": "~1.5 h", "book": "Walk in, roughly a fifth of the boat price."},
            ],
        },
        "stops": [
            ("Akureyri", "town"),
            ("Góðafoss", "sight"),
            ("Húsavík harbour", "split"),
        ],
        "night": "Húsavík",
    },
    {
        "day": 4,
        "title": "Ásbyrgi, Dettifoss, Mývatn",
        "summary": "The geothermal day. Free apart from one car park and the optional baths.",
        "note": "Hverir charges for parking. Mývatn Nature Baths is a per-person ticket — the "
                "one genuinely optional spend today.",
        "stops": [
            ("Ásbyrgi Canyon", "sight"),
            ("Dettifoss", "sight"),
            ("Hverír", "sight"),
            ("Grjótagjá", "sight"),
            ("Dimmuborgir", "sight"),
            ("Myvatn Nature Baths", "optional"),
        ],
        "night": "Möðrudalur – Fjalladýrð",
    },
    {
        "day": 5,
        "title": "Stuðlagil and the east fjords",
        "summary": "Basalt columns, then down the fjord road.",
        "note": "Stuðlagil is free; the walk from the east-bank car park is the good one.",
        "stops": [
            ("Stuðlagil Canyon", "sight"),
            ("Egilsstaðir", "town"),
            ("Fáskrúðsfjörður", "town"),
            ("Petra's Stone Collection", "optional"),
        ],
        "night": "Tjaldvæðið Bragðavöllum",
    },
    {
        "day": 6,
        "title": "Glacier lagoon and Skaftafell",
        "summary": "The big one, mirrored from the other direction. Start early.",
        "note": "Four paid car parks in a row today — Jökulsárlón, Diamond Beach, Skaftafell and "
                "Fjaðrárgljúfur. Same 330 km campsite gap as the other plan, just reversed.",
        "stops": [
            ("Stokksnes and Vestrahorn", "optional"),
            ("Höfn", "town"),
            ("Jökulsárlón Glacial Lagoon", "sight"),
            ("Diamond Beach", "sight"),
            ("Skaftafell", "sight"),
            ("Svartifoss waterfall (Parking)", "hike"),
            ("Fjaðrárgljúfur", "sight"),
        ],
        "night": "Kleifarmörk",
    },
    {
        "day": 7,
        "title": "South coast home",
        "summary": "The postcard run, in reverse, on the way back to the city.",
        "half": True,
        "note": "Not really a half day — five headline stops and 4 h of driving. If you are flying "
                "out this evening, drop Dyrhólaey and Gljúfrafoss.",
        "stops": [
            ("Vík í Mýrdal", "town"),
            ("Reynisfjara Beach", "sight"),
            ("Dyrhólaey", "sight"),
            ("Skógafoss", "sight"),
            ("Seljalandsfoss", "sight"),
            ("Reykjavík", "end"),
        ],
        "night": None,
    },
]

VARIANTS = {
    "counter-clockwise": {
        "label": "Counter-clockwise (south coast first)",
        "days": COUNTERCLOCKWISE,
        "note": "South coast early, empty north-west transit late. The half day at the end is short.",
    },
    "clockwise": {
        "label": "Clockwise (north first)",
        "days": CLOCKWISE,
        "note": "North first, south coast last. Includes a free Reykjavík day, but the Golden "
                "Circle drops out and the final day is not really a half day.",
    },
}


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


def nkey(s):
    s = unicodedata.normalize("NFC", str(s)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).casefold().strip()


def cost_band(tickets):
    """Group the curated tickets field into something you can budget against.

    Car-park fees are per car and small; the per-person tickets are where the
    money actually goes, so they are kept separate rather than lumped as 'paid'.
    """
    t = (tickets or "").lower()
    if not t or "not assessed" in t:
        return "unknown"
    if "free" in t and "tour fee" not in t:
        return "free"
    if "parking" in t or "shuttle" in t:
        return "parking fee (per car)"
    if "pre-booking" in t or "entrance" in t or "tour fee" in t or "reservation" in t:
        return "ticket (per person)"
    return "unknown"


def main():
    # simplify() recurses once per polyline split; OSRM legs are ~4k points deep.
    sys.setrecursionlimit(20000)
    places = load("iceland_places.csv")
    camps = load("iceland_campsites.csv")
    camp_pts = {n: (float(c["lat"]), float(c["lon"])) for n, c in camps.items()}

    ranked = {}
    with open(DATA / "iceland_places_ranked.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ranked[nkey(r["name"])] = r

    def coord(name):
        if name in EXTRA:
            return EXTRA[name]
        if name in places:
            return (float(places[name]["lat"]), float(places[name]["lon"]))
        raise SystemExit(f"no coordinates for stop: {name!r}")

    out_variants = {}
    for key, spec in VARIANTS.items():
        days, cursor = [], REYKJAVIK
        for d_spec in spec["days"]:
            stops = []
            for name, kind in d_spec["stops"]:
                lat, lon = coord(name)
                rk = ranked.get(nkey(name), {})
                stops.append({
                    "name": name, "kind": kind, "lat": lat, "lon": lon,
                    "category": rk.get("category", ""),
                    "tier": rk.get("tier", ""),
                    "popularity": rk.get("popularity", ""),
                    "tickets": rk.get("tickets", ""),
                    "cost": cost_band(rk.get("tickets")),
                })

            night = camps.get(d_spec["night"]) if d_spec["night"] else None

            if d_spec.get("no_drive"):
                leg = {"km": 0.0, "hours": 0.0, "geometry": []}
                end = cursor
            else:
                waypoints = [cursor] + [(s["lat"], s["lon"]) for s in stops]
                if night:
                    waypoints.append(camp_pts[d_spec["night"]])
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
                **{k: v for k, v in d_spec.items() if k not in ("stops", "night")},
                "stops": stops,
                "km": leg["km"],
                "driving_hours": leg["hours"],
                "geometry": leg["geometry"],
                "long_day": leg["km"] > 300 or leg["hours"] > 5.0,
                "night": ({"name": night["name"], "lat": float(night["lat"]),
                           "lon": float(night["lon"]), "open": night["open"],
                           "tel": night["tel"], "website": night["website"],
                           "facilities": night["facilities"], "page": night["page"]}
                          if night else None),
                "nearby_campsites": nearby,
            })
            cursor = end
            print(f"  day {d_spec['day']}: {leg['km']:>6.1f} km  {leg['hours']:>4.1f} h  "
                  f"-> {d_spec['night'] or 'Reykjavík'}")

        paid_parking = sum(1 for d in days for s in d["stops"] if s["cost"] == "parking fee (per car)")
        tickets = sum(1 for d in days for s in d["stops"] if s["cost"] == "ticket (per person)")
        out_variants[key] = {
            "label": spec["label"],
            "note": spec["note"],
            "direction": key,
            "total_km": round(sum(d["km"] for d in days), 1),
            "total_driving_hours": round(sum(d["driving_hours"] for d in days), 1),
            "paid_parking_stops": paid_parking,
            "per_person_ticket_stops": tickets,
            "days": days,
        }
        print(f"{spec['label']}: {out_variants[key]['total_km']} km / "
              f"{out_variants[key]['total_driving_hours']} h · "
              f"{paid_parking} paid car parks, {tickets} per-person tickets\n")

    out = {
        "title": "Iceland Ring Road — 6.5 days",
        "start": "Reykjavík", "end": "Reykjavík",
        "default": "counter-clockwise",
        "variants": out_variants,
    }
    (DATA / "routes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written to {DATA / 'routes.json'}")


if __name__ == "__main__":
    main()
