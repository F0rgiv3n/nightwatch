# Nightwatch

A simple earthquake monitor for **Greece**. Every few minutes it checks the
public [USGS earthquake service](https://earthquake.usgs.gov/) for recent
earthquakes in the Greece area and sends a notification to your phone (via
[ntfy.sh](https://ntfy.sh)) for any new one above a magnitude you choose.

It's one small file (`nightwatch.py`) and one config file.

## Demo

A real earthquake alert delivered to a phone via ntfy — tap it and it opens the
official USGS event page with the full details:

<p align="center">
  <img src="docs/notification.png" alt="Nightwatch earthquake notification on a phone" width="300">
  &nbsp;&nbsp;
  <img src="docs/usgs-event.png" alt="The USGS event page opened from the notification" width="300">
</p>

## How it works

1. Read `config.yaml` (which area and minimum magnitude to watch).
2. Ask USGS for recent earthquakes inside a map box around Greece.
3. Compare against `seen.json` (the earthquakes we already saw).
4. Send a notification for any new one, then save the ids.
5. Wait a few minutes and repeat.

The first time it runs it just saves a baseline (no notifications), so you
don't get flooded on startup.

## Run it locally

```bash
pip install -r requirements.txt

export NTFY_TOPIC=nightwatch-pick-something-random
python nightwatch.py
```

Then open `https://ntfy.sh/nightwatch-pick-something-random` in a browser or the
ntfy app to receive the alerts.

## Run it with Docker

```bash
docker build -t nightwatch .
docker run -e NTFY_TOPIC=nightwatch-pick-something-random nightwatch
```

## Configuration

Edit `config.yaml`:

```yaml
interval: 300   # seconds between checks (300 = every 5 minutes)

sources:
  - name: greece-earthquakes
    type: usgs
    min_magnitude: 3.5      # only notify for magnitude 3.5 and above
    period_days: 1          # look at the last 24 hours

    # Bounding box around Greece (latitude / longitude).
    min_latitude: 34.0
    max_latitude: 42.0
    min_longitude: 19.0
    max_longitude: 29.5
```

| Setting         | Meaning                                            |
| --------------- | -------------------------------------------------- |
| `min_magnitude` | Ignore earthquakes weaker than this                |
| `period_days`   | How far back to look on each check                 |
| `min/max_latitude`, `min/max_longitude` | The map box to watch       |

To watch a different region, just change the bounding box. Raise
`min_magnitude` if you get too many alerts (Greece is very seismically active).

## License

MIT
