"""Preprocessing pipeline and block cache for SpanishBCBL MEG.

Pipeline per typing block (each step has a flag in :class:`PreprocConfig`):

1. Load the raw .fif with ``allow_maxshield=True`` (MNE follows split parts).
2. Mark bad channels with ``find_bad_channels_maxwell``.
3. tSSS with ``maxwell_filter`` (``st_duration=10``). All blocks of one
   subject use one ``destination``: the ``dev_head_t`` of the subject's first
   block.
4. Notch filter at 50 and 100 Hz.
5. Band-pass 0.5-45 Hz.
6. Resample to 100 Hz.
7. Keep the 306 MEG channels. (We pick them right after tSSS, before the
   filters. The result for the MEG channels is the same, and it saves time and
   memory.)
8. Robust scaling per block: per channel, subtract the median and divide by
   the inter-quartile range (IQR). Clamp at +-5.

The preset ``"v1"`` uses the Brain2Qwerty v1 band: 0.1-20 Hz, resample to 50 Hz.

Cache format (one pair of files per block)::

    <cache>/<subject>/<session>_<block>.npz
        data      float16 [306, T]   scaled MEG data at sfreq
        sfreq     float64 scalar
        ch_names  str [306]
        ch_types  str [306]          "mag" or "grad"
        ch_pos    float32 [306, 3]   sensor positions (device frame, m)
    <cache>/<subject>/<session>_<block>.json   sidecar (see build_sidecar)
    <cache>/_index.json                        all cached blocks and their QC

The split helper :func:`assign_split` and the sidecar builders use the
standard library and numpy only. :func:`process_block` needs MNE.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from fidetype.data import spanishbcbl as sb
from fidetype.streams.vocab import normalize_text

PIPELINE_NAME = "spanishbcbl-preproc"
PIPELINE_REVISION = 1  # Increase when the code changes the output.
SIDECAR_SCHEMA = 1

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocConfig:
    preset: str = "default"
    maxwell_bads: bool = True
    tsss: bool = True
    st_duration: float = 10.0
    common_destination: bool = True
    notch: tuple[float, ...] | None = (50.0, 100.0)
    l_freq: float | None = 0.5
    h_freq: float | None = 45.0
    sfreq_out: float = 100.0
    pick_meg: bool = True
    robust_scale: bool = True
    clamp: float | None = 5.0
    check_23hz: bool = True
    align_tol_s: float = 0.02
    seg_pre_s: float = 0.4
    seg_post_s: float = 0.5
    stim_channel: str = "STI101"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notch"] = list(self.notch) if self.notch else None
        return d

    @property
    def version(self) -> str:
        """A stable string that changes when the config or pipeline changes."""
        blob = json.dumps({"rev": PIPELINE_REVISION, **self.to_dict()}, sort_keys=True)
        return f"{PIPELINE_NAME}-r{PIPELINE_REVISION}-{hashlib.sha1(blob.encode()).hexdigest()[:10]}"


PRESETS: dict[str, PreprocConfig] = {
    "default": PreprocConfig(),
    "v1": PreprocConfig(preset="v1", l_freq=0.1, h_freq=20.0, sfreq_out=50.0),
}


def get_config(preset: str = "default", **overrides: Any) -> PreprocConfig:
    return replace(PRESETS[preset], **overrides)


# ---------------------------------------------------------------------------
# Split rule
# ---------------------------------------------------------------------------

SPLIT_FRACTIONS = (("train", 80), ("val", 10), ("test", 10))


def assign_split(text: str) -> str:
    """Return "train", "val" or "test" for a sentence (80/10/10).

    The rule hashes the normalised text with SHA-1. So every repetition of a
    sentence, in any subject, gets the same split, and the result never
    changes between runs or machines.
    """
    norm = normalize_text(text)
    bucket = int(hashlib.sha1(norm.encode("utf-8")).hexdigest()[:8], 16) % 100
    acc = 0
    for name, pct in SPLIT_FRACTIONS:
        acc += pct
        if bucket < acc:
            return name
    return SPLIT_FRACTIONS[-1][0]


# ---------------------------------------------------------------------------
# Sidecar
# ---------------------------------------------------------------------------

SEGMENT_KEYS = {
    "trial_idx": int,
    "is_training": bool,
    "start_sample": int,
    "end_sample": int,
    "target_text": str,
    "typed_text": str,
    "key_samples": list,
    "key_chars": list,
    "key_target_chars": list,
    "split": str,
}
SIDECAR_KEYS = {
    "schema": int,
    "subject": str,
    "participant": str,
    "session": str,
    "block": str,
    "source": dict,
    "preprocessing": dict,
    "qc": dict,
    "sfreq": float,
    "n_times": int,
    "segments": list,
}


def build_segments(
    log: sb.BlockLog,
    key_samples_raw: dict[int, np.ndarray],
    sfreq_raw: float,
    sfreq_out: float,
    n_times: int,
    pre_s: float = 0.4,
    post_s: float = 0.5,
    key_matched: dict[int, np.ndarray] | None = None,
) -> list[dict[str, Any]]:
    """Make one segment per trial that has key presses.

    ``key_samples_raw`` holds raw sample indices (from :func:`align_block`).
    The segment runs from the first key press - ``pre_s`` to the last key
    press + ``post_s``, in samples at ``sfreq_out``, clipped to the block.
    ``key_samples`` are relative to the segment start.
    """
    ratio = sfreq_out / sfreq_raw
    pre, post = int(round(pre_s * sfreq_out)), int(round(post_s * sfreq_out))
    segs: list[dict[str, Any]] = []
    for tr in log.trials:
        if not tr.keys:
            continue
        ks = np.round(np.asarray(key_samples_raw[tr.idx], float) * ratio).astype(np.int64)
        start = max(0, int(ks.min()) - pre)
        end = min(int(n_times), int(ks.max()) + post + 1)
        tt = sb.trial_text(tr.sentence, [k.char for k in tr.keys])
        seg = {
            "trial_idx": int(tr.idx),
            "is_training": bool(tr.is_training),
            "start_sample": start,
            "end_sample": end,
            "target_text": tt.target_text,
            "typed_text": tt.typed_text,
            "key_samples": [int(s - start) for s in ks],
            "key_chars": tt.key_chars,
            "key_target_chars": tt.key_target_chars,
            "split": assign_split(tt.target_text),
        }
        if key_matched is not None:
            seg["n_keys_unmatched"] = int((~np.asarray(key_matched[tr.idx], bool)).sum())
        segs.append(seg)
    return segs


def validate_sidecar(d: dict[str, Any]) -> list[str]:
    """Return a list of schema problems (empty list = valid)."""
    errs: list[str] = []
    for k, typ in SIDECAR_KEYS.items():
        if k not in d:
            errs.append(f"missing key {k!r}")
        elif typ is float and isinstance(d[k], (int, float)):
            pass
        elif not isinstance(d[k], typ):
            errs.append(f"{k!r} is {type(d[k]).__name__}, expected {typ.__name__}")
    for i, s in enumerate(d.get("segments", [])):
        for k, typ in SEGMENT_KEYS.items():
            if k not in s:
                errs.append(f"segment {i}: missing {k!r}")
            elif not isinstance(s[k], typ):
                errs.append(f"segment {i}: {k!r} is {type(s[k]).__name__}")
        if all(k in s for k in SEGMENT_KEYS):
            n = len(s["key_samples"])
            if not (len(s["key_chars"]) == len(s["key_target_chars"]) == n):
                errs.append(f"segment {i}: key list lengths differ")
            if s["end_sample"] <= s["start_sample"]:
                errs.append(f"segment {i}: empty segment")
            if any(not 0 <= k < s["end_sample"] - s["start_sample"] for k in s["key_samples"]):
                errs.append(f"segment {i}: key sample outside the segment")
            if s["split"] not in ("train", "val", "test"):
                errs.append(f"segment {i}: bad split {s['split']!r}")
            if s["target_text"] != normalize_text(s["target_text"]):
                errs.append(f"segment {i}: target_text not normalised")
    return errs


def cache_paths(cache_root: str | Path, spec: sb.BlockSpec) -> tuple[Path, Path]:
    base = Path(cache_root) / spec.subject / f"{spec.session}_{spec.block}"
    return base.with_suffix(".npz"), base.with_suffix(".json")


def is_cached(cache_root: str | Path, spec: sb.BlockSpec, cfg: PreprocConfig) -> bool:
    npz, js = cache_paths(cache_root, spec)
    if not (npz.is_file() and js.is_file()):
        return False
    try:
        side = json.loads(js.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return side.get("preprocessing", {}).get("version") == cfg.version


def write_index(cache_root: str | Path) -> dict[str, Any]:
    """Scan all sidecars and write ``<cache>/_index.json``."""
    root = Path(cache_root)
    blocks = []
    for js in sorted(root.glob("S*/*.json")):
        try:
            d = json.loads(js.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        segs = d.get("segments", [])
        blocks.append(
            {
                "npz": js.with_suffix(".npz").relative_to(root).as_posix(),
                "sidecar": js.relative_to(root).as_posix(),
                "subject": d.get("subject"),
                "participant": d.get("participant"),
                "session": d.get("session"),
                "block": d.get("block"),
                "version": d.get("preprocessing", {}).get("version"),
                "sfreq": d.get("sfreq"),
                "n_times": d.get("n_times"),
                "n_segments": len(segs),
                "n_test_trials": sum(not s["is_training"] for s in segs),
                "split_counts": {k: sum(s["split"] == k for s in segs) for k in ("train", "val", "test")},
                "qc": d.get("qc", {}),
            }
        )
    index = {"schema": SIDECAR_SCHEMA, "updated": time.strftime("%Y-%m-%d %H:%M:%S"), "blocks": blocks}
    tmp = root / "_index.json.tmp"
    tmp.write_text(json.dumps(index, indent=1), encoding="utf-8")
    os.replace(tmp, root / "_index.json")
    return index


# ---------------------------------------------------------------------------
# Signal helpers (numpy)
# ---------------------------------------------------------------------------


def robust_scale(data: np.ndarray, clamp: float | None = 5.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scale each row by its median and IQR, then clamp. Return (scaled, median, iqr)."""
    med = np.median(data, axis=1, keepdims=True)
    q75, q25 = np.percentile(data, [75, 25], axis=1, keepdims=True)
    iqr = q75 - q25
    iqr[iqr == 0] = 1.0
    out = (data - med) / iqr
    if clamp is not None:
        np.clip(out, -clamp, clamp, out=out)
    return out, med.ravel(), iqr.ravel()


