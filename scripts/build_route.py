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
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OSRM = "https://router.project-osrm.org/route/v1/driving/"

REYKJAVIK = (64.1466, -21.9426)
# Car is collected and dropped at the airport, so the loop starts and ends here.
AIRPORT = (63.9850, -22.6056)

# Road trip runs day 1 to day 6; the outbound flight is 17:00 on day 6, so the
# car has to be back at KEF by about 15:00. Reykjavik is handled before day 1.
START_DATE = datetime.date(2026, 9, 12)     # Reykjavik is the 11th, before this
FLIGHT_HOME = "17:00 on Fri 18 Sept"
DAY_START_HOUR = 7.0                        # early starts are fine, and needed
LATEST_FINISH_DAY6 = 15.0                   # car back at KEF by 15:00 on the 18th
SUNSET_HOUR = 20.0                          # Reykjavik sets ~20:20 on 12 Sep, ~20:00 on the 18th

_MONTHS = {**{m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)},
    **{m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "maí", "jún", "júl", "ágú", "sep", "okt", "nóv", "des"], 1)}}


def season(text):
    """Parse a campsite's opening season. The field is hand-typed in a mix of
    English and Icelandic ("1st of June - 30th of September", "23. maí -
    31. ágúst", "all year round"), so match day/month pairs in either order."""
    t = (text or "").lower().replace("–", "-").replace("—", "-")
    if "all year" in t:
        return (1, 1), (31, 12)
    found = []
    for a, b, c, d in re.findall(
            r"(\d{1,2})\s*(?:st|nd|rd|th|\.)?\s*(?:of\s+)?([a-záéíóúýþæö]{3,})"
            r"|([a-záéíóúýþæö]{3,})\s*\.?\s*(\d{1,2})", t):
        day, mon = (a, b) if a else (d, c)
        if mon[:3] in _MONTHS:
            found.append((int(day), _MONTHS[mon[:3]]))
    return (found[0], found[1]) if len(found) >= 2 else None


def open_on(camp_open, date):
    """True/False if the season parses, None if it does not."""
    sp = season(camp_open)
    if not sp:
        return None
    (d1, m1), (d2, m2) = sp
    return datetime.date(date.year, m1, d1) <= date <= datetime.date(date.year, m2, d2)

