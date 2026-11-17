"""Live key-window models for ``fidetype live`` (P14-04).

A live model turns a raw signal window (EMG, EEG) into one key-press
posterior over :data:`fidetype.adapters.kt_semg.KEY_VOCAB` (32 W3C
``KeyboardEvent.code`` names). It reuses the KT-sEMG reference decoder:

- features: :func:`fidetype.adapters.kt_semg.window_features` (log-RMS
  per channel in ``n_sub`` sub-windows of ``[t - pre_s, t + post_s]``);
- standardisation: :class:`RunningScaler`, a causal z-score with running
  statistics (a live stream has no "whole run" to standardise on);
- classifier: :class:`fidetype.adapters.kt_semg.LdaKeyDecoder` (shrinkage
  LDA, numpy only).

A model is two files: ``<name>.model.json`` (the model card: sample rate,
channels, window, timing, training data, licence, SHA-256 of the weights)
and ``<name>.weights.json`` (the LDA weights as plain JSON arrays: no
pickle, no binary file in the package). ``load_model`` checks the SHA-256.
``builtin:synthetic-keys`` is a small model trained
on our own synthetic signal (:mod:`fidetype.live.synthetic`); it ships in
the package. It decodes only that synthetic signal.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from os import PathLike
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from fidetype.adapters.kt_semg import KEY_VOCAB, LdaKeyDecoder, window_features

__all__ = ["MODEL_SCHEMA", "RunningScaler", "KeyWindowModel", "load_model", "resolve_asset", "builtin_dir"]

MODEL_SCHEMA = "fidetype.live-model/0.1"
WEIGHTS_SCHEMA = "fidetype.live-weights/0.1"
#: Timing modes. ``markers``: one window per key-onset marker (``keypress``) on the markers stream.
#: ``fixed``: one window every ``hop_s`` seconds (no onset information; for boards without key markers).
TIMING_MODES = ("markers", "fixed")


def builtin_dir() -> Path:
    """The folder of the packaged assets (``builtin:<name>``)."""
    return Path(str(resources.files("fidetype.live").joinpath("assets")))


def resolve_asset(spec: str | PathLike[str], suffix: str) -> Path:
    """``builtin:<name>`` -> the packaged ``<name><suffix>``; else the path itself."""
    s = str(spec)
    if s.startswith("builtin:"):
        p = builtin_dir() / f"{s.removeprefix('builtin:')}{suffix}"
        if not p.is_file():
            raise FileNotFoundError(f"no packaged asset {s!r} ({p.name})")
        return p
    return Path(s)


class RunningScaler:
    """Causal per-feature z-score with running mean and variance (Welford).

    It starts from a prior (``mu0``, ``sd0``) with weight ``n0`` pseudo
    windows, so the first windows are not standardised on one sample.
    Training and live use use the same class, so the features match.
    """

    def __init__(self, mu0: np.ndarray, sd0: np.ndarray, n0: float = 20.0) -> None:
        self.n = float(n0)
        self.mean = np.asarray(mu0, dtype=np.float64).copy()
        self.m2 = (np.asarray(sd0, dtype=np.float64) ** 2) * self.n

    def update_transform(self, x: np.ndarray) -> np.ndarray:
        """Add the rows of ``x`` (K, D) one by one; return each row standardised with the statistics before it."""
        x = np.atleast_2d(np.asarray(x, dtype=np.float64))
        out = np.empty_like(x)
        for i, row in enumerate(x):
            sd = np.sqrt(self.m2 / self.n) + 1e-9
            out[i] = (row - self.mean) / sd
            self.n += 1.0
            d = row - self.mean
            self.mean += d / self.n
            self.m2 += d * (row - self.mean)
        return out


@dataclass
class KeyWindowModel:
    """Window features -> running z-score -> LDA key posterior (module docstring)."""

    lda: LdaKeyDecoder
    card: dict[str, Any]
    weights_sha256: str = ""
    scaler_prior: tuple[np.ndarray, np.ndarray] | None = field(default=None, repr=False)

    # --- card fields --------------------------------------------------------

    @property
    def name(self) -> str:
        return str(self.card.get("name", "live-model"))

    @property
    def version(self) -> str:
        return str(self.card.get("version", "0"))

    @property
    def sample_rate(self) -> float:
        return float(self.card["sample_rate"])

    @property
    def channels(self) -> int:
        return int(self.card["channels"])

    @property
    def pre_s(self) -> float:
        return float(self.card["window"]["pre_s"])

    @property
    def post_s(self) -> float:
        return float(self.card["window"]["post_s"])

    @property
    def n_sub(self) -> int:
        return int(self.card["window"]["n_sub"])

    @property
    def timing(self) -> str:
        return str(self.card.get("timing", "markers"))

    @property
    def hop_s(self) -> float:
        return float(self.card.get("hop_s", self.pre_s + self.post_s))

    @property
    def modality(self) -> str:
        return str(self.card.get("modality", "other"))

    @property
    def vocab(self) -> tuple[str, ...]:
        return KEY_VOCAB

    # --- decoding -----------------------------------------------------------

    def features(self, emg: np.ndarray, times_s: np.ndarray | list[float]) -> np.ndarray:
        """Raw window features (K, n_sub * C) at ``times_s`` (seconds from the first sample of ``emg``)."""
        return window_features(emg, list(times_s), fs=self.sample_rate, pre_s=self.pre_s, post_s=self.post_s,
                               n_sub=self.n_sub)

    def new_scaler(self) -> RunningScaler:
        mu, sd = self.scaler_prior if self.scaler_prior is not None else (
            np.zeros(self.n_sub * self.channels), np.ones(self.n_sub * self.channels))
        return RunningScaler(mu, sd, float(self.card.get("scaler_n0", 20.0)))

    def log_proba(self, z: np.ndarray) -> np.ndarray:
        """Key log posteriors (K, 32) of standardised features ``z``."""
        return self.lda.predict_log_proba(np.atleast_2d(z))

    # --- files ----------------------------------------------------------------

    def save(self, stem: str | PathLike[str]) -> tuple[Path, Path]:
        """Write ``<stem>.weights.json`` and ``<stem>.model.json``. Return both paths."""
        stem = Path(stem)
        npz = stem.with_name(stem.name + ".weights.json")
        mu, sd = self.scaler_prior if self.scaler_prior is not None else (
            np.zeros(self.n_sub * self.channels), np.ones(self.n_sub * self.channels))
        arrays = {"means": self.lda.means, "precision": self.lda.precision, "log_prior": self.lda.log_prior,
                  "mu": self.lda.mu, "scale": self.lda.scale, "scaler_mu": mu, "scaler_sd": sd}
        doc = {"schema": WEIGHTS_SCHEMA, **{k: np.asarray(v, dtype=np.float64).tolist() for k, v in arrays.items()}}
        npz.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
        sha = hashlib.sha256(npz.read_bytes()).hexdigest()
        self.weights_sha256 = sha
        card = dict(self.card)
        card.update(schema=MODEL_SCHEMA, weights=npz.name, weights_sha256=sha, vocab=list(KEY_VOCAB))
        js = stem.with_name(stem.name + ".model.json")
        js.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        self.card = card
        return npz, js


def load_model(spec: str | PathLike[str]) -> KeyWindowModel:
    """Load ``builtin:<name>`` or a ``*.model.json`` path (the weights file sits next to it)."""
    js = resolve_asset(spec, ".model.json")
    card = json.loads(js.read_text(encoding="utf-8"))
    if card.get("schema") != MODEL_SCHEMA:
        raise ValueError(f"not a live model card (schema {card.get('schema')!r}, expected {MODEL_SCHEMA!r})")
    if card.get("timing", "markers") not in TIMING_MODES:
        raise ValueError(f"unknown timing {card.get('timing')!r}")
    if tuple(card.get("vocab", KEY_VOCAB)) != KEY_VOCAB:
        raise ValueError("the model vocab is not KEY_VOCAB")
    npz = js.parent / str(card["weights"])
    raw = npz.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if card.get("weights_sha256") and card["weights_sha256"] != sha:
        raise ValueError(f"weights SHA-256 mismatch for {npz.name}: the file changed after the card was written")
    z = json.loads(raw.decode("utf-8"))
    if z.get("schema") != WEIGHTS_SCHEMA:
        raise ValueError(f"{npz.name} is not a live weights file (schema {z.get('schema')!r})")
    a = {k: np.asarray(z[k], dtype=np.float64) for k in ("means", "precision", "log_prior", "mu", "scale")}
    lda = LdaKeyDecoder(a["means"], a["precision"], a["log_prior"], a["mu"], a["scale"])
    prior = (np.asarray(z["scaler_mu"]), np.asarray(z["scaler_sd"])) if "scaler_mu" in z else None
    return KeyWindowModel(lda, card, sha, prior)


def fit_model(features_per_run: list[np.ndarray], labels_per_run: list[np.ndarray], card: Mapping[str, Any],
              shrinkage: float = 0.1, n0: float = 20.0) -> KeyWindowModel:
    """Fit a model on raw features of several runs (each run standardised causally on its own, as live)."""
    allx = np.concatenate([f for f in features_per_run if len(f)])
    mu0, sd0 = allx.mean(0), allx.std(0) + 1e-9
    zs = []
    for f in features_per_run:
        sc = RunningScaler(mu0, sd0, n0)
        zs.append(sc.update_transform(f) if len(f) else f)
    Z = np.concatenate([z for z in zs if len(z)])
    y = np.concatenate([np.asarray(lb, dtype=np.int64) for lb in labels_per_run if len(lb)])
    lda = LdaKeyDecoder.fit(Z, y, shrinkage=shrinkage)
    c = dict(card)
    c["scaler_n0"] = n0
    return KeyWindowModel(lda, c, "", (mu0, sd0))
