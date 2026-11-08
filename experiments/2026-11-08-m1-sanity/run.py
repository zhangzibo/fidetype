"""M1 sanity check: is there linear keystroke signal in the SpanishBCBL cache?

Replicates the Brain2Qwerty v1 Fig. 2 linear analysis on our cache:
- time-resolved ridge classifier (306 channels, one time sample), hand (L/R) and letter;
- one window classifier (-0.2..+0.3 s, 50 ms bins);
- controls: (a) permuted labels, (b) random non-key times with shuffled real labels;
- evoked GFP (mag, grad) of the keystroke average.

Usage (repo root):
    C:\\Venvs\\fidetype-rocm\\Scripts\\python.exe experiments/2026-11-08-m1-sanity/run.py
    ... run.py --raw-check      # extra: compare cache vs raw .fif (S25 ses1 block1, first 300 s)
Read only on the cache. One process, numpy only (no sklearn), RAM < ~2 GB.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")

import argparse
import json
import time
from pathlib import Path

import numpy as np

from fidetype.data.preprocess import load_cached_block

CACHE = Path(r"C:\Users\zhang\bci-data\cache\spanishbcbl\v1")
RAW_ROOT = Path(r"C:\Users\zhang\bci-data\SpanishBCBL")
OUT = Path(__file__).resolve().parent / "results"
SF = 100.0
PRE, POST = 50, 50  # samples: -0.5 .. +0.5 s at 100 Hz
TIMES = np.arange(-PRE, POST + 1) / SF
WIN = (-0.2, 0.3)
BIN = 5  # 50 ms bins for the window classifier
LEFT = set("qwertasdfgzxcvb")  # B is typed with the left index finger
RIGHT = set("yuiophjklnm")  # n/m; Spanish n-tilde is normalised to n
ALPHAS = np.logspace(-1, 5, 13)
N_FOLDS = 5
SEED = 0


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def cached_blocks() -> dict[str, list[Path]]:
    idx = json.loads((CACHE / "_index.json").read_text(encoding="utf-8"))
    subs: dict[str, list[Path]] = {}
    for b in idx["blocks"]:
        p = CACHE / b["npz"]
        if p.exists() and p.with_suffix(".json").exists():
            subs.setdefault(b["subject"], []).append(p)
    return subs


def subject_epochs(paths: list[Path], rng: np.random.Generator) -> dict:
    """Letter-key epochs [n, 306, 101] float16 plus random non-key epochs."""
    eps, chars, groups, rnd = [], [], [], []
    ch_types = None
    for bi, p in enumerate(paths):
        blk = load_cached_block(p)
        ch_types = np.array(blk.ch_types)
        assert blk.sfreq == SF, blk.sfreq
        T = blk.data.shape[1]
        all_keys = []
        for seg in blk.sidecar["segments"]:
            st = seg["start_sample"]
            for ks, ch in zip(seg["key_samples"], seg["key_chars"]):
                a = st + ks
                all_keys.append(a)
                if len(ch) == 1 and "a" <= ch <= "z" and a - PRE >= 0 and a + POST < T:
                    eps.append(blk.data[:, a - PRE : a + POST + 1])
                    chars.append(ch)
                    groups.append(bi * 1000 + seg["trial_idx"])
        # Random centres >= 0.25 s from any key press (any key, any trial).
        keys = np.sort(np.array(all_keys))
        n_want = sum(1 for g in groups if g // 1000 == bi)
        cand = rng.integers(PRE, T - POST - 1, size=n_want * 20)
        pos = np.searchsorted(keys, cand)
        d_lo = np.abs(cand - keys[np.clip(pos - 1, 0, len(keys) - 1)])
        d_hi = np.abs(keys[np.clip(pos, 0, len(keys) - 1)] - cand)
        ok = cand[np.minimum(d_lo, d_hi) >= 25]
        ok = rng.permutation(ok)[:n_want]
        rnd.extend(blk.data[:, c - PRE : c + POST + 1] for c in ok)
        del blk
    X = np.stack(eps).astype(np.float16)
    R = np.stack(rnd).astype(np.float16)
    return {"X": X, "R": R, "chars": np.array(chars), "groups": np.array(groups), "ch_types": ch_types}


# ---------------------------------------------------------------------------
# Ridge classifier (numpy), alpha by efficient leave-one-out (as sklearn RidgeClassifierCV)
# ---------------------------------------------------------------------------


def ridge_fit(X: np.ndarray, Y: np.ndarray):
    """X [n, p] z-scored, Y [n, k] in {-1, +1}. Returns (W [p, k], b [k], alpha)."""
    ym = Y.mean(0)
    Yc = Y - ym
    U, s, Vt = np.linalg.svd(X, full_matrices=False)
    UtY = U.T @ Yc
    s2 = s**2
    best = None
    for a in ALPHAS:
        f = s2 / (s2 + a)
        H = (U**2) @ f  # diag of hat matrix
        resid = Yc - U @ (f[:, None] * UtY)
        loo = ((resid / (1 - H)[:, None]) ** 2).mean()
        if best is None or loo < best[0]:
            best = (loo, a)
    a = best[1]
    W = Vt.T @ ((s / (s2 + a))[:, None] * UtY)
    return W, ym, a


def code_targets(y: np.ndarray, classes: np.ndarray) -> np.ndarray:
    if len(classes) == 2:
        return np.where(y == classes[1], 1.0, -1.0)[:, None]
    Y = -np.ones((len(y), len(classes)))
    Y[np.arange(len(y)), np.searchsorted(classes, y)] = 1.0
    return Y


def predict(Xte: np.ndarray, W, b, classes):
    S = Xte @ W + b
    if len(classes) == 2:
        return classes[(S[:, 0] > 0).astype(int)]
    return classes[S.argmax(1)]


def group_folds(groups: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    ug = rng.permutation(np.unique(groups))
    fold_of = {g: i % N_FOLDS for i, g in enumerate(ug)}
    return np.array([fold_of[g] for g in groups])


def cv_accuracy(feat_fn, n: int, y: np.ndarray, folds: np.ndarray) -> float:
    """feat_fn(idx) -> features [len(idx), p] float64. Fold-wise z-score then ridge."""
    classes = np.unique(y)
    correct = 0
    for k in range(N_FOLDS):
        tr, te = np.where(folds != k)[0], np.where(folds == k)[0]
        Xtr, Xte = feat_fn(tr), feat_fn(te)
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
        Xtr = (Xtr - mu) / sd
        Xte = (Xte - mu) / sd
        W, b, _ = ridge_fit(Xtr, code_targets(y[tr], classes))
        correct += int((predict(Xte, W, b, classes) == y[te]).sum())
    return correct / n


def decode(E: np.ndarray, y: np.ndarray, folds: np.ndarray) -> dict:
    """Time-resolved curve and window accuracy for epochs E [n, 306, 101]."""
    n = len(y)
    curve = []
    for t in range(E.shape[2]):
        curve.append(cv_accuracy(lambda idx, t=t: E[idx, :, t].astype(np.float64), n, y, folds))
    i0, i1 = int(round((WIN[0] + 0.5) * SF)), int(round((WIN[1] + 0.5) * SF))
    nb = (i1 - i0) // BIN

    def win_feat(idx):
        w = E[idx, :, i0 : i0 + nb * BIN].astype(np.float32)
        return w.reshape(len(idx), w.shape[1], nb, BIN).mean(3).reshape(len(idx), -1).astype(np.float64)

    win = cv_accuracy(win_feat, n, y, folds)
    curve = np.array(curve)
    ip = int(curve.argmax())
    vals, cnt = np.unique(y, return_counts=True)
    return {
        "curve": curve.tolist(),
        "peak": float(curve[ip]),
        "peak_ms": float(TIMES[ip] * 1000),
        "pre_mean": float(curve[TIMES < -0.3].mean()),  # baseline level, -0.5..-0.3 s
        "window": float(win),
        "chance": float(cnt.max() / n),
        "n": int(n),
        "n_classes": int(len(vals)),
    }


# ---------------------------------------------------------------------------
# Evoked
# ---------------------------------------------------------------------------


def gfp(E: np.ndarray, ch_types: np.ndarray) -> dict:
    ev = E.astype(np.float32).mean(0)  # [306, 101]
    return {t: np.sqrt((ev[ch_types == t] ** 2).mean(0)).tolist() for t in ("mag", "grad")}


def raw_check() -> dict:
    """Cache vs raw .fif (no tSSS) for S25 ses1 block1, first 300 s: evoked GFP and hand decoding."""
    import mne

    mne.set_log_level("ERROR")
    p = CACHE / "S25" / "ses1_block1.npz"
    blk = load_cached_block(p)
    side = blk.sidecar
    raw = mne.io.read_raw_fif(RAW_ROOT / side["source"]["fif"], allow_maxshield=True, preload=False)
    raw.pick("meg").crop(0, 300.0).load_data()
    raw.notch_filter([50, 100]).filter(0.5, 45.0).resample(SF)
    rd = raw.get_data()
    ct = np.array(raw.get_channel_types())
    out = {}
    for name, D in (("cache", blk.data), ("raw", rd)):
        eps, chars = [], []
        for seg in side["segments"]:
            for ks, ch in zip(seg["key_samples"], seg["key_chars"]):
                a = seg["start_sample"] + ks
                if len(ch) == 1 and "a" <= ch <= "z" and a - PRE >= 0 and a + POST < rd.shape[1]:
                    eps.append(D[:, a - PRE : a + POST + 1].astype(np.float32))
                    chars.append(ch)
        E = np.stack(eps)
        if name == "raw":  # per-channel scale so mag and grad are comparable
            E = E / (np.median(np.abs(rd), axis=1)[None, :, None] + 1e-20)
        g = gfp(E, ct if name == "raw" else np.array(blk.ch_types))
        out[name] = {"gfp": g, "n": len(E)}
        # Optional "lag" scan: correlation of the evoked mag GFP peak time
        out[name]["gfp_peak_ms"] = {t: float(TIMES[int(np.argmax(v))] * 1000) for t, v in g.items()}
    # Channel-wise correlation of cache vs raw over the first 300 s (tSSS changes the signal, so < 1).
    names = list(raw.ch_names)
    idx = [blk.ch_names.index(c) for c in names]
    Tm = min(rd.shape[1], blk.data.shape[1])
    cc = [np.corrcoef(rd[i, :Tm], blk.data[j, :Tm].astype(np.float64))[0, 1] for i, j in enumerate(idx)]
    # Lag search on the mean over channels of xcorr (+-50 samples) to detect any time shift.
    lags = np.arange(-20, 21)
    sub = np.arange(0, 306, 6)
    xc = []
    for L in lags:
        a = rd[:, 1000 + L : Tm - 1000 + L][sub]
        b = blk.data[:, 1000 : Tm - 1000][[idx[i] for i in sub]].astype(np.float64)
        a = (a - a.mean(1, keepdims=True)) / a.std(1, keepdims=True)
        b = (b - b.mean(1, keepdims=True)) / b.std(1, keepdims=True)
        xc.append(float((a * b).mean()))
    out["chan_corr_median"] = float(np.median(cc))
    out["chan_corr_by_type"] = {t: float(np.median(np.array(cc)[ct == t])) for t in ("mag", "grad")}
    out["best_lag_samples"] = int(lags[int(np.argmax(xc))])
    out["xcorr"] = dict(zip(lags.tolist(), xc))
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", default=None)
    ap.add_argument("--raw-check", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.raw_check:
        res = raw_check()
        (OUT / "raw_check.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in res.items() if k != "xcorr"}, indent=1)[:3000])
        return
    subs = cached_blocks()
    if args.subjects:
        subs = {s: subs[s] for s in args.subjects.split(",")}
    res_path = OUT / "decoding.json"
    allres = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else {}
    for subj, paths in sorted(subs.items()):
        t0 = time.time()
        rng = np.random.default_rng(SEED)
        d = subject_epochs(paths, rng)
        X, R, chars, groups = d["X"], d["R"], d["chars"], d["groups"]
        hand = np.array(["L" if c in LEFT else "R" for c in chars])
        folds = group_folds(groups, rng)
        r = {"blocks": [p.parent.name + "/" + p.stem for p in paths], "n_keys": int(len(chars)),
             "n_trials": int(len(np.unique(groups))), "n_random": int(len(R))}
        r["evoked"] = gfp(X, d["ch_types"])
        r["evoked_random"] = gfp(R, d["ch_types"])
        r["hand"] = decode(X, hand, folds)
        r["char"] = decode(X, chars, folds)
        r["hand_perm"] = decode(X, rng.permutation(hand), folds)
        r["char_perm"] = decode(X, rng.permutation(chars), folds)
        nR = len(R)
        perm = rng.permutation(len(hand))[:nR]
        rf = group_folds(groups[perm], rng)
        r["hand_random"] = decode(R, hand[perm], rf)
        r["char_random"] = decode(R, chars[perm], rf)
        r["time_s"] = round(time.time() - t0, 1)
        allres[subj] = r
        res_path.write_text(json.dumps(allres), encoding="utf-8")
        print(f"{subj}: n={len(chars)} hand peak {r['hand']['peak']:.3f}@{r['hand']['peak_ms']:.0f}ms "
              f"(chance {r['hand']['chance']:.3f}, win {r['hand']['window']:.3f}) | char peak {r['char']['peak']:.3f} "
              f"(chance {r['char']['chance']:.3f}, win {r['char']['window']:.3f}) | perm {r['hand_perm']['peak']:.3f} "
              f"rand {r['hand_random']['peak']:.3f} | {r['time_s']}s", flush=True)
        del d, X, R


if __name__ == "__main__":
    main()
