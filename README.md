# Sentinel

[![CI](https://github.com/F0rgiv3n/sentinel/actions/workflows/ci.yml/badge.svg)](https://github.com/F0rgiv3n/sentinel/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**A legal-first, source-agnostic change-monitoring framework.**

Sentinel watches things that change on the internet — new software releases, news
headlines, forum posts, earthquakes — and pushes you a notification when they do.
It is built around one principle that most "website monitor" projects ignore:

> **Be a good citizen of the web.** Prefer official APIs. Scrape only where it's
> allowed, and even then, do it politely.

That principle is baked into the architecture, not bolted on — see
[Legal & ethical design](#legal--ethical-design) below.

---

## Why this exists

Plenty of bots poll a URL on a tight loop and diff the HTML. That's brittle,
wasteful, and often against a site's terms. Sentinel takes the opposite approach:
a small, pluggable core that normalizes **any** source into the same shape, then
applies one diff engine, one history store, and one notification layer to all of
them. Adding a new thing to watch is a ~30-line class.

## Features

- **Pluggable sources** — RSS/Atom, GitHub Releases, Hacker News, USGS
  earthquakes out of the box; add your own by subclassing one base class.
- **One diff engine for everything** — content-hashed, so it detects both *new*
  items and *edits* to existing ones.
- **Persistent history (SQLite)** — survives restarts; a single file you can
  back up or mount as a Docker volume.
- **Polite HTTP by construction** — robots.txt enforcement, per-host rate
  limiting with `Crawl-delay`, conditional GET (ETag / If-Modified-Since), and
  an honest `User-Agent`.
- **Declarative YAML config** — with `${ENV}` substitution so secrets stay out
  of the file.
- **ntfy push notifications** — free, no app account needed.
- **Docker-first** — multi-stage build, non-root runtime, healthcheck, and a
  one-command `docker compose up`.
- **Tested** — unit tests for the diff engine, config loader, and storage.

## Architecture

```
                ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   config.yaml ─┤   Sources    │   │ PoliteClient │   │   Notifier   │
                │ (pluggable)  │   │ robots.txt + │   │   (ntfy)     │
                │  rss         │   │ rate limit + │   │              │
                │  github      │──▶│ conditional  │   └──────▲───────┘
                │  hackernews  │   │     GET      │          │
                │  usgs        │   └──────────────┘          │
                └──────┬───────┘                             │
                       │ Snapshot (normalized Items)         │
                       ▼                                     │
                ┌──────────────┐   ┌──────────────┐   ┌──────┴───────┐
                │  Diff engine │──▶│   Scheduler  │──▶│   Changes    │
                │ new / updated│   │  async loop  │   │ new / updated│
                └──────▲───────┘   └──────┬───────┘   └──────────────┘
                       │                  │
                ┌──────┴──────────────────▼───────┐
                │      Storage (SQLite history)    │
                │  seen items + conditional cursor │
                └──────────────────────────────────┘
```

Each layer talks only to the normalized `Item`/`Snapshot`/`Change` types, so any
piece can be swapped without touching the others.

## Quickstart (Docker — recommended)

```bash
git clone https://github.com/F0rgiv3n/sentinel.git
cd sentinel

cp .env.example .env                 # set NTFY_TOPIC to something unguessable
cp config.example.yaml config.yaml   # pick what to watch

docker compose up -d                 # build + run in the background
docker compose logs -f               # watch it work
```

Subscribe to your topic in the [ntfy app](https://ntfy.sh) (or
`https://ntfy.sh/<your-topic>` in a browser) and you'll get a push whenever a
watched source changes. History persists in the `sentinel-data` volume.

## Quickstart (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

export NTFY_TOPIC=sentinel-changeme-7f3a
cp config.example.yaml config.yaml

sentinel sources          # list configured sources
sentinel once             # poll everything once (records a baseline first run)
sentinel run              # run the scheduler forever
```

## Configuration

Everything lives in `config.yaml` (see `config.example.yaml` for a documented
template). `${VAR}` and `${VAR:-default}` are expanded from the environment.

```yaml
user_agent: "Sentinel/0.1 (+https://github.com/F0rgiv3n/sentinel)"
database: data/sentinel.db
default_interval: 300          # seconds; per-source interval overrides this
notify_on_first_run: false     # silence the startup baseline

notify:
  type: ntfy
  topic: "${NTFY_TOPIC}"
  server: "${NTFY_SERVER:-https://ntfy.sh}"

sources:
  - name: big-earthquakes
    type: usgs_earthquakes
    feed: "4.5_day"
    min_magnitude: 5.0
    interval: 600

  - name: ruff-releases
    type: github_releases
    repo: astral-sh/ruff
    interval: 3600
```

### Built-in source types

| `type`              | Watches                                  | Access            | Key options                          |
| ------------------- | ---------------------------------------- | ----------------- | ------------------------------------ |
| `usgs_earthquakes`  | USGS real-time quake feed                | Public GeoJSON    | `feed`, `min_magnitude`              |
| `github_releases`   | A repo's releases                        | Official REST API | `repo` (`owner/name`)                |
| `hackernews`        | HN stories matching a keyword            | Algolia HN API    | `query`, `limit`                     |
| `rss`               | Any RSS/Atom feed                        | Open feed         | `url`                                |

All sources accept `name`, `interval`, and `respect_robots`.

## Legal & ethical design

This is the part most monitors skip. Sentinel treats it as a feature:

- **API-first.** Where an official API exists (GitHub, Hacker News, USGS) we use
  it instead of scraping HTML. These sources opt out of robots.txt checks
  because robots.txt governs *crawlers* — a documented API client is the
  sanctioned path — but they still rate-limit.
- **robots.txt enforcement.** For crawl-style (`rss`/HTML) sources we fetch and
  honor `robots.txt`, including any `Crawl-delay`. A disallowed URL is skipped,
  not fetched.
- **Conditional GET.** Every request that can sends `If-None-Match` /
  `If-Modified-Since`; a `304 Not Modified` short-circuits the whole cycle,
  saving the server (and you) bandwidth.
- **Per-host rate limiting.** We never issue back-to-back requests to the same
  host faster than the configured minimum (or the site's `Crawl-delay`,
  whichever is larger).
- **Honest identity.** A real, contactable `User-Agent` on every request.

> **Note:** Respecting robots.txt and rate limits does not by itself make
> scraping a given site lawful — always check the site's Terms of Service.
> Sentinel gives you the tools to be polite; using them responsibly is on you.

## Extending: add a new source

```python
from sentinel.http import PoliteClient
from sentinel.models import Item, Snapshot, SourceState
from sentinel.sources.base import Source, register

@register
class MySource(Source):
    type = "my_source"

    def __init__(self, name, my_option, **kwargs):
        super().__init__(name, **kwargs)
        self.my_option = my_option

    async def fetch(self, client: PoliteClient, state: SourceState) -> Snapshot | None:
        resp = await client.get("https://example.com/feed.json",
                                etag=state.etag, respect_robots=self.respect_robots)
        if resp.status_code == 304:
            return None
        resp.raise_for_status()
        items = [Item(id=str(x["id"]), title=x["title"], url=x["link"])
                 for x in resp.json()]
        return Snapshot(source=self.name, items=items, etag=resp.headers.get("ETag"))
```

Then reference it in `config.yaml`:

```yaml
sources:
  - name: my-thing
    type: my_source
    my_option: hello
```

Notifiers extend the same way — subclass `notify.base.Notifier` and register it
in `notify/__init__.py` (Telegram/Discord/email are natural next additions).

## Development

```bash
pip install -e ".[dev]"
pytest          # run the test suite
ruff check .    # lint
```

## Project layout

```
sentinel/
├── http.py            # PoliteClient: robots.txt, rate limit, conditional GET
├── models.py          # Item / Snapshot / SourceState
├── diffing.py         # content-hash diff engine
├── storage.py         # SQLite history
├── scheduler.py       # async fetch→diff→notify loop
├── config.py          # YAML + ${ENV} loader
├── __main__.py        # CLI (run / once / sources)
├── sources/           # pluggable sources (+ registry)
└── notify/            # pluggable notifiers (ntfy)
```

## License

MIT — see [LICENSE](LICENSE).
