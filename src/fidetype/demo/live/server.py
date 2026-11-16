"""The local demo server (P14-06): the FEP-0004 WebSocket server plus one replay player per track.

It reuses :class:`fidetype.adapters.ws.WSServer` (bound to 127.0.0.1):

- ``GET /``                the demo page (``web/index.html`` in this package)
- ``GET /state/state.json`` the tracks, their status, licences and the full-set numbers
- ``ws /events``           the demo messages (``demo_*``), resumable with ``from_seq``
- ``ws /decisions``        only the ``trust_decision`` events (FEP-0001), as any NTS
                           consumer (an AAC app, P14-09) would read them

Each player thread waits until each message of its track is due (real
time divided by ``speed``) and publishes it. The players add the running
counts. A background thread per track computes the full-set numbers
(:meth:`~fidetype.demo.live.tracks.Track.summary`).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import threading
import time
import traceback
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from fidetype.demo.live.tracks import Track, category

STATE_SCHEMA = "fidetype.live-demo-state/0.1"


def free_port(host: str, preferred: int) -> int:
    """``preferred`` if it is free on ``host``, else a free port from the OS."""
    for port in ([preferred] if preferred else []) + [0]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind((host, port))
            return int(s.getsockname()[1])
        except OSError:
            continue
        finally:
            s.close()
    raise OSError("no free port")


def web_dir() -> Path:
    return Path(str(resources.files("fidetype.demo.live").joinpath("web")))


class _Counts:
    def __init__(self) -> None:
        self.n = self.commit = self.offer = self.withhold = self.wrong_commit = self.offer_hit = 0
        self.passes = 0

    def add(self, action: str, outcome: str) -> None:
        self.n += 1
        c = category(action)
        setattr(self, c, getattr(self, c) + 1)
        self.wrong_commit += outcome == "commit-wrong"
        self.offer_hit += outcome == "offer-hit"

    def as_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in ("n", "commit", "offer", "withhold", "wrong_commit", "offer_hit", "passes")}
        d["wrong_commit_rate"] = round(self.wrong_commit / self.n, 4) if self.n else None
        return d


class DemoServer:
    """Serve the page and replay ``tracks`` (already loaded) until :meth:`stop`."""

    def __init__(self, tracks: list[Track], host: str = "127.0.0.1", port: int = 8770, speed: float = 1.0,
                 loop: bool = True, start: int = 0, unavailable: list[dict[str, Any]] | None = None,
                 log: Callable[[str], None] | None = None, summaries: bool = True) -> None:
        from fidetype.adapters.ws import OutputHub, ServerSettings, WSServer

        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("the demo server binds to the local machine only")
        if speed <= 0:
            raise ValueError("speed must be positive")
        self.tracks = tracks
        self.speed = float(speed)
        self.loop = loop
        self.start_index = max(0, int(start))
        self.unavailable = list(unavailable or [])
        self.log = log or (lambda m: None)
        self.want_summaries = summaries
        self.port = free_port(host, port)
        self.host = host
        self.state_dir = Path(tempfile.mkdtemp(prefix="fidetype-demo-"))
        self.events = OutputHub("events", resumable=True, history=50_000, queue_size=4096,
                                welcome_extra={"demo": "fidetype live demo"})
        self.decisions = OutputHub("decisions", resumable=True, history=8192)
        origins = [f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"]
        self.ws = WSServer(settings=ServerSettings(host=host, port=self.port, origins=origins,
                                                   static={"/": str(web_dir()), "/state": str(self.state_dir)}),
                           decisions=self.decisions, events=self.events)
        self.summaries: dict[str, Any] = {}
        self.counts = {t.id: _Counts() for t in tracks}
        self.errors: dict[str, str] = {}
        self.stopping = threading.Event()
        self.threads: list[threading.Thread] = []
        self.lock = threading.Lock()
        self.started_at = time.time()

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    # --- state file ---------------------------------------------------------------------
    def state(self) -> dict[str, Any]:
        from fidetype import __version__

        tr = []
        for t in self.tracks:
            i = t.info()
            i["summary"] = self.summaries.get(t.id)
            i["error"] = self.errors.get(t.id)
            tr.append(i)
        return {"schema": STATE_SCHEMA, "fidetype_version": __version__, "speed": self.speed, "loop": self.loop,
                "tracks": tr, "unavailable": self.unavailable, "started_at": self.started_at}

    def write_state(self) -> None:
        with self.lock:
            tmp = self.state_dir / "state.json.tmp"
            tmp.write_text(json.dumps(self.state(), ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.state_dir / "state.json")

    # --- lifecycle ----------------------------------------------------------------------
    def start(self) -> "DemoServer":
        self.write_state()
        self.ws.start()
        for t in self.tracks:
            th = threading.Thread(target=self._play, args=(t,), name=f"demo-play-{t.id}", daemon=True)
            th.start()
            self.threads.append(th)
            if self.want_summaries:
                sm = threading.Thread(target=self._summary, args=(t,), name=f"demo-summary-{t.id}", daemon=True)
                sm.start()
                self.threads.append(sm)
        return self

    def stop(self) -> None:
        self.stopping.set()
        for th in self.threads:
            th.join(2.0)
        self.ws.stop()
        shutil.rmtree(self.state_dir, ignore_errors=True)

    def __enter__(self) -> "DemoServer":
        return self.start()

    def __exit__(self, *exc: Any) -> None:
        self.stop()

    # --- workers ------------------------------------------------------------------------
    def _publish(self, msg: dict[str, Any]) -> None:
        self.events.publish(msg)

    def _summary(self, t: Track) -> None:
        try:
            s = t.summary()
        except Exception as e:  # report, do not crash the demo
            self.log(f"track {t.id}: summary failed: {e}")
            s = {"error": str(e)[:300]}
        self.summaries[t.id] = s
        self.write_state()
        self._publish({"type": "demo_summary", "track": t.id, "summary": s})

    def _wait_until(self, due: float) -> bool:
        while not self.stopping.is_set():
            left = due - time.monotonic()
            if left <= 0:
                return True
            self.stopping.wait(min(left, 0.2))
        return False

    def _play(self, t: Track) -> None:
        try:
            self._play_loop(t)
        except Exception as e:
            self.errors[t.id] = f"{type(e).__name__}: {e}"[:300]
            self.log(f"track {t.id}: replay stopped: {self.errors[t.id]}")
            self.log(traceback.format_exc())
            self.write_state()
            self._publish({"type": "demo_error", "track": t.id, "error": self.errors[t.id]})

    def _play_loop(self, t: Track) -> None:
        n = len(t)
        k = self.start_index % n if n else 0
        counts = self.counts[t.id]
        while not self.stopping.is_set() and n:
            t0 = time.monotonic()
            for t_rel, msg in t.utterance(k):
                if not self._wait_until(t0 + t_rel / self.speed):
                    return
                if msg is None:
                    continue
                out = dict(msg, track=t.id, u=k, n_total=n)
                if msg["type"] == "demo_decision":
                    d = msg["decision"]
                    counts.add(d["action"], msg["outcome"])
                    out["counts"] = counts.as_dict()
                    self.decisions.publish(dict(d, session=f"{t.id}/{d.get('session', k)}"))
                self._publish(out)
            if not self._wait_until(time.monotonic() + t.gap_s / self.speed):
                return
            k += 1
            if k >= n:
                if not self.loop:
                    self._publish({"type": "demo_track_end", "track": t.id})
                    return
                k = 0
                counts.passes += 1
