"""Configuration of the collector (FEP-0006 section 6): load, check, explain errors.

The file format is TOML (read with the standard-library ``tomllib``) or
JSON. YAML is not supported (FEP-0006 decision, v0.1): a YAML reader needs
a new dependency (PyYAML), and TOML and JSON hold the same structure one to
one. A ``.yaml`` / ``.yml`` file gives a clear :class:`ConfigError`.

Every error is a :class:`ConfigError` whose message starts with the path
of the bad value, for example ``pipelines.main.processors[1]: unknown
processor 'trsut' (known: check, privacy, trust)``.

Relative file paths in the configuration resolve against the folder of
the configuration file, not against the working folder.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any

#: Keys of an ``lsl`` receiver (FEP-0006 section 2; the settings of ``fidetype.adapters.lsl.LSLMapping``).
LSL_RECEIVER_KEYS = {"stream_name", "stream_type", "source_id", "events", "stream_id", "stop_at_end", "on_gap",
                     "gap_factor", "clock", "out_of_order", "values", "vocab", "vocab_type", "blank",
                     "boundary_markers", "plain_markers", "merge_window_s", "resolve_timeout_s", "open_timeout_s",
                     "reconnect_mode", "reconnect_timeout_s"}
#: Component kinds -> allowed ``type`` values -> allowed keys (``type`` excluded) -> required keys.
SCHEMA: dict[str, dict[str, tuple[set[str], set[str]]]] = {
    "receivers": {
        "file": ({"paths", "follow", "eof", "batch", "idle_timeout_s", "poll_interval_s", "stream_id"}, {"paths"}),
        "websocket": ({"listen", "token_env", "origins", "certfile", "keyfile", "reorder_window",
                       "reorder_timeout_s", "resume_timeout_s", "queue_max"}, set()),
        "lsl": (LSL_RECEIVER_KEYS, set()),
    },
    "processors": {
        "validate": ({"on_invalid", "level"}, set()),
        "trust": ({"config", "decoder", "max_attempts", "route", "min_signal_quality", "declaration_check",
                   "ledger"}, {"config"}),
        "redact": ({"mode", "key_env", "key_id", "hypothesis_text"}, set()),
        "thin": ({"keep_provisional"}, set()),
    },
    "exporters": {
        "jsonl": ({"path", "types", "append"}, {"path"}),
        "stdout": ({"types"}, set()),
        # ``receiver``: share the /decisions channel of a websocket receiver's server.
        # No ``receiver``: start a standalone /decisions server (for file replay demos).
        "websocket": ({"receiver", "listen", "token_env", "origins", "certfile", "keyfile", "linger_s"}, set()),
        "lsl": ({"stream_name", "source_id", "config_id", "no_text"}, set()),
    },
}
TOP_KEYS = {"service", "receivers", "processors", "exporters", "pipelines"}
SERVICE_KEYS = {"log", "metrics_file", "health", "duration_s", "max_streams"}
HEALTH_KEYS = {"listen", "token_env", "allow_unauthenticated"}
#: Default address of the health and metrics endpoint: localhost only.
DEFAULT_HEALTH_LISTEN = "127.0.0.1:13133"
#: Keys of a websocket exporter that only a standalone /decisions server uses.
WS_STANDALONE_KEYS = {"listen", "token_env", "origins", "certfile", "keyfile", "linger_s"}
PIPELINE_KEYS = {"receivers", "processors", "exporters"}
#: Keys that would put a secret into the file. Secrets come from environment variables.
SECRET_KEYS = {"token", "key", "password", "secret"}
DECISION_TYPES = {"trust_decision"}
INPUT_TYPES = {"header", "frame", "segment_end", "end", "signal_quality", "hypothesis", "decision", "pointer",
               "intent", "intent_feedback", "control", "control_enable"}


class ConfigError(ValueError):
    """The collector configuration is not valid. The message names the bad value."""


@dataclass
class ComponentConfig:
    kind: str  # receivers | processors | exporters
    name: str
    type: str
    options: dict[str, Any]


@dataclass
class PipelineConfig:
    name: str
    receivers: list[str]
    processors: list[str]
    exporters: list[str]


@dataclass
class CollectorConfig:
    service: dict[str, Any]
    receivers: dict[str, ComponentConfig]
    processors: dict[str, ComponentConfig]
    exporters: dict[str, ComponentConfig]
    pipelines: dict[str, PipelineConfig]
    base_dir: Path = field(default_factory=Path.cwd)

    def path(self, p: str) -> Path:
        """Resolve a path of the configuration against the folder of the configuration file."""
        q = Path(p)
        return q if q.is_absolute() else self.base_dir / q

    def describe(self) -> str:
        """A short text plan of the pipelines (``fidetype collector --check``)."""
        lines = []
        for p in self.pipelines.values():
            def fmt(kind: str, names: list[str]) -> str:
                comps = getattr(self, kind)
                return ", ".join(f"{n} ({comps[n].type})" for n in names) or "-"
            lines.append(f"pipeline {p.name}: receivers [{fmt('receivers', p.receivers)}] -> processors "
                         f"[{fmt('processors', p.processors)}] -> exporters [{fmt('exporters', p.exporters)}]")
        return "\n".join(lines)


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def read_file(path: str | PathLike[str]) -> dict[str, Any]:
    """Read a TOML (``.toml``) or JSON (``.json``) file into a dict."""
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"{p}: configuration file not found")
    suffix = p.suffix.lower()
    try:
        if suffix == ".toml":
            with p.open("rb") as f:
                return tomllib.load(f)
        if suffix == ".json":
            d = json.loads(p.read_text(encoding="utf-8"), parse_constant=_reject_constant)
            if not isinstance(d, dict):
                raise ConfigError(f"{p}: the top level must be an object")
            return d
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{p}: not valid TOML: {e}") from None
    except ValueError as e:
        if isinstance(e, ConfigError):
            raise
        raise ConfigError(f"{p}: not valid JSON: {e}") from None
    if suffix in (".yaml", ".yml"):
        raise ConfigError(f"{p}: YAML is not supported (it would need a new dependency, PyYAML); "
                          "write the same structure as TOML (.toml) or JSON (.json)")
    raise ConfigError(f"{p}: unknown configuration format {suffix!r}; use .toml or .json")


def is_loopback(host: str) -> bool:
    """True for ``localhost`` and loopback IP addresses (127.0.0.0/8, ::1)."""
    import ipaddress

    h = host.strip("[]").lower()
    if h == "localhost":
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def load(path: str | PathLike[str]) -> CollectorConfig:
    """Load and check a configuration file."""
    p = Path(path)
    return parse(read_file(p), base_dir=p.resolve().parent)


def _check_keys(where: str, d: Any, allowed: set[str], required: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: must be a table (object), not {type(d).__name__}")
    for k in d:
        if k.lower() in SECRET_KEYS:
            raise ConfigError(f"{where}.{k}: secrets must not be in the configuration file; "
                              "name an environment variable with token_env / key_env")
    unknown = sorted(set(d) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unknown key {unknown[0]!r} (allowed: {', '.join(sorted(allowed))})")
    missing = sorted(set(required) - set(d))
    if missing:
        raise ConfigError(f"{where}: missing required key {missing[0]!r}")
    return d


def _names(where: str, v: Any) -> list[str]:
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise ConfigError(f"{where}: must be a list of component names")
    if len(set(v)) != len(v):
        raise ConfigError(f"{where}: a name appears twice")
    return list(v)


def _opt_type(where: str, d: dict[str, Any], key: str, types: tuple[type, ...], what: str) -> None:
    if key in d:
        v = d[key]
        if isinstance(v, bool) and bool not in types:
            raise ConfigError(f"{where}.{key}: must be {what}, not a boolean")
        if not isinstance(v, types):
            raise ConfigError(f"{where}.{key}: must be {what}, not {type(v).__name__}")


def _opt_enum(where: str, d: dict[str, Any], key: str, values: tuple[str, ...]) -> None:
    if key in d and d[key] not in values:
        raise ConfigError(f"{where}.{key}: must be one of {', '.join(map(repr, values))}, not {d[key]!r}")


def _listen(where: str, v: Any) -> None:
    if not isinstance(v, str) or ":" not in v:
        raise ConfigError(f"{where}: must be 'host:port', for example '127.0.0.1:8765'")
    host, _, port = v.rpartition(":")
    if not host or not port.isdigit() or not 0 <= int(port) <= 65535:
        raise ConfigError(f"{where}: must be 'host:port' with a port in 0..65535, not {v!r}")


def _check_component(kind: str, name: str, d: dict[str, Any]) -> ComponentConfig:
    where = f"{kind}.{name}"
    if not isinstance(d, dict):
        raise ConfigError(f"{where}: must be a table (object)")
    typ = d.get("type")
    known = SCHEMA[kind]
    if typ is None:
        raise ConfigError(f"{where}: missing required key 'type' (one of {', '.join(sorted(known))})")
    if typ not in known:
        raise ConfigError(f"{where}.type: unknown {kind[:-1]} type {typ!r} (known: {', '.join(sorted(known))})")
    allowed, required = known[typ]
    opts = {k: v for k, v in d.items() if k != "type"}
    _check_keys(where, opts, allowed, required)
    num = (int, float)
    if kind == "receivers" and typ == "file":
        paths = opts["paths"]
        if isinstance(paths, str):
            paths = opts["paths"] = [paths]
        if not isinstance(paths, list) or not paths or not all(isinstance(x, str) and x for x in paths):
            raise ConfigError(f"{where}.paths: must be a non-empty list of file paths")
        _opt_type(where, opts, "follow", (bool,), "true or false")
        _opt_enum(where, opts, "eof", ("close", "cut"))
        _opt_type(where, opts, "batch", (int,), "an integer")
        _opt_type(where, opts, "idle_timeout_s", num, "a number")
        _opt_type(where, opts, "poll_interval_s", num, "a number")
        _opt_type(where, opts, "stream_id", (str,), "a string")
        if opts.get("batch", 1) < 1:
            raise ConfigError(f"{where}.batch: must be >= 1")
        if opts.get("idle_timeout_s", 1.0) <= 0 or opts.get("poll_interval_s", 1.0) <= 0:
            raise ConfigError(f"{where}: idle_timeout_s and poll_interval_s must be > 0")
        if "stream_id" in opts and len(paths) > 1:
            raise ConfigError(f"{where}.stream_id: only valid with one path (each file is its own stream)")
    elif kind == "receivers" and typ == "websocket":
        if "listen" in opts:
            _listen(f"{where}.listen", opts["listen"])
        _opt_type(where, opts, "token_env", (str,), "the name of an environment variable")
        _opt_type(where, opts, "certfile", (str,), "a file path")
        _opt_type(where, opts, "keyfile", (str,), "a file path")
        if "origins" in opts and not (isinstance(opts["origins"], list)
                                      and all(isinstance(o, str) for o in opts["origins"])):
            raise ConfigError(f"{where}.origins: must be a list of strings")
        for k in ("reorder_window", "queue_max"):
            _opt_type(where, opts, k, (int,), "an integer")
        for k in ("reorder_timeout_s", "resume_timeout_s"):
            _opt_type(where, opts, k, num, "a number")
        if "keyfile" in opts and "certfile" not in opts:
            raise ConfigError(f"{where}.keyfile: needs certfile")
    elif kind == "receivers" and typ == "lsl":
        if not any(k in opts for k in ("stream_name", "stream_type", "source_id")):
            raise ConfigError(f"{where}: give at least one of stream_name, stream_type, source_id")
        for k in ("stream_name", "stream_type", "source_id", "events", "stream_id", "vocab_type"):
            _opt_type(where, opts, k, (str,), "a string")
            if k in opts and ("'" in opts[k] or not opts[k]):
                raise ConfigError(f"{where}.{k}: must be a non-empty string without a single quote")
        _opt_type(where, opts, "stop_at_end", (bool,), "true or false")
        _opt_enum(where, opts, "on_gap", ("abort", "mark", "segment"))
        _opt_enum(where, opts, "clock", ("receiver", "sender"))
        _opt_enum(where, opts, "out_of_order", ("clamp", "drop", "error"))
        _opt_enum(where, opts, "values", ("auto", "log_probs", "probs", "logits"))
        _opt_enum(where, opts, "plain_markers", ("ignore", "hypothesis"))
        _opt_enum(where, opts, "reconnect_mode", ("thread", "inline"))
        _opt_type(where, opts, "blank", (int, str), "a token index or a token")
        for k in ("vocab", "boundary_markers"):
            if k in opts and not (isinstance(opts[k], list) and opts[k] and all(isinstance(x, str) for x in opts[k])):
                raise ConfigError(f"{where}.{k}: must be a non-empty list of strings")
        for k in ("gap_factor", "merge_window_s", "resolve_timeout_s", "open_timeout_s", "reconnect_timeout_s"):
            _opt_type(where, opts, k, num, "a number")
        for k in ("resolve_timeout_s", "open_timeout_s", "reconnect_timeout_s"):
            if k in opts and not opts[k] > 0:
                raise ConfigError(f"{where}.{k}: must be > 0")
        if opts.get("gap_factor", 2.5) <= 1:
            raise ConfigError(f"{where}.gap_factor: must be > 1")
        if opts.get("merge_window_s", 0.0) < 0:
            raise ConfigError(f"{where}.merge_window_s: must be >= 0")
    elif kind == "processors" and typ == "validate":
        _opt_enum(where, opts, "on_invalid", ("cut", "log"))
        _opt_enum(where, opts, "level", ("core",))
    elif kind == "processors" and typ == "trust":
        _opt_type(where, opts, "config", (str,), "a file path")
        _opt_enum(where, opts, "decoder", ("none", "greedy", "demo"))
        _opt_type(where, opts, "max_attempts", (int,), "an integer")
        _opt_enum(where, opts, "route", ("auto", "frames", "hypothesis"))
        _opt_type(where, opts, "min_signal_quality", num, "a number")
        _opt_enum(where, opts, "declaration_check", ("off", "warn", "abstain", "offer-only"))
        if opts.get("max_attempts", 1) < 1:
            raise ConfigError(f"{where}.max_attempts: must be >= 1")
        if "ledger" in opts:
            led = _check_keys(f"{where}.ledger", opts["ledger"], {"path", "text_mode", "id_mode", "key_env", "key_id"},
                              {"path"})
            _opt_type(f"{where}.ledger", led, "path", (str,), "a file path")
            _opt_enum(f"{where}.ledger", led, "text_mode", ("store", "hash", "omit"))
            _opt_enum(f"{where}.ledger", led, "id_mode", ("store", "hash", "omit"))
            _opt_type(f"{where}.ledger", led, "key_env", (str,), "the name of an environment variable")
    elif kind == "processors" and typ == "redact":
        _opt_enum(where, opts, "mode", ("drop", "hmac"))
        _opt_type(where, opts, "key_env", (str,), "the name of an environment variable")
        _opt_type(where, opts, "key_id", (str,), "a string")
        _opt_type(where, opts, "hypothesis_text", (bool,), "true or false")
        if opts.get("mode", "drop") == "hmac" and "key_env" not in opts:
            raise ConfigError(f"{where}: mode 'hmac' needs key_env (the environment variable that holds the key)")
    elif kind == "processors" and typ == "thin":
        _opt_enum(where, opts, "keep_provisional", ("changes", "none", "all"))
    elif kind == "exporters" and typ in ("jsonl", "stdout"):
        if typ == "jsonl":
            _opt_type(where, opts, "path", (str,), "a file path")
            _opt_type(where, opts, "append", (bool,), "true or false")
        types = opts.get("types", ["trust_decision"])
        if isinstance(types, str):
            types = [types]
        if not isinstance(types, list) or not types or not all(isinstance(t, str) for t in types):
            raise ConfigError(f"{where}.types: must be a non-empty list of event types")
        if "*" in types and len(types) > 1:
            raise ConfigError(f"{where}.types: '*' must be alone")
        if typ == "jsonl":
            dec, inp = set(types) & DECISION_TYPES, set(types) - DECISION_TYPES
            if dec and (inp or "*" in types):
                raise ConfigError(f"{where}.types: a JSON Lines file holds decisions or input events, not both "
                                  "(spec TD-11: a decision log has no header and no input events)")
            if "*" in types:
                raise ConfigError(f"{where}.types: '*' would mix decisions and input events in one file (TD-11); "
                                  "list the types, for example ['trust_decision'] or ['header', 'frame', ...]")
        opts["types"] = types
    elif kind == "exporters" and typ == "lsl":
        for k in ("stream_name", "source_id", "config_id"):
            _opt_type(where, opts, k, (str,), "a string")
            if k in opts and not opts[k]:
                raise ConfigError(f"{where}.{k}: must not be empty")
        _opt_type(where, opts, "no_text", (bool,), "true or false")
    elif kind == "exporters" and typ == "websocket":
        _opt_type(where, opts, "receiver", (str,), "the name of a websocket receiver")
        if "receiver" in opts:
            extra = sorted(set(opts) & WS_STANDALONE_KEYS)
            if extra:
                raise ConfigError(f"{where}.{extra[0]}: only valid for a standalone /decisions server (no "
                                  "'receiver'); with 'receiver' the settings of the receiver's server apply")
        else:
            if "listen" in opts:
                _listen(f"{where}.listen", opts["listen"])
            _opt_type(where, opts, "token_env", (str,), "the name of an environment variable")
            _opt_type(where, opts, "certfile", (str,), "a file path")
            _opt_type(where, opts, "keyfile", (str,), "a file path")
            _opt_type(where, opts, "linger_s", num, "a number")
            if "origins" in opts and not (isinstance(opts["origins"], list)
                                          and all(isinstance(o, str) for o in opts["origins"])):
                raise ConfigError(f"{where}.origins: must be a list of strings")
            if "keyfile" in opts and "certfile" not in opts:
                raise ConfigError(f"{where}.keyfile: needs certfile")
            if opts.get("linger_s", 0) < 0:
                raise ConfigError(f"{where}.linger_s: must be >= 0")
    return ComponentConfig(kind, name, typ, opts)


def parse(d: dict[str, Any], base_dir: str | PathLike[str] | None = None) -> CollectorConfig:
    """Check a configuration dict (already read from TOML or JSON)."""
    _check_keys("<config>", d, TOP_KEYS, {"pipelines"})
    service = _check_keys("service", d.get("service", {}), SERVICE_KEYS)
    _opt_enum("service", service, "log", ("info", "quiet"))
    _opt_type("service", service, "metrics_file", (str,), "a file path")
    _opt_type("service", service, "duration_s", (int, float), "a number")
    _opt_type("service", service, "max_streams", (int,), "an integer")
    if "health" in service:
        h = _check_keys("service.health", service["health"], HEALTH_KEYS)
        h.setdefault("listen", DEFAULT_HEALTH_LISTEN)
        _listen("service.health.listen", h["listen"])
        _opt_type("service.health", h, "token_env", (str,), "the name of an environment variable")
        _opt_type("service.health", h, "allow_unauthenticated", (bool,), "true or false")
        host = h["listen"].rpartition(":")[0]
        if not is_loopback(host) and "token_env" not in h and h.get("allow_unauthenticated") is not True:
            raise ConfigError("service.health.listen: binds beyond localhost without a token; set token_env "
                              "(the environment variable that holds a bearer token for /metrics), or set "
                              "allow_unauthenticated = true to accept an open /metrics (/healthz is always open)")
    comps: dict[str, dict[str, ComponentConfig]] = {}
    for kind in ("receivers", "processors", "exporters"):
        sec = d.get(kind, {})
        if not isinstance(sec, dict):
            raise ConfigError(f"{kind}: must be a table of named components")
        comps[kind] = {name: _check_component(kind, name, c) for name, c in sec.items()}
    pls = d["pipelines"]
    if not isinstance(pls, dict) or not pls:
        raise ConfigError("pipelines: must be a table with at least one pipeline")
    used: dict[str, dict[str, str]] = {"receivers": {}, "processors": {}}
    pipelines: dict[str, PipelineConfig] = {}
    for pname, p in pls.items():
        where = f"pipelines.{pname}"
        _check_keys(where, p, PIPELINE_KEYS, {"receivers", "exporters"})
        lists = {k: _names(f"{where}.{k}", p.get(k, [])) for k in PIPELINE_KEYS}
        if not lists["receivers"]:
            raise ConfigError(f"{where}.receivers: needs at least one receiver")
        if not lists["exporters"]:
            raise ConfigError(f"{where}.exporters: needs at least one exporter")
        for k, names in lists.items():
            for i, n in enumerate(names):
                if n not in comps[k]:
                    known = ", ".join(sorted(comps[k])) or "none defined"
                    raise ConfigError(f"{where}.{k}[{i}]: unknown {k[:-1]} {n!r} (known: {known})")
                if k in used:
                    if n in used[k]:
                        raise ConfigError(f"{where}.{k}[{i}]: {k[:-1]} {n!r} is already used by pipeline "
                                          f"{used[k][n]!r}; a {k[:-1]} keeps state, so define a second one")
                    used[k][n] = pname
        types = [comps["processors"][n].type for n in lists["processors"]]
        if "redact" in types and "trust" in types and types.index("redact") < types.index("trust"):
            raise ConfigError(f"{where}.processors: 'redact' comes before 'trust'; the trust layer needs the "
                              "text, so put redact after trust")
        if "trust" in types and "validate" in types and types.index("validate") > types.index("trust"):
            raise ConfigError(f"{where}.processors: put 'validate' before 'trust' (it checks the input events)")
        if types.count("trust") > 1:
            raise ConfigError(f"{where}.processors: at most one trust processor per pipeline")
        for i, n in enumerate(lists["exporters"]):
            ex = comps["exporters"][n]
            if ex.type == "websocket" and "receiver" in ex.options:
                r = ex.options["receiver"]
                if r not in lists["receivers"] or comps["receivers"][r].type != "websocket":
                    raise ConfigError(f"exporters.{n}.receiver: {r!r} must be a websocket receiver of pipeline "
                                      f"{pname!r} (it serves /decisions on the receiver's server); leave out "
                                      "'receiver' for a standalone /decisions server")
        pipelines[pname] = PipelineConfig(pname, lists["receivers"], lists["processors"], lists["exporters"])
    for kind in ("receivers", "processors"):
        unused = sorted(set(comps[kind]) - set(used[kind]))
        if unused:
            raise ConfigError(f"{kind}.{unused[0]}: defined but not used by any pipeline")
    return CollectorConfig(service, comps["receivers"], comps["processors"], comps["exporters"], pipelines,
                           Path(base_dir) if base_dir is not None else Path.cwd())
