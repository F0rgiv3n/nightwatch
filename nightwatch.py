"""
Nightwatch - a simple earthquake monitor for Greece.

Every few minutes it asks the public USGS earthquake service for recent
earthquakes inside a map box around Greece, and sends a phone notification
(via ntfy.sh) for any new one above a chosen magnitude.

Settings live in config.yaml. The ntfy topic comes from the NTFY_TOPIC
environment variable.
"""

import json
import math
import os
import time
from datetime import datetime, timedelta, timezone

import requests
import yaml

# A friendly, identifying User-Agent on every request (good manners).
HEADERS = {"User-Agent": "Nightwatch/1.0 (https://github.com/F0rgiv3n/nightwatch)"}

SEEN_FILE = "seen.json"


def fetch_usgs(settings):
    """Recent earthquakes from USGS, limited to a geographic box.

    Returns a list of items: {"id", "title", "url"}.
    """
    # How far back to look (in days) and the smallest magnitude we care about.
    period_days = settings.get("period_days", 1)
    start = datetime.now(timezone.utc) - timedelta(days=period_days)

    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": settings.get("min_magnitude", 0),
        # Bounding box (a rectangle on the map) around the area we watch.
        "minlatitude": settings.get("min_latitude"),
        "maxlatitude": settings.get("max_latitude"),
        "minlongitude": settings.get("min_longitude"),
        "maxlongitude": settings.get("max_longitude"),
    }
    # Drop any settings that weren't provided in config.yaml.
    params = {key: value for key, value in params.items() if value is not None}

    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    data = requests.get(url, headers=HEADERS, params=params, timeout=20).json()

    items = []
    for quake in data["features"]:
        info = quake["properties"]
        items.append({
            "id": quake["id"],
            "title": f"M{info['mag']} - {info['place']}",
            "url": info["url"],
        })
    return items


# NOA labels most events with a coarse region (often just "Greece"), so for a
# useful notification heading we work out the nearest town from the coordinates
# ourselves. Names are kept in the genitive ("της Χαλκίδας") to read naturally
# in "22 km ΒΔ της Χαλκίδας". (name, latitude, longitude)
GREEK_CITIES = [
    ("της Αθήνας", 37.98, 23.73), ("της Θεσσαλονίκης", 40.64, 22.94),
    ("της Πάτρας", 38.25, 21.73), ("του Ηρακλείου", 35.34, 25.13),
    ("της Λάρισας", 39.64, 22.42), ("του Βόλου", 39.36, 22.95),
    ("των Ιωαννίνων", 39.67, 20.85), ("της Καβάλας", 40.94, 24.41),
    ("της Χαλκίδας", 38.46, 23.60), ("της Καλαμάτας", 37.04, 22.11),
    ("της Τρίπολης", 37.51, 22.37), ("της Κέρκυρας", 39.62, 19.92),
    ("της Ρόδου", 36.43, 28.22), ("της Κω", 36.89, 27.29),
    ("των Χανίων", 35.51, 24.02), ("της Μυτιλήνης", 39.11, 26.55),
    ("της Χίου", 38.37, 26.14), ("της Σάμου", 37.75, 26.98),
    ("της Αλεξανδρούπολης", 40.85, 25.87), ("της Κοζάνης", 40.30, 21.79),
    ("της Σπάρτης", 37.07, 22.43), ("του Αγρινίου", 38.62, 21.41),
    ("της Λαμίας", 38.90, 22.43), ("της Κατερίνης", 40.27, 22.51),
    ("των Σερρών", 41.09, 23.55), ("του Ναυπλίου", 37.57, 22.80),
    ("του Πύργου", 37.67, 21.44), ("της Ζακύνθου", 37.79, 20.90),
    ("του Αργοστολίου", 38.18, 20.49), ("της Σύρου", 37.44, 24.94),
    ("της Νάξου", 37.10, 25.38), ("της Σαντορίνης", 36.42, 25.43),
    ("της Καρπάθου", 35.51, 27.21), ("της Λήμνου", 39.87, 25.06),
    ("του Ρεθύμνου", 35.37, 24.47), ("του Αγίου Νικολάου", 35.19, 25.72),
    ("της Πρέβεζας", 38.96, 20.75), ("της Κορίνθου", 37.94, 22.93),
    ("της Λιβαδειάς", 38.44, 22.88), ("της Λίμνης Ευβοίας", 38.77, 23.32),
    ("της Καρδίτσας", 39.36, 21.92), ("των Τρικάλων", 39.56, 21.77),
    ("της Κομοτηνής", 41.12, 25.40), ("της Ξάνθης", 41.13, 24.88),
    ("της Δράμας", 41.15, 24.15), ("της Βέροιας", 40.52, 22.20),
    ("του Μεσολογγίου", 38.37, 21.43), ("της Άρτας", 39.16, 20.99),
]

# 8-point compass in Greek, clockwise from North.
_COMPASS = ["Β", "ΒΑ", "Α", "ΝΑ", "Ν", "ΝΔ", "Δ", "ΒΔ"]


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometres."""
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _compass(lat1, lon1, lat2, lon2):
    """Rough compass direction (Β/ΒΑ/…) from point 1 towards point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    return _COMPASS[round(bearing / 45) % 8]


