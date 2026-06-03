"""Command-line entrypoint.

    sentinel run     [-c config.yaml]   # run the scheduler forever
    sentinel once    [-c config.yaml]   # poll every source once, then exit
    sentinel sources [-c config.yaml]   # list configured sources
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from .config import load_config
from .http import PoliteClient
from .scheduler import Scheduler
from .storage import Storage


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel", description=__doc__)
    parser.add_argument("-c", "--config", default="config.yaml", help="path to config YAML")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=["run", "once", "sources"],
        help="what to do (default: run)",
    )
    return parser


async def _run(command: str, config_path: str) -> int:
    config = load_config(config_path)

    if command == "sources":
        for source in config.sources:
            print(f"  {source.name:<24} {source.type:<18} every {source.interval}s")
        return 0

    storage = Storage(config.database)
    client = PoliteClient(config.user_agent, min_interval=1.0)
    scheduler = Scheduler(config, storage, client)
    try:
        if command == "once":
            sent = await scheduler.run_once()
            print(f"Done. {sent} notification(s) sent.")
        else:
            await scheduler.run()
    finally:
        await client.aclose()
        await config.notifier.aclose()
        storage.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(args.verbose)
    try:
        return asyncio.run(_run(args.command, args.config))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
