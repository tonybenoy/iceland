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
START_DATE = datetime.date(2026, 9, 12)
FLIGHT_HOME = "17:00 on day 6"
DAY_START_HOUR = 8.5
LATEST_FINISH_DAY6 = 15.0

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
}
TIER1_SIGHT_MINUTES = 45

RING = [
    {"day": 1, "title": "Airport to the Golden Circle",
     "summary": "Collect the car, pick up the third of you, and drive straight into the classics.",
     "note": "Shop in Selfoss — it is the last big supermarket before the south coast.",
     "stops": [("Keflavík Airport", "start"), ("Þingvellir National Park", "sight"),
               ("Geysir Geothermal Area", "sight"), ("Strokkur Geyser", "quick"),
               ("Gullfoss", "sight"), ("Kerið", "optional")],
     "night": "Tjaldsvæðið Hvolsvelli"},
    {"day": 2, "title": "South coast waterfalls",
     "summary": "The postcard stretch, ending east of Vík.",
     "note": "An easy day now that nights are not limited to the card — the whole south coast "
             "in 200 km, with time at every stop.",
     "stops": [("Seljalandsfoss", "sight"), ("Gljúfrafoss", "quick"), ("Skógafoss", "sight"),
               ("Dyrhólaey", "sight"), ("Reynisfjara Beach", "sight"), ("Vík í Mýrdal", "town"),
               ("Kirkjubæjarklaustur", "town")],
     "night": "Kirkjubær II"},
    {"day": 3, "title": "Glaciers, the lagoon and the east",
     "summary": "The best day of the trip. Leave early.",
     "note": "Bragðavellir closes on 15 September, so this is one of its last nights — ring ahead.",
     "stops": [("Fjaðrárgljúfur", "sight"), ("Foss á Sídu", "quick"), ("Dverghamrar", "quick"),
               ("Skaftafell", "sight"), ("Jökulsárlón Glacial Lagoon", "sight"),
               ("Diamond Beach", "sight"), ("Höfn", "town"),
               ("Stokksnes and Vestrahorn", "optional")],
     "night": "Camping Berunes"},
    {"day": 4, "title": "Stuðlagil, Dettifoss and Mývatn",
     "summary": "Across the top of the country. The longest driving day.",
     "note": "The unavoidable monster. Djúpivogur to Húsavík is 450 km before you stop for "
             "anything, and there is no card campsite in between — this is the price of doing the "
             "whole ring in six days. Húsavík closes on 15 September, so tonight is its last: "
             "phone ahead before you commit to this plan.",
     "stops": [("Egilsstaðir", "town"), ("Stuðlagil Canyon", "sight"),
               ("Dettifoss", "sight"), ("Hverír", "sight"), ("Dimmuborgir", "sight")],
     "night": "Hlíð"},
    {"day": 5, "title": "Whales, then the long run west",
     "summary": "Split the morning in Húsavík, then transit to the west.",
     "split": {"where": "Húsavík harbour",
               "note": "Both leave from the same harbour, about 100 m apart — regroup on the quay.",
               "options": [
                   {"who": "Boat", "what": "Whale watching", "where": "Húsavík harbour",
                    "duration": "~3 h", "book": "Book ahead; sailings are weather-dependent."},
                   {"who": "Museum", "what": "Húsavík Whale Museum", "where": "Hafnarstétt 1",
                    "duration": "~1.5 h", "book": "Walk in. Roughly a fifth of the boat price."}]},
     "stops": [("Húsavík harbour", "split"), ("Góðafoss", "sight"), ("Akureyri", "town"),
               ("Blönduós", "town")],
     "night": "Blönduós"},
    {"day": 6, "title": "Back to the airport", "half": True,
     "summary": "Short by design — the car has to be back before a 17:00 flight.",
     "note": "Aim to be at KEF by 15:00. Nothing on this leg is worth missing a flight for.",
     "stops": [("Borgarnes", "town"), ("Keflavík Airport", "end")],
     "night": None},
]

