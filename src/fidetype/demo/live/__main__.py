"""``fidetype demo live``: the visible replay demo (P14-06).

::

    fidetype demo live                       # default tracks (T15 implant + emg2qwerty EMG); opens the browser
    fidetype demo live --tracks synthetic    # no data needed
    fidetype demo live --check               # show which tracks have their data, then exit
    fidetype demo live --prepare emg2qwerty  # one-time preparation of a track (truth, split, trust config)
    fidetype demo live --no-browser --port 8770 --speed 2

The server binds to 127.0.0.1 only. Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

from fidetype.demo.live import config as C
from fidetype.demo.live.tracks import Track, make_track


def _prepare(track_id: str, cfg: dict, base: Path | None) -> int:
    spec = next((t for t in cfg["tracks"] if t["id"] == track_id), None)
    if spec is None or not spec.get("prepare"):
        print(f"track {track_id!r} has no preparation step", file=sys.stderr)
        return 2
    prep = spec["prepare"]
    if prep.get("kind") != "emg2qwerty":
        print(f"unknown preparation kind {prep.get('kind')!r}", file=sys.stderr)
        return 2
    from fidetype.demo.live.emg_prepare import prepare

    streams = C.expand(spec["streams_dir"], base)
    raw = C.expand(prep["raw"], base)
    out = C.expand(prep["out"], base)
    try:
        prepare(streams, raw, out, log=lambda m: print(m, file=sys.stderr))
    except FileNotFoundError as e:
        print(f"cannot prepare {track_id}: {e}", file=sys.stderr)
        return 2
    print(f"prepared {track_id}: {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="fidetype demo live",
                                 description="Replay recorded decoder output in the browser and show each trust "
                                             "decision (commit / offer / withhold). Local only (127.0.0.1).")
    ap.add_argument("--config", type=Path, help="demo configuration (default: the packaged live-demo.json)")
    ap.add_argument("--tracks", help="comma-separated track ids (default: the config's default_tracks)")
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed (1 = real time; default 1)")
    ap.add_argument("--port", type=int, default=8770, help="port on 127.0.0.1 (default 8770; a free one if taken)")
    ap.add_argument("--start", type=int, default=0, metavar="K", help="start at utterance K of each track")
    ap.add_argument("--no-loop", action="store_true", help="stop each track after its last utterance")
    ap.add_argument("--no-browser", action="store_true", help="do not open the browser")
    ap.add_argument("--duration", type=float, metavar="S", help="stop after S seconds (default: run until Ctrl+C)")
    ap.add_argument("--check", action="store_true", help="print the status of every track and exit")
    ap.add_argument("--prepare", metavar="TRACK", help="run the one-time preparation of TRACK and exit")
    a = ap.parse_args(argv)
    if a.speed <= 0:
        ap.error("--speed must be positive")
    try:
        cfg, base = C.load(a.config)
    except C.DemoConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.prepare:
        return _prepare(a.prepare, cfg, base)
    all_tracks = [make_track(s, base) for s in cfg["tracks"]]
    if a.check:
        for t in all_tracks:
            st, msg = t.status()
            print(f"{t.id:<12} {t.kind:<12} {st:<13} {msg}")
        return 0
    explicit = a.tracks is not None
    wanted = [x.strip() for x in a.tracks.split(",") if x.strip()] if explicit else list(
        cfg.get("default_tracks") or [t.id for t in all_tracks])
    by_id = {t.id: t for t in all_tracks}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        print(f"error: unknown track {unknown[0]!r} (known: {', '.join(by_id)})", file=sys.stderr)
        return 2
    chosen: list[Track] = []
    unavailable = []
    for w in wanted:
        t = by_id[w]
        st, msg = t.status()
        if st != "ok":
            print(f"track {w}: {st}: {msg}", file=sys.stderr)
            unavailable.append({"id": w, "title": t.title, "status": st, "message": msg})
            continue
        chosen.append(t)
    if explicit and unavailable:
        print("error: a requested track is not available (see above). Nothing was started.", file=sys.stderr)
        return 2
    if not chosen:
        print("error: none of the default tracks has its data. The demo replays recorded data from "
              f"{C.data_root()} (set {C.DATA_ENV} to change it). See docs/demo.md, or run without data: "
              "fidetype demo live --tracks synthetic", file=sys.stderr)
        return 2
    for t in chosen:
        try:
            t.load()
        except Exception as e:
            print(f"error: track {t.id} could not load its data: {e}", file=sys.stderr)
            return 2
    from fidetype.adapters.ws import WSUnavailableError
    from fidetype.demo.live.server import DemoServer

    try:
        srv = DemoServer(chosen, port=a.port, speed=a.speed, loop=not a.no_loop, start=a.start,
                         unavailable=unavailable, log=lambda m: print(m, file=sys.stderr))
        srv.start()
    except WSUnavailableError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"Fidetype live demo: {srv.url}  (replay of recorded data; tracks: {', '.join(t.id for t in chosen)})")
    print("Press Ctrl+C to stop.")
    if not a.no_browser:
        import webbrowser

        webbrowser.open(srv.url)
    try:
        end = time.monotonic() + a.duration if a.duration else None
        while end is None or time.monotonic() < end:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        srv.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
