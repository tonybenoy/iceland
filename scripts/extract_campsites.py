#!/usr/bin/env python3
"""Extract the Utilegukortid camping sites from utilegukortid.is.

The listing page at /all-camping-sites/?lang=en renders only 30 posts behind
Divi's AJAX pagination, so this goes to the WordPress REST API instead:
category 46 ("Camping Sites"), whose X-WP-Total header confirms the count.

Field labels in the posts are hand-typed and inconsistent ("ZIP/Town" vs
"Zip / City", "Reykjavik" vs "Reykjavík", broken nested <strong> tags), so
values are sliced out of flattened text between known labels rather than
matched against markup. Amenities are icons only, but each <img> carries a
bilingual alt ("Salerni / Toilets"); the half after the slash is the English
name. Coordinates come from the Google Maps embed URLs, which encode position
in the `pb` parameter as !2d<lon>!3d<lat> -- longitude first.

Writes data/iceland_campsites.csv and data/iceland_campsites.json.
"""

import csv
import html
import json
import pathlib
import re
import urllib.request

API = (
    "https://utilegukortid.is/wp-json/wp/v2/posts"
    "?categories=46&per_page=100&lang=en"
    "&_fields=id,slug,link,title,categories,content"
)
OUT = pathlib.Path(__file__).resolve().parent.parent / "data"

REGIONS = {
    47: "West Iceland",
    48: "Westfjords",
    49: "North Iceland",
    50: "East Iceland",
    51: "South Iceland",
}
REGION_ORDER = list(REGIONS.values()) + [""]

# Info-block labels, in the order they appear on the page.
LABELS = [
    ("address", r"Address"),
    ("zip_town", r"(?:Zip|ZIP)\s*[/ ]\s*(?:Town|City)"),
    ("tel", r"Tel(?:ephone)?"),
    ("email", r"E-?mail"),
    ("website", r"Website"),
    ("open", r"Open"),
    ("km_from_reykjavik", r"Distance from Reykjav[ií]k"),
    ("km_from_seydisfjordur", r"Distance from Sey\w+"),
]
ANY_LABEL = re.compile("|".join(f"(?P<{k}>{v})" for k, v in LABELS), re.I)
# The labels also occur in body prose ("open from 12:00"), so confine the
# search to the block between the "Information" heading and "Service on site".
INFO_BLOCK = re.compile(r"(?is)>\s*(?:Service\s+)?Information\s*<.*?(?=<h4|Service on site)")


def to_text(fragment: str) -> str:
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>", "\n", fragment)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", t)


def parse_fields(content: str) -> dict:
    block = INFO_BLOCK.search(content)
    text = to_text(block.group(0) if block else content)
    hits = list(ANY_LABEL.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else m.end() + 200
        value = text[m.end() : end].split("\n")[0]  # a value never crosses a line break
        value = re.sub(r"\s+", " ", value).strip(" :–-")
        if value and not out.get(m.lastgroup):
            out[m.lastgroup] = value
    return out


def coords(content: str) -> tuple[str, str]:
    m = re.search(r"!2d(-?\d+\.\d+)!3d(-?\d+\.\d+)", content)  # embed pb: 2d=lon, 3d=lat
    if m:
        return m.group(2), m.group(1)
    m = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+),", content)  # /@lat,lon,17z
    if m:
        return m.group(1), m.group(2)
    return "", ""


def facilities(content: str) -> list[str]:
    names = []
    for alt in re.findall(r'<img[^>]*/icons_[^>]*alt="([^"]*)"', content):
        # A few alts are double-escaped ("Chairs &amp;amp; Tables").
        name = html.unescape(html.unescape(alt)).split("/")[-1].strip()
        if name and name not in names:
            names.append(name)
    return names


def build_row(post: dict) -> dict:
    c = post["content"]["rendered"]
    f = parse_fields(c)
    tel = re.search(r'href="tel:([^"]+)"', c)
    mail = re.search(r'href="mailto:([^"]+)"', c)
    site = re.search(
        r'href="(https?://(?!(?:www\.)?'
        r'(?:google|maps|goo\.gl|utilegukortid|i0\.wp|facebook|instagram))[^"]+)"',
        c,
    )
    short = re.search(r"https://maps\.app\.goo\.gl/\w+", c)
    lat, lon = coords(c)
    return {
        "name": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", post["title"]["rendered"]))).strip(),
        "region": ", ".join(REGIONS[i] for i in post["categories"] if i in REGIONS),
        "address": f.get("address", ""),
        "zip_town": f.get("zip_town", ""),
        "tel": tel.group(1) if tel else f.get("tel", ""),
        "email": mail.group(1) if mail else f.get("email", ""),
        "website": f.get("website", "") or (site.group(1) if site else ""),
        "open": f.get("open", ""),
        "km_from_reykjavik": f.get("km_from_reykjavik", "").replace(" km", ""),
        "km_from_seydisfjordur": f.get("km_from_seydisfjordur", "").replace(" km", ""),
        "lat": lat,
        "lon": lon,
        "facilities": "; ".join(facilities(c)),
        "maps_url": short.group(0)
        if short
        else (f"https://www.google.com/maps?q={lat},{lon}" if lat else ""),
        "page": post["link"],
    }


def main() -> None:
    req = urllib.request.Request(API, headers={"User-Agent": "iceland-data/1.0"})
    with urllib.request.urlopen(req) as r:
        total = r.headers.get("X-WP-Total")
        posts = json.load(r)
    if total and int(total) != len(posts):
        raise SystemExit(f"expected {total} posts, got {len(posts)} -- pagination needed")

    rows = [build_row(p) for p in posts]
    rows.sort(
        key=lambda r: (
            REGION_ORDER.index(r["region"]) if r["region"] in REGION_ORDER else 99,
            r["name"],
        )
    )

    OUT.mkdir(exist_ok=True)
    with (OUT / "iceland_campsites.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "iceland_campsites.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(rows)} campsites written to {OUT}")


if __name__ == "__main__":
    main()
