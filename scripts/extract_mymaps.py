#!/usr/bin/env python3
"""Extract placemarks from the Google My Maps behind two Iceland map pages.

Both source pages are only shells -- the content lives in an embedded Google
My Maps iframe. Google exposes every layer's placemarks as KML at
/maps/d/kml?mid=<id>; `forcekml=1` returns plain XML rather than a zipped KMZ.

Sources:
  places        https://adventures.com/information/map-of-iceland/
  gas_stations  https://www.google.com/maps/d/u/0/viewer?mid=1wTIeHwmiHN2...

The gas-station map labels its pins with bare brand names ("N1" x15), so
`--geocode` attaches a locality per point via OpenStreetMap's Nominatim
(rate-limited to ~1 req/s per their usage policy). Without the flag the
locality columns are left empty and no external service is contacted.

Usage:
    python3 scripts/extract_mymaps.py                     # both maps, no geocoding
    python3 scripts/extract_mymaps.py gas_stations --geocode
"""

import argparse
import csv
import re
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

NS = {"k": "http://www.opengis.net/kml/2.2"}


def clean(s: str) -> str:
    """Placemark labels carry non-breaking spaces and doubled spaces."""
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()

OUT = pathlib.Path(__file__).resolve().parent.parent / "data"
UA = "iceland-data/1.0 (personal dataset build)"

MAPS = {
    "places": {
        "mid": "1Z6VqQXTWN-zVPcNqA4WD43oDQGV6n0um",
        "out": "iceland_places",
        # Folder names are meaningful categories (Waterfalls, Caves, ...).
        "label": "category",
    },
    "gas_stations": {
        "mid": "1wTIeHwmiHN2QQcL_ySY7_rmLaxHkan6o",
        "out": "iceland_gas_stations",
        # The single folder is just "GASOLINERAS"; the pin name is the brand.
        "label": "brand",
    },
}


def fetch_kml(mid: str) -> bytes:
    url = f"https://www.google.com/maps/d/kml?mid={mid}&forcekml=1"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as r:
        return r.read()


def parse(kml: bytes, label: str) -> list[dict]:
    doc = ET.fromstring(kml).find("k:Document", NS)
    if doc.find(".//k:NetworkLink", NS) is not None:
        # Google splits genuinely large maps across NetworkLinks; a flat export
        # would silently be partial.
        sys.exit("KML contains a NetworkLink -- export may be incomplete")
    rows = []
    for folder in doc.findall("k:Folder", NS):
        category = clean(folder.findtext("k:name", "", NS) or "")
        for pm in folder.findall("k:Placemark", NS):
            coords = pm.find(".//k:Point/k:coordinates", NS)
            lat = lon = ""
            if coords is not None and coords.text:
                lon, lat = coords.text.strip().split(",")[:2]
            name = clean(pm.findtext("k:name", "", NS) or "")
            row = {"name": name, "lat": lat, "lon": lon}
            if label == "category":
                row = {"category": category, **row}
            else:
                row = {"brand": name, "layer": category, "lat": lat, "lon": lon}
            rows.append(row)
    return rows


def reverse_geocode(rows: list[dict]) -> None:
    """Attach a locality per point via Nominatim, ~1 req/s.

    Nominatim returns no `state` for Iceland, so only locality is useful.
    """
    for row in rows:
        row["locality"] = ""
        if not row.get("lat"):
            continue
        q = urllib.parse.urlencode(
            {"format": "jsonv2", "lat": row["lat"], "lon": row["lon"],
             "zoom": 14, "addressdetails": 1}
        )
        req = urllib.request.Request(
            "https://nominatim.openstreetmap.org/reverse?" + q, headers={"User-Agent": UA}
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as f:
                a = json.load(f).get("address", {})
            row["locality"] = next(
                (a[k] for k in ("town", "village", "city", "hamlet", "suburb", "municipality")
                 if a.get(k)), ""
            )
        except Exception as exc:  # a failed lookup must not lose the row
            print(f"  geocode failed for {row.get('brand') or row.get('name')}: {exc}",
                  file=sys.stderr)
        time.sleep(1.1)


def write(rows: list[dict], stem: str) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / f"{stem}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / f"{stem}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("map", nargs="?", choices=sorted(MAPS), help="default: both")
    p.add_argument("--geocode", action="store_true",
                   help="attach locality via Nominatim (~1 req/s)")
    args = p.parse_args()

    for key in [args.map] if args.map else sorted(MAPS):
        spec = MAPS[key]
        rows = parse(fetch_kml(spec["mid"]), spec["label"])
        if args.geocode:
            reverse_geocode(rows)
        write(rows, spec["out"])
        print(f"{len(rows):>4} {key} written to {OUT}/{spec['out']}.{{csv,json}}")


if __name__ == "__main__":
    main()
