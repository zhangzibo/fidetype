"""T15 split audit, step 2: trial-id intersections for each committed T15 result family.

Needs match.py output (derived/t15-split-audit/match.json). Read only on every input. Writes
derived/t15-split-audit/audit.json (counts only) and prints it. Repo copy: results/audit-counts.json
(counts only, no text, no plain trial ids).

  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-t15-split-audit/audit.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import h5py  # noqa: E402
import numpy as np  # noqa: E402

from fidetype.benchmark.hallucination import trial_hash  # noqa: E402
from fidetype.benchmark.tracks import id_hash  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OUT = DER / "t15-split-audit"
H5 = Path("C:/Users/zhang/bci-data/brain-to-text-25/neural/extracted/hdf5_data_final")
PKL = Path("C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl")


def h5_index():
    """(session, part, idx) -> (session, block, trial_num); part in train / val_select / val_eval / test."""
    idx = {}
    for sd in sorted(p for p in H5.iterdir() if p.is_dir()):
        for fpart in ("train", "val", "test"):
            fp = sd / f"data_{fpart}.hdf5"
            if not fp.exists():
                continue
            with h5py.File(fp, "r") as f:
                for i, k in enumerate(sorted(f.keys())):
                    a = f[k].attrs
                    bt = (sd.name, int(a["block_num"]), int(a["trial_num"]))
                    if fpart == "val":
                        idx[(sd.name, "val_select" if i % 2 == 0 else "val_eval", i // 2)] = bt
                    else:
                        idx[(sd.name, fpart, i)] = bt
    return idx


def npz_keys(path: Path):
    if not path.exists():
        return None
    with np.load(path) as z:
        return [k for k in z.files]


def main() -> None:
    res: dict = {}
    match = json.loads((OUT / "match.json").read_text(encoding="utf-8"))
    by_index = {m["pkl_index"]: m for m in match}

    # 1. HDF5 partitions: is any (session, block, trial_num) in two partitions?
    idx = h5_index()
    parts_of = defaultdict(set)
    for (s, p, i), bt in idx.items():
        parts_of[bt].add(p)
    res["hdf5_trials"] = dict(Counter(p for (_, p, _) in idx))
    res["hdf5_block_trial_in_two_parts"] = sum(len(v) > 1 for v in parts_of.values())
    train_bt = {bt for (s, p, i), bt in idx.items() if p == "train"}
    sel_bt = {bt for (s, p, i), bt in idx.items() if p == "val_select"}

    # derived npz parts (what the M4 decoders actually loaded)
    sessions = json.loads((DER / "m4-01-02-lookahead" / "sessions.json").read_text(encoding="utf-8"))
    dn = Counter()
    known = Counter()
    for s in sessions:
        with np.load(DER / "m4-01-02-lookahead" / f"{s}.npz") as z:
            for p in ("train", "val_select", "val_eval"):
                if f"{p}_n" in z:
                    dn[p] += int(z[f"{p}_n"])
                    known[p] += int(np.asarray(z[f"{p}_known"]).sum())
    res["derived_npz_parts"] = {"n": dict(dn), "known_used": dict(known)}

    # 2. decoder output files: which parts do their keys come from; do they hit a train trial?
    files = {
        "m4-12-fixed0 val_eval (M4-12, P14-03, P14-05, P15-05/06/07, P5-02, P15-04, P5-11, demo)":
            DER / "m4-01-02-lookahead" / "logprobs-m4-12-fixed0.npz",
        "m4-01-la-fixed0 val_eval (M4-01/02)": DER / "m4-01-02-lookahead" / "logprobs-m4-01-la-fixed0.npz",
        "m2-19 m4-12-fixed0 val_select+val_eval (M2-19 fit; calibration set of the M4-12 guards)":
            DER / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz",
        "m4-13 val_eval (M4-13 queue)": DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz",
        "m4-13 val_select (trust-reruns CPU decode)": DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz",
    }
    fo = {}
    for name, p in files.items():
        keys = npz_keys(p)
        if keys is None:
            fo[name] = "file not present yet"
            continue
        c = Counter()
        hit_train = hit_sel = 0
        for k in keys:
            s, part, i = k.split("|")[:3]
            c[part] += 1
            bt = idx.get((s, part, int(i)))
            hit_train += bt in train_bt
            hit_sel += part != "val_select" and bt in sel_bt
        fo[name] = {"keys_by_part": dict(c), "keys_on_a_train_trial": hit_train,
                    "non_val_select_keys_on_a_val_select_trial": hit_sel}
    res["decoder_outputs"] = fo

    # 3. b2t25-t15 track: our split equals the committed v0.1 / v0.2 split files
    v01 = json.loads((REPO / "src/fidetype/benchmark/splits/v0.1/b2t25-t15-copytask.json").read_text(encoding="utf-8"))
    v01_split = {e["id"]: e["split"] for e in v01["scored"]}
    ours = {f"t15-copytask-{m['pkl_index']:04d}": m["track_split"] for m in match if m["track_split"] != "not-125k"}
    res["track_split_equals_v01_file"] = ours == v01_split
    v02 = json.loads((REPO / "src/fidetype/benchmark/splits/tracks-v0.2/b2t25-t15.json").read_text(encoding="utf-8"))
    v02_h = {e["h"]: e.get("s") or e.get("split") for e in v02["entries"]}
    res["track_v02_hashes_match_ours"] = sum(id_hash("b2t25-t15", k) in v02_h for k in ours) == len(ours) == len(v02_h)

    # 4. track split x M4 part (strict match) + upper bound for unmatched trials
    tab = Counter()
    upper = Counter()
    for m in match:
        sp = m["track_split"]
        part = m["m4_part"] or "unmatched"
        tab[(sp, part)] += 1
        if m["m4_part"] is None:
            for p in m["text_candidate_parts"]:
                upper[(sp, p)] += 1
    res["track_x_m4_strict"] = {f"{a}|{b}": n for (a, b), n in sorted(tab.items())}
    res["unmatched_with_same_day_same_sentence_in_part"] = {f"{a}|{b}": n for (a, b), n in sorted(upper.items())}

    # 5. P6-08 partial entry (M4-12 + guard): scored units -> M4 part
    h2pkl = {id_hash("b2t25-t15", f"t15-copytask-{m['pkl_index']:04d}"): m["pkl_index"] for m in match}
    sub = DER / "p6-02b-v02-entries" / "submissions" / "b2t25-t15__m4-12__guard" / "units.jsonl"
    units = []
    with sub.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "unit" in r:
                units.append(r["unit"])
    pc = Counter((by_index[h2pkl[u]]["track_split"], by_index[h2pkl[u]]["m4_part"] or "unmatched") for u in units)
    res["p6_08_partial_scored_units"] = {"n": len(units), "track_split|m4_part": {f"{a}|{b}": n for (a, b), n in pc.items()}}
    # calibration of that entry: val_select minus every val_select trial with (day, sentence) of a test trial;
    # check: strict-matched val_select<->test trials all removed?
    texts = json.loads((DER / "m4-01-02-lookahead" / "texts.json").read_text(encoding="utf-8"))
    import datetime
    from fidetype.adapters.b2t25 import normalize_words as norm
    off = json.loads((OUT / "match-summary.json").read_text(encoding="utf-8"))["day_offset"]
    truth_rows = [m for m in match if m["track_split"] == "test"]
    test_keys = {(m["session"],) for m in truth_rows}
    # (session, normalised words) of test trials, from the truth texts via texts.json is not possible; use
    # match rows: a val_select key is removed if some test trial has the same session and the same words.
    removed, kept = set(), set()
    test_words_by_session = defaultdict(set)
    from fidetype.adapters.b2t25 import load_copytask
    trials = {t.index: t for t in load_copytask(PKL, verify=True)}
    for m in truth_rows:
        test_words_by_session[m["session"]].add(norm(trials[m["pkl_index"]].cue_sentence))
    for s in sessions:
        for i, w in enumerate(texts[s].get("val_select", [])):
            (removed if norm(w) in test_words_by_session.get(s, set()) else kept).add(f"{s}|val_select|{i}")
    strict_sel = {m["hdf5_key"] for m in truth_rows if m["m4_part"] == "val_select"}
    res["p6_08_guard_calibration"] = {"val_select_removed": len(removed), "val_select_kept": len(kept),
                                      "strict_matched_test_trials_left_in_calibration": len(strict_sel & kept)}
    del test_keys, off, datetime

    # 6. word decoder tune set (b2t25-trust stage tune: 400 fit trials, rng seed 0; published logits) and
    #    the frozen split-A trust config (all 812 cal trials) -> M4 part
    fit = sorted((m for m in match if m["track_split"] == "cal"), key=lambda m: m["pkl_index"])
    # stage tune draws indices into the fit list in day order, file order inside the day
    by_day = defaultdict(list)
    for m in sorted(match, key=lambda m: m["pkl_index"]):
        if m["track_split"] != "not-125k":
            by_day[m["day"]].append(m)
    fit = []
    for d in sorted(by_day):
        ts = by_day[d]
        fit += ts[: len(ts) // 2]
    rng = np.random.default_rng(0)
    sub_i = sorted(rng.choice(len(fit), min(400, len(fit)), replace=False))
    res["word_decoder_tune_400"] = dict(Counter(fit[i]["m4_part"] or "unmatched" for i in sub_i))
    res["track_cal_812_frozen_splitA"] = dict(Counter(m["m4_part"] or "unmatched" for m in fit))

    # 7. halluc-v0.1 T15 split: are its trial hashes the val_eval keys?
    hs = json.loads((REPO / "src/fidetype/benchmark/splits/halluc-v0.1/b2t25-t15-val-eval.json").read_text(encoding="utf-8"))
    hh = {t["h"] for t in hs["trials"]}
    # the split rule writes "<session>|val|<i>" with i = index inside the session's val_eval list
    ids = {"val_eval": set(), "val_select": set(), "train": set()}
    for (s, p, i) in idx:
        if p in ids:
            ids[p].add(trial_hash(hs["dataset"], f"{s}|val|{i}" if p != "train" else f"{s}|train|{i}"))
    res["halluc_t15_split"] = {"n": len(hh), "equal_to_val_eval_ids": len(hh & ids["val_eval"]),
                               "note": "val_select ids use the same pattern, so only the val_eval match is meaningful"}

    # 8. Paper 1 re-splits: word-decoder tune trials (positions in fit + test) inside each re-split test set
    rs = {}
    for name, sp in (("r3_50", REPO / "experiments/2026-11-12-paper1-r3-analyses/repeated-splits/results/splits-b2t.json"),
                     ("r4_200", Path("C:/Users/zhang/bci-data/cache/paper1-r4/splits-b2t-200.json"))):
        if not sp.exists():
            rs[name] = "split file not present"
            continue
        d = json.loads(sp.read_text(encoding="utf-8"))
        tune_pos = set(int(i) for i in sub_i)  # fit list positions = positions in fit + test
        ov = [len(tune_pos & set(x["test"])) for x in d["splits"]]
        rs[name] = {"splits": len(ov), "test_size": len(d["splits"][0]["test"]), "tune_in_test_min": min(ov),
                    "tune_in_test_median": float(np.median(ov)), "tune_in_test_max": max(ov)}
    res["paper1_resplits_tune_in_test"] = rs

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "audit-counts.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "results" / "match-summary.json").write_text(
        (OUT / "match-summary.json").read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