def peak_prominence_db(freqs: np.ndarray, psd: np.ndarray, f0: float, search: float = 0.6) -> dict[str, float]:
    """Height of the largest peak within ``f0 +- search`` Hz above its ring.

    The ring is the median power at 1.5-5 Hz distance from the peak.
    """
    sel = np.abs(freqs - f0) <= search
    i = np.flatnonzero(sel)[np.argmax(psd[sel])]
    fp = freqs[i]
    ring = (np.abs(freqs - fp) > 1.5) & (np.abs(freqs - fp) < 5)
    return {"freq": float(fp), "prominence_db": float(10 * np.log10(psd[i] / np.median(psd[ring])))}


# ---------------------------------------------------------------------------
# The block pipeline (MNE)
# ---------------------------------------------------------------------------


def peak_memory_gb() -> float | None:
    """Peak working set of this process in GB (Windows only, else None)."""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t)
                for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                          "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")
            ]

        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        psapi = ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            return None
        return round(pmc.PeakWorkingSetSize / 1e9, 2)
    except Exception:  # noqa: BLE001
        return None


def _psd_23hz(raw, tmin: float, picks: str = "mag") -> dict[str, float]:
    import mne  # noqa: F401

    tmax = min(tmin + 60.0, raw.times[-1])
    psd = raw.compute_psd(method="welch", fmin=15.0, fmax=32.0, tmin=tmin, tmax=tmax, n_fft=8192, picks=picks, verbose="ERROR")
    return peak_prominence_db(psd.freqs, np.median(psd.get_data(), axis=0), 23.3)


