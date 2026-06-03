# Sentinel

A simple change monitor. It checks a few online sources every few minutes and
sends a notification to your phone (via [ntfy.sh](https://ntfy.sh)) whenever
something new appears.

It can watch:

- **Earthquakes** — the public USGS feed
- **GitHub releases** — new releases of any repository
- **Hacker News** — stories matching a keyword
- **RSS / Atom feeds** — any feed you like

All of it is one file (`sentinel.py`, ~190 lines) and one config file.

## How it works

1. Read `config.yaml` to see what to watch.
2. For each source, fetch the current list of items.
3. Compare against `seen.json` (the ids we saw last time).
4. Send a notification for anything new, then save the new ids.
5. Wait a few minutes and repeat.

The first time it sees a source it just saves a baseline (no notifications),
so you don't get flooded on startup.

## Run it locally

```bash
pip install -r requirements.txt

export NTFY_TOPIC=sentinel-pick-something-random
python sentinel.py
```

Then open `https://ntfy.sh/sentinel-pick-something-random` in a browser or the
ntfy app to receive the alerts.

## Run it with Docker

```bash
docker build -t sentinel .
docker run -e NTFY_TOPIC=sentinel-pick-something-random sentinel
```

## Configuration

Edit `config.yaml`:

```yaml
interval: 300   # seconds between checks

sources:
  - name: big-earthquakes
    type: usgs
    feed: "4.5_day"
    min_magnitude: 5.0

  - name: ruff-releases
    type: github
    repo: astral-sh/ruff

  - name: hn-python
    type: hackernews
    query: python

  - name: hn-frontpage
    type: rss
    url: https://hnrss.org/frontpage
```

| `type`        | What it watches               | Settings                  |
| ------------- | ----------------------------- | ------------------------- |
| `usgs`        | USGS earthquake feed          | `feed`, `min_magnitude`   |
| `github`      | A repo's releases             | `repo` (`owner/name`)     |
| `hackernews`  | HN stories matching a keyword | `query`                   |
| `rss`         | Any RSS/Atom feed             | `url`                     |

## Adding a new source

Write a function that returns a list of `{"id", "title", "url"}` items and add
it to the `SOURCES` dictionary in `sentinel.py`. That's it.

## License

MIT
