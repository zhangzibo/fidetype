"""Shared paths and T15 data loading for the trust reruns on the M4-13 decoder (plan: plan.md). Our own code.

Two sources of T15 phoneme log-probs (41 symbols, 80 ms frames, keys ``<session>|<part>|<i>|L0``):

- ``m4-13`` (the real runs): calibration = val_select decoded on the CPU by ``decode_cpu.py`` (best.pt) into
  ``DER/trust-reruns-m4-13/``; held out = val_eval decoded on the GPU by the M4-13 queue itself
  (``DER/m4-13/logprobs-m4-13-long0-val_eval.npz``, read only).
- ``m4-12`` (dry runs and the "weaker decoder" of P15-03): the M4-12 fixed0 files that P14-03 / P15-05 / P5-02
  used (read only).

Texts and phonemes come from the M4-01/02 derived folder (read only). The order is (session order, index), as in
the P14-03 / P15-05 loaders. Nothing here writes outside ``OWN_ROOTS``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

DER = Path("C:/Users/zhang/bci-data/derived")
RUNS = Path("C:/Users/zhang/bci-data/runs")
D_IN = DER / "m4-01-02-lookahead"  # READ ONLY: texts, sessions, phonemes
M413_RUN = RUNS / "m4-13-long0"  # READ ONLY: best.pt
M413_DONE = RUNS / "m4-13-queue.DONE"  # READ ONLY: the M4-13 queue's finish marker
M413_OWN = DER / "m4-13"  # READ ONLY: the M4-13 queue writes val_eval log-probs here
LOGITS = DER / "trust-reruns-m4-13"  # OURS: CPU decode of val_select, queue log and stage markers
OWN_ROOTS = {
    "queue": LOGITS,
    "p15-03": DER / "p15-03-f1-m4-13",
    "p15-05": DER / "f2-reruns-m4-13" / "p15-05",
    "p15-06": DER / "f2-reruns-m4-13" / "p15-06",
    "p15-06-t12": DER / "f2-reruns-m4-13" / "p15-06-t12-single",
    "p5-02": DER / "p5-02-precision-m4-13",
}
FOREIGN = [DER / n for n in ("m4-13", "m4-01-02-lookahead", "m2-19-trust-retune", "f2-e3-llm-grounding",
                             "p15-06-halluc-bound", "p5-02-precision", "f1-e2-pilot", "f1-e2-pilot-gated",
                             "p15-02-hooks", "p11-01-emg-decoder")]

SOURCES = {
    "m4-13": {"cal": LOGITS / "logprobs-m4-13-long0-val_select.npz",
              "held": M413_OWN / "logprobs-m4-13-long0-val_eval.npz",
              "cal_meta": LOGITS / "decode-m4-13-long0-val_select.json",
              "held_meta": M413_OWN / "decode-m4-13-long0-val_eval.json"},
    "m4-12": {"cal": DER / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz",
              "held": D_IN / "logprobs-m4-12-fixed0.npz",
              "cal_meta": DER / "m2-19-trust-retune" / "decode-m2-19-m4-12-fixed0.json",
              "held_meta": D_IN / "decode-m4-12-fixed0.json"},
}


def held_m413() -> tuple[Path, Path]:
    """The M4-13 val_eval log-probs: the queue's GPU decode if it exists, else our CPU fallback decode."""
    a = (M413_OWN / "logprobs-m4-13-long0-val_eval.npz", M413_OWN / "decode-m4-13-long0-val_eval.json")
    if a[0].exists():
        return a
    return LOGITS / "logprobs-m4-13-long0-val_eval.npz", LOGITS / "decode-m4-13-long0-val_eval.json"


SOURCES["m4-13"]["held"], SOURCES["m4-13"]["held_meta"] = held_m413()


def own(name: str, dry: bool = False) -> Path:
    """Our output folder for ``name``; dry runs write to a ``dryrun/`` subfolder (never mixed with a real run)."""
    p = OWN_ROOTS[name] / "dryrun" if dry else OWN_ROOTS[name]
    assert not any(f == p or f in p.parents for f in FOREIGN), p
    p.mkdir(parents=True, exist_ok=True)
    return p


def source_name() -> str:
    """``TRUST_RERUN_SOURCE`` (m4-13 = real run, default; m4-12 = dry run)."""
    s = os.environ.get("TRUST_RERUN_SOURCE", "m4-13")
    assert s in SOURCES, s
    return s


def is_dry() -> bool:
    return os.environ.get("TRUST_RERUN_DRY", "0") == "1"