def subject_destination(data_root: str | Path, spec: sb.BlockSpec):
    """Return the ``dev_head_t`` of a block (used as the subject's destination)."""
    import mne

    info = mne.io.read_info(Path(data_root) / spec.fif, verbose="ERROR")
    return info["dev_head_t"]


def _choose_log(events, first_samp, sfreq, spec: sb.BlockSpec, data_root: Path, tol: float):
    """Align with the named log. If the key match is poor, try the other logs of the session."""
    cands = [spec.log] + list(spec.alt_logs)
    best = None
    for i, rel in enumerate(cands):
        try:
            log = sb.parse_log(data_root / rel)
            al = sb.align_block(events, first_samp, sfreq, log, tol=tol)
        except Exception:  # noqa: BLE001 - a wrong log can fail to align
            continue
        score = al.qc["key_matched_fraction"]
        if best is None or score > best[2].qc["key_matched_fraction"]:
            best = (rel, log, al)
        if i == 0 and score >= 0.9:
            break
    if best is None:
        raise RuntimeError(f"no log could be aligned for {spec.key}")
    return best


def process_block(
    spec: sb.BlockSpec,
    data_root: str | Path,
    cache_root: str | Path,
    cfg: PreprocConfig,
    destination: Any = None,
) -> dict[str, Any]:
    """Run the pipeline on one block and write its .npz and .json files.

    Returns a summary dict (the sidecar QC plus timings).
    """
    import mne

    mne.set_log_level("ERROR")
    data_root = Path(data_root)
    t0 = time.time()
    timings: dict[str, float] = {}

    def tick(name: str) -> None:
        nonlocal t0
        now = time.time()
        timings[name] = round(now - t0, 1)
        t0 = now

    raw = mne.io.read_raw_fif(data_root / spec.fif, allow_maxshield=True, preload=True, verbose="ERROR")
    sfreq_raw = float(raw.info["sfreq"])
    n_files = len(raw.filenames)
    tick("load")

    events = mne.find_events(raw, stim_channel=cfg.stim_channel, shortest_event=1, consecutive=True, verbose="ERROR")
    log_rel, log, al = _choose_log(events, raw.first_samp, sfreq_raw, spec, data_root, cfg.align_tol_s)
    tick("align")

    qc: dict[str, Any] = {"alignment": al.qc, "log_used": log_rel, "log_reassigned": log_rel != spec.log}
    check_t = min(120.0, max(0.0, raw.times[-1] - 60.0))
    if cfg.check_23hz:
        qc["peak_23hz_before"] = _psd_23hz(raw, check_t)

    bads: list[str] = []
    if cfg.maxwell_bads:
        noisy, flat = mne.preprocessing.find_bad_channels_maxwell(
            raw, origin="auto", coord_frame="head", h_freq=40.0, verbose="ERROR"
        )
        bads = sorted(set(noisy) | set(flat))
        raw.info["bads"] = bads
        qc["bads_noisy"], qc["bads_flat"] = list(noisy), list(flat)
    qc["bad_channels"] = bads
    tick("bads")

    if cfg.tsss:
        raw = mne.preprocessing.maxwell_filter(
            raw,
            origin="auto",
            coord_frame="head",
            st_duration=cfg.st_duration,
            destination=destination if cfg.common_destination else None,
            verbose="ERROR",
        )
        tick("tsss")
        if cfg.check_23hz:
            after = _psd_23hz(raw, check_t)
            qc["peak_23hz_after"] = after
            qc["peak_23hz_removed"] = bool(after["prominence_db"] < 3.0)

    if cfg.pick_meg:
        raw.pick("meg", exclude=[])
    if cfg.notch:
        raw.notch_filter(list(cfg.notch), verbose="ERROR")
        tick("notch")
    if cfg.l_freq is not None or cfg.h_freq is not None:
        raw.filter(cfg.l_freq, cfg.h_freq, verbose="ERROR")
        tick("bandpass")
    if cfg.sfreq_out != sfreq_raw:
        raw.resample(cfg.sfreq_out, verbose="ERROR")
        tick("resample")
    data = raw.get_data()
    if cfg.robust_scale:
        data, _, _ = robust_scale(data, cfg.clamp)
    tick("scale")

    ch_names = list(raw.ch_names)
    ch_types = list(raw.get_channel_types())
    ch_pos = np.array([ch["loc"][:3] for ch in raw.info["chs"]], dtype=np.float32)
    n_times = int(data.shape[1])
    segs = build_segments(
        log, al.key_samples, sfreq_raw, cfg.sfreq_out, n_times, cfg.seg_pre_s, cfg.seg_post_s, al.key_matched
    )
    dht = raw.info["dev_head_t"]
    sidecar = {
        "schema": SIDECAR_SCHEMA,
        "subject": spec.subject,
        "participant": spec.participant,
        "session": spec.session,
        "block": spec.block,
        "source": {
            "fif": spec.fif,
            "split_parts": spec.split_parts,
            "n_fif_files_read": n_files,
            "log": log_rel,
            "session_dir": spec.session_dir,
            "notes": spec.notes,
            "sfreq_raw": sfreq_raw,
            "n_times_raw": int(round(n_times * sfreq_raw / cfg.sfreq_out)),
            "duration_s": round(n_times / cfg.sfreq_out, 2),
        },
        "preprocessing": {
            "version": cfg.version,
            "config": cfg.to_dict(),
            "mne_version": mne.__version__,
            "destination_dev_head_t": (np.asarray(destination["trans"]).tolist() if destination is not None else None),
            "dev_head_t_out": np.asarray(dht["trans"]).tolist() if dht is not None else None,
        },
        "qc": qc,
        "sfreq": float(cfg.sfreq_out),
        "n_times": n_times,
        "segments": segs,
    }
    errs = validate_sidecar(sidecar)
    if errs:
        raise RuntimeError(f"sidecar invalid for {spec.key}: {errs[:5]}")

    npz_path, js_path = cache_paths(cache_root, spec)
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_npz = npz_path.with_name(npz_path.stem + ".tmp.npz")
    np.savez(
        tmp_npz,
        data=data.astype(np.float16),
        sfreq=np.float64(cfg.sfreq_out),
        ch_names=np.array(ch_names),
        ch_types=np.array(ch_types),
        ch_pos=ch_pos,
    )
    os.replace(tmp_npz, npz_path)
    tick("write")
    sidecar["qc"]["timings_s"] = timings
    sidecar["qc"]["peak_memory_gb"] = peak_memory_gb()
    tmp_js = js_path.with_suffix(".json.tmp")
    tmp_js.write_text(json.dumps(sidecar, indent=1), encoding="utf-8")
    os.replace(tmp_js, js_path)  # The sidecar is written last: it marks the block as done.
    return {"key": spec.key, "qc": qc, "n_segments": len(segs), "n_times": n_times}