def describe_location(lat, lon, fallback):
    """A human place for the heading, e.g. "22 km ΒΔ της Χαλκίδας".

    Finds the nearest town from GREEK_CITIES. If the epicenter is very close we
    just name the area; if it's far from every town (open sea) we fall back to
    whatever region NOA gave us.
    """
    name, city_lat, city_lon = min(
        GREEK_CITIES, key=lambda c: _haversine_km(lat, lon, c[1], c[2])
    )
    distance = _haversine_km(lat, lon, city_lat, city_lon)
    if distance < 3:
        return f"στην ευρύτερη περιοχή {name}"
    if distance <= 120:
        return f"{round(distance)} km {_compass(city_lat, city_lon, lat, lon)} {name}"
    return fallback


def fetch_noa(settings):
    """Recent earthquakes from the National Observatory of Athens (NOA).

    NOA is Greece's national seismic network: it catalogs Greek earthquakes far
    more completely and quickly than the global USGS feed (it even feeds EMSC),
    so it's the better source for Greece. Its FDSN service only speaks the
    pipe-delimited "text" format (no GeoJSON), which we parse here.

    Returns a list of items: {"id", "title", "url"}.
    """
    period_days = settings.get("period_days", 1)
    start = datetime.now(timezone.utc) - timedelta(days=period_days)

    params = {
        "format": "text",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        # NOTE: the NOA FDSN service uses the short FDSN names (minmag, minlat …),
        # unlike USGS which wants minmagnitude/minlatitude.
        "minmag": settings.get("min_magnitude", 0),
        "minlat": settings.get("min_latitude"),
        "maxlat": settings.get("max_latitude"),
        "minlon": settings.get("min_longitude"),
        "maxlon": settings.get("max_longitude"),
    }
    # Drop any settings that weren't provided in config.yaml.
    params = {key: value for key, value in params.items() if value is not None}

    url = "https://eida.gein.noa.gr/fdsnws/event/1/query"
    text = requests.get(url, headers=HEADERS, params=params, timeout=20).text

    # Each line is pipe-delimited:
    #   EventID|Time|Lat|Lon|Depth|Author|Catalog|Contributor|ContributorID|
    #   MagType|Magnitude|MagAuthor|EventLocationName|EventType
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # skip the header line and any blanks
        fields = line.split("|")
        event_id, lat, lon = fields[0], fields[2], fields[3]
        magnitude = float(fields[10])
        region = fields[12] or "Ελλάδα"
        where = describe_location(float(lat), float(lon), region)
        items.append({
            "id": event_id,
            "title": f"M{magnitude:.1f} · {where}",
            # NOA has no stable per-event page, so link to the epicenter on a map.
            "url": f"https://www.google.com/maps?q={lat},{lon}",
        })
    return items


# Map the "type" in config.yaml to the function that handles it.
SOURCES = {
    "usgs": fetch_usgs,
    "noa": fetch_noa,
}


def send_notification(topic, title, url):
    """Send one push notification to our ntfy topic.

    `title` becomes the bold heading (e.g. "M4.2 - 74 km W of Kýthira, Greece"),
    the body invites a tap, and tapping opens the USGS event page.
    """
    requests.post(
        f"https://ntfy.sh/{topic}",
        data="Tap to open the epicenter on a map".encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Tags": "earth_africa",   # shows a 🌍 icon in the notification
            "Click": url or topic,
        },
        timeout=15,
    )


def load_seen():
    """Read the ids we've already seen from seen.json (or start empty)."""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return json.load(f)
    return {}


def save_seen(seen):
    """Write the ids we've seen back to seen.json."""
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def check_all_sources(config, seen, topic):
    """Check every source once and notify about anything new."""
    for source in config["sources"]:
        name = source["name"]
        fetch = SOURCES[source["type"]]

        try:
            items = fetch(source)
        except Exception as error:
            print(f"[{name}] error: {error}")
            continue

        # Ids we saw the previous time we checked this source.
        previous_ids = seen.get(name)
        new_items = [it for it in items if previous_ids is None or it["id"] not in previous_ids]

        # Remember the current ids for next time.
        seen[name] = [it["id"] for it in items]

        if previous_ids is None:
            # First time we see this source: just save a baseline, don't spam.
            print(f"[{name}] baseline saved ({len(items)} items)")
        else:
            for item in new_items:
                print(f"[{name}] NEW: {item['title']}")
                send_notification(topic, item["title"], item["url"])


def main():
    topic = os.environ["NTFY_TOPIC"]  # required

    with open("config.yaml") as f:
        config = yaml.safe_load(f)

    seen = load_seen()

    # RUN_ONCE=1 does a single check and exits. This is what the GitHub Actions
    # schedule uses. Without it we loop forever (handy when running on a server).
    if os.getenv("RUN_ONCE"):
        check_all_sources(config, seen, topic)
        save_seen(seen)
        return

    interval = config.get("interval", 300)  # seconds between checks
    print(f"Nightwatch started. Checking every {interval}s.")
    while True:
        check_all_sources(config, seen, topic)
        save_seen(seen)
        time.sleep(interval)


if __name__ == "__main__":
    main()
