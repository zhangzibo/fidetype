"""Stage prep (CPU) for M3-28 (v2): extract, normalise (causal rolling window), phonemise, split. Writes only outside the repo,
except results/prep.json (counts, no text).

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-13-confirmatory-t12-v2/prep.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t12 as T  # noqa: E402

B = T.B


def extract() -> None:
    done = T.EXTRACT / ".extracted"
    if done.exists():
        return
    arc = Path(T.CONFIG["archive"])
    h = hashlib.md5()
    with open(arc, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    assert h.hexdigest() == T.CONFIG["archive_md5"], "archive md5 mismatch"
    T.EXTRACT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(arc, "r:gz") as tf:
        tf.extractall(T.EXTRACT, filter="data")
    done.write_text("ok\n")


def main() -> None:
    t0 = time.time()
    extract()
    cmu = T.load_cmudict(T.CONFIG["cmudict"])
    T.DERIVED.mkdir(parents=True, exist_ok=True)
    tr_files = {T.session_name(p): p for p in T.session_files("train")}
    te_files = {T.session_name(p): p for p in T.session_files("test")}
    sessions = sorted(set(tr_files) & set(te_files))  # names t12.YYYY.MM.DD sort by date
    N = len(sessions)
    a, c = int(round(N / 3)), int(round(N / 4))
    role = {s: ("fit_a" if i < a else "calibration" if i < a + c else "test") for i, s in enumerate(sessions)}
    texts: dict = {}
    summary: dict = {"sessions": [], "N": N, "n_fit_a_sessions": a, "n_cal_sessions": c, "n_test_sessions": N - a - c}
    tot_chars, tot_s = 0, 0.0
    for si, s in enumerate(sessions):
        tr = T.load_session(tr_files[s])
        te = T.load_session(te_files[s])
        blocks = sorted(set(tr["blocks"].tolist()))
        val_block = blocks[-1]
        is_val = tr["blocks"] == val_block
        assert np.all(np.diff(tr["blocks"]) >= 0), "train trials not in block order"
        assert te["blocks"].min() > tr["blocks"].max(), "test block is not after the train blocks"
        # Causal rolling normalisation (v2): session time order = train-file trials (file order),
        # then the test-block trials. Each trial is z-scored with the mean / SD over all bins of
        # the W previous trials. The first W trials (first train block, decoder-train data only)
        # use the stats of those same W trials.
        W = int(T.CONFIG["normalisation"]["window_trials"])
        CLIP = float(T.CONFIG["normalisation"]["clip_abs_z"])
        seq = list(tr["features"]) + list(te["features"])
        Z = []
        sums = [(x.astype(np.float64).sum(0), (x.astype(np.float64) ** 2).sum(0), x.shape[0]) for x in seq]
        def stats(lo, hi):
            s1 = sum(sums[k][0] for k in range(lo, hi)); s2 = sum(sums[k][1] for k in range(lo, hi))
            n = sum(sums[k][2] for k in range(lo, hi))
            mu = s1 / n
            sd = np.sqrt(np.maximum(s2 / n - mu ** 2, 0.0))
            sd[sd < 1e-6] = 1.0
            return mu, sd
        first = stats(0, W)
        for j, x in enumerate(seq):
            mu, sd = first if j < W else stats(j - W, j)
            # clip: a channel that was almost silent in the window gives huge z-scores (float16 overflow -> NaN loss)
            Z.append(np.clip((x - mu) / sd, -CLIP, CLIP).astype(np.float16))
        n_tr = len(tr["features"])
        trZ, teZ = Z[:n_tr], Z[n_tr:]
        assert not is_val[:W].any(), "first window must be decoder-train data"
        rec = {"session": s, "index": si, "role": role[s], "n_train_blocks": len(blocks)}
        out = {}
        for part, d, Zs, mask in (("train", tr, trZ, ~is_val), ("val", tr, trZ, is_val),
                                  ("pool", te, teZ, np.ones(len(te["texts"]), bool))):
            idx = np.where(mask)[0]
            X = [Zs[i] for i in idx]
            words = [B.normalize_words(d["texts"][i]) for i in idx]
            phs = [T.phonemize(w, cmu) for w in words]
            out[part] = {"X": X, "words": words, "ph": [p for p, _ in phs], "known": [k for _, k in phs]}
            rec[f"n_{part}"] = len(idx)
            rec[f"n_{part}_oov"] = int(sum(not k for _, k in phs))
            if part == "train":
                tot_chars += sum(len(w) for w in words)
                tot_s += sum(x.shape[0] for x in X) * 0.02
        np.savez(T.DERIVED / f"{s}.npz",
                 **{f"{p}_X{i}": x for p in out for i, x in enumerate(out[p]["X"])},
                 **{f"{p}_n": np.array(len(out[p]["X"])) for p in out},
                 **{f"{p}_ph{i}": np.array([T.PH_ID[q] for q in ph], np.int16) for p in out for i, ph in enumerate(out[p]["ph"])},
                 **{f"{p}_known": np.array(out[p]["known"], bool) for p in out})
        texts[s] = {p: out[p]["words"] for p in out}
        summary["sessions"].append(rec)
        print(s, rec, flush=True)
    (T.DERIVED / "texts.json").write_text(json.dumps(texts), encoding="utf-8")
    summary["speech_rate_decoder_train"] = {"chars_per_min": tot_chars / tot_s * 60, "seconds": tot_s, "chars": tot_chars}
    for r in ("fit_a", "calibration", "test"):
        summary[f"n_pool_{r}"] = sum(x["n_pool"] for x in summary["sessions"] if x["role"] == r)
    summary["n_decoder_train"] = sum(x["n_train"] for x in summary["sessions"])
    summary["n_decoder_val"] = sum(x["n_val"] for x in summary["sessions"])
    summary["seconds"] = round(time.time() - t0, 1)
    T.dump(summary, T.RESULTS / "prep.json")
    print(json.dumps({k: v for k, v in summary.items() if k != "sessions"}, indent=1))


if __name__ == "__main__":
    main()