# ---------------------------------------------------------------------------
# Reading the cache
# ---------------------------------------------------------------------------


@dataclass
class CachedBlock:
    data: np.ndarray  # float16 [306, T]
    sfreq: float
    ch_names: list[str]
    ch_types: list[str]
    ch_pos: np.ndarray
    sidecar: dict[str, Any] = field(default_factory=dict)

    def segment(self, i: int) -> np.ndarray:
        s = self.sidecar["segments"][i]
        return self.data[:, s["start_sample"] : s["end_sample"]]


def load_cached_block(npz_path: str | Path) -> CachedBlock:
    """Load one cached block (.npz plus its .json sidecar)."""
    npz_path = Path(npz_path)
    with np.load(npz_path) as z:
        blk = CachedBlock(
            data=z["data"],
            sfreq=float(z["sfreq"]),
            ch_names=[str(c) for c in z["ch_names"]],
            ch_types=[str(c) for c in z["ch_types"]],
            ch_pos=z["ch_pos"],
        )
    blk.sidecar = json.loads(npz_path.with_suffix(".json").read_text(encoding="utf-8"))
    return blk


def split_counts(sidecars: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Count trials and unique sentences per split over many sidecars."""
    trials = {"train": 0, "val": 0, "test": 0}
    sents: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    for d in sidecars:
        for s in d["segments"]:
            trials[s["split"]] += 1
            sents[s["split"]].add(s["target_text"])
    return {"trials": trials, "sentences": {k: len(v) for k, v in sents.items()}}