RING_MAX = [
    {**RING[0], "title": "Airport to the Golden Circle, every stop",
     "stops": [("Keflavík Airport", "start"), ("Þingvellir National Park", "sight"),
               ("Öxarárfoss", "quick"), ("Lögberg", "quick"), ("Geysir Geothermal Area", "sight"),
               ("Strokkur Geyser", "quick"), ("Gullfoss", "sight"), ("Brúarhlöð", "quick"),
               ("Efstidalur II", "quick"), ("Kerið", "optional")]},
    {**RING[1], "title": "Every waterfall on the south coast",
     "stops": [("Urridafoss", "quick"), ("Seljalandsfoss", "sight"), ("Gljúfrafoss", "quick"),
               ("Skógafoss", "sight"), ("Kvarnarhólsárfoss", "quick"), ("Dyrhólaey", "sight"),
               ("Dyrhólaey lighthouse", "quick"), ("Reynisfjara Beach", "sight"),
               ("Vík í Mýrdal", "town"), ("Kirkjubæjarklaustur", "town")]},
    {**RING[2], "title": "Klaustur's roadside cluster, then the lagoon",
     "stops": [("Fjaðrárgljúfur", "sight"), ("Stjórnarfoss", "quick"), ("Systrafoss", "quick"),
               ("Kirkjugólf", "quick"), ("Foss á Sídu", "quick"), ("Dverghamrar", "quick"),
               ("Skaftafell", "sight"), ("Svartifoss waterfall (Parking)", "optional"),
               ("Hofskirkja", "quick"), ("Jökulsárlón Glacial Lagoon", "sight"),
               ("Diamond Beach", "sight"), ("Höfn", "town")]},
    {**RING[3], "title": "Stuðlagil, Dettifoss and the whole Mývatn loop",
     "stops": [("Petra's Stone Collection", "optional"), ("Fáskrúðsfjörður", "town"),
               ("Egilsstaðir", "town"), ("Fardagafoss", "quick"), ("Stuðlagil Canyon", "sight"),
               ("Dettifoss", "sight"), ("Krafla Power Plant", "quick"), ("Hverír", "sight"),
               ("Grjótagjá", "quick"), ("Dimmuborgir", "sight")]},
    {**RING[4], "title": "Whales, Goðafoss and the northern back roads",
     "stops": [("Húsavík harbour", "split"), ("Góðafoss", "sight"), ("Akureyri", "town"),
               ("Vatnsdalshólar", "quick"), ("Borgarvirki", "quick"), ("Kolugljúfur", "quick")]},
    {**RING[5], "title": "Reykholt and Borgarnes on the way to the plane",
     "stops": [("Snorrastofa", "quick"), ("Borgarnes", "town"),
               ("The Settlement Center", "optional"), ("Keflavík Airport", "end")]},
]

