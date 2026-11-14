"""Stage prep (CPU): verify + extract the T15 neural data, phonemise, split. Writes only outside the repo,
except results/prep.json (counts, no text).

Run (repo root): C:\\venvs\\fidetype-rocm\\Scripts\\python.exe -I experiments/2026-11-13-m4-01-02-lookahead/prep.py
(needs h5py; the .venv has no h5py).
"""

from __future__ import annotations

import json
import sys
import time
import zipfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t15 as T  # noqa: E402

B = T.B


def extract() -> None:
    done = T.EXTRACT / ".extracted"
    if done.exists():
        return
    arc = Path(T.CONFIG["archive"])
    assert arc.stat().st_size == T.CONFIG["archive_size"], "archive size mismatch"
    sha = T.sha256_file(arc)
    assert sha == T.CONFIG["archive_sha256"], f"archive sha256 mismatch: {sha}"
    T.EXTRACT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(arc) as zf:
        for m in zf.infolist():
            # safe extraction: no absolute paths, no '..'
            name = m.filename.replace("\\", "/")
            assert not name.startswith("/") and ".." not in name.split("/"), name
            zf.extract(m, T.EXTRACT)
    done.write_text(f"ok sha256 {sha}\n")


def read_h5(path: Path) -> list[dict]:
    import h5py

    out = []
    with h5py.File(path, "r") as f:
        keys = sorted(f.keys())
        for k in keys:
            g = f[k]
            x = np.asarray(g["input_features"][()], dtype=np.float32)
            lab = g.attrs.get("sentence_label", None)
            if isinstance(lab, bytes):
                lab = lab.decode("utf-8")
            out.append({"key": k, "X": x, "label": None if lab is None else str(lab),
                        "block": int(g.attrs.get("block_num", -1)), "trial": int(g.attrs.get("trial_num", -1))})
    return out


def main() -> None:
    t0 = time.time()
    extract()
    cmu = T.load_cmudict(T.CONFIG["cmudict"])
    T.DERIVED.mkdir(parents=True, exist_ok=True)
    roots = sorted({p.parent for p in T.EXTRACT.rglob("data_train.hdf5")})
    sess = [r.name for r in roots]
    texts: dict = {}
    summary: dict = {"sessions": [], "n_sessions": len(sess)}
    tot_chars, tot_s = 0, 0.0
    lens = []
    for s, r in zip(sess, roots):
        rec = {"session": s}
        out = {}
        tr = read_h5(r / "data_train.hdf5")
        va = read_h5(r / "data_val.hdf5") if (r / "data_val.hdf5").exists() else []
        parts = {"train": tr, "val_select": va[0::2], "val_eval": va[1::2]}
        for part, rows in parts.items():
            words = [B.normalize_words(x["label"] or "") for x in rows]
            phs = [T.phonemize(w, cmu) for w in words]
            known = [k and len(p) > 0 for p, k in phs]
            out[part] = {"X": [x["X"].astype(np.float16) for x in rows], "words": words, "ph": [p for p, _ in phs], "known": known}
            rec[f"n_{part}"] = len(rows)
            rec[f"n_{part}_oov"] = int(sum(not k for k in known))
            if part == "train":
                for x, w, k in zip(rows, words, known):
                    if k:
                        tot_chars += len(w)
                        tot_s += x["X"].shape[0] * 0.02
                lens += [x["X"].shape[0] for x in rows]
        np.savez(T.DERIVED / f"{s}.npz",
                 **{f"{p}_X{i}": x for p in out for i, x in enumerate(out[p]["X"])},
                 **{f"{p}_n": np.array(len(out[p]["X"])) for p in out},
                 **{f"{p}_ph{i}": np.array([T.PH_ID[q] for q in ph], np.int16) for p in out for i, ph in enumerate(out[p]["ph"])},
                 **{f"{p}_known": np.array(out[p]["known"], bool) for p in out})
        texts[s] = {p: out[p]["words"] for p in out}
        summary["sessions"].append(rec)
        print(s, rec, flush=True)
    (T.DERIVED / "sessions.json").write_text(json.dumps(sess), encoding="utf-8")
    (T.DERIVED / "texts.json").write_text(json.dumps(texts), encoding="utf-8")
    for p in ("train", "val_select", "val_eval"):
        summary[f"n_{p}"] = sum(x[f"n_{p}"] for x in summary["sessions"])
        summary[f"n_{p}_used"] = sum(x[f"n_{p}"] - x[f"n_{p}_oov"] for x in summary["sessions"])
    summary["speech_rate_train"] = {"chars_per_min": tot_chars / tot_s * 60, "seconds": tot_s, "chars": tot_chars}
    summary["train_bins"] = {"median": float(np.median(lens)), "p95": float(np.percentile(lens, 95)), "max": int(max(lens))}
    summary["seconds"] = round(time.time() - t0, 1)
    T.dump(summary, T.RESULTS / "prep.json")
    print(json.dumps({k: v for k, v in summary.items() if k != "sessions"}, indent=1))


if __name__ == "__main__":
    main()
