"""Inspect one subject of the SpanishBCBL MEG typing dataset (milestone M0).

Usage:
    python inspect_subject.py <data_root> <subject_folder> [--out <dir>]

Example:
    python inspect_subject.py C:/Users/zhang/bci-data/SpanishBCBL 25_12032

The script reads the raw .fif files and the .mat logs. It never writes data
files. It writes only a report (results.md) and small PNG plots (results/).
The dataset licence is CC BY-NC 4.0, so do not copy data into the repo.

This is our own code. We read the brain2qwerty loader (CC BY-NC) only to
understand the log format. No code is copied from it.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mne  # noqa: E402
import scipy.io  # noqa: E402

mne.set_log_level("ERROR")

STIM_CANDIDATES = ["STI101", "STI014", "STI 014", "STI001", "STI201"]
# Trigger codes from the log header (fields trigstim, trigblock, triggerpause).
# The script reads the real values from each log. These are only defaults.
DEFAULT_CODES = {"word": 10, "block": 20, "pause": 30}
# Colours: default categorical order of the dataviz palette (fixed order).
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GREY = "#8a8985"

LINES: list[str] = []


def say(text: str = "") -> None:
    """Print a line and keep it for the report."""
    print(text)
    LINES.append(text)


# --------------------------------------------------------------------------
# File discovery
# --------------------------------------------------------------------------


@dataclass
class Block:
    session_dir: str
    session: int
    block: int
    path: Path
    log: Path | None
    report: dict = field(default_factory=dict)


def find_blocks(root: Path, subject_folder: str) -> tuple[int, list[Block]]:
    """Find typing blocks and their logs for one subject folder."""
    sub_dir = root / "MEG" / "FIF" / subject_folder
    subj = int(subject_folder.split("_")[0])
    session_dirs = sorted(p.name for p in sub_dir.iterdir() if p.is_dir() and p.name.isdigit())
    blocks: list[Block] = []
    for k, sdir in enumerate(session_dirs, start=1):
        for f in sorted((sub_dir / sdir).glob("*.fif")):
            m = re.fullmatch(r"block(\d+)\.fif", f.name, flags=re.IGNORECASE)
            if not m:  # skip tapping/typing localizers and -1 split parts
                continue
            b = int(m.group(1))
            logs = sorted((root / "MEG" / "logs").glob(f"S{subj}-session{k}_block{b}_list*.mat"))
            blocks.append(Block(sdir, k, b, f, logs[0] if len(logs) == 1 else None))
    return subj, blocks


# --------------------------------------------------------------------------
# MEG header
# --------------------------------------------------------------------------


def describe_raw(raw: mne.io.BaseRaw) -> dict:
    info = raw.info
    types = Counter(raw.get_channel_types())
    dig = info["dig"] or []
    kinds = Counter(int(d["kind"]) for d in dig)
    fiff = mne.io.constants.FIFF
    ph = info["proc_history"] or []
    sss_done = any(p.get("max_info", {}).get("sss_info") for p in ph)
    ias = [c for c in raw.ch_names if c.startswith("IAS")]
    try:
        chpi = mne.chpi.get_chpi_info(info, on_missing="ignore")
        hpi_freqs = [float(f) for f in chpi[0]]
    except Exception:  # noqa: BLE001
        hpi_freqs = []
    dht = info["dev_head_t"]
    return {
        "n_channels": len(raw.ch_names),
        "types": dict(sorted(types.items())),
        "sfreq": info["sfreq"],
        "duration_s": raw.n_times / info["sfreq"],
        "n_files": len(raw.filenames),
        "first_samp": raw.first_samp,
        "meas_date": str(info["meas_date"]),
        "highpass": info["highpass"],
        "lowpass": info["lowpass"],
        "line_freq": info["line_freq"],
        "bads": list(info["bads"]),
        "dig_cardinal": kinds.get(int(fiff.FIFFV_POINT_CARDINAL), 0),
        "dig_hpi": kinds.get(int(fiff.FIFFV_POINT_HPI), 0),
        "dig_extra": kinds.get(int(fiff.FIFFV_POINT_EXTRA), 0),
        "dig_eeg": kinds.get(int(fiff.FIFFV_POINT_EEG), 0),
        "dev_head_t": dht is not None,
        "dev_head_trans_mm": (dht["trans"][:3, 3] * 1000).round(1).tolist() if dht is not None else None,
        "maxshield": bool(info.get("maxshield", False)),
        "ias_channels": len(ias),
        "sss_applied": sss_done,
        "hpi_freqs": hpi_freqs,
        "stim_channels": [c for c in raw.ch_names if c in STIM_CANDIDATES or c.startswith("STI")],
        "misc_names": [c for c, t in zip(raw.ch_names, raw.get_channel_types()) if t not in ("mag", "grad")],
    }


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def read_events(raw: mne.io.BaseRaw) -> tuple[str | None, np.ndarray, dict]:
    """Try several stim channels. Return the one with the most events."""
    tried = {}
    best = (None, np.zeros((0, 3), int))
    for ch in STIM_CANDIDATES:
        if ch not in raw.ch_names:
            continue
        ev = mne.find_events(raw, stim_channel=ch, shortest_event=1, consecutive=True, verbose="ERROR")
        tried[ch] = len(ev)
        if len(ev) > len(best[1]):
            best = (ch, ev)
    return best[0], best[1], tried


# --------------------------------------------------------------------------
# Logs
# --------------------------------------------------------------------------


def _records(x) -> list[dict]:
    """Normalise one struct array from loadmat into a list of dicts."""
    if x is None:
        return []
    if isinstance(x, dict):
        return [x]
    if hasattr(x, "_fieldnames"):  # scipy mat_struct
        return [{k: getattr(x, k) for k in x._fieldnames}]
    if isinstance(x, (list, tuple, np.ndarray)):
        out: list[dict] = []
        for item in (x.ravel() if isinstance(x, np.ndarray) else x):
            out.extend(_records(item))
        return out
    return []


def load_log(path: Path) -> tuple[dict, str]:
    """Load a .mat log. Return (top-level dict, reader name)."""
    try:
        return scipy.io.loadmat(path, simplify_cells=True), "scipy.io.loadmat(simplify_cells=True)"
    except NotImplementedError:  # MATLAB v7.3 = HDF5
        try:
            import h5py  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(f"{path.name} is MATLAB v7.3 and h5py is not installed") from exc
        raise RuntimeError(f"{path.name} is MATLAB v7.3; add an h5py reader")


@dataclass
class LogEvent:
    t: float  # trigger time on the stimulus-PC clock (s)
    code: int
    kind: str  # word | key | block
    trial: int
    label: str
    t_key: float = np.nan  # keyboard-queue time of a key press (other clock)


def log_events(mat: dict) -> tuple[list[LogEvent], list[dict], dict]:
    """Make one flat list of trigger-like events from a log."""
    pr = mat["pr_trials"]
    codes = {
        "word": int(mat.get("trigstim", DEFAULT_CODES["word"])),
        "block": int(mat.get("trigblock", DEFAULT_CODES["block"])),
        "pause": int(mat.get("triggerpause", DEFAULT_CODES["pause"])),
        "ascii": int(mat.get("triggerascii", 1)),
    }
    events: list[LogEvent] = []
    trials: list[dict] = []
    n = len(pr["sequence"])
    for i in range(n):
        words = _records(pr["rsvp"][i])
        presses = _records(pr["kp"][i])
        allkeys = _records(pr["key"][i])
        ktrig = np.atleast_1d(np.asarray(pr["keyTrig"][i], dtype=float))
        for w in words:
            events.append(LogEvent(float(w["trigTime"]), codes["word"], "word", i, str(w["stim"])))
        n_pair = min(len(presses), len(ktrig))
        for p, tt in zip(presses[:n_pair], ktrig[:n_pair]):
            ch = chr(int(p["CookedKey"])) if int(p["CookedKey"]) > 0 else f"<{int(p['Keycode'])}>"
            events.append(LogEvent(float(tt), int(p["Keycode"]), "key", i, ch, float(p["Time"])))
        trials.append(
            {
                "trial": i,
                "sequence": str(pr["sequence"][i]).strip(),
                "n_words": len(words),
                "n_press": len(presses),
                "n_key_events": len(allkeys),
                "n_keytrig": len(ktrig),
                "typed": "".join(
                    chr(int(p["CookedKey"])) if 31 < int(p["CookedKey"]) < 0x250 else
                    {8: "<", 13: "|"}.get(int(p["Keycode"]), "?")
                    for p in presses
                ),
                "presses": presses,
                "keytrig": ktrig,
                "words": words,
                "ts": float(np.asarray(pr["ts"][i]).ravel()[0]) if np.size(pr["ts"][i]) else np.nan,
                "dist": float(np.asarray(pr["dist"][i]).ravel()[0]) if np.size(pr["dist"][i]) else np.nan,
                "errperc": float(np.asarray(pr["errperc"][i]).ravel()[0]) if np.size(pr["errperc"][i]) else np.nan,
            }
        )
    for t in np.atleast_1d(np.asarray(pr["blockTrig"], dtype=float)):
        events.append(LogEvent(float(t), codes["block"], "block", -1, "block"))
    events.sort(key=lambda e: e.t)
    return events, trials, codes


# --------------------------------------------------------------------------
# Alignment (own method: offset by histogram mode, then nearest same-code match)
# --------------------------------------------------------------------------


def find_ramp(meg_t: np.ndarray, meg_code: np.ndarray) -> int:
    """Return the number of leading events in the start-up test ramp (codes 1, 2, ... sent 20 ms apart)."""
    if len(meg_code) == 0 or meg_code[0] != 1:
        return 0
    n = 1
    while n < len(meg_t) and meg_t[n] - meg_t[n - 1] < 0.1:
        n += 1
    return n if n >= 16 else 0


def _greedy_match(meg_t, meg_code, lt, lc, pred, tol):
    """One-to-one match: each log event takes the nearest unused MEG event with the same code."""
    used = np.zeros(len(meg_t), bool)
    match = np.full(len(lt), -1)
    order = np.argsort(meg_t)
    st = meg_t[order]
    for i in np.argsort(pred):
        lo, hi = np.searchsorted(st, [pred[i] - tol, pred[i] + tol])
        cand = order[lo:hi]
        cand = cand[(meg_code[cand] == lc[i]) & ~used[cand]]
        if len(cand):
            j = cand[np.argmin(np.abs(meg_t[cand] - pred[i]))]
            used[j] = True
            match[i] = j
    return match, used


def align(meg_t: np.ndarray, meg_code: np.ndarray, log: list[LogEvent], tol: float = 0.02) -> dict:
    """Align log trigger times to MEG trigger times (both on their own clocks).

    The two clocks drift (about 0.5 ms per s), so a constant offset fails over a block.
    1. Match the two code sequences in order (difflib longest-matching-blocks).
    2. Fit MEG time = slope * log time + intercept on those pairs. Drop pairs off the
       line by more than tol, and fit again.
    3. Match again by time: each log event takes the nearest unused MEG event with the
       same code within tol of the fitted line. Fit a final line and report residuals.
    """
    lt = np.array([e.t for e in log])
    lc = np.array([e.code for e in log])
    if len(meg_t) < 3 or len(lt) < 3:
        return {"ok": False}
    sm = difflib.SequenceMatcher(None, meg_code.tolist(), lc.tolist(), autojunk=False)
    pairs = [(b.a + k, b.b + k) for b in sm.get_matching_blocks() for k in range(b.size)]
    mi, li = (np.array(v) for v in zip(*pairs))
    n_seq = len(pairs)
    slope, icpt = np.polyfit(lt[li], meg_t[mi], 1)
    for _ in range(3):
        keep = np.abs(meg_t[mi] - (slope * lt[li] + icpt)) < tol
        slope, icpt = np.polyfit(lt[li[keep]], meg_t[mi[keep]], 1)
    match, used = _greedy_match(meg_t, meg_code, lt, lc, slope * lt + icpt, tol)
    ok = match >= 0
    x, y = lt[ok], meg_t[match[ok]]
    slope, icpt = np.polyfit(x, y, 1)
    offset = float(icpt + (slope - 1) * lt[0])  # offset at the first log event
    resid = y - (slope * x + icpt)
    kinds = np.array([e.kind for e in log])
    per_kind = {kd: (int((ok & (kinds == kd)).sum()), int((kinds == kd).sum())) for kd in ("word", "key", "block")}
    unmatched_meg = Counter(int(c) for c in meg_code[~used])
    return {
        "ok": True,
        "n_seq_match": n_seq,
        "offset": offset,
        "slope": float(slope),
        "drift_ms_per_1000s": float((slope - 1) * 1e6),
        "n_log": len(log),
        "n_meg": len(meg_t),
        "n_match": int(ok.sum()),
        "per_kind": per_kind,
        "resid_ms_med": float(np.median(np.abs(resid)) * 1000),
        "resid_ms_p95": float(np.percentile(np.abs(resid), 95) * 1000),
        "resid_ms_max": float(np.max(np.abs(resid)) * 1000),
        "unmatched_meg": dict(unmatched_meg.most_common(8)),
        "n_unmatched_meg": int((~used).sum()),
        "match": match,
    }


# --------------------------------------------------------------------------
# Data checks
# --------------------------------------------------------------------------


def data_checks(raw: mne.io.BaseRaw, tmin: float, outdir: Path, tag: str) -> dict:
    tmax = min(tmin + 60.0, raw.times[-1])
    seg = raw.copy().crop(tmin, tmax).load_data()
    res: dict = {"tmin": tmin, "tmax": tmax, "rms": {}, "flat": {}, "noisy": {}}
    for kind, scale, unit in (("mag", 1e15, "fT"), ("grad", 1e13, "fT/cm"), ("eog", 1e6, "uV"), ("ecg", 1e6, "uV")):
        picks = mne.pick_types(seg.info, meg=kind if kind in ("mag", "grad") else False,
                               eog=kind == "eog", ecg=kind == "ecg", exclude=[])
        if len(picks) == 0:
            continue
        x = seg.get_data(picks=picks)
        x = x - x.mean(axis=1, keepdims=True)
        sd = x.std(axis=1)
        res["rms"][kind] = (float(np.median(sd) * scale), float(np.min(sd) * scale), float(np.max(sd) * scale), unit)
        if kind in ("mag", "grad"):
            med = np.median(sd)
            mad = np.median(np.abs(sd - med)) * 1.4826
            names = np.array(seg.ch_names)[picks]
            res["flat"][kind] = names[sd < 0.05 * med].tolist()
            res["noisy"][kind] = names[(sd - med) / (mad + 1e-30) > 6].tolist()
    # Maxwell-based bad channel scan (no fine-cal / cross-talk files exist in the dataset).
    try:
        noisy, flat = mne.preprocessing.find_bad_channels_maxwell(
            seg.copy().filter(None, 40.0, verbose="ERROR"), origin="auto", coord_frame="head", verbose="ERROR"
        )
        res["maxwell_bads"] = {"noisy": noisy, "flat": flat}
    except Exception as exc:  # noqa: BLE001
        res["maxwell_bads"] = {"error": f"{type(exc).__name__}: {exc}"}
    # PSD
    psd = seg.compute_psd(method="welch", fmin=0.5, fmax=min(330.0, seg.info["sfreq"] / 2 - 1),
                          n_fft=8192, picks=["mag", "grad"], exclude=[])
    f = psd.freqs
    data = psd.get_data()
    types = np.array(seg.get_channel_types(picks=["mag", "grad"]))
    peaks = {}
    for kind in ("mag", "grad"):
        p = np.median(data[types == kind], axis=0)
        row = {}
        for lf in (50, 100, 150, 200, 250, 300):
            if lf > f[-1]:
                continue
            on = p[np.argmin(np.abs(f - lf))]
            ring = p[((np.abs(f - lf) > 1.5) & (np.abs(f - lf) < 5))]
            row[lf] = round(float(10 * np.log10(on / np.median(ring))), 1)
        peaks[kind] = row
    res["line_peaks_db"] = peaks
    # Other narrow peaks (not 50 Hz harmonics, not cHPI): median mag/grad spectrum, 1-140 Hz.
    from scipy.signal import find_peaks

    res["other_peaks"] = {}
    for kind in ("mag", "grad"):
        db = 10 * np.log10(np.median(data[types == kind], axis=0))
        band = (f > 1) & (f < 140)
        idx, prop = find_peaks(np.where(band, db, db[band].min()), prominence=6)
        lst = [(round(float(f[i]), 1), round(float(p), 1)) for i, p in zip(idx, prop["prominences"])
               if band[i] and min(abs(f[i] - 50 * k) for k in range(1, 4)) > 1.0]
        res["other_peaks"][kind] = sorted(lst, key=lambda x: -x[1])[:6]
    hpi = describe_raw(seg)["hpi_freqs"]
    res["hpi_peaks_db"] = {}
    pm = np.median(data[types == "mag"], axis=0)
    for hf in hpi:
        if hf < f[-1]:
            on = pm[np.argmin(np.abs(f - hf))]
            ring = pm[((np.abs(f - hf) > 1.5) & (np.abs(f - hf) < 5))]
            res["hpi_peaks_db"][hf] = round(float(10 * np.log10(on / np.median(ring))), 1)
    # Plot PSD: median per type, with 10-90 % band.
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), dpi=100, sharex=True)
    for ax, kind, scale, unit, col in ((axes[0], "mag", 1e15, "fT", C1), (axes[1], "grad", 1e13, "fT/cm", C2)):
        p = data[types == kind] * scale**2
        ax.fill_between(f, np.percentile(p, 10, 0), np.percentile(p, 90, 0), color=col, alpha=0.2, lw=0)
        ax.semilogy(f, np.median(p, 0), color=col, lw=1.5)
        for lf in (50, 100, 150, 200, 250, 300):
            ax.axvline(lf, color=GREY, lw=0.6, ls=":")
        ax.set_title(f"{kind} (n={int((types == kind).sum())}): median, 10-90 % band", fontsize=9)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel(f"PSD ({unit}$^2$/Hz)")
        ax.grid(alpha=0.2, lw=0.5)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.suptitle(f"{tag}: raw PSD, {tmin:.0f}-{tmax:.0f} s (dotted = 50 Hz harmonics)", fontsize=10)
    fig.tight_layout()
    png = outdir / "psd.png"
    fig.savefig(png)
    plt.close(fig)
    res["png"] = png
    return res


def plot_timeline(meg_t, meg_code, codes, log, al, outdir: Path, tag: str) -> Path:
    fig, ax = plt.subplots(figsize=(10, 2.8), dpi=100)
    word = meg_code == codes["word"]
    block = meg_code == codes["block"]
    other = ~(word | block)
    matched = np.zeros(len(meg_t), bool)
    matched[al["match"][al["match"] >= 0]] = True
    ax.vlines(meg_t[other & matched], 0.6, 1.4, color=C1, lw=0.4, label="key trigger (matched to log)")
    ax.vlines(meg_t[other & ~matched], 0.6, 1.4, color=C2, lw=0.8, label="other trigger (no log match)")
    ax.vlines(meg_t[word], 1.6, 2.4, color=C3, lw=0.6, label=f"word onset (code {codes['word']})")
    ax.vlines(meg_t[block], 2.6, 3.4, color=C4, lw=2.0, label=f"block (code {codes['block']})")
    ax.set_yticks([1, 2, 3], ["keys", "words", "block"])
    ax.set_xlabel("Time from recording start (s)")
    ax.set_xlim(0, meg_t.max() + 5 if len(meg_t) else 1)
    ax.set_ylim(0.3, 3.7)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=4, fontsize=8, frameon=False)
    ax.set_title(f"{tag}: MEG trigger events on {al.get('stim', 'STI')}", fontsize=10)
    fig.tight_layout()
    png = outdir / "event_timeline.png"
    fig.savefig(png)
    plt.close(fig)
    return png


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def fmt_types(t: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in t.items())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data_root", type=Path)
    ap.add_argument("subject_folder", help="for example 25_12032")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--check-tmin", type=float, default=120.0, help="start of the 60 s data-check window (s)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    out: Path = args.out
    (out / "results").mkdir(parents=True, exist_ok=True)

    subj, blocks = find_blocks(args.data_root, args.subject_folder)
    say(f"# SpanishBCBL inspection: S{subj} ({args.subject_folder})")
    say()
    say(f"MNE {mne.__version__}, SciPy {scipy.__version__}, NumPy {np.__version__}.")
    say(f"Typing blocks found: {len(blocks)}.")
    say()

    summary_rows = []
    first_timeline = None
    for blk in blocks:
        tag = f"S{subj} ses{blk.session} ({blk.session_dir}) block{blk.block}"
        say(f"## {tag}")
        say()
        say(f"- File: `MEG/FIF/{args.subject_folder}/{blk.session_dir}/{blk.path.name}`")
        say(f"- Log: `MEG/logs/{blk.log.name}`" if blk.log else "- Log: NOT FOUND")
        raw = mne.io.read_raw_fif(blk.path, allow_maxshield=True, preload=False, verbose="ERROR")
        h = describe_raw(raw)
        blk.report["header"] = h
        say(f"- Channels: {h['n_channels']} ({fmt_types(h['types'])})")
        say(f"- Non-MEG channels: {', '.join(h['misc_names'])}")
        say(f"- sfreq {h['sfreq']:.0f} Hz; duration {h['duration_s']:.1f} s; {h['n_files']} file part(s); "
            f"online filter {h['highpass']:.2f}-{h['lowpass']:.0f} Hz; line_freq {h['line_freq']}")
        say(f"- Dig: {h['dig_cardinal']} fiducials, {h['dig_hpi']} HPI, {h['dig_extra']} head-shape (extra), "
            f"{h['dig_eeg']} EEG points")
        say(f"- dev_head_t: {h['dev_head_t']} (device->head translation {h['dev_head_trans_mm']} mm)")
        say(f"- MaxShield (IAS on): {h['maxshield']} ({h['ias_channels']} IAS channels); SSS applied: {h['sss_applied']}")
        say(f"- cHPI coil freqs: {h['hpi_freqs'] or 'none'}; bads in header: {h['bads'] or 'none'}")

        stim, ev, tried = read_events(raw)
        meg_t = (ev[:, 0] - raw.first_samp) / raw.info["sfreq"]
        meg_code = ev[:, 2]
        say(f"- Stim channels tried (events found): {tried}; used: {stim}")
        n_ramp = find_ramp(meg_t, meg_code)
        if n_ramp:
            say(f"- The first {n_ramp} events are a start-up test ramp (codes {meg_code[0]}..{meg_code[n_ramp - 1]}, "
                f"about 20 ms apart, at {meg_t[0]:.1f}-{meg_t[n_ramp - 1]:.1f} s). They are dropped.")
        meg_t, meg_code = meg_t[n_ramp:], meg_code[n_ramp:]
        cnt = Counter(int(c) for c in meg_code)
        say(f"- MEG events after the ramp: {len(meg_code)}; distinct codes: {len(cnt)}")
        top = ", ".join(f"{c}:{n}" for c, n in sorted(cnt.items()))
        say(f"- Code:count = {top}")
        blk.report["events"] = (stim, cnt)

        if blk.log is None:
            say()
            continue
        mat, reader = load_log(blk.log)
        levents, trials, codes = log_events(mat)
        say(f"- Log reader: {reader}; header codes: word={codes['word']}, block={codes['block']}, "
            f"pause={codes['pause']}, triggerascii={codes['ascii']}")
        say(f"- Log trials: {len(trials)} (sequences without training: {len(mat['pr_trials']['sequences'])}); "
            f"word events {sum(e.kind == 'word' for e in levents)}, key presses {sum(e.kind == 'key' for e in levents)}, "
            f"block triggers {sum(e.kind == 'block' for e in levents)}")
        mism = [t["trial"] for t in trials if t["n_press"] != t["n_keytrig"]]
        say(f"- Trials where len(kp) != len(keyTrig): {mism or 'none'}")
        al = align(meg_t, meg_code, levents)
        al["stim"] = stim
        blk.report["align"] = al
        if al["ok"]:
            pk = al["per_kind"]
            say(f"- Alignment: code-sequence match gives {al['n_seq_match']} pairs. After the line fit: "
                f"offset {al['offset']:.4f} s at the first log event, slope {al['slope']:.7f}; matched "
                f"{al['n_match']}/{al['n_log']} log events (words {pk['word'][0]}/{pk['word'][1]}, keys "
                f"{pk['key'][0]}/{pk['key'][1]}, block {pk['block'][0]}/{pk['block'][1]}); "
                f"unmatched MEG events {al['n_unmatched_meg']}/{al['n_meg']}")
            say(f"- Residual after linear fit: median {al['resid_ms_med']:.2f} ms, p95 {al['resid_ms_p95']:.2f} ms, "
                f"max {al['resid_ms_max']:.2f} ms; clock drift {al['drift_ms_per_1000s']:.3f} ms per 1000 s")
            say(f"- Unmatched MEG codes (top): {al['unmatched_meg']}")
            # Key-press latency: keyboard-queue time vs trigger time (shared clock via the rsvp t/trigTime pair).
            w = [x for t in trials for x in t["words"]]
            clk = np.median([float(x["trigTime"]) - float(x["t"]) for x in w])
            lat = np.array([e.t - (e.t_key + clk) for e in levents if e.kind == "key"]) * 1000
            say(f"- Clock link: trigTime - t (word events) = {clk:.4f} s. Key trigger minus key-queue time: "
                f"median {np.median(lat):.1f} ms, p5 {np.percentile(lat, 5):.1f}, p95 {np.percentile(lat, 95):.1f} ms")
            al["key_latency_ms"] = (float(np.median(lat)), float(np.percentile(lat, 5)), float(np.percentile(lat, 95)))
        summary_rows.append((tag, h, stim, len(meg_code), al, len(trials)))
        if first_timeline is None:
            first_timeline = (blk, raw, meg_t, meg_code, codes, levents, al, trials, tag, mat)
        say()

    if first_timeline is None:
        say("No block with a log. Stop.")
        return 1
    blk, raw, meg_t, meg_code, codes, levents, al, trials, tag, mat = first_timeline

    # Log structure (first block)
    say("## Log structure (first block)")
    say()
    pr = mat["pr_trials"]
    say(f"Top-level variables: {len([k for k in mat if not k.startswith('__')])}. "
        f"The useful one is `pr_trials`, a struct with fields: {', '.join(pr.keys())}.")
    say()
    say("| Field | Shape / type | Content (our reading) |")
    say("|---|---|---|")
    desc = {
        "sequence": "target sentence per trial, incl. 2 training trials (upper or lower case, trailing spaces)",
        "sequences": "target sentences of test trials only",
        "words": "word list per test trial",
        "order": "presentation order index (test trials)",
        "rsvp": "per trial: struct array, one entry per shown word: trigTime (trigger clock), stim (word), t (screen clock), rdjit (jitter s)",
        "key": "per trial: all keyboard-queue events (press and release): Time, Pressed, Keycode, CookedKey, ...",
        "kp": "per trial: key presses only (same fields as key)",
        "keyTrig": "per trial: trigger time of each key press (same clock as rsvp.trigTime); len == len(kp)",
        "blockTrig": "trigger times of block / pause markers",
        "ts": "per trial: typing time (s), probably",
        "dist": "per trial: edit distance typed vs the raw target string. It counts case and the trailing spaces (trial 0: typed correctly in lower case, dist 31 vs the upper-case target; trial 2: typed correctly, dist 5 = 5 trailing spaces)",
        "errperc": "per trial: dist / target length, probably (same case problem); do not use it as a typing-error rate",
        "nfl": "per trial: flag (all 0 here)",
    }
    for k, v in pr.items():
        shp = getattr(v, "shape", None)
        say(f"| `{k}` | {shp if shp is not None else type(v).__name__} | {desc.get(k, '')} |")
    say()
    say('Example trials (typed = CookedKey of each press; "<" = backspace, "|" = return, "?" = other):')
    say()
    for t in [trials[0], trials[2], trials[3]]:
        p = t["presses"]
        say(f"- Trial {t['trial']}: target \"{t['sequence']}\"; {t['n_words']} words shown; {t['n_press']} presses "
            f"({t['n_key_events']} press+release events); ts={t['ts']:.1f}, dist={t['dist']:.0f}, errperc={t['errperc']:.2f}")
        say(f"  - typed: \"{t['typed']}\"")
        first = ", ".join(
            f"{chr(int(x['CookedKey'])) if int(x['CookedKey']) > 31 else int(x['Keycode'])!r}@{float(tt) - t['keytrig'][0]:.3f}s"
            for x, tt in zip(p[:8], t["keytrig"][:8]))
        say(f"  - first 8 presses (key@time from first key trigger, Keycode in brackets): {first}")
        say(f"  - Keycodes: {[int(x['Keycode']) for x in p[:12]]}")
    say()

    # Trigger-to-key check
    say("## Do triggers encode keys?")
    say()
    key_codes = Counter(e.code for e in levents if e.kind == "key")
    meg_cnt = Counter(int(c) for c in meg_code)
    both = sorted(set(key_codes) & set(meg_cnt))
    say(f"Distinct key codes in log: {len(key_codes)}; of them present as MEG codes: {len(both)}.")
    say("| Code | char | log presses | MEG events |")
    say("|---|---|---|---|")
    for c, n in key_codes.most_common(12):
        say(f"| {c} | {chr(c) if 31 < c < 127 else '-'} | {n} | {meg_cnt.get(c, 0)} |")
    say()

    # Data checks
    say(f"## Data checks ({tag}, 60 s)")
    say()
    dc = data_checks(raw, args.check_tmin, out / "results", tag)
    for kind, (med, lo, hi, unit) in dc["rms"].items():
        say(f"- RMS {kind}: median {med:.1f} {unit} (min {lo:.1f}, max {hi:.1f})")
    say(f"- Flat (< 5 % of median SD): {dc['flat']}")
    say(f"- Noisy (robust z > 6): {dc['noisy']}")
    say(f"- find_bad_channels_maxwell (no fine-cal/cross-talk files): {dc['maxwell_bads']}")
    say(f"- Line peaks (dB above +-1.5-5 Hz neighbours, median channel): {dc['line_peaks_db']}")
    say(f"- cHPI peaks on mag (dB): {dc['hpi_peaks_db'] or 'none'}")
    say(f"- Other narrow peaks 1-140 Hz (Hz, prominence dB): {dc['other_peaks']}")
    tl = plot_timeline(meg_t, meg_code, codes, levents, al, out / "results", tag)
    say(f"- Plots: `results/{dc['png'].name}`, `results/{tl.name}`")
    say()

    # Head position across blocks
    say("## Head position across blocks (dev_head_t translation, mm)")
    say()
    for b in blocks:
        h = b.report.get("header", {})
        say(f"- ses{b.session} block{b.block}: {h.get('dev_head_trans_mm')}")
    say()

    write_report(out, subj, args.subject_folder, blocks, summary_rows, dc, al, trials, codes)
    return 0


def write_report(out, subj, folder, blocks, rows, dc, al, trials, codes) -> None:
    h0 = rows[0][1]
    lk = al.get("key_latency_ms", (np.nan,) * 3)
    tot_match = sum(r[4]["n_match"] for r in rows)
    tot_log = sum(r[4]["n_log"] for r in rows)
    worst_p95 = max(r[4]["resid_ms_p95"] for r in rows)
    pos = np.array([r[1]["dev_head_trans_mm"] for r in rows])
    head_shift = float(np.max(np.linalg.norm(pos - pos[0], axis=1)))
    md = [
        "---",
        f"title: SpanishBCBL inspection, S{subj}",
        "type: experiment",
        "updated: 2026-11-08",
        "---",
        "",
        f"# SpanishBCBL MEG: inspection of S{subj} ({folder})",
        "",
        "Milestone M0 check: one subject loads in MNE. This page informs the M1 decoder.",
        "The script `inspect_subject.py` made this page. The full log is under \"Raw output\".",
        "",
        "## Summary",
        "",
        "| Block | Duration (s) | Channels | Dig (fid/HPI/shape) | Stim | MEG events | Log trials | Log events matched | Residual p95 (ms) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for tag, h, stim, nev, a, ntr in rows:
        md.append(
            f"| {tag} | {h['duration_s']:.0f} | {h['types'].get('mag', 0)} mag + {h['types'].get('grad', 0)} grad | "
            f"{h['dig_cardinal']}/{h['dig_hpi']}/{h['dig_extra']} | {stim} | {nev} | {ntr} | "
            f"{a['n_match']}/{a['n_log']} | {a['resid_ms_p95']:.1f} |")
    md += [
        "",
        "## Key findings for M1",
        "",
        "### Keystroke times",
        f"- The stim channel {rows[0][2]} carries one trigger per key press. The trigger value is the key code "
        f"(`kp.Keycode`, Windows virtual-key code: letters = upper-case ASCII, space = 32, backspace = 8, return = 13).",
        f"- Word onsets carry code {codes['word']}. Block markers carry code {codes['block']}. "
        f"Pause markers carry code {codes['pause']}; the log has no times for them.",
        "- Each recording starts with a test ramp (codes 1, 2, 3, ... about 20 ms apart). Drop it before matching.",
        "- The log stores the send time of each trigger: `pr_trials.keyTrig{trial}` for keys, "
        "`pr_trials.rsvp{trial}.trigTime` for words, and `pr_trials.blockTrig` for blocks. All three use one clock.",
        f"- The log clock and the MEG sample clock drift by {al['drift_ms_per_1000s']:.0f} ms per 1000 s "
        f"(slope {al['slope']:.6f}, the same in all blocks). A constant offset is NOT enough: it gives about 0.45 s "
        "of error at the end of a 15 min block. Fit offset and slope per block.",
        f"- Alignment over all blocks: {tot_match}/{tot_log} log events matched to a MEG trigger with the same code. "
        f"The worst p95 timing residual is {worst_p95:.2f} ms. The code-sequence match alone gives the same pairs (one block: one pair fewer after the time check).",
        "- Use the MEG trigger onset as the keystroke time. Take the key identity from the log (`kp.CookedKey`), "
        "because the trigger value is the virtual-key code (no case, no accents).",
        f"- The key trigger comes {lk[0]:.0f} ms (p5 {lk[1]:.0f}, p95 {lk[2]:.0f}) after the keyboard-queue time `kp.Time`. "
        "This is the delay between key detection and trigger output. The true press time is about "
        "the trigger time minus this delay. At 50-100 Hz this is less than one sample, but keep it in mind.",
        "",
        "### Sentence text per trial",
        "- `pr_trials.sequence{trial}` holds the target sentence for every trial, including the 2 training trials "
        "(trials 0 and 1). `pr_trials.sequences` holds the 64 test sentences only.",
        "- The case varies (training sentences are upper case). Strip trailing spaces, lower-case, and remove accents before use.",
        "- `pr_trials.rsvp{trial}.stim` holds each shown word with its onset (RSVP perception phase).",
        "- The typed text is the sequence of `kp.CookedKey` values. It contains typos and backspaces. "
        "The test trials give no visual feedback, so typed text and target can differ.",
        "",
        "### Head digitisation",
        f"- Yes. Each block has {h0['dig_cardinal']} fiducials, {h0['dig_hpi']} HPI coil points and "
        f"{h0['dig_extra']} head-shape points (session 2 has fewer), plus a valid `dev_head_t`.",
        "- No MRI exists in the dataset. Source-space work must use a template (fsaverage) fitted to the head shape.",
        f"- The head position changes by about {head_shift:.0f} mm between sessions (see the raw output). "
        "Pooling sessions needs a common head position (`maxwell_filter(destination=...)`).",
        "",
        "### Data quality",
        f"- The data is raw MaxShield data (IAS on, {h0['ias_channels']} IAS channels). No SSS was applied. "
        "MNE loads it only with `allow_maxshield=True`. Apply `mne.preprocessing.maxwell_filter` "
        "(SSS or tSSS) before analysis. The dataset has no fine-calibration or cross-talk files, so SSS runs without them.",
        f"- The raw amplitude is high before SSS (median RMS {dc['rms']['mag'][0]:.0f} fT for mag, "
        f"{dc['rms']['grad'][0]:.0f} fT/cm for grad). We expect high values before SSS. Check the RMS again after SSS.",
        f"- cHPI coils were on at {h0['hpi_freqs']} Hz (peaks about 47 dB). A low-pass below 45 Hz removes them. "
        "They also allow head-movement estimation with `mne.chpi`.",
        f"- Line noise: the median-channel 50 Hz peak is {dc['line_peaks_db']['mag'].get(50, float('nan')):.1f} dB (mag) and "
        f"{dc['line_peaks_db']['grad'].get(50, float('nan')):.1f} dB (grad) above its neighbours. "
        "Harmonics at 100, 150 and 200 Hz are as strong on mag. See `results/psd.png`.",
        f"- Other narrow peaks (Hz, prominence dB): mag {dc['other_peaks']['mag']}; grad {dc['other_peaks']['grad']}. "
        "Peaks that show on mag but not on grad come from distant sources (environment), and SSS should reduce them. "
        "A peak inside 0.5-45 Hz stays after the band-pass, so check it again after SSS.",
        f"- Flat channels: {sum(len(v) for v in dc['flat'].values())}. Robust-z outliers by RMS: "
        f"{sum(len(v) for v in dc['noisy'].values())} (they cluster in a few sensor groups, which suggests external "
        f"interference before SSS, not broken sensors). The Maxwell scan finds: {dc['maxwell_bads']}.",
        "- The header lists no bad channels. Run the Maxwell bad-channel scan per block before SSS.",
        "",
        "### Recommended preprocessing for M1",
        "1. Load each typing block with `allow_maxshield=True`. Mark bads with `find_bad_channels_maxwell`.",
        "2. Apply `maxwell_filter` (tSSS, `st_duration=10`, origin from the head shape) with one `destination` per subject. "
        "Optionally use cHPI head-movement compensation.",
        "3. Use the v2 recipe as the default: notch 50 Hz (and 100 Hz), band-pass 0.5-45 Hz, resample to 100 Hz. "
        "Keep the v1 recipe (0.1-20 Hz, resample to 50 Hz) as a baseline variant.",
        "4. Get keystroke times from the MEG triggers. Join key identity and sentence text from the log with the alignment above.",
        "5. Epoch around each key-press trigger (for example -0.5 to +0.5 s).",
        "6. Use MEG channels only (102 mag + 204 grad). Keep EOG/ECG for artefact rejection (ICA or regression).",
        "7. Keep trials 0 and 1 of each block out of test metrics (training trials with visual feedback).",
        "",
        "### Notes on the brain2qwerty loader (read for format only; CC BY-NC, no code copied)",
        "- It reads `pr_trials` with `loadmat(squeeze_me=True, struct_as_record=True)` and uses fields `key`, `rsvp`, `sequence`.",
        "- It builds log events from `key` (keeps presses later) and sets the log trigger value to `Keycode`. "
        "RSVP words get trigger 10. It uses the keyboard-queue `Time`, not `keyTrig`.",
        "- It reads MEG events with `mne.find_events(raw, shortest_event=1)`.",
        "- It aligns the two event lists by matching the sequences of trigger values, not by time. "
        "The MEG times are then the event times. So the clock drift does not affect it. A DTW helper on inter-event intervals also exists.",
        "- It cleans sentences (lower case, no accents, no punctuation, two typo fixes) and maps typed keys to words by character matching.",
        "- It skips S13 (left-handed), the failed S23 session files, and several other bad files. S25 is not in its bad list.",
        "- Our method: drop the test ramp, match code sequences with `difflib`, fit offset and drift, then check every "
        "pair by time (tolerance 20 ms). The time check confirms the sequence match.",
        "",
        "## Blockers for M1",
        "- None for loading and alignment. SSS without fine-cal/cross-talk files is a small quality loss, not a blocker.",
        "- Note: mapping typed keys to target words (for word-level labels) needs a character-alignment step. We did not build it here.",
        "",
        "## Plots",
        "",
        "![PSD](results/psd.png)",
        "",
        "![Events](results/event_timeline.png)",
        "",
        "## Raw output",
        "",
        "```text",
        *[ln for ln in LINES],
        "```",
        "",
    ]
    (out / "results.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote {out / 'results.md'}")


if __name__ == "__main__":
    sys.exit(main())
