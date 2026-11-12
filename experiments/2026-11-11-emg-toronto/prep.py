"""Toronto sEMG typing: cut one EMG window per key press (CPU).

Reads all RHD recordings with our adapter (``fidetype.adapters.toronto_semg``),
filters them, and saves one window per key press to a cache outside the repo.

Per recording: high-pass 20 Hz (Butterworth, order 4, zero phase), notch
60 Hz (Q 30), low-pass 450 Hz, decimate 2 kHz -> 1 kHz. Per session: divide
each channel by its median std over the session's recordings (label-free,
so it is allowed on a test session). Window: -0.35 .. +0.35 s around the
aligned key time (700 samples). Files that the dataset marks ``Used = No``
in ``Warnings.csv`` are dropped.

Run (repo root):
    .venv\\Scripts\\python.exe -I experiments/2026-11-11-emg-toronto/prep.py
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import signal

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from fidetype.adapters import toronto_semg as T  # noqa: E402

CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
RAW = Path(CONFIG["raw_root"])
CACHE = Path(CONFIG["cache"])
FS_IN = T.SAMPLE_RATE_HZ
FS = 1000.0
W0, W1 = CONFIG["window_s"]
NW = int(round((W1 - W0) * FS))


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with open(CACHE / "prep.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def excluded_files() -> set[str]:
    out = set()
    with open(RAW / "Warnings.csv", encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("Used") or "").strip().lower() == "no":
                # Match by file stem only: the stem holds date and time, so it is
                # unique, and the participant numbers in Warnings.csv (1-20) are
                # not the folder numbers (P1-P19). In the published zip none of
                # these files is in CleanData (checked 2026-11-11).
                out.add(row["Filename"].strip())
    return out


SOS_HP = signal.butter(4, 20.0, "highpass", fs=FS_IN, output="sos")
SOS_LP = signal.butter(8, 450.0, "lowpass", fs=FS_IN, output="sos")
B_N, A_N = signal.iirnotch(60.0, 30.0, fs=FS_IN)


def clean(x: np.ndarray) -> np.ndarray:
    y = signal.sosfiltfilt(SOS_HP, x.astype(np.float64), axis=1)
    y = signal.filtfilt(B_N, A_N, y, axis=1)
    y = signal.sosfiltfilt(SOS_LP, y, axis=1)
    return y[:, ::2].astype(np.float32)


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    recs = T.list_recordings(RAW / "CleanData")
    excl = excluded_files()
    log(f"{len(recs)} recordings; {len(excl)} files marked Used=No")
    by_session: dict[tuple[str, str], list[T.RecordingInfo]] = defaultdict(list)
    for r in recs:
        by_session[(r.participant, r.session)].append(r)

    X, rows, file_rows = [], [], []
    prof_sum = np.zeros((T.N_CHANNELS, NW // 20), np.float64)
    prof_n = 0
    ikis = []
    skipped = defaultdict(int)
    for (p, s), rs in sorted(by_session.items(), key=lambda kv: (int(kv[0][0][1:]), kv[0][1])):
        sdir = RAW / "CleanData" / p / s
        keylog = T.parse_keylog(sdir / "Keylogs.txt")
        lags = T.load_lag_timings(sdir / "LAG_TIMINGS.csv")
        data = []
        for r in rs:
            if r.stem in excl:
                skipped["used_no"] += 1
                continue
            if r.stem not in lags:
                skipped["no_lag"] += 1
                continue
            try:
                rec = T.read_rhd(r.path)
            except T.RhdFormatError as e:
                skipped["rhd_error"] += 1
                log(f"skip {r.key}: {e}")
                continue
            if rec.amplifier_uv.shape[0] != T.N_CHANNELS or rec.sample_rate != FS_IN:
                skipped["format"] += 1
                continue
            data.append((r, rec, clean(rec.amplifier_uv)))
        if not data:
            continue
        scale = np.median(np.stack([d[2].std(axis=1) for d in data]), axis=0) + 1e-6
        # order of the recordings of one letter within the session (1, 2, ...)
        order = defaultdict(int)
        for r, rec, y in sorted(data, key=lambda d: d[0].start):
            order[r.letter] += 1
            lag, lag_err = lags[r.stem]
            ev = T.key_events(r, keylog, lag, rec.duration_s - rec.t0_s, margin_s=max(-W0, W1) + 0.01)
            if not ev:
                skipped["no_events"] += 1
                continue
            y = y / scale[:, None]
            letter_t = [e.t for e in ev if e.char != " "]
            ikis.extend(np.diff(letter_t).tolist())
            fi = len(file_rows)
            file_rows.append({"key": r.key, "participant": p, "session": s, "letter": r.letter,
                              "order": order[r.letter], "lag": lag, "lag_error": lag_err, "n_events": len(ev),
                              "duration_s": rec.duration_s})
            for k, e in enumerate(ev):
                i0 = int(round((e.t + W0) * FS))
                w = y[:, i0 : i0 + NW]
                if w.shape[1] != NW:
                    skipped["edge"] += 1
                    continue
                X.append(w.astype(np.float16))
                rows.append((fi, T.KEY_CHARS.index(e.char), e.t, k))
                prof_sum += np.abs(w).reshape(T.N_CHANNELS, NW // 20, 20).mean(axis=2)
                prof_n += 1
        log(f"{p}/{s}: {len(data)} files, total windows {len(X)}")
    Xa = np.stack(X)
    ra = np.array(rows, dtype=np.float64)
    prof = (prof_sum / max(prof_n, 1)).mean(axis=0)
    centers = W0 + (np.arange(NW // 20) + 0.5) * 0.02
    np.savez(CACHE / "windows.npz", X=Xa, file_idx=ra[:, 0].astype(np.int32), label=ra[:, 1].astype(np.int16),
             t=ra[:, 2], press_idx=ra[:, 3].astype(np.int16))
    info = {
        "n_windows": int(len(Xa)), "n_files": len(file_rows), "skipped": dict(skipped),
        "fs": FS, "window_s": [W0, W1], "filters": "HP 20 Hz (Butter 4, zero phase), notch 60 Hz Q30, LP 450 Hz, decimate to 1 kHz; per-session channel scale",
        "label_counts": {T.KEY_CHARS[i]: int(c) for i, c in zip(*np.unique(ra[:, 1].astype(int), return_counts=True))},
        "alignment_profile": {"centers_s": centers.round(3).tolist(), "mean_abs": prof.round(4).tolist(),
                               "peak_s": float(centers[int(np.argmax(prof))])},
        "inter_key_interval_s": {"median": float(np.median(ikis)), "mean": float(np.mean(ikis)), "n": len(ikis)},
        "seconds": round(time.time() - t0, 1),
    }
    (CACHE / "files.json").write_text(json.dumps(file_rows, indent=0), encoding="utf-8")
    (CACHE / "info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    log(f"done: {info['n_windows']} windows, {info['n_files']} files, peak {info['alignment_profile']['peak_s']} s, "
        f"IKI median {info['inter_key_interval_s']['median']:.3f} s, skipped {dict(skipped)} ({info['seconds']} s)")


if __name__ == "__main__":
    main()
