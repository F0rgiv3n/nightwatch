"""
Nightwatch - a simple change monitor.

It checks a few online sources (earthquakes, GitHub releases, Hacker News,
RSS feeds) every few minutes and sends a phone notification (via ntfy.sh)
whenever something new appears.

What it watches is set in config.yaml. The ntfy topic comes from the
NTFY_TOPIC environment variable.
"""

import json
import os
import time

import feedparser
import requests
import yaml

# We send a friendly, identifying User-Agent with every request (good manners).
HEADERS = {"User-Agent": "Nightwatch/1.0 (https://github.com/F0rgiv3n/nightwatch)"}

SEEN_FILE = "seen.json"


# --------------------------------------------------------------------------
# Sources
#
# Each function receives that source's settings from config.yaml and returns
# a list of items. An item is a small dictionary: {"id", "title", "url"}.
# The "id" must be unique and stable so we can tell new items from old ones.
# --------------------------------------------------------------------------

def fetch_usgs(settings):
    """Earthquakes from the public USGS feed (no API key needed)."""
    feed = settings.get("feed", "4.5_day")
    min_magnitude = settings.get("min_magnitude", 0)
    url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{feed}.geojson"

    data = requests.get(url, headers=HEADERS, timeout=20).json()

    items = []
    for quake in data["features"]:
        magnitude = quake["properties"]["mag"]
        if magnitude is None or magnitude < min_magnitude:
            continue
        items.append({
            "id": quake["id"],
            "title": f"M{magnitude} - {quake['properties']['place']}",
            "url": quake["properties"]["url"],
        })
    return items


def fetch_github(settings):
    """Releases of a GitHub repository (official API, no key needed)."""
    repo = settings["repo"]  # e.g. "astral-sh/ruff"
    url = f"https://api.github.com/repos/{repo}/releases"

    releases = requests.get(url, headers=HEADERS, timeout=20).json()

    items = []
    for release in releases:
        items.append({
            "id": str(release["id"]),
            "title": f"{repo} {release['tag_name']}",
            "url": release["html_url"],
        })
    return items


def fetch_hackernews(settings):
    """Hacker News stories that match a keyword (official search API)."""
    query = settings["query"]
    url = f"https://hn.algolia.com/api/v1/search_by_date?query={query}&tags=story"

    hits = requests.get(url, headers=HEADERS, timeout=20).json()["hits"]

    items = []
    for hit in hits:
        story_id = hit["objectID"]
        items.append({
            "id": story_id,
            "title": hit.get("title") or "(no title)",
            "url": hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
        })
    return items


def fetch_rss(settings):
    """Any RSS or Atom feed."""
    feed = feedparser.parse(settings["url"])

    items = []
    for entry in feed.entries:
        items.append({
            "id": entry.get("id") or entry.get("link"),
            "title": entry.get("title", "(no title)"),
            "url": entry.get("link"),
        })
    return items


# Map the "type" in config.yaml to the function that handles it.
SOURCES = {
    "usgs": fetch_usgs,
    "github": fetch_github,
    "hackernews": fetch_hackernews,
    "rss": fetch_rss,
}


# --------------------------------------------------------------------------
# Notifications and saved state
# --------------------------------------------------------------------------

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


# --------------------------------------------------------------------------
# Main logic
# --------------------------------------------------------------------------

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

    interval = config.get("interval", 300)  # seconds between checks
    seen = load_seen()

    print(f"Nightwatch started. Checking {len(config['sources'])} sources every {interval}s.")
    while True:
        check_all_sources(config, seen, topic)
        save_seen(seen)
        time.sleep(interval)


if __name__ == "__main__":
    main()
