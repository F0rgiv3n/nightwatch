# 🌍 Nightwatch — Greece Earthquake Alerts

[![Earthquake monitor](https://github.com/F0rgiv3n/nightwatch/actions/workflows/monitor.yml/badge.svg)](https://github.com/F0rgiv3n/nightwatch/actions/workflows/monitor.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Nightwatch** watches for earthquakes in Greece and pushes a notification to
your phone within minutes of one happening — for free, fully automated, using
only official public data.

It runs itself 24/7 on **GitHub Actions** (no server to rent, no credit card),
reads earthquake data from the **U.S. Geological Survey (USGS)** public API, and
delivers alerts through **[ntfy](https://ntfy.sh)**. The whole thing is one
readable Python file.

---

## 📲 Demo

A real alert delivered to a phone. Tapping it opens the official USGS event page
with the full details (map, magnitude, depth, coordinates):

<p align="center">
  <img src="docs/notification.png" alt="Nightwatch earthquake notification on a phone" width="300">
  &nbsp;&nbsp;
  <img src="docs/usgs-event.png" alt="The USGS event page opened from the notification" width="300">
</p>

---

## Why this exists

Greece is one of the most seismically active countries in Europe — small and
moderate earthquakes happen almost daily. I wanted a **simple, reliable, and
free** way to get an instant heads-up on my phone whenever a notable earthquake
strikes the country, without:

- installing yet another app full of ads,
- paying for a server to keep a script running, or
- scraping anything I shouldn't.

Nightwatch solves exactly that, and along the way it's a compact demonstration
of a real end-to-end pipeline: **fetch data → detect what's new → notify →
persist state → run on a schedule.**

## What it does

- ⏱️ Checks for recent Greek earthquakes **every 15 minutes**.
- 🗺️ Filters by a **geographic bounding box** around Greece (mainland, Aegean,
  islands) using the USGS query API — not a global feed with the wrong results.
- 🎚️ Only alerts above a **magnitude you choose** (default M3.5), so you're not
  buzzed for every tiny tremor.
- 🔁 Remembers what it has already reported, so you get each earthquake **once**.
- 🤫 Stays silent on first run (saves a baseline) so it never floods you on
  startup.
- 🔔 Sends a clean push notification that links straight to the official USGS
  page.

## How it works

```
                 ┌──────────────────────────────────────────────┐
   GitHub Actions│  every 15 min  →  python nightwatch.py        │
   (the "cron")  └───────────────────────┬──────────────────────┘
                                         │
                 ┌───────────────────────▼──────────────────────┐
                 │ 1. Ask USGS for recent quakes in the Greece   │
                 │    bounding box, above the chosen magnitude   │
                 │ 2. Compare against seen.json (already alerted)│
                 │ 3. For each NEW quake → send ntfy push        │
                 │ 4. Save the updated seen.json                 │
                 └───────────────────────┬──────────────────────┘
                                         │
                          ntfy.sh ───────▼──────►  📱 your phone
```

State (`seen.json`) is kept between scheduled runs using the **GitHub Actions
cache**, so the bot remembers what it already sent — without polluting the git
history with bot commits.

## Tech stack & what it demonstrates

This is intentionally small, but it touches a full, realistic toolchain:

| Area | What's shown |
| --- | --- |
| **Public API integration** | Consuming the USGS `fdsnws` REST API, parsing GeoJSON |
| **Geospatial filtering** | Bounding-box (lat/lon) querying for a region |
| **Change detection** | Stateful "what's new since last time" logic |
| **Push notifications** | Event-driven alerts via ntfy |
| **Containerization** | A small, single-stage **Dockerfile** |
| **CI/CD & automation** | A scheduled **GitHub Actions** workflow that runs the job 24/7 |
| **Secrets management** | Notification target stored as a GitHub Actions **secret**, never hard-coded |
| **Stateful workflows** | Persisting `seen.json` across runs via Actions **cache** |
| **Clean code** | One readable file, plain functions, no over-engineering |

## Getting started

### Run locally

```bash
pip install -r requirements.txt

export NTFY_TOPIC=your-unguessable-topic     # pick any unique name
python nightwatch.py
```

Subscribe to the same topic in the [ntfy app](https://ntfy.sh) (or open
`https://ntfy.sh/your-unguessable-topic` in a browser) to receive the alerts.

### Run with Docker

```bash
docker build -t nightwatch .
docker run -e NTFY_TOPIC=your-unguessable-topic nightwatch
```

### Run it 24/7 with GitHub Actions (free)

1. Fork/clone this repo to your own GitHub account.
2. Add a repository **secret** named `NTFY_TOPIC`
   (Settings → Secrets and variables → Actions) with your topic name.
3. That's it — the workflow in [`.github/workflows/monitor.yml`](.github/workflows/monitor.yml)
   runs every 15 minutes. You can also trigger it manually from the **Actions**
   tab ("Run workflow").

> The first scheduled run records a silent baseline; you'll start getting alerts
> from the next new earthquake onward.

## Configuration

Everything lives in [`config.yaml`](config.yaml):

```yaml
interval: 300   # seconds between checks when running as a long-lived process

sources:
  - name: greece-earthquakes
    type: usgs
    min_magnitude: 3.5      # only notify for magnitude 3.5 and above
    period_days: 1          # look back this many days on each check

    # Bounding box around Greece (latitude / longitude):
    min_latitude: 34.0
    max_latitude: 42.0
    min_longitude: 19.0
    max_longitude: 29.5
```

| Setting | Meaning |
| --- | --- |
| `min_magnitude` | Ignore earthquakes weaker than this |
| `period_days` | How far back to look on each check |
| `min/max_latitude`, `min/max_longitude` | The map box (region) to watch |
| `interval` | Seconds between checks (only used in the long-running loop, not in Actions) |

**Watch a different region:** just change the bounding box.
**Too many alerts?** Raise `min_magnitude` (Greece is very seismically active).

## Project structure

```
nightwatch/
├── nightwatch.py              # the whole program (fetch → detect → notify)
├── config.yaml                # what to watch
├── requirements.txt           # requests, PyYAML
├── Dockerfile                 # containerized run
├── .github/workflows/
│   └── monitor.yml            # scheduled 24/7 runner (GitHub Actions)
├── docs/                      # demo screenshots
└── README.md
```

## Extending it

Nightwatch is structured so other data sources slot in easily. Each source is a
function that returns a list of `{"id", "title", "url"}` items; register it in
the `SOURCES` dict in `nightwatch.py` and reference its `type` in `config.yaml`.
Natural next additions: the Greek **NOA / EMSC** seismic feeds, weather warnings,
or anything with a public API.

## Notes & limitations

- **Data source:** USGS is a global authority and reliably catalogs Greek
  earthquakes from roughly M3+. For very small local events, the Greek national
  network (NOA) or EMSC would be more exhaustive — a good future source.
- **Timing:** GitHub's scheduled workflows can be delayed by a few minutes under
  load, so treat alerts as "within ~15–20 minutes," not real-time/emergency
  warnings.
- **Notifications:** ntfy topics on the public server are readable by anyone who
  knows the name — pick an unguessable one.

## License

[MIT](LICENSE) — free to use, modify, and learn from.
