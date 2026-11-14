"""``python -m fidetype.collector --config collector.toml`` (same as ``fidetype collector``)."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from fidetype.collector.config import ConfigError, load


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fidetype collector",
                                 description="Run the Fidetype collector v0 (FEP-0006): receivers -> processors -> "
                                             "exporters, from one TOML or JSON configuration file.")
    ap.add_argument("--config", required=True, help="collector configuration (.toml or .json)")
    ap.add_argument("--check", action="store_true", help="check the configuration, print the pipelines, and exit")
    ap.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    ap.add_argument("--max-streams", type=int, default=None, help="stop after this many streams sent end")
    a = ap.parse_args(argv)
    try:
        cfg = load(a.config)
        if a.check:
            print(cfg.describe())
            return 0
        from fidetype.collector.service import Collector

        col = Collector(cfg)
        col.run(duration_s=a.duration, max_streams=a.max_streams)
    except ConfigError as e:
        print(f"fidetype collector: configuration error: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"fidetype collector: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"fidetype collector: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
