"""
Nightwatch - a simple earthquake monitor for Greece.

Every few minutes it asks the public USGS earthquake service for recent
earthquakes inside a map box around Greece, and sends a phone notification
(via ntfy.sh) for any new one above a chosen magnitude.

Settings live in config.yaml. The ntfy topic comes from the NTFY_TOPIC
environment variable.
"""

import json
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


# Map the "type" in config.yaml to the function that handles it.
# (Only earthquakes for now, but easy to extend later.)
SOURCES = {
    "usgs": fetch_usgs,
}


def send_notification(topic, title, url):
    """Send one push notification to our ntfy topic."""
    requests.post(
        f"https://ntfy.sh/{topic}",
        data=title.encode("utf-8"),
        headers={"Title": "Nightwatch", "Click": url or topic},
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
                send_notification(topic, f"{name}: {item['title']}", item["url"])


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
