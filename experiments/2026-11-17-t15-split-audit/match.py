"""T15 split audit, step 1: map every t15_copyTask.pkl trial to its B2T '25 HDF5 trial.

Read only. The pkl (published online RNN logits, 1,718 copy-task evaluation trials) and the HDF5 neural
dataset (train / val / test per session) come from the same Dryad record (Card et al. 2024, CC0).
The pkl has no block or trial number, so a pkl trial matches an HDF5 trial on
  (session date = post-implant day + offset, normalised sentence, number of frames).
HDF5 test trials have no sentence label; they match on (date, frames) only.

M4 parts (experiments/2026-11-13-m4-01-02-lookahead/prep.py): train = HDF5 train; val_select = HDF5 val
with an even index in sorted key order; val_eval = odd index; HDF5 test is not used by any M4 decoder.

Writes per-trial rows (hashed ids, no text) to C:/Users/zhang/bci-data/derived/t15-split-audit/ and
prints counts. Usage:
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-t15-split-audit/match.py
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import h5py  # noqa: E402

from fidetype.adapters.b2t25 import PATCH_SIZE, PATCH_STRIDE, load_copytask, normalize_words  # noqa: E402
from fidetype.benchmark.prepare import b2t25_trials  # noqa: E402

PKL = Path("C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl")
H5 = Path("C:/Users/zhang/bci-data/brain-to-text-25/neural/extracted/hdf5_data_final")
OUT = Path("C:/Users/zhang/bci-data/derived/t15-split-audit")


def h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def read_h5():
    rows = []
    for sd in sorted(p for p in H5.iterdir() if p.is_dir()):
        s = sd.name
        date = datetime.date(*map(int, s[4:].split(".")))
        for fpart in ("train", "val", "test"):
            fp = sd / f"data_{fpart}.hdf5"
            if not fp.exists():
                continue
            with h5py.File(fp, "r") as f:
                for i, k in enumerate(sorted(f.keys())):
                    g = f[k]
                    lab = g.attrs.get("sentence_label", None)
                    if isinstance(lab, bytes):
                        lab = lab.decode("utf-8")
                    if fpart == "train":
                        m4 = "train"
                    elif fpart == "val":
                        m4 = "val_select" if i % 2 == 0 else "val_eval"
                    else:
                        m4 = "hdf5_test"
                    idx = i if fpart != "val" else i // 2
                    rows.append({"session": s, "date": date, "fpart": fpart, "m4": m4,
                                 "key": f"{s}|{m4}|{idx}" if m4 != "hdf5_test" else f"{s}|test|{i}",
                                 "T": int(g.attrs["n_time_steps"]),
                                 "words": None if lab is None else normalize_words(str(lab)),
                                 "block": int(g.attrs.get("block_num", -1))})
    return rows


def frames(T: int) -> int:
    return (T - PATCH_SIZE) // PATCH_STRIDE + 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    trials = load_copytask(PKL, verify=True)
    split = {t.id: t.split for t in b2t25_trials(PKL)}  # track split, 125k trials only
    h5 = read_h5()
    print("hdf5 trials", Counter(r["m4"] for r in h5))

    # day offset: majority of (date - post_implant_day) over exact sentence matches
    by_words = defaultdict(list)
    for r in h5:
        if r["words"]:
            by_words[r["words"]].append(r)
    c = Counter()
    for t in trials:
        for r in by_words.get(normalize_words(t.cue_sentence), []):
            c[(r["date"] - datetime.date(2023, 1, 1)).days - t.post_implant_day] += 1
    off, n_off = c.most_common(1)[0]
    print("day offset (days since 2023-01-01 minus post-implant day):", off, "votes", n_off, "next", c.most_common(3)[1:])

    def date_of(day: int) -> datetime.date:
        return datetime.date(2023, 1, 1) + datetime.timedelta(days=day + off)

    by_date = defaultdict(list)
    for r in h5:
        by_date[r["date"]].append(r)

    # frame relation check on unique (date, words) matches
    rel = Counter()
    for t in trials:
        cands = [r for r in by_date.get(date_of(t.post_implant_day), []) if r["words"] == normalize_words(t.cue_sentence)]
        if len(cands) == 1:
            rel[t.n_frames - frames(cands[0]["T"])] += 1
    print("pkl frames - frames(n_time_steps) on unique text matches:", rel.most_common(8))
    ok = {-17, -16, -15, -14}  # pkl frames - frames(n_time_steps) seen on unique text matches (online logits are ~16 frames shorter)

    used = set()
    out = []
    stats = Counter()
    for t in trials:
        tid = f"t15-copytask-{t.index:04d}"
        sp = split.get(tid, "not-125k")
        d = date_of(t.post_implant_day)
        w = normalize_words(t.cue_sentence)
        day_rows = by_date.get(d, [])
        text_c = [r for r in day_rows if r["words"] == w]
        exact = [r for r in text_c if (t.n_frames - frames(r["T"])) in ok]
        test_c = [r for r in day_rows if r["words"] is None and (t.n_frames - frames(r["T"])) in ok]
        if len(exact) == 1:
            r, how = exact[0], "text+frames"
        elif len(exact) > 1:
            r, how = None, "ambiguous-text+frames"
        elif text_c and not test_c:
            r, how = (text_c[0], "text-only") if len(text_c) == 1 else (None, "ambiguous-text-only")
        elif len(test_c) == 1 and not text_c:
            r, how = test_c[0], "frames-only(hdf5_test)"
        elif test_c:
            r, how = None, "ambiguous-frames(hdf5_test)"
        else:
            r, how = None, "no-match"
        if r is not None:
            if r["key"] in used:
                stats["reused_hdf5_trial"] += 1
            used.add(r["key"])
        out.append({"pkl_id_hash": h(tid), "pkl_index": t.index, "track_split": sp, "day": t.post_implant_day,
                    "session": d.strftime("t15.%Y.%m.%d"), "how": how,
                    "m4_part": r["m4"] if r else None, "hdf5_key_hash": h(r["key"]) if r else None,
                    "hdf5_key": r["key"] if r else None,
                    "n_text_candidates_any_part": len(text_c),
                    "text_candidate_parts": sorted({x["m4"] for x in text_c})})
        stats[how] += 1
    print("match quality:", dict(stats))

    tab = Counter((o["track_split"], o["m4_part"] or "unmatched") for o in out)
    print("track split x M4 part:")
    for k in sorted(tab, key=str):
        print("  ", k, tab[k])
    # text-level: a test trial whose sentence occurs in M4 train on any day
    train_words = {r["words"] for r in h5 if r["m4"] == "train" and r["words"]}
    sel_words = {r["words"] for r in h5 if r["m4"] == "val_select" and r["words"]}
    ev_words = {r["words"] for r in h5 if r["m4"] == "val_eval" and r["words"]}
    txt = Counter()
    for t in trials:
        sp = split.get(f"t15-copytask-{t.index:04d}", "not-125k")
        w = normalize_words(t.cue_sentence)
        txt[(sp, "sentence_in_m4_train_any_day")] += w in train_words
    print("text overlap:", dict(txt))
    # HDF5 internal: val_eval sentences that also occur in train
    ve = [r for r in h5 if r["m4"] == "val_eval"]
    vs = [r for r in h5 if r["m4"] == "val_select"]
    internal = {"val_eval_n": len(ve), "val_eval_sentence_in_train": sum(r["words"] in train_words for r in ve),
                "val_select_n": len(vs), "val_select_sentence_in_train": sum(r["words"] in train_words for r in vs),
                "val_eval_sentence_in_val_select": sum(r["words"] in sel_words for r in ve)}
    print("hdf5 internal text overlap:", internal)

    summary = {"day_offset": off, "frame_relation": dict(rel.most_common(8)), "match_quality": dict(stats),
               "split_x_part": {f"{a}|{b}": n for (a, b), n in sorted(tab.items(), key=str)},
               "text_overlap": {f"{a}|{b}": n for (a, b), n in txt.items()}, "hdf5_internal": internal,
               "hdf5_counts": dict(Counter(r["m4"] for r in h5))}
    (OUT / "match.json").write_text(json.dumps(out, indent=0, default=str), encoding="utf-8")
    (OUT / "match-summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
