"""Configuration of the live demo (P14-06).

A demo configuration is a JSON file with a list of **tracks**. A track is
one replay source: recorded decoder output, a trust configuration, the
ground truth for the wrong-commit count, and the dataset and licence
that the page shows. The ``kind`` of a track selects its code
(:mod:`fidetype.demo.live.tracks`):

``trust-log``
    Replays recorded ``trust_decision`` events (FEP-0001) with their
    original timing (T15 implant replay, M2-19 run). Optional: decoder
    log-probabilities for the live phoneme preview.
``nts-streams``
    Replays NTS stream files (decoder output) at real time through the
    streaming trust layer with a frozen trust configuration. Any decoder
    that writes NTS files plugs in here by configuration only: the
    emg2qwerty LDA baseline today, the P11-01 EMG decoder (written by
    :mod:`fidetype.adapters.ctc_logits`) later.
``synthetic``
    The synthetic M7-01 session (:mod:`fidetype.demo`). No data needed.

Paths may use ``${DATA}`` (the environment variable ``FIDETYPE_DATA``,
default ``~/bci-data``) and ``${REPO}`` (the checkout root, if the
package runs from one). Relative paths are relative to the file.
"""

from __future__ import annotations

import json
import os
import re
from importlib import resources
from pathlib import Path
from typing import Any

SCHEMA = "fidetype.live-demo-config/0.1"
DEFAULT_CONFIG = "live-demo.json"
DATA_ENV = "FIDETYPE_DATA"
DATA_DEFAULT = "~/bci-data"
KINDS = ("trust-log", "nts-streams", "synthetic")
_VAR = re.compile(r"\$\{([A-Z_]+)\}")


class DemoConfigError(ValueError):
    pass


def data_root() -> Path:
    return Path(os.path.expanduser(os.environ.get(DATA_ENV) or DATA_DEFAULT))


def repo_root() -> Path | None:
    """The checkout root (the folder with ``pyproject.toml`` and ``src/fidetype``), or None for a wheel install."""
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "pyproject.toml").is_file() and (p / "src" / "fidetype").is_dir():
            return p
    return None


def expand(value: str, base: Path | None) -> Path:
    """Expand ``${DATA}`` / ``${REPO}`` / ``~`` and resolve a relative path against ``base``."""
    def sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name == "DATA":
            return str(data_root())
        if name == "REPO":
            r = repo_root()
            if r is None:
                raise DemoConfigError("${REPO} is used, but the package does not run from a checkout")
            return str(r)
        v = os.environ.get(name)
        if v is None:
            raise DemoConfigError(f"unknown variable ${{{name}}} (set it in the environment)")
        return v

    p = Path(os.path.expanduser(_VAR.sub(sub, value)))
    if not p.is_absolute() and base is not None:
        p = base / p
    return p


def load(path: str | Path | None = None) -> tuple[dict[str, Any], Path | None]:
    """Load and check a demo configuration. Return (config, folder of the file)."""
    if path is None:
        text = resources.files("fidetype.demo.live").joinpath(DEFAULT_CONFIG).read_text(encoding="utf-8")
        base = None
    else:
        p = Path(path)
        if not p.is_file():
            raise DemoConfigError(f"demo configuration not found: {p}")
        text = p.read_text(encoding="utf-8")
        base = p.resolve().parent
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as e:
        raise DemoConfigError(f"demo configuration is not valid JSON: {e}") from e
    check(cfg)
    return cfg, base


def check(cfg: Any) -> None:
    if not isinstance(cfg, dict) or cfg.get("schema") != SCHEMA:
        raise DemoConfigError(f"demo configuration needs \"schema\": \"{SCHEMA}\"")
    tracks = cfg.get("tracks")
    if not isinstance(tracks, list) or not tracks:
        raise DemoConfigError("demo configuration needs a non-empty \"tracks\" list")
    seen: set[str] = set()
    for i, t in enumerate(tracks):
        if not isinstance(t, dict):
            raise DemoConfigError(f"track {i} is not an object")
        tid = t.get("id")
        if not isinstance(tid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", tid or ""):
            raise DemoConfigError(f"track {i}: \"id\" must be a short lower-case name")
        if tid in seen:
            raise DemoConfigError(f"track id {tid!r} is used twice")
        seen.add(tid)
        if t.get("kind") not in KINDS:
            raise DemoConfigError(f"track {tid}: \"kind\" must be one of {', '.join(KINDS)}")
        if not isinstance(t.get("title"), str):
            raise DemoConfigError(f"track {tid}: \"title\" is required")
        ds = t.get("dataset")
        if not isinstance(ds, dict) or not isinstance(ds.get("name"), str) or not isinstance(ds.get("licence"), str):
            raise DemoConfigError(f"track {tid}: \"dataset\" needs \"name\" and \"licence\" (the page shows them)")