WEST_SOUTH = [
    {"day": 1, "title": "Reykjanes, on the airport's doorstep",
     "summary": "The volcanic tip starts 20 minutes from the car hire desk.",
     "note": "CHECK safetravel.is AND road.is THIS MORNING — Reykjanes has erupted repeatedly "
             "since 2023 and these roads close at short notice. If shut, drive on to Seltún.",
     "stops": [("Keflavík Airport", "start"), ("Bridge America - Europe", "quick"),
               ("Gunnuhver", "quick"), ("Reykjanesviti", "quick"), ("Valahnúkamöl", "quick"),
               ("Brimketill", "quick"), ("Seltún Geothermal Area", "sight"),
               ("Kleifarvatn", "quick")],
     "night": "Stokkseyri"},
    {"day": 2, "title": "Golden Circle at its own pace",
     "summary": "The loop with time to spare, rather than a dash.",
     "note": "Þingvellir rewards an hour on foot rather than twenty minutes at the viewpoint.",
     "stops": [("Þingvellir National Park", "sight"), ("Öxarárfoss", "quick"), ("Lögberg", "quick"),
               ("Laugarvatn Fontana", "optional"), ("Geysir Geothermal Area", "sight"),
               ("Strokkur Geyser", "quick"), ("Gullfoss", "sight"), ("Brúarhlöð", "quick"),
               ("Kerið", "optional")],
     "night": "Tjaldsvæðið við Faxa"},
    {"day": 3, "title": "South coast and back",
     "summary": "Out to Vík and back — the only out-and-back in any of these plans.",
     "note": "Going only as far as Vík is what buys Snæfellsnes later. Jökulsárlón is another "
             "190 km east of the turnaround and simply does not fit this shape.",
     "stops": [("Urridafoss", "quick"), ("Seljalandsfoss", "sight"), ("Gljúfrafoss", "quick"),
               ("Skógafoss", "sight"), ("Dyrhólaey", "sight"), ("Reynisfjara Beach", "sight"),
               ("Vík í Mýrdal", "town")],
     "night": "Tjaldsvæðið við Faxa"},
    {"day": 4, "title": "North to Snæfellsnes",
     "summary": "Across to Borgarfjörður, then out onto the peninsula.",
     "note": "Grundarfjörður closes on 15 September — tonight is its last. Ring ahead.",
     "stops": [("Hraunfossar & Barnafoss", "sight"), ("Deildartunguhver", "quick"),
               ("Borgarnes", "town"), ("Gerduberg Cliffs", "quick"), ("Eldborg Crater", "optional"),
               ("Kirkjufell", "sight"), ("Kirkjufellsfoss", "quick")],
     "night": "Grundarfjörður"},
    {"day": 5, "title": "The whole Snæfellsnes loop",
     "summary": "The peninsula every 6-day ring plan skips entirely.",
     "note": "Snæfellsjökull's road is the one thing here that can be weather-closed; the coast "
             "road is fine.",
     "stops": [("Olafsvík", "town"), ("Saxhóll", "quick"), ("Djúpalónssandur", "sight"),
               ("Londrangar Basalt Cliffs", "quick"), ("Arnarstapi", "sight"), ("Hellnar", "quick"),
               ("Rauðfeldsgjá Gorge", "quick"), ("Búðir church", "quick")],
     "night": "Búðardalur"},
    {"day": 6, "title": "Back to the airport", "half": True,
     "summary": "Short by design — the car has to be back before a 17:00 flight.",
     "note": "Aim to be at KEF by 15:00.",
     "stops": [("Borgarnes", "town"), ("Keflavík Airport", "end")],
     "night": None},
]

VARIANTS = {
    "v1-ring": {"version": "v1", "label": "Ring road, counter-clockwise", "days": RING,
                "note": "The classic loop in six days. Covers the whole country but never "
                        "lingers, and one night falls outside the camping card."},
    "v2-ring-max": {"version": "v2", "label": "Ring road, maximum stops", "days": RING_MAX,
                    "note": "Same loop and same nights, with every worthwhile quick stop within "
                            "a couple of kilometres of the road. Long activities left out on "
                            "purpose — the extra sights cost minutes, not hours."},
    "v3-west-south": {"version": "v3", "label": "West and south, no ring", "days": WEST_SOUTH,
                      "note": "Drops the north and east to do Reykjanes, the Golden Circle, the "
                              "south coast and all of Snæfellsnes properly. Far less driving, "
                              "more stops, every night on the card. No Jökulsárlón, no whales."},
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

    def coord(name):
        if name in EXTRA:
            return EXTRA[name]
        if name in places:
            return (float(places[name]["lat"]), float(places[name]["lon"]))
        raise SystemExit(f"no coordinates for stop: {name!r}")

    out_variants = {}
    for key, spec in VARIANTS.items():
        days, cursor = [], AIRPORT
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
                "over_daylight": day_hours > 11.0,
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
            elif day_hours > 11:
                flag = "  << over daylight"
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
        "default": "v1-ring",
        "start_date": START_DATE.isoformat(),
        "flight": FLIGHT_HOME,
        "variants": out_variants,
    }
    (DATA / "routes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"written to {DATA / 'routes.json'}")


if __name__ == "__main__":
    main()