# Stops that aren't in iceland_places.csv but the route needs.
EXTRA = {
    "Reykjavík": REYKJAVIK,
    "Keflavík Airport": AIRPORT,
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
# Rough time on the ground per stop, so a day has a length and not just a
# distance. "quick" is a roadside look or a five-minute walk.
STOP_MINUTES = {
    "start": 30, "end": 0, "town": 20, "quick": 15,
    "sight": 35, "hike": 90, "optional": 30, "split": 180,
    "swim": 60, "tour": 45,
}
TIER1_SIGHT_MINUTES = 45

# 12-18 September. Six nights, then the car is back at KEF for a 17:00 flight.
# Covers south, east, north and west including Snaefellsnes, with the whale
# boat at Husavik. Nights are wherever the driving wants them -- no card.
FINAL = [
    {"day": 1, "title": "Golden Circle, then south",
     "summary": "Straight off the plane into the classics, then down to the south coast.",
     "note": "Early start pays for itself all week. Shop in Selfoss — last big supermarket "
             "before the south coast.",
     "stops": [("Keflavík Airport", "start"), ("Þingvellir National Park", "sight"),
               ("Öxarárfoss", "quick"), ("Lögberg", "quick"), ("Geysir Geothermal Area", "sight"),
               ("Strokkur Geyser", "quick"), ("Gullfoss", "sight"), ("Brúarhlöð", "quick"),
               ("Kerið", "optional"), ("Urridafoss", "quick")],
     "night": "Tjaldsvæðið Hvolsvelli"},
    {"day": 2, "title": "Every waterfall on the south coast",
     "summary": "Six waterfalls, two headlands, a black beach and the Klaustur cluster.",
     "note": "Gljúfrafoss is 600 m from Seljalandsfoss and half of people miss it. The five "
             "stops around Kirkjubæjarklaustur are within a kilometre of Route 1 — ten minutes each.",
     "stops": [("Seljalandsfoss", "sight"), ("Gljúfrafoss", "quick"), ("Skógafoss", "sight"),
               ("Kvarnarhólsárfoss", "quick"), ("Dyrhólaey", "sight"),
               ("Dyrhólaey lighthouse", "quick"), ("Reynisfjara Beach", "sight"),
               ("Vík í Mýrdal", "town"), ("Fjaðrárgljúfur", "sight"), ("Stjórnarfoss", "quick"),
               ("Systrafoss", "quick"), ("Kirkjugólf", "quick"), ("Foss á Sídu", "quick"),
               ("Dverghamrar", "quick")],
     "night": "Skaftafell"},
    {"day": 3, "title": "Glacier lagoon and the south-east corner",
     "summary": "Svartifoss before breakfast crowds, then the lagoon and Vestrahorn.",
     "note": "You are camped inside the national park, so Svartifoss is a first-thing walk with "
             "nobody on it. Stokksnes is private land, about 1,000 ISK.",
     "stops": [("Svartifoss waterfall (Parking)", "hike"), ("Hofskirkja", "quick"),
               ("Jökulsárlón Glacial Lagoon", "sight"), ("Diamond Beach", "sight"),
               ("Höfn", "town"), ("Stokksnes and Vestrahorn", "sight")],
     "night": "Camping Berunes"},
    {"day": 4, "title": "East fjords, Stuðlagil and Mývatn",
     "summary": "The fjord road, the basalt canyon, then the whole geothermal lake in the evening.",
     "note": "Stuðlagil's east-bank car park is the one with the good walk down. The Mývatn "
             "cluster is done this evening rather than tomorrow, which is what keeps day 6 sane.",
     "stops": [("Petra's Stone Collection", "optional"), ("Fáskrúðsfjörður", "town"),
               ("Reyðarfjörður", "quick"), ("Egilsstaðir", "town"), ("Fardagafoss", "quick"),
               ("Stuðlagil Canyon", "sight"), ("Krafla Power Plant", "quick"),
               ("Hverír", "sight"), ("Grjótagjá", "quick"), ("Dimmuborgir", "sight")],
     "night": "Hlíð"},
    {"day": 5, "title": "Dettifoss, the whales, then west",
     "summary": "Dettifoss early, the boat at Húsavík, then Goðafoss and a run west.",
     "note": "Book the whale trip now — September sailings fill and get cancelled for weather. "
             "An afternoon departure leaves the morning for Dettifoss and the lake.",
     "split": {"where": "Húsavík harbour",
               "note": "Both leave from the same harbour, about 100 m apart — regroup on the quay.",
               "options": [
                   {"who": "Boat", "what": "Whale watching", "where": "Húsavík harbour",
                    "duration": "~3 h", "book": "Book ahead. The one big spend of the trip."},
                   {"who": "Museum", "what": "Húsavík Whale Museum", "where": "Hafnarstétt 1",
                    "duration": "~1.5 h", "book": "For anyone not sailing, or if it blows out."}]},
     "stops": [("Dettifoss", "sight"), ("Húsavík harbour", "split"), ("Góðafoss", "sight"),
               ("Akureyri", "town")],
     "night": "Blönduós"},
    {"day": 6, "title": "North coast to Snæfellsnes",
     "summary": "Vatnsnes in the morning, then the whole Snæfellsnes loop.",
     "note": "The monster — expect to finish after dark, which is fine on Route 1 and the 54. "
             "Drop Kolugljúfur and Borgarvirki first if you are behind. Grundarfjörður's campsite "
             "shut on 15 September, so tonight is Arnarstapi on the south side — which also makes "
             "the flight morning short.",
     "stops": [("Vatnsdalshólar", "quick"), ("Borgarvirki", "quick"),
               ("Hvitserkur", "sight"), ("Kolugljúfur", "quick"), ("Borgarnes", "town"),
               ("Gerduberg Cliffs", "quick"), ("Kirkjufell", "sight"), ("Kirkjufellsfoss", "quick"),
               ("Olafsvík", "town"), ("Saxhóll", "quick"), ("Djúpalónssandur", "sight"),
               ("Londrangar Basalt Cliffs", "quick")],
     "night": "Tjaldsvæðið á Arnastapa"},
    {"day": 7, "title": "Snæfellsnes south, then the plane", "half": True,
     "summary": "Three stops on the doorstep, then a clear run to Keflavík.",
     "note": "Deliberately short. Aim to be at KEF by 15:00 for the 17:00 flight — you should "
             "manage it by lunchtime with an early start.",
     "stops": [("Arnarstapi", "sight"), ("Rauðfeldsgjá Gorge", "quick"), ("Búðir church", "quick"),
               ("Borgarnes", "town"), ("Keflavík Airport", "end")],
     "night": None},
]

# Same week, same flight, but the Golden Circle comes out and the hours go into
# the north instead: Asbyrgi, which is nearly free because Route 862 is a
# through-road, and the Trollaskagi coast, which costs 1.4 h more than the
# Route 1 shortcut it replaces. Buys back enough slack to do Snaefellsnes over a
# day and a morning rather than one 11.7 h push, so nothing finishes after dark.
NORTH = [
    {"day": 1, "title": "Out of Reykjavík, the whole south coast",
     "summary": "Six waterfalls, two headlands, a black beach, finishing at the canyon.",
     "note": "Gljúfrafoss is 600 m from Seljalandsfoss and half of people miss it. Shop in "
             "Selfoss — last big supermarket before the south coast.",
     "stops": [("Reykjavík", "start"), ("Urridafoss", "quick"), ("Seljalandsfoss", "sight"),
               ("Gljúfrafoss", "quick"), ("Skógafoss", "sight"), ("Kvarnarhólsárfoss", "quick"),
               ("Dyrhólaey", "sight"), ("Dyrhólaey lighthouse", "quick"),
               ("Reynisfjara Beach", "sight"), ("Vík í Mýrdal", "town"),
               ("Fjaðrárgljúfur", "sight")],
     "night": "Kirkjubær II"},
    {"day": 2, "title": "Klaustur cluster, Svartifoss and the glacier lagoon",
     "summary": "Five stops within a kilometre of the road, then the park, the lagoon, Vestrahorn.",
     "note": "The five stops around Kirkjubæjarklaustur are ten minutes each. Svartifoss is a "
             "45-minute walk up from the Skaftafell car park — you are not camped at the foot of "
             "it in this version, so expect company. Stokksnes is private land, about 1,000 ISK.",
     "stops": [("Stjórnarfoss", "quick"), ("Systrafoss", "quick"), ("Kirkjugólf", "quick"),
               ("Foss á Sídu", "quick"), ("Dverghamrar", "quick"),
               ("Svartifoss waterfall (Parking)", "hike"), ("Hofskirkja", "quick"),
               ("Jökulsárlón Glacial Lagoon", "sight"), ("Diamond Beach", "sight"),
               ("Höfn", "town"), ("Stokksnes and Vestrahorn", "sight")],
     "night": "Camping Berunes"},
    {"day": 3, "title": "East fjords, Stuðlagil and Mývatn",
     "summary": "The fjord road, the basalt canyon, then the whole geothermal lake in the evening.",
     "note": "Stuðlagil's east-bank car park is the one with the good walk down, and the 38 km "
             "round trip down Jökuldalur is the most expensive single detour in the week — it is "
             "the first thing to drop if the weather turns.",
     "stops": [("Petra's Stone Collection", "optional"), ("Fáskrúðsfjörður", "town"),
               ("Reyðarfjörður", "quick"), ("Egilsstaðir", "town"), ("Fardagafoss", "quick"),
               ("Stuðlagil Canyon", "sight"), ("Krafla Power Plant", "quick"),
               ("Hverír", "sight"), ("Grjótagjá", "quick"), ("Dimmuborgir", "sight")],
     "night": "Hlíð"},
    {"day": 4, "title": "Dettifoss, Ásbyrgi and the whales",
     "summary": "The Diamond Circle done properly, including the canyon most people drive past.",
     "note": "Route 862 is paved the whole way from Route 1 north to Route 85, so Dettifoss and "
             "Ásbyrgi sit on a through-road rather than an out-and-back — Ásbyrgi costs eleven "
             "minutes of driving. Book the whale trip now; September sailings fill and get "
             "cancelled for weather. Akureyri's own campsite is not in the OSM extract, so "
             "tonight is Vaglaskógur in the forest 20 km east, and Akureyri opens tomorrow.",
     "split": {"where": "Húsavík harbour",
               "note": "Both leave from the same harbour, about 100 m apart — regroup on the quay.",
               "options": [
                   {"who": "Boat", "what": "Whale watching", "where": "Húsavík harbour",
                    "duration": "~3 h", "book": "Book ahead. The one big spend of the trip."},
                   {"who": "Museum", "what": "Húsavík Whale Museum", "where": "Hafnarstétt 1",
                    "duration": "~1.5 h", "book": "For anyone not sailing, or if it blows out."}]},
     "stops": [("Dettifoss", "sight"), ("Ásbyrgi Canyon", "sight"),
               ("Húsavík harbour", "split"), ("Góðafoss", "sight")],
     "night": "Vaglaskógur"},
    {"day": 5, "title": "The Tröllaskagi coast",
     "summary": "Akureyri, then the north coast road instead of Route 1 — Siglufjörður and a soak.",
     "note": "Route 1 does Akureyri to Blönduós in two hours and shows you nothing. The coast "
             "road costs about 78 km and 1.4 h more and is the cheapest unseen ground on the "
             "trip. Grettislaug is two stone pots on the shore at Reykir facing Drangey, 17 km "
             "up a dead-end road past Sauðárkrókur — the pool Grettir swam ashore to in the "
             "saga. No closing time to race, unlike the municipal pool at Hofsós. Bring your "
             "own towels. No Vatnsnes today: Hvítserkur is a 68 km spur and you cannot have "
             "both peninsulas in one day. v4 takes that one.",
     "stops": [("Akureyri", "town"), ("Dalvik", "town"), ("Ólafsfjarðar", "quick"),
               ("Siglufjördur", "sight"), ("Sauðárkrókur", "town"),
               ("Grettislaug", "swim"), ("Borgarnes", "town")],
     "night": "Tjaldsvæðið Borgarnesi"},
    {"day": 6, "title": "Snæfellsnes, unhurried",
     "summary": "The whole peninsula with time to stop — Stykkishólmur, Kirkjufell, a lava tube.",
     "note": "v4 covers this same ground in one 11.7 h push; here it gets a day and a morning. "
             "Vatnshellir is a guided 45-minute descent on a fixed tour schedule, about "
             "5,900 ISK a head — turn up for a departure, you cannot just walk in. "
             "Grundarfjörður's campsite shut on 15 September, so tonight is Arnarstapi on the "
             "south side — which also makes the flight morning short.",
     "stops": [("Gerduberg Cliffs", "quick"), ("Stykkishólmur", "town"), ("Kirkjufell", "sight"),
               ("Kirkjufellsfoss", "quick"), ("Olafsvík", "town"), ("Saxhóll", "quick"),
               ("Djúpalónssandur", "sight"), ("Vatnshellir", "tour"),
               ("Londrangar Basalt Cliffs", "quick")],
     "night": "Tjaldsvæðið á Arnastapa"},
    {"day": 7, "title": "Snæfellsnes south, then the plane", "half": True,
     "summary": "Three stops on the doorstep, then a clear run to Keflavík.",
     "note": "Deliberately short. Aim to be at KEF by 15:00 for the 17:00 flight — you should "
             "manage it by lunchtime with an early start.",
     "stops": [("Arnarstapi", "sight"), ("Rauðfeldsgjá Gorge", "quick"), ("Búðir church", "quick"),
               ("Borgarnes", "town"), ("Keflavík Airport", "end")],
     "night": None},
]

# which variant the site opens on for a viewer who has never picked one
DEFAULT_VARIANT = "north"

VARIANTS = {
    "final": {"version": "v4", "label": "The whole island — 12–18 September", "days": FINAL,
              "note": "South, east, north and west including all of Snæfellsnes, with the "
                      "Húsavík whale boat. Six nights, no camping card, early starts. Day 6 "
                      "finishes after dark on purpose."},
    "north": {"version": "v5", "label": "The north coast — 12–18 September", "days": NORTH,
              "start": REYKJAVIK,
              "note": "No Golden Circle in this one, and no Vatnsnes. Those hours go north "
                      "instead — Ásbyrgi, which is eleven minutes of driving, and the "
                      "Tröllaskagi coast with Siglufjörður and a soak at Grettislaug. Starts "
                      "in Reykjavík, and Snæfellsnes gets a day and a morning rather than one "
                      "long push, so nothing finishes in the dark."},
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
    camps = load("iceland_campsites_all.csv")
    camp_pts = {n: (float(c["lat"]), float(c["lon"])) for n, c in camps.items()}

    ranked = {}
    with open(DATA / "iceland_places_ranked.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ranked[nkey(r["name"])] = r

    # Coordinates come from the raw scrape, so the same corrections build_places.py
    # applies have to be honoured here too -- otherwise a name the geocoder resolved
    # to the wrong real place silently routes the car there. Grettislaug is the case
    # that caught this: there is a hot spring of that name on Reykjaströnd and a
    # municipal pool of the same name in Reykhólar, 200 km apart.
    coord_fixes = json.loads(
        (DATA / "curated_places.json").read_text(encoding="utf-8"))["coord_fixes"]

    def coord(name):
        if name in EXTRA:
            return EXTRA[name]
        if name in coord_fixes:
            return tuple(coord_fixes[name])
        if name in places:
            return (float(places[name]["lat"]), float(places[name]["lon"]))
        raise SystemExit(f"no coordinates for stop: {name!r}")

    out_variants = {}
    for key, spec in VARIANTS.items():
        # most variants collect the car at KEF; one starts from town instead
        days, cursor = [], spec.get("start", AIRPORT)
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
                    "minutes": (TIER1_SIGHT_MINUTES
                                if kind == "sight" and rk.get("tier", "").startswith("Tier 1")
                                else STOP_MINUTES.get(kind, 30)),
                })

            date = START_DATE + datetime.timedelta(days=d_spec["day"] - 1)
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

            # only offer alternatives that are actually open that night
            nearby = sorted(
                ({"name": n, "km": round(haversine(end, p), 1),
                  "open": camps[n].get("card_open") or camps[n].get("opening_hours", ""),
                  "on_card": camps[n].get("on_card", ""), "lat": p[0], "lon": p[1]}
                 for n, p in camp_pts.items()
                 if open_on(camps[n].get("card_open"), date) is not False),
                key=lambda c: c["km"],
            )[:4]

            stop_hours = round(sum(s["minutes"] for s in stops) / 60, 1)
            day_hours = round(leg["hours"] + stop_hours, 1)
            finish = DAY_START_HOUR + day_hours
            night_open = open_on(night.get("card_open"), date) if night else None
            days.append({
                **{k: v for k, v in d_spec.items() if k not in ("stops", "night")},
                "stops": stops,
                "km": leg["km"],
                "driving_hours": leg["hours"],
                "stop_hours": stop_hours,
                "day_hours": day_hours,
                "over_daylight": finish > SUNSET_HOUR,
                "geometry": leg["geometry"],
                "long_day": leg["km"] > 300 or leg["hours"] > 5.0,
                "date": date.isoformat(),
                "date_label": f"{date:%a %-d %b}",
                "starts": f"{int(DAY_START_HOUR):02d}:{int(DAY_START_HOUR % 1 * 60):02d}",
                "finishes": f"{int(finish):02d}:{int(finish % 1 * 60):02d}",
                "flight_risk": bool(d_spec.get("half")) and finish > LATEST_FINISH_DAY6,
                "night_offcard": d_spec.get("night_offcard"),
                "night_open": night_open,
                "night": ({"name": night["name"], "date": date.isoformat(),
                           "lat": float(night["lat"]), "lon": float(night["lon"]),
                           "open": night.get("card_open") or night.get("opening_hours", ""),
                           "on_card": night.get("on_card", ""),
                           "tel": night.get("phone", ""), "website": night.get("website", ""),
                           "page": night.get("osm", "")}
                          if night else None),
                "nearby_campsites": nearby,
            })
            cursor = end
            flag = ""
            if night and night_open is False:
                flag = f"  *** {d_spec['night']} CLOSED ***"
            elif finish > SUNSET_HOUR:
                flag = "  << finishes after dark"
            print(f"  day {d_spec['day']} {date:%d %b}: {leg['km']:>6.1f} km  "
                  f"drive {leg['hours']:>4.1f} h  stops {stop_hours:>4.1f} h  "
                  f"= {day_hours:>4.1f} h  ends {int(DAY_START_HOUR + day_hours):02d}:00{flag}")

        paid_parking = sum(1 for d in days for s in d["stops"] if s["cost"] == "parking fee (per car)")
        tickets = sum(1 for d in days for s in d["stops"] if s["cost"] == "ticket (per person)")
        out_variants[key] = {
            "label": spec["label"],
            "version": spec["version"],
            "note": spec["note"],
            "start_date": START_DATE.isoformat(),
            "flight": FLIGHT_HOME,
            "offcard_nights": sum(1 for d in days
                                  if d.get("night") and not d["night"].get("on_card")),
            "closed_nights": sum(1 for d in days if d.get("night_open") is False),
            "direction": key,
            "total_km": round(sum(d["km"] for d in days), 1),
            "total_driving_hours": round(sum(d["driving_hours"] for d in days), 1),
            "total_stops": sum(len(d["stops"]) for d in days),
            "longest_day_hours": max(d["day_hours"] for d in days),
            "latest_finish": max(d["finishes"] for d in days),
            "nights": sum(1 for d in days if d["night"]),
            "paid_parking_stops": paid_parking,
            "per_person_ticket_stops": tickets,
            "days": days,
        }
        v = out_variants[key]
        print(f"{spec['label']}: {v['total_km']} km / {v['total_driving_hours']} h driving · "
              f"{v['total_stops']} stops · longest day {v['longest_day_hours']} h · "
              f"{paid_parking} car parks, {tickets} tickets\n")

    out = {
        "title": "Iceland Ring Road — 6.5 days",
        "start": "Keflavík Airport", "end": "Keflavík Airport",
        "default": DEFAULT_VARIANT,
        "start_date": START_DATE.isoformat(),
        "flight": FLIGHT_HOME,
        "variants": out_variants,
    }
    (DATA / "routes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # flat CSV of every stop in every variant, for sorting in a spreadsheet
    cols = ["variant", "version", "day", "date", "order", "name", "kind", "category",
            "tier", "popularity", "cost", "tickets", "minutes", "lat", "lon",
            "day_km", "day_driving_hours", "day_hours", "night", "night_on_card"]
    with (DATA / "route_stops.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for key, v in out_variants.items():
            for d in v["days"]:
                for i, st in enumerate(d["stops"], 1):
                    w.writerow({
                        "variant": key, "version": v["version"], "day": d["day"],
                        "date": d["date"], "order": i, "name": st["name"], "kind": st["kind"],
                        "category": st["category"], "tier": st["tier"],
                        "popularity": st["popularity"], "cost": st["cost"],
                        "tickets": st["tickets"], "minutes": st["minutes"],
                        "lat": st["lat"], "lon": st["lon"],
                        "day_km": d["km"], "day_driving_hours": d["driving_hours"],
                        "day_hours": d["day_hours"],
                        "night": d["night"]["name"] if d["night"] else "",
                        "night_on_card": d["night"]["on_card"] if d["night"] else "",
                    })
    print(f"written to {DATA / 'route_stops.csv'}")
    print(f"written to {DATA / 'routes.json'}")


if __name__ == "__main__":
    main()