def dry_limits() -> tuple[int, int]:
    """(calibration items, held-out items) for a dry run; (0, 0) = all."""
    if not is_dry():
        return 0, 0
    return int(os.environ.get("TRUST_RERUN_NCAL", "160")), int(os.environ.get("TRUST_RERUN_NHELD", "60"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _subset(keys: list[str], n: int) -> list[str]:
    """Dry-run subset: evenly spaced over the sessions (deterministic)."""
    if not n or n >= len(keys):
        return keys
    idx = np.linspace(0, len(keys) - 1, n).round().astype(int)
    return [keys[i] for i in sorted(set(idx.tolist()))]


def load_part(path: Path, part: str, limit: int = 0, norm_text: bool = True, with_keys: bool = False):
    """(log-probs float32 list, texts, phoneme symbol strings[, keys]) of ``part`` in ``path``, in session order."""
    from fidetype.adapters import b2t25 as B

    texts = json.loads((D_IN / "texts.json").read_text(encoding="utf-8"))
    sessions = json.loads((D_IN / "sessions.json").read_text(encoding="utf-8"))
    order = {s: j for j, s in enumerate(sessions)}
    z = np.load(path)
    keys = sorted((k for k in z.files if f"|{part}|" in k), key=lambda k: (order[k.split("|")[0]], int(k.split("|")[2])))
    keys = _subset(keys, limit)
    npz: dict = {}
    xs, ts, ph = [], [], []
    for k in keys:
        s, p, i, _ = k.split("|")
        if s not in npz:
            npz[s] = np.load(D_IN / f"{s}.npz")
        xs.append(z[k].astype(np.float32))
        t = texts[s][p][int(i)]
        ts.append(" ".join(t.split()) if norm_text else t)
        ph.append(B.phonemes_to_symbols([B.VOCAB[j] for j in npz[s][f"{p}_ph{int(i)}"]]))
    out = (xs, ts, ph)
    return (*out, keys) if with_keys else out


def load_t15(source: str | None = None, norm_text: bool = True, with_keys: bool = False):
    """(cal, held) of a source with the dry-run limits applied."""
    src = SOURCES[source or source_name()]
    nc, nh = dry_limits()
    cal = load_part(src["cal"], "val_select", nc, norm_text, with_keys)
    held = load_part(src["held"], "val_eval", nh, norm_text, with_keys)
    return cal, held


def provenance(source: str | None = None) -> dict:
    """Checkpoint hashes of the decoded log-probs (from the decode JSON files)."""
    src = SOURCES[source or source_name()]
    out = {"source": source or source_name()}
    for k in ("cal", "held"):
        m = json.loads(src[f"{k}_meta"].read_text(encoding="utf-8"))
        out[k] = {"file": str(src[k]), "checkpoint_sha256": m.get("checkpoint_sha256"), "step": m.get("step"),
                  "epoch": m.get("epoch"), "device": m.get("device")}
    if out["source"] == "m4-13":  # calibration and held-out log-probs must come from the same best.pt
        assert out["cal"]["checkpoint_sha256"] == out["held"]["checkpoint_sha256"], out
    return out


def word_decoder():
    """The P14-03 / P15-05 T15 word route: B2T '25 phoneme beam + lexicon + n-gram LM, tuned (read only)."""
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    return bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")}), bt


def private_mb() -> int:
    if os.name != "nt":
        return -1
    import ctypes
    import ctypes.wintypes as W

    class PMC(ctypes.Structure):
        _fields_ = [("cb", W.DWORD), ("PageFaultCount", W.DWORD)] + [(f, ctypes.c_size_t) for f in (
            "PeakWorkingSetSize", "WorkingSetSize", "QPPPU", "QPPU", "QPNPPU", "QNPPU", "PagefileUsage",
            "PeakPagefileUsage")]

    k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD]
    m = PMC()
    m.cb = ctypes.sizeof(m)
    ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(m), m.cb)
    return int(m.PagefileUsage / 2**20)


class Logger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, *a) -> None:
        line = time.strftime("%Y-%m-%d %H:%M:%S ") + f"[{private_mb()} MB] " + " ".join(str(x) for x in a)
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def peak_mb() -> int:
    """Peak private bytes of this process in MB (Windows; -1 elsewhere)."""
    if os.name != "nt":
        return -1
    import ctypes
    import ctypes.wintypes as W

    class PMC(ctypes.Structure):
        _fields_ = [("cb", W.DWORD), ("PageFaultCount", W.DWORD)] + [(f, ctypes.c_size_t) for f in (
            "PeakWorkingSetSize", "WorkingSetSize", "QPPPU", "QPPU", "QPNPPU", "QNPPU", "PagefileUsage",
            "PeakPagefileUsage")]

    k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    k32.GetCurrentProcess.restype = W.HANDLE
    ps.GetProcessMemoryInfo.argtypes = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD]
    m = PMC()
    m.cb = ctypes.sizeof(m)
    ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(m), m.cb)
    return int(m.PeakPagefileUsage / 2**20)


def _report_peak() -> None:
    print(f"[trust-reruns] peak private memory {peak_mb()} MB", file=sys.stderr, flush=True)


import atexit  # noqa: E402

atexit.register(_report_peak)
