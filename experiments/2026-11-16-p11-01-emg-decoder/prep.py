r"""P11-01 data preparation: emg2qwerty HDF5 sessions -> compact feature + label cache (CPU only).

Our own code (Apache-2.0). No Meta code is read or copied. The data is CC BY-NC-SA 4.0 (research
use only). The cache is derived data: it stays local and is never committed.

Safety: the HDF5 files are untrusted downloads. We open them only through
``fidetype.adapters.emg2qwerty.Session`` (h5py, read-only, JSON logs checked field by field, no
pickles). Run with ``python -I`` from the repo root (not from the data folder).

Output (one set of files per session in ``<out>/sessions/``):
- ``<name>.feat.npy``  float16 (n_frames, 32, 12): log band power. Channels 0-15 = left band,
  16-31 = right band. Frame k covers samples [k*HOP, k*HOP + WIN); its time stamp is the end of
  the window (causal): (k*HOP + WIN) / 2000 s from the first sample.
- ``<name>.lab.npz``   key_frame (int64, the first frame whose window ends at or after key-down),
  key_tok (int16, token id, see VOCAB), prompt_lo / prompt_hi (int64 frame range of each text
  prompt), feat_sum / feat_sq (float64 (32, 12), for global normalisation statistics).
- ``<name>.done.json`` marker + counts. A session with a marker is skipped on a re-run (resume).

Commands (repo root):
  python -I experiments/2026-11-16-p11-01-emg-decoder/prep.py splits <data> <out>
  python -I experiments/2026-11-16-p11-01-emg-decoder/prep.py features <data> <out> [--workers 4] [--limit N]
  python -I experiments/2026-11-16-p11-01-emg-decoder/prep.py index <out>
  python -I experiments/2026-11-16-p11-01-emg-decoder/prep.py estimate <data>
A file ``<out>/pause`` (or ``stop``) makes ``features`` finish the current sessions and exit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

from fidetype.adapters import emg2qwerty as e2q

FS = 2000
WIN = 64  # 32 ms window
HOP = 20  # 10 ms hop -> 100 frames per s
N_CH = 32
#: rfft of 64 samples = 33 bins of 31.25 Hz. Bin 0 (DC) is dropped. Bins 1..32 are pooled into
#: 12 bands with about log spacing: edges are bin indices (lower inclusive, upper exclusive).
BAND_EDGES = (1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 33)
N_BANDS = len(BAND_EDGES) - 1
LOG_EPS = 1e-6
BLOCK_ROWS = 262_144
BYTES_PER_FRAME = N_CH * N_BANDS * 2  # float16

# --- vocabulary: blank + printable ASCII + Backspace + Enter -----------------------------------
BLANK = 0
PRINTABLE = [chr(c) for c in range(32, 127)]  # ' ' .. '~' (95 chars)
BACKSPACE = "⌫"  # ⌫ (display symbol of the Backspace key)
ENTER = "⏎"  # ⏎ (display symbol of the Enter key)
VOCAB = ["<blank>"] + PRINTABLE + [BACKSPACE, ENTER]  # 98 entries
TOK = {ch: i for i, ch in enumerate(VOCAB)}
NAMED_TOKEN = {"Key.space": TOK[" "], "Key.backspace": TOK[BACKSPACE], "Key.enter": TOK[ENTER]}

# --- splits (ours; the metadata defines none) --------------------------------------------------
SPLIT_SALT = "fidetype-p11-01-2026-11-16"
N_TEST_USERS = 8
MIN_SESSIONS_TEST_USER = 8  # 2 val + 2 test + at least 4 train sessions


def key_token(key: str) -> int | None:
    """Token id of a logged key string, or None (modifier, arrow, non-ASCII: not a target)."""
    if key in NAMED_TOKEN:
        return NAMED_TOKEN[key]
    if len(key) == 1 and key in TOK and key != "<blank>":
        return TOK[key]
    return None


def band_matrix() -> np.ndarray:
    """(33, 12) averaging matrix from rfft power bins to bands."""
    m = np.zeros((WIN // 2 + 1, N_BANDS), np.float32)
    for b in range(N_BANDS):
        lo, hi = BAND_EDGES[b], BAND_EDGES[b + 1]
        m[lo:hi, b] = 1.0 / (hi - lo)
    return m


_HANN = np.hanning(WIN).astype(np.float32)
_BANDS = band_matrix()


def n_frames(n_samples: int) -> int:
    return 0 if n_samples < WIN else (n_samples - WIN) // HOP + 1


def frames_from_block(x: np.ndarray) -> np.ndarray:
    """(m, 32) float32 samples -> (n_frames(m), 32, 12) float32 log band power."""
    nf = n_frames(len(x))
    if nf == 0:
        return np.zeros((0, N_CH, N_BANDS), np.float32)
    w = np.lib.stride_tricks.sliding_window_view(x, WIN, axis=0)[::HOP][:nf]  # (nf, 32, WIN)
    w = w - w.mean(axis=2, keepdims=True)
    spec = np.fft.rfft(w * _HANN, axis=2)  # (nf, 32, 33)
    p = (spec.real ** 2 + spec.imag ** 2).astype(np.float32)
    return np.log(p @ _BANDS + LOG_EPS)


def sample_to_frame(sample: np.ndarray) -> np.ndarray:
    """First frame whose window end (k*HOP + WIN) is at or after the sample index."""
    s = np.asarray(sample, np.int64)
    return np.maximum(0, -((WIN - s) // HOP)).astype(np.int64)  # ceil((s - WIN) / HOP), >= 0


def session_features(sess: e2q.Session, out_path: Path) -> tuple[int, np.ndarray, np.ndarray]:
    """Stream one session into ``out_path`` (.npy memmap). Returns n_frames, sum, sum of squares."""
    n = sess.n_samples
    nf = n_frames(n)
    mm = np.lib.format.open_memmap(out_path, mode="w+", dtype=np.float16, shape=(nf, N_CH, N_BANDS))
    s1 = np.zeros((N_CH, N_BANDS), np.float64)
    s2 = np.zeros((N_CH, N_BANDS), np.float64)
    k = 0
    ds = sess._ds  # read whole rows once per block (one pass over the file)
    while k < nf:
        lo = k * HOP
        k_end = min(nf, k + (BLOCK_ROWS - WIN) // HOP + 1)
        hi = (k_end - 1) * HOP + WIN
        rows = ds[lo:hi]
        x = np.concatenate([np.asarray(rows[f], np.float32) for f in e2q.BAND_FIELDS], axis=1)
        if not np.all(np.isfinite(x)):
            x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        f = frames_from_block(x)
        assert len(f) == k_end - k, (len(f), k_end - k)
        mm[k:k_end] = f.astype(np.float16)
        s1 += f.sum(axis=0, dtype=np.float64)
        s2 += np.square(f, dtype=np.float64).sum(axis=0)
        k = k_end
    mm.flush()
    del mm
    return nf, s1, s2


def session_labels(sess: e2q.Session, nf: int) -> dict[str, np.ndarray | int]:
    ev = e2q.key_events(sess)
    toks, frames, dropped = [], [], 0
    for e in ev:
        t = key_token(e.key)
        if t is None:
            dropped += 1
            continue
        toks.append(t)
        frames.append(e.sample)
    kf = sample_to_frame(np.array(frames, np.int64)) if frames else np.zeros(0, np.int64)
    keep = kf < nf
    t0 = sess.t0
    plo, phi = [], []
    for p in sess.prompts:
        a, b = sess.sample_index([p.start, p.end])
        if p.end - t0 < 0 or p.start - t0 > sess.duration_s:
            continue
        plo.append(int(sample_to_frame(np.array([a]))[0]))
        phi.append(min(nf, int(sample_to_frame(np.array([b]))[0]) + 1))
    return {
        "key_frame": kf[keep],
        "key_tok": np.array(toks, np.int16)[keep],
        "prompt_lo": np.array(plo, np.int64),
        "prompt_hi": np.array(phi, np.int64),
        "dropped_keys": dropped + int((~keep).sum()),
    }


def process_one(path: str, out_dir: str) -> dict:
    p, out = Path(path), Path(out_dir) / "sessions"
    stem = p.stem
    done = out / f"{stem}.done.json"
    if done.exists():
        return json.loads(done.read_text(encoding="utf-8"))
    t_start = time.time()
    with e2q.Session(p) as sess:
        tmp_feat = out / f"{stem}.feat.tmp.npy"
        nf, s1, s2 = session_features(sess, tmp_feat)
        lab = session_labels(sess, nf)
        tmp_lab = out / f"{stem}.lab.tmp.npz"
        np.savez(tmp_lab, key_frame=lab["key_frame"], key_tok=lab["key_tok"], prompt_lo=lab["prompt_lo"],
                 prompt_hi=lab["prompt_hi"], feat_sum=s1, feat_sq=s2)
        os.replace(tmp_feat, out / f"{stem}.feat.npy")
        os.replace(tmp_lab, out / f"{stem}.lab.npz")
        rec = {"session": stem, "user": sess.user, "n_samples": sess.n_samples, "n_frames": nf,
               "n_keys": int(len(lab["key_tok"])), "dropped_keys": int(lab["dropped_keys"]),
               "n_prompts": int(len(lab["prompt_lo"])), "seconds": round(time.time() - t_start, 1)}
    done.write_text(json.dumps(rec), encoding="utf-8")
    return rec


def _worker(args: tuple[str, str]) -> tuple[str, dict | None, str | None]:
    path, out_dir = args
    try:
        return path, process_one(path, out_dir), None
    except Exception:  # keep going; the session is logged and retried on the next run
        return path, None, traceback.format_exc(limit=5)


# --- splits --------------------------------------------------------------------------------------

def make_splits(rows: list[e2q.MetadataRow]) -> dict:
    """Our split rule (fixed before training; see plan.md, section Splits).

    Test users: among users with >= MIN_SESSIONS_TEST_USER sessions, the 8 with the smallest
    SHA-256(SPLIT_SALT + user). Per test user, sessions in name (= date) order: the last 2 are
    'test', the 2 before are 'val', the rest are 'train' (personalised). All sessions of the other
    users are 'generic_train'.
    """
    by_user: dict[str, list[str]] = {}
    for r in rows:
        by_user.setdefault(r.user, []).append(r.session)
    eligible = [u for u, s in by_user.items() if len(s) >= MIN_SESSIONS_TEST_USER]
    rank = sorted(eligible, key=lambda u: hashlib.sha256((SPLIT_SALT + u).encode()).hexdigest())
    test_users = sorted(rank[:N_TEST_USERS])
    personal = {}
    for u in test_users:
        s = sorted(by_user[u])
        personal[u] = {"train": s[:-4], "val": s[-4:-2], "test": s[-2:]}
    generic_train = sorted(s for u, ss in by_user.items() if u not in test_users for s in ss)
    return {
        "rule": "see prep.py make_splits; salt " + SPLIT_SALT,
        "test_users": test_users,
        "generic_train": generic_train,
        "generic_val": sorted(s for u in test_users for s in personal[u]["val"]),
        "generic_test": sorted(s for u in test_users for s in personal[u]["test"]),
        "personal": personal,
        "counts": {"users": len(by_user), "generic_train_users": len(by_user) - len(test_users),
                   "generic_train_sessions": len(generic_train),
                   "personal_train_sessions": sum(len(v["train"]) for v in personal.values())},
    }


# --- commands --------------------------------------------------------------------------------------

def estimate_bytes(rows: list[e2q.MetadataRow]) -> int:
    frames = sum(r.duration_mins * 60.0 * FS / HOP for r in rows)
    return int(frames * BYTES_PER_FRAME)


def cmd_estimate(a: argparse.Namespace) -> int:
    rows = e2q.read_metadata(Path(a.data) / "metadata.csv")
    b = estimate_bytes(rows)
    free = shutil.disk_usage(Path(a.out) if a.out else Path(a.data)).free
    print(json.dumps({"sessions": len(rows), "estimate_gb": round(b / 1e9, 1), "free_gb": round(free / 1e9, 1)}))
    return 0


def cmd_splits(a: argparse.Namespace) -> int:
    rows = e2q.read_metadata(Path(a.data) / "metadata.csv")
    sp = make_splits(rows)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "splits.json").write_text(json.dumps(sp, indent=1), encoding="utf-8")
    print(json.dumps(sp["counts"]))
    return 0


def _log(out: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(out / "prep.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def cmd_features(a: argparse.Namespace) -> int:
    data, out = Path(a.data), Path(a.out)
    (out / "sessions").mkdir(parents=True, exist_ok=True)
    rows = e2q.read_metadata(data / "metadata.csv")
    need = estimate_bytes(rows)
    free = shutil.disk_usage(out).free
    have = sum(f.stat().st_size for f in (out / "sessions").glob("*.feat.npy"))
    if need > a.max_gb * 1e9:
        _log(out, f"REFUSE: estimate {need / 1e9:.1f} GB > --max-gb {a.max_gb}")
        return 2
    if free - (need - have) < a.min_free_gb * 1e9:
        _log(out, f"REFUSE: free {free / 1e9:.1f} GB, still need {(need - have) / 1e9:.1f} GB, keep {a.min_free_gb} GB")
        return 2
    paths = e2q.list_sessions(data)
    if a.limit:
        paths = paths[: a.limit]
    for t in (out / "sessions").glob("*.tmp.*"):
        t.unlink()  # partial files of an interrupted run
    todo = [p for p in paths if not (out / "sessions" / f"{p.stem}.done.json").exists()]
    _log(out, f"start: {len(paths)} sessions, {len(todo)} to do, estimate {need / 1e9:.1f} GB, free {free / 1e9:.1f} GB, workers {a.workers}")
    n_ok = n_err = 0
    t0 = time.time()
    jobs = [(str(p), str(out)) for p in todo]
    if a.workers <= 1:
        it = map(_worker, jobs)
        pool = None
    else:
        import multiprocessing as mp
        pool = mp.get_context("spawn").Pool(a.workers, maxtasksperchild=8)
        it = pool.imap_unordered(_worker, jobs)
    stopped = False
    try:
        for path, rec, err in it:
            if err:
                n_err += 1
                _log(out, f"ERROR {Path(path).name}: {err.strip().splitlines()[-1]}")
            else:
                n_ok += 1
                if n_ok % 10 == 0 or n_ok == len(todo):
                    rate = n_ok / max(time.time() - t0, 1e-9)
                    _log(out, f"done {n_ok}/{len(todo)} (errors {n_err}); last {rec['session']} {rec['seconds']} s; "
                              f"ETA {(len(todo) - n_ok) / max(rate, 1e-9) / 60:.0f} min")
            if (out / "pause").exists() or (out / "stop").exists():
                stopped = True
                _log(out, "pause/stop file seen: finishing running sessions, then exit")
                break
    finally:
        if pool is not None:
            if stopped:
                pool.terminate()  # running sessions write .tmp files only; they are removed at restart
            else:
                pool.close()
            pool.join()
    _log(out, f"end: ok {n_ok}, errors {n_err}, stopped {stopped}, {(time.time() - t0) / 60:.1f} min")
    if not stopped and n_err == 0 and not a.limit:
        cmd_index(a)
        (out / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    return 0 if n_err == 0 else 1


def cmd_index(a: argparse.Namespace) -> int:
    out = Path(a.out)
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((out / "sessions").glob("*.done.json"))]
    s1 = np.zeros((N_CH, N_BANDS)); s2 = np.zeros((N_CH, N_BANDS))
    sp = json.loads((out / "splits.json").read_text(encoding="utf-8")) if (out / "splits.json").exists() else None
    train = set(sp["generic_train"]) if sp else {r["session"] for r in recs}
    n = 0
    for r in recs:
        if r["session"] in train:
            with np.load(out / "sessions" / f"{r['session']}.lab.npz", allow_pickle=False) as z:
                s1 += z["feat_sum"]; s2 += z["feat_sq"]
            n += r["n_frames"]
    mean = s1 / max(n, 1)
    std = np.sqrt(np.maximum(s2 / max(n, 1) - mean ** 2, 1e-8))
    np.savez(out / "norm_generic_train.npz", mean=mean.astype(np.float32), std=std.astype(np.float32), n_frames=n)
    idx = {"vocab": VOCAB, "fs": FS, "win": WIN, "hop": HOP, "band_edges": list(BAND_EDGES), "log_eps": LOG_EPS,
           "sessions": recs,
           "totals": {"sessions": len(recs), "frames": int(sum(r["n_frames"] for r in recs)),
                      "keys": int(sum(r["n_keys"] for r in recs)),
                      "dropped_keys": int(sum(r["dropped_keys"] for r in recs)),
                      "bytes": int(sum((out / "sessions" / f"{r['session']}.feat.npy").stat().st_size for r in recs))}}
    (out / "index.json").write_text(json.dumps(idx, indent=1), encoding="utf-8")
    print(json.dumps(idx["totals"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("estimate"); s.add_argument("data"); s.add_argument("--out", default=None)
    s = sub.add_parser("splits"); s.add_argument("data"); s.add_argument("out")
    s = sub.add_parser("features"); s.add_argument("data"); s.add_argument("out")
    s.add_argument("--workers", type=int, default=4); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--max-gb", type=float, default=150.0); s.add_argument("--min-free-gb", type=float, default=100.0)
    s = sub.add_parser("index"); s.add_argument("out")
    a = ap.parse_args(argv)
    return {"estimate": cmd_estimate, "splits": cmd_splits, "features": cmd_features, "index": cmd_index}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
