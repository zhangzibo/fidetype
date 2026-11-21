"""Toy pretrained models: try the pretrained API without a download (P14-44).

::

    import fidetype.pretrained as ftp

    toy = ftp.toy_model()                                  # tiny random gru-ctc model in a temporary folder
    st = toy.decode(np.zeros((200, 16), np.float32), session=toy.sessions[0])
    path = ftp.make_toy_manifest("toy-folder")             # or: write the files, then ftp.load(str(path), weights=...)

A toy model has **random weights**. It has learned nothing, so its text is noise. It uses the
same runtime, the same loader checks (SHA-256 and size of each file) and the same NTS output
as a real model. Its manifest has ``task = "tutorial"`` and no trust config.

Supported runtime: ``gru-ctc`` (the runtime of ``t15-m4-13`` and ``t12-v2``).

Our own code (Apache-2.0).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from os import PathLike
from pathlib import Path
from typing import Any, Sequence

import numpy as np

__all__ = ["TOY_RUNTIMES", "TOY_SESSIONS", "make_toy_manifest", "toy_model"]

#: The runtimes that have a toy model.
TOY_RUNTIMES = ("gru-ctc",)
#: The default session names of a toy model (its day layer has one entry per session).
TOY_SESSIONS = ("toy.2026.01.01", "toy.2026.01.02")


def make_toy_manifest(folder: str | PathLike[str], *, runtime: str = "gru-ctc", name: str = "toy-gru",
                      n_in: int = 16, hidden: int = 32, layers: int = 2, sessions: Sequence[str] = TOY_SESSIONS,
                      seed: int = 0) -> Path:
    """Write random weights and a manifest that lists their SHA-256 and size. Return the manifest path.

    ``folder`` gets ``<name>.weights.npz`` and ``<name>.json``. Load the model with
    ``fidetype.pretrained.load(str(path), weights=folder)``. ``n_in``: input channels per 20 ms bin.
    """
    if runtime not in TOY_RUNTIMES:
        raise ValueError(f"no toy model for runtime {runtime!r}; toy runtimes: {list(TOY_RUNTIMES)}")
    from fidetype.adapters import b2t25 as B
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, NumpyLookaheadGRU

    sessions = [str(s) for s in sessions]
    if not sessions:
        raise ValueError("a toy model needs at least one session name")
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    patch, stride = 4, 2
    cfg = LookaheadGRUConfig(n_in=int(n_in), n_out=len(B.VOCAB), n_sessions=len(sessions), hidden=int(hidden),
                             layers=int(layers), patch=patch, stride=stride, smooth_sd=1.0, la_max=3, la_proj=4)
    params = {k: v for k, v in NumpyLookaheadGRU.random(cfg, seed=seed).params.items() if not k.startswith("la_")}
    weights = d / f"{name}.weights.npz"
    np.savez(weights, **params)
    manifest: dict[str, Any] = {
        "schema": "fidetype.pretrained-manifest/0.1", "name": name, "version": "1",
        "title": "Toy model: random GRU-CTC phoneme decoder (learned nothing)", "status": "available",
        "task": "tutorial", "modality": "intracortical", "runtime": runtime,
        "input": {"bin_s": 0.02, "channels": int(n_in), "file_format": "b2t25-hdf5"},
        "output": {"vocab_type": "phoneme", "vocab_id": B.VOCAB_ID, "frame_period_s": 0.02 * stride,
                   "latency_s": 0.0},
        "architecture": {"patch": patch, "stride": stride, "layers": int(layers), "hidden": int(hidden),
                         "smooth_sd": 1.0, "lookahead": None, "input_round": "float16", "sessions": sessions},
        "files": [{"role": "weights", "name": weights.name, "sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                   "size": weights.stat().st_size, "url": None}],
        "licence": {"data.licence": "CC0-1.0", "data.research_only": False, "weights": "CC0-1.0",
                    "weights_status": "toy model, random numbers"},
        "limits": ["Random weights: the output is noise. Use it to learn the API only."],
        "trust": None, "trust_note": "toy model: no trust config (calibrate one with fidetype.trust.calibrate)",
    }
    path = d / f"{name}.json"
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return path


def toy_model(folder: str | PathLike[str] | None = None, **kwargs: Any) -> Any:
    """Make and load a toy model (a :class:`~fidetype.pretrained.PretrainedDecoder`).

    ``folder``: where the files go (default: a new temporary folder, which stays after the
    call). ``kwargs``: as :func:`make_toy_manifest`. ``model.sessions`` lists the session names.
    """
    from fidetype.pretrained import load

    d = Path(folder) if folder is not None else Path(tempfile.mkdtemp(prefix="fidetype-toy-"))
    return load(str(make_toy_manifest(d, **kwargs)), weights=d)
