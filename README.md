# 🌍 Nightwatch — earthquake alerts for Greece

**🇬🇧 English** · [🇬🇷 Ελληνικά](README.el.md)

[![Earthquake monitor](https://github.com/geogoor/nightwatch/actions/workflows/monitor.yml/badge.svg)](https://github.com/geogoor/nightwatch/actions/workflows/monitor.yml)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Nightwatch keeps an eye on earthquakes in Greece and pushes a notification to my
phone a couple of minutes after one happens. It's free, it runs on its own, and
it only uses official public data.

I built it for a simple reason: Greece shakes *a lot* — small and moderate
quakes happen almost every day — and I wanted a quiet, reliable heads-up on my
phone without installing yet another ad-filled app or paying for a server just to
keep a script alive.

It's a small project on purpose, but it does the whole loop end to end: ask an
official source for recent quakes → work out which ones are new → send a push →
remember what it already sent → repeat on a schedule. The entire thing is one
readable Python file.

> ℹ️ **This is a proof-of-concept / portfolio project, not a safety system.** It
> works well enough to be genuinely useful and to show the pipeline off, but
> please don't rely on it as an official early-warning service. More in
> [*Notes & limitations*](#notes--limitations).

---

## 📲 What it looks like

A real alert on the phone. Tapping it opens a map centred on the earthquake's
epicenter, so you can see exactly where it was:

<p align="center">
  <img src="docs/notification.png" alt="A Nightwatch earthquake notification on a phone" width="300">
  &nbsp;&nbsp;
  <img src="docs/usgs-event.png" alt="An earthquake details page" width="300">
</p>

> The right-hand screenshot is from the earlier USGS-based version (see the next
> section). Today the notification opens a map of the epicenter instead.

---

## What I changed, and why (June 2026)

This is the interesting part, so it's worth telling honestly.

Nightwatch originally pulled its data from **USGS** (the U.S. Geological Survey).
It worked — until it didn't. A real **M3.2 near Crete** went by with no alert,
and then two days later a bigger quake *did* notify me. That's backwards, so I
went digging.

The culprit was the data source. USGS is a **global** catalogue: it's excellent
for big events anywhere on Earth, but it routinely **misses moderate (M3–4)
Greek earthquakes, or lists them late**. The quake I missed was simply never in
the USGS feed at the time — even though the Greek national network had it within
a minute.

So I switched the source to the **National Observatory of Athens (NOA)** — the
Γεωδυναμικό Ινστιτούτο, Greece's own seismic network (and the one that feeds the
European EMSC). It catalogues Greek quakes far more completely and much faster.
While I was in there, I also:

- **lowered the alert threshold from M3.5 to M3.0** — NOA reports magnitudes on
  the local **ML / Richter** scale, which is exactly what Greek news quotes;
- **made the notifications more useful** — NOA doesn't have a public page per
  event, so tapping an alert now opens the **epicenter on a map**. And since
  NOA usually only labels events as a vague "Greece", the heading names the
  **nearest town**, worked out from the coordinates (e.g. *M5.2 · 13 km ΝΑ της
  Λίμνης Ευβοίας*) — no geocoding service, just a built-in list of towns and a
  distance calculation.

The old USGS source is still in the code as an alternate, in case it's ever
useful for another region.

## How it works

```
                 ┌──────────────────────────────────────────────┐
   GitHub Actions│  every 5 min   →  python nightwatch.py        │
   (the "cron")  └───────────────────────┬──────────────────────┘
                                         │
                 ┌───────────────────────▼──────────────────────┐
                 │ 1. Ask NOA for recent quakes in the Greece    │
                 │    bounding box, above the chosen magnitude   │
                 │ 2. Compare against seen.json (already alerted)│
                 │ 3. For each NEW quake → send an ntfy push     │
                 │ 4. Save the updated seen.json                 │
                 └───────────────────────┬──────────────────────┘
                                         │
                          ntfy.sh ───────▼──────►  📱 my phone
```

A few details that make it behave nicely:

- It filters by a **bounding box** around Greece (mainland, Aegean, the islands),
  so you only get quakes from the region you care about.
- It **stays silent on the very first run** — it just records what's already out
  there as a baseline, so it never floods you on startup.
- It remembers what it has reported in `seen.json`, so you get each quake **once**.
- On GitHub Actions that state is kept in the **Actions cache** between runs, so
  the bot remembers what it sent without committing bot noise into git history.

## What it touches (for the portfolio-curious)

Small, but it walks through a realistic end-to-end toolchain:

| Area | What's shown |
| --- | --- |
| Public API integration | Consuming the NOA `fdsnws` REST API and parsing the FDSN text format |
| Geospatial filtering | Bounding-box (lat/lon) querying for a region |
| Change detection | Stateful "what's new since last time" logic |
| Push notifications | Event-driven alerts via ntfy |
| Containerization | A small, single-stage Dockerfile |
| CI/CD & automation | A scheduled GitHub Actions workflow that runs the job 24/7 |
| Secrets management | The notification target lives in a GitHub Actions secret, never hard-coded |
| Stateful workflows | Persisting `seen.json` across runs via the Actions cache |

## Running it

### Locally

```bash
pip install -r requirements.txt

export NTFY_TOPIC=your-unguessable-topic     # pick any unique name
python nightwatch.py
```

Subscribe to the same topic in the [ntfy app](https://ntfy.sh) (or just open
`https://ntfy.sh/your-unguessable-topic` in a browser) to receive the alerts.

### With Docker

```bash
docker build -t nightwatch .
docker run -e NTFY_TOPIC=your-unguessable-topic nightwatch
```

### 24/7 on GitHub Actions (free)

1. Fork/clone this repo to your own GitHub account.
2. Add a repository **secret** named `NTFY_TOPIC`
   (Settings → Secrets and variables → Actions) with your topic name.
3. That's it — the workflow in [`.github/workflows/monitor.yml`](.github/workflows/monitor.yml)
   runs every 5 minutes, and you can also trigger it by hand from the **Actions**
   tab ("Run workflow").

The first run records a silent baseline; you'll start getting alerts from the
next new earthquake onward.

## Configuration

Everything lives in [`config.yaml`](config.yaml):

```yaml
interval: 300   # seconds between checks when running as a long-lived process

sources:
  - name: greece-earthquakes-noa
    type: noa               # National Observatory of Athens (best source for Greece)
    min_magnitude: 3.0      # only notify for magnitude 3.0 and above (Richter / ML)
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

Want a different region? Change the bounding box. Too many alerts? Raise
`min_magnitude` — Greece is genuinely busy.

## Adding another source

Each source is just a function that returns a list of `{"id", "title", "url"}`
items. Register it in the `SOURCES` dict in `nightwatch.py` and reference its
`type` in `config.yaml` — that's the whole contract. A `usgs` source ships
alongside `noa` as a worked example. Natural next additions: EMSC, weather
warnings, or anything with a public API.

## Notes & limitations

- **It's a proof of concept.** A portfolio/demo project, not a hardened service.
  Coverage, reliability and timing are good enough to show the pipeline working —
  not something to bet your safety on.
- **About the timing.** On GitHub Actions this is *not* real-time. GitHub's cron
  fires every ~5 minutes at best and is often delayed, so treat alerts as "within
  several minutes." For genuinely fast, reliable delivery, run the **Docker**
  container continuously on a small cloud host (or any always-on machine) — it
  loops on its own short `interval` instead of waiting for GitHub's scheduler.
- **Data source.** NOA (National Observatory of Athens) is Greece's national
  network: it catalogues Greek quakes far more completely and faster than the
  global USGS feed, and reports magnitudes on the local ML / Richter scale. Some
  events come in as fast automatic solutions that can later be revised — that's
  the price of real-time.
- **ntfy topics** on the public server are readable by anyone who knows the name,
  so pick one that isn't easy to guess.

## License

[MIT](LICENSE) — free to use, modify, and learn from.
