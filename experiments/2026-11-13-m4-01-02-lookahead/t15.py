"""Shared code for M4-01 / M4-02 (T15 neural data, lookahead decoder). Our own code.

Data: Card et al. 2024, ``t15_copyTask_neuralData.zip`` (CC0). One folder per
session with ``data_train.hdf5`` / ``data_val.hdf5`` / ``data_test.hdf5``; one
HDF5 group per trial with the dataset ``input_features`` (T x 512, 20 ms bins)
and the attribute ``sentence_label``. This module writes nothing into the
repo except aggregate results: features and texts go to ``DERIVED``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
EXTRACT = Path(CONFIG["extract_dir"])
DERIVED = Path(CONFIG["derived_dir"])
RUNS = Path(CONFIG["runs_root"])
RESULTS = HERE / "results"

from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, lookahead_bins  # noqa: E402

PH_ID = {p: i for i, p in enumerate(B.VOCAB)}  # 0 blank, 1 SIL, 2..40 phonemes
LA_MS = list(CONFIG["lookahead_ms"])
LA_BINS = [lookahead_bins(ms) for ms in LA_MS]


def model_config(n_sessions: int) -> LookaheadGRUConfig:
    return LookaheadGRUConfig(n_sessions=n_sessions, **CONFIG["model"])


def load_cmudict(path: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split("#")[0].split()
            if len(parts) < 2:
                continue
            w = re.sub(r"\(\d+\)$", "", parts[0].lower())
            if w not in out:
                out[w] = [re.sub(r"\d", "", p) for p in parts[1:]]
    return out


def phonemize(words: str, cmu: dict[str, list[str]]) -> tuple[list[str], bool]:
    ph: list[str] = []
    ok = True
    for w in words.split():
        p = cmu.get(w)
        if p is None:
            ok = False
            continue
        if ph:
            ph.append("SIL")
        ph.extend(p)
    return ph, ok


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def dump(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, np.floating):
            o = float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, float) and not np.isfinite(o):
            return str(o)
        return o

    path.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")


def sessions() -> list[str]:
    return json.loads((DERIVED / "sessions.json").read_text(encoding="utf-8"))


def load_part(part: str, max_items: int | None = None):
    """Items (session index, X float16 (T, 512), phoneme ids int64, words, key) of a derived part."""
    ss = sessions()
    items = []
    for si, s in enumerate(ss):
        p = DERIVED / f"{s}.npz"
        z = np.load(p)
        n = int(z[f"{part}_n"]) if f"{part}_n" in z else 0
        for i in range(n):
            if not bool(z[f"{part}_known"][i]):
                continue
            items.append((si, z[f"{part}_X{i}"], z[f"{part}_ph{i}"].astype(np.int64), f"{s}|{part}|{i}"))
            if max_items and len(items) >= max_items:
                return items
    return items


def texts() -> dict:
    return json.loads((DERIVED / "texts.json").read_text(encoding="utf-8"))


def set_threads(n: int = 4) -> None:
    for v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[v] = str(n)


def below_normal_priority() -> None:
    """Windows: BELOW_NORMAL_PRIORITY_CLASS for this process (no-op elsewhere)."""
    if sys.platform != "win32":
        try:
            os.nice(10)
        except OSError:
            pass
        return
    import ctypes
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)
