"""P6-10 (gap 33), step 1: build the hash-only map B2T '25 HDF5 trial -> b2t25-t15 test unit.

Read only on the data. Same match rule as the T15 split audit
(experiments/2026-11-17-t15-split-audit/match.py): a pkl trial matches an HDF5 trial on
(session date = post-implant day + 197 days after 2023-01-01, normalised sentence, frame count).
An unlabelled HDF5 test trial matches on (date, frame count) only.

- "strict": one candidate (the audit's match).
- "possible": every candidate of an ambiguous pkl trial (the audit's "up to" counts).

The output holds only salted hashes, partition names and counts: no sentence text and no plain
trial ids. Output: src/fidetype/benchmark/splits/overlap-maps/b2t25-t15__b2t25-hdf5.json.

  set OMP_NUM_THREADS=2
  .venv\\Scripts\\python.exe -I experiments/2026-11-21-p6-10-overlap-check/build_map.py
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

import h5py  # noqa: E402

from fidetype.adapters.b2t25 import PATCH_SIZE, PATCH_STRIDE, load_copytask, normalize_words  # noqa: E402
from fidetype.benchmark import overlap as OV  # noqa: E402
from fidetype.benchmark import tracks as TR  # noqa: E402
from fidetype.benchmark.prepare import b2t25_trials  # noqa: E402

PKL = Path("C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl")
H5 = Path("C:/Users/zhang/bci-data/brain-to-text-25/neural/extracted/hdf5_data_final")
OUT = REPO / "src/fidetype/benchmark/splits/overlap-maps/b2t25-t15__b2t25-hdf5.json"
DAY_OFFSET = 197  # audit: 1,436 sentence matches agree on it
FRAME_OK = {-17, -16, -15, -14}  # audit: pkl frames - frames(n_time_steps) on unique text matches


def frames(T: int) -> int:
    return (T - PATCH_SIZE) // PATCH_STRIDE + 1


def read_h5() -> list[dict]:
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
                    a = f[k].attrs
                    lab = a.get("sentence_label", None)
                    if isinstance(lab, bytes):
                        lab = lab.decode("utf-8")
                    sub = fpart if fpart != "val" else ("val_select" if i % 2 == 0 else "val_eval")
                    rows.append({"date": date, "partition": fpart, "sub": sub,
                                 "t": OV.hdf5_trial_hash(s, int(a["block_num"]), int(a["trial_num"])),
                                 "T": int(a["n_time_steps"]),
                                 "words": None if lab is None else normalize_words(str(lab))})
    return rows


def main() -> None:
    trials = load_copytask(PKL, verify=True)
    split = {t.id: t.split for t in b2t25_trials(PKL)}
    h5 = read_h5()
    by_date = defaultdict(list)
    for r in h5:
        by_date[r["date"]].append(r)
    words_in = defaultdict(set)  # normalised sentence -> partitions that hold it (any day)
    for r in h5:
        if r["words"]:
            words_in[r["words"]].update({r["partition"], r["sub"]})

    tsplit = TR.load_split("b2t25-t15")
    test_h = {e["h"] for e in tsplit["entries"] if e["s"] == "test"}
    rows, text, quality = [], {}, Counter()
    for t in trials:
        tid = f"t15-copytask-{t.index:04d}"
        if split.get(tid) != "test":
            continue
        u = TR.id_hash("b2t25-t15", tid)
        assert u in test_h, tid
        d = datetime.date(2023, 1, 1) + datetime.timedelta(days=t.post_implant_day + DAY_OFFSET)
        w = normalize_words(t.cue_sentence)
        day = by_date.get(d, [])
        text_c = [r for r in day if r["words"] == w]
        exact = [r for r in text_c if (t.n_frames - frames(r["T"])) in FRAME_OK]
        test_c = [r for r in day if r["words"] is None and (t.n_frames - frames(r["T"])) in FRAME_OK]
        if len(exact) == 1:
            strict, cands = exact[0], []
        elif len(exact) > 1:
            strict, cands = None, exact
        elif text_c and not test_c:
            strict, cands = (text_c[0], []) if len(text_c) == 1 else (None, text_c)
        elif len(test_c) == 1 and not text_c:
            strict, cands = test_c[0], []
        elif test_c:
            strict, cands = None, test_c + text_c
        else:
            strict, cands = None, []
        quality["strict" if strict else ("possible" if cands else "no-match")] += 1
        if strict is not None:
            rows.append({"t": strict["t"], "p": strict["partition"], "sub": strict["sub"], "u": u, "q": "strict"})
        for r in cands:
            rows.append({"t": r["t"], "p": r["partition"], "sub": r["sub"], "u": u, "q": "possible"})
        parts = sorted(words_in.get(w, set()))
        if parts:
            text[u] = parts
    rows.sort(key=lambda r: (r["u"], r["q"] != "strict", r["t"]))
    counts = {
        "test_units": len(test_h),
        "match_quality": dict(quality),
        "units_strict_by_partition": dict(Counter(r["sub"] for r in rows if r["q"] == "strict")),
        "units_any_by_partition": {p: len({r["u"] for r in rows if r["sub"] == p}) for p in
                                   ("train", "val_select", "val_eval", "test")},
        "units_sentence_in_partition": {p: sum(p in v for v in text.values()) for p in
                                        ("train", "val", "val_select", "val_eval")},
    }
    doc = OV.make_map_doc(rows, text, counts, split_digest=tsplit["digest"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Header indented; one trial row / one text row per line (small diffs on a rebuild).
    head = json.dumps({k: v for k, v in doc.items() if k not in ("trials", "text")}, indent=1)
    trows = [json.dumps(r) for r in doc["trials"]]
    xrows = [f"{json.dumps(u)}: {json.dumps(v)}" for u, v in doc["text"].items()]
    body = (head[:-2] + ',\n "trials": [\n  ' + ",\n  ".join(trows) + '\n ],\n "text": {\n  '
            + ",\n  ".join(xrows) + "\n }\n}\n")
    OUT.write_text(body, encoding="utf-8")
    assert json.loads(OUT.read_text(encoding="utf-8")) == json.loads(json.dumps(doc))
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "map-counts.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=1))


if __name__ == "__main__":
    main()
