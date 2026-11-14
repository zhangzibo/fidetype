"""The collector service (FEP-0006 sections 2 and 7): build the pipelines from a configuration and run them.

One loop, one thread for the pipelines (the WebSocket server and the
health endpoint have their own threads). Each step: every receiver of a
pipeline gives its new items, the items go through the processors in
order, then to every exporter of the pipeline. The loop reads new input
only after the last items reached the exporters, so a slow processor or
exporter slows the reading (back-pressure); nothing is dropped to keep up.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from fidetype.collector import exporters as E
from fidetype.collector import processors as P
from fidetype.collector import receivers as R
from fidetype.collector.config import DEFAULT_HEALTH_LISTEN, CollectorConfig, ComponentConfig, ConfigError, is_loopback


#: Default gap mode of an ``lsl`` receiver. Stricter than the LSL-G1 reference default (``mark``):
#: in the collector a frame gap inside an utterance is a loss (FEP-0006 5.2), not a note.
LSL_COLLECTOR_ON_GAP = "abort"


def _stderr(msg: str) -> None:
    sys.stderr.write(f"[fidetype.collector] {msg}\n")
    sys.stderr.flush()


def _env_secret(where: str, name: str | None) -> str | None:
    if not name:
        return None
    v = os.environ.get(name)
    if not v:
        raise ConfigError(f"{where}: environment variable {name!r} is empty or not set")
    return v


def _host_port(v: str) -> tuple[str, int]:
    host, _, port = v.rpartition(":")
    return host.strip("[]"), int(port)


@dataclass
class Pipeline:
    name: str
    receivers: list[R.Receiver]
    processors: list[P.Processor]
    exporters: list[E.Exporter]

    def _run(self, items: list[R.Item], start: int = 0) -> None:
        for proc in self.processors[start:]:
            if not items:
                return
            items = proc.process(items)
        if items:
            for ex in self.exporters:
                ex.export(items)

    def step(self, timeout: float) -> int:
        n = 0
        multi = len(self.receivers) > 1
        for rec in self.receivers:
            if rec.done:
                continue
            items = self._prefix(rec, rec.poll(timeout / max(1, len(self.receivers))))
            n += len(items)
            self._run(items)
        return n

    def _prefix(self, rec: R.Receiver, items: list[R.Item]) -> list[R.Item]:
        """FEP-0006 1.4: with several receivers, the stream id is ``<receiver>/<stream id>``.

        So the stream ids of two receivers never meet in one trust session. The decisions of the
        stream carry it as ``session``. With one receiver the stream id stays as it is.
        """
        if len(self.receivers) < 2:
            return items
        return [(f"{rec.name}/{sid}", {**ev, "stream": f"{rec.name}/{sid}"} if ev.get("type") == R.STATUS else ev)
                for sid, ev in items]

    def finish(self) -> None:
        for rec in self.receivers:
            self._run(self._prefix(rec, rec.finish()))
        for i, proc in enumerate(self.processors):
            self._run(proc.finish(), i + 1)

    @property
    def done(self) -> bool:
        return all(r.done for r in self.receivers)


class Collector:
    """Build and run the pipelines of a :class:`CollectorConfig`.

    ::

        col = Collector(config.load("collector.toml"))
        col.run()                    # until every finite receiver is done, the duration, or Ctrl+C
        print(col.metrics())
    """

    def __init__(self, config: CollectorConfig, log: Callable[[str], None] | None = None) -> None:
        self.config = config
        quiet = config.service.get("log") == "quiet"
        self.log = (lambda m: None) if quiet else (log or _stderr)
        self.stop_event = threading.Event()
        self.started_at: float | None = None
        self.state = "new"
        self._receivers: dict[str, R.Receiver] = {}
        self._exporters: dict[str, E.Exporter] = {}
        self.pipelines: list[Pipeline] = []
        self._health: ThreadingHTTPServer | None = None
        self._lock = threading.Lock()
        self._build()

    # --- build ------------------------------------------------------------------------

    def _receiver(self, c: ComponentConfig) -> R.Receiver:
        o = c.options
        if c.type == "file":
            return R.FileReceiver(c.name, [self.config.path(p) for p in o["paths"]], self.log,
                                  follow=o.get("follow", False), eof=o.get("eof", "close"), batch=o.get("batch", 256),
                                  idle_timeout_s=float(o.get("idle_timeout_s", 10.0)),
                                  poll_interval_s=float(o.get("poll_interval_s", 0.05)), stream_id=o.get("stream_id"))
        if c.type == "lsl":
            return self._lsl_receiver(c)
        from fidetype.adapters import ws as W

        host, port = _host_port(o.get("listen", f"127.0.0.1:{W.DEFAULT_PORT}"))
        ingest = W.IngestSettings(reorder_window=o.get("reorder_window", 16),
                                  reorder_timeout_s=float(o.get("reorder_timeout_s", 0.25)),
                                  resume_timeout_s=float(o.get("resume_timeout_s", 10.0)))
        ssl = None
        if "certfile" in o:
            ssl = W._ssl_context(str(self.config.path(o["certfile"])),
                                 str(self.config.path(o["keyfile"])) if "keyfile" in o else None, server=True)
        return R.WebSocketReceiver(c.name, self.log, host=host, port=port,
                                   token=_env_secret(f"receivers.{c.name}.token_env", o.get("token_env")),
                                   origins=o.get("origins"), ssl=ssl, ingest=ingest, queue_max=o.get("queue_max", 8192))

    def _lsl_receiver(self, c: ComponentConfig) -> R.Receiver:
        from fidetype.adapters import lsl as L

        if not L.pylsl_available():
            raise ConfigError(f"receivers.{c.name}: type 'lsl' needs pylsl: pip install \"fidetype[lsl]\"")
        o = c.options
        try:
            mapping = L.LSLMapping(
                values=o.get("values", "auto"), vocab=o.get("vocab"), vocab_type=o.get("vocab_type"),
                blank=o.get("blank"), clock=o.get("clock", "receiver"), out_of_order=o.get("out_of_order", "clamp"),
                gap_factor=float(o.get("gap_factor", 2.5)), on_gap=o.get("on_gap", LSL_COLLECTOR_ON_GAP),
                boundary_markers=tuple(o.get("boundary_markers", ("segment_end",))),
                plain_markers=o.get("plain_markers", "ignore"), merge_window_s=float(o.get("merge_window_s", 0.05)),
                reconnect_mode=o.get("reconnect_mode", "thread"),
                reconnect_timeout_s=float(o.get("reconnect_timeout_s", 30.0)),
                open_timeout_s=float(o.get("open_timeout_s", L.DEFAULT_OPEN_TIMEOUT_S)))
        except ValueError as e:
            raise ConfigError(f"receivers.{c.name}: {e}") from None
        log = self.log
        name = c.name

        def open_source() -> object:
            return L.open_source(o.get("stream_name"), o.get("stream_type"), o.get("source_id"),
                                 events=o.get("events", "auto"), mapping=mapping,
                                 timeout=float(o.get("resolve_timeout_s", 10.0)),
                                 log=lambda m: log(f"receivers.{name}: {m}"))

        return R.LSLReceiver(c.name, self.log, open_source, stream_id=o.get("stream_id"),
                             stop_at_end=o.get("stop_at_end", True))

    def _processor(self, c: ComponentConfig) -> P.Processor:
        o = c.options
        if c.type == "validate":
            return P.ValidateProcessor(c.name, self.log, on_invalid=o.get("on_invalid", "cut"),
                                       level=o.get("level", "core"))
        if c.type == "trust":
            cfg_path = self.config.path(o["config"])
            if not cfg_path.is_file():
                raise ConfigError(f"processors.{c.name}.config: trust configuration not found: {cfg_path}")
            ledger = None
            if "ledger" in o:
                from fidetype.trust.provenance import ProvenanceLedger

                lo = o["ledger"]
                key = _env_secret(f"processors.{c.name}.ledger.key_env", lo.get("key_env"))
                ledger = ProvenanceLedger(self.config.path(lo["path"]), text_mode=lo.get("text_mode", "hash"),
                                          id_mode=lo.get("id_mode", "hash"),
                                          hash_key=key.encode("utf-8") if key else None, key_id=lo.get("key_id"))
            try:
                return P.TrustProcessor(c.name, self.log, cfg_path, decoder=o.get("decoder", "none"),
                                        max_attempts=o.get("max_attempts", 2), route=o.get("route", "auto"),
                                        min_signal_quality=o.get("min_signal_quality"),
                                        declaration_check=o.get("declaration_check", "warn"), ledger=ledger)
            except (ValueError, KeyError, OSError) as e:
                raise ConfigError(f"processors.{c.name}: cannot build the trust layer: {e}") from None
        if c.type == "redact":
            key = _env_secret(f"processors.{c.name}.key_env", o.get("key_env"))
            return P.RedactProcessor(c.name, self.log, mode=o.get("mode", "drop"),
                                     key=key.encode("utf-8") if key else None, key_id=o.get("key_id"),
                                     hypothesis_text=o.get("hypothesis_text", True))
        return P.ThinProcessor(c.name, self.log, keep_provisional=o.get("keep_provisional", "changes"))

    def _exporter(self, c: ComponentConfig) -> E.Exporter:
        o = c.options
        if c.type == "jsonl":
            return E.JsonlExporter(c.name, self.log, self.config.path(o["path"]), o["types"], append=o.get("append", False))
        if c.type == "stdout":
            return E.StdoutExporter(c.name, self.log, o["types"])
        if c.type == "lsl":
            from fidetype.adapters import lsl as L

            if not L.pylsl_available():
                raise ConfigError(f"exporters.{c.name}: type 'lsl' needs pylsl: pip install \"fidetype[lsl]\"")
            return E.LSLExporter(c.name, self.log, stream_name=o.get("stream_name"), source_id=o.get("source_id"),
                                 config_id=o.get("config_id"), no_text=o.get("no_text", False))
        if "receiver" not in o:  # a standalone /decisions server
            from fidetype.adapters import ws as W

            host, port = _host_port(o.get("listen", f"127.0.0.1:{W.DEFAULT_PORT}"))
            ssl = None
            if "certfile" in o:
                ssl = W._ssl_context(str(self.config.path(o["certfile"])),
                                     str(self.config.path(o["keyfile"])) if "keyfile" in o else None, server=True)
            return E.StandaloneWebSocketExporter(
                c.name, self.log, host=host, port=port,
                token=_env_secret(f"exporters.{c.name}.token_env", o.get("token_env")),
                origins=o.get("origins"), ssl=ssl, linger_s=float(o.get("linger_s", 0.0)))
        rec = self._receivers[o["receiver"]]
        assert isinstance(rec, R.WebSocketReceiver)
        return E.WebSocketExporter(c.name, self.log, rec.hub)

    def _build(self) -> None:
        cfg = self.config
        for name, c in cfg.receivers.items():
            self._receivers[name] = self._receiver(c)
        for name, c in cfg.exporters.items():
            self._exporters[name] = self._exporter(c)
        for p in cfg.pipelines.values():
            self.pipelines.append(Pipeline(p.name, [self._receivers[n] for n in p.receivers],
                                           [self._processor(cfg.processors[n]) for n in p.processors],
                                           [self._exporters[n] for n in p.exporters]))
        # An LSL decisions outlet names the trust configuration in its desc (LSL-X1): take it from the
        # trust processor(s) of the pipeline(s) it serves, when the file does not set config_id.
        for name, ex in self._exporters.items():
            if isinstance(ex, E.LSLExporter) and ex.config_id is None:
                ids = {x.config_id for pl in self.pipelines if ex in pl.exporters
                       for x in pl.processors if isinstance(x, P.TrustProcessor)}
                if len(ids) == 1:
                    ex.config_id = ids.pop()

    # --- lifecycle --------------------------------------------------------------------

    def start(self) -> "Collector":
        for ex in self._exporters.values():
            ex.start()
        for rec in self._receivers.values():
            rec.start()
        h = self.config.service.get("health")
        if h is not None:
            host, port = _host_port(h.get("listen", DEFAULT_HEALTH_LISTEN))
            token = _env_secret("service.health.token_env", h.get("token_env"))
            if not is_loopback(host) and token is None:
                self.log("service.health: WARNING: /metrics listens beyond localhost without a token "
                         "(allow_unauthenticated = true)")
            self._start_health(host, port, token)
        self.started_at = time.monotonic()
        self.state = "running"
        for line in self.config.describe().splitlines():
            self.log(line)
        return self

    def step(self, timeout: float = 0.05) -> int:
        with self._lock:
            return sum(p.step(timeout) for p in self.pipelines if not p.done)

    @property
    def done(self) -> bool:
        return all(p.done for p in self.pipelines)

    def ended_streams(self) -> int:
        return sum(r.counts.get("ended_streams", 0) for r in self._receivers.values())

    def stop(self) -> None:
        if self.state == "stopped":
            return
        self.state = "stopping"
        with self._lock:
            for p in self.pipelines:
                p.finish()
        for rec in self._receivers.values():
            rec.stop()
        for ex in self._exporters.values():
            ex.stop()
        if self._health is not None:
            self._health.shutdown()
            self._health.server_close()
            self._health = None
        mf = self.config.service.get("metrics_file")
        self.state = "stopped"
        if mf:
            p = self.config.path(mf)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.metrics(), indent=2) + "\n", encoding="utf-8")

    def run(self, duration_s: float | None = None, max_streams: int | None = None) -> str:
        """Run until every receiver is done, ``duration_s``, ``max_streams`` ended streams, :meth:`request_stop` or Ctrl+C."""
        svc = self.config.service
        duration_s = duration_s if duration_s is not None else svc.get("duration_s")
        max_streams = max_streams if max_streams is not None else svc.get("max_streams")
        if self.state == "new":
            self.start()
        t0 = time.monotonic()
        reason = ""
        try:
            while True:
                if self.stop_event.is_set():
                    reason = "stopped"
                    break
                if self.done:
                    reason = "input done"
                    break
                if duration_s is not None and time.monotonic() - t0 >= duration_s:
                    reason = "duration"
                    break
                if max_streams is not None and self.ended_streams() >= max_streams:
                    reason = "max_streams"
                    break
                self.step(0.05)
            linger = max((ex.linger_s for ex in self._exporters.values()), default=0.0)
            if reason == "input done" and linger > 0:
                self.log(f"input done; serving /decisions for {linger:g} s more (linger_s)")
                self.stop_event.wait(linger)
        except KeyboardInterrupt:
            reason = "interrupted"
        finally:
            self.stop()
        self.log(f"stop ({reason}): " + json.dumps(self.summary()))
        return reason

    def request_stop(self) -> None:
        self.stop_event.set()

    # --- metrics and health -------------------------------------------------------------

    def metrics(self) -> dict[str, Any]:
        """Counters of every component. No host name, client address, token, key or decoded text."""
        return {
            "state": self.state,
            "uptime_s": 0.0 if self.started_at is None else round(time.monotonic() - self.started_at, 3),
            "pipelines": {p.name: {
                "receivers": {r.name: r.stats() for r in p.receivers},
                "processors": {x.name: x.stats() for x in p.processors},
                "exporters": {x.name: x.stats() for x in p.exporters},
            } for p in self.pipelines},
        }

    def summary(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ended_streams": self.ended_streams()}
        for p in self.pipelines:
            for x in p.processors:
                if isinstance(x, P.TrustProcessor):
                    s = x.stats()
                    for k in ("final_decisions", "decisions", "aborted_utterances", "rejected_events"):
                        out[k] = out.get(k, 0) + s[k]
        return out

    def _start_health(self, host: str, port: int, token: str | None = None) -> None:
        """``GET /healthz`` and ``GET /metrics``. With ``token``: ``/metrics`` needs ``Authorization: Bearer <token>``.

        ``/healthz`` stays open (FEP-0006 section 7, decision on question 3), so a liveness probe works
        without a header. It shows only ``{"status": ...}``: no counter, no name, no address.
        """
        from fidetype.adapters import ws as W

        col = self
        check = W.token_checker(token) if token else None

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path == "/healthz":  # open (liveness probes): status only
                    self._send({"status": "ok" if col.state == "running" else col.state})
                    return
                if self.path != "/metrics":
                    self.send_error(404)
                    return
                if check is not None and not check(W.bearer_token(self.headers.get("Authorization"))):
                    data = b'{"error": "unauthorized"}\n'
                    self.send_response(401)
                    self.send_header("WWW-Authenticate", "Bearer")
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self._send(col.metrics(), 200)

            def _send(self, body: dict[str, Any], code: int | None = None) -> None:
                data = (json.dumps(body) + "\n").encode("utf-8")
                self.send_response(code if code is not None else (200 if body.get("status") == "ok" else 503))
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:  # no client addresses in any log
                pass

        self._health = ThreadingHTTPServer((host, port), Handler)
        self._health.daemon_threads = True
        threading.Thread(target=self._health.serve_forever, name="fidetype-collector-health", daemon=True).start()

    @property
    def health_port(self) -> int | None:
        return None if self._health is None else int(self._health.server_address[1])

    def receiver(self, name: str) -> R.Receiver:
        return self._receivers[name]


def run_file(path: str | Path, **kw: Any) -> Collector:
    """Load a configuration file, run the collector to the end, return it (for its metrics)."""
    from fidetype.collector.config import load

    col = Collector(load(path))
    col.run(**kw)
    return col
