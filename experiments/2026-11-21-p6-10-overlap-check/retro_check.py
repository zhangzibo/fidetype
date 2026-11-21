"""P6-10 (gap 33), step 2: run the overlap check over the committed v0.2 entries.

The committed cards were scored before P6-10, so their manifests have no ``training_data`` field. This
script writes one declaration per entry family from the free-text ``decoder.training_data`` of the card and
the experiment pages (``DECL`` below, with the reason). It then runs
:func:`fidetype.benchmark.overlap.check_overlap` on the scored units:

- full-coverage entries: every test unit of the committed split;
- partial entries (M4-12, M4-13 on b2t25-t15): the unit keys of the local submission folder
  (``C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/submissions``).

No truth is read, so declared text hashes are not compared. The committed map still gives the text
check for the B2T '25 HDF5 partitions. The cards are not changed. Output (counts only, no hashes):
results/retro-check.json.

  set OMP_NUM_THREADS=2
  .venv\\Scripts\\python.exe -I experiments/2026-11-21-p6-10-overlap-check/retro_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark import overlap as OV  # noqa: E402
from fidetype.benchmark import tracks as TR  # noqa: E402

RESULTS = REPO / "benchmark/results/v0.2"
SUBS = Path("C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/submissions")

#: Our reading of each entry family's training data: (match on the card file name, declaration, basis).
M4 = {"sources": [
    {"dataset": "b2t25-hdf5", "partitions": ["train"], "use": "train"},
    {"dataset": "b2t25-hdf5", "partitions": ["val_select"], "use": "tune", "note": "checkpoint choice"},
    {"dataset": "b2t25-hdf5", "partitions": ["val_select"], "use": "calibration", "exclude": OV.EXCLUDE_ALL,
     "note": "guard calibration: val_select minus the 106 trials with a test unit's day and sentence"}]}
CARD_RNN = {"dataset": "brain-to-text-25", "partitions": ["card-2024-online-decoder-training"], "use": "train",
            "note": "published online RNN logits; the training blocks of Card et al. 2024 are not mapped"}
DECL = [
    ("b2t25-t15__m4-1", M4, "M4-12 / M4-13: HDF5 train; checkpoint on val_select; guard on val_select minus "
                            "test matches (P6-08 results, T15 split audit)"),
    ("b2t25-t15__ours__", {"sources": [CARD_RNN, {"dataset": "b2t25-t15", "partitions": ["cal"], "use": "tune",
                                                  "note": "word-decoder settings, 400 cal trials"},
                                       {"dataset": "b2t25-t15", "partitions": ["cal"], "use": "calibration"}]},
     "published logits + our word decoder tuned on track cal; CRC / LTT on cal"),
    ("b2t25-t15__published__", {"sources": [CARD_RNN, {"dataset": "b2t25-t15", "partitions": ["cal"],
                                                       "use": "calibration"}]},
     "published logits and published decoding; CRC / LTT on cal"),
    ("b2t24-t12__", {"sources": [{"dataset": "b2t24-t12", "partitions": ["train"], "use": "train"},
                                 {"dataset": "b2t24-t12", "partitions": ["cal"], "use": "calibration"}]},
     "card: 'b2t24-t12 train split (train blocks of the train partition)'; guard on cal"),
    ("willett-hw__", {"sources": [{"dataset": "willett-hw", "partitions": ["train", "val"], "use": "train"},
                                  {"dataset": "willett-hw", "partitions": ["train", "val"], "use": "calibration"}]},
     "card: 'own training (earlier sessions)'; guard calibration 'train+val (earlier sessions)'"),
    ("kt-semg__", {"sources": [{"dataset": "kt-semg", "partitions": ["train"], "use": "train"},
                               {"dataset": "kt-semg", "partitions": ["cal"], "use": "calibration"}]},
     "card: 'kt-semg train split (20 runs)'; guard on cal"),
    ("spanishbcbl-meg__", {"sources": [{"dataset": "spanishbcbl-meg", "partitions": ["train"], "use": "train"},
                                       {"dataset": "spanishbcbl-meg", "partitions": ["val"], "use": "calibration"},
                                       {"dataset": "tatoeba-es", "use": "train", "note": "char LM"}]},
     "card: 'SpanishBCBL train split' + Tatoeba es char LM; CRC / LTT on val"),
    ("toronto-semg__", {"sources": [{"dataset": "toronto-semg", "partitions": ["train"], "use": "train"},
                                    {"dataset": "toronto-semg", "partitions": ["cal"], "use": "calibration"},
                                    {"dataset": "tatoeba-en", "use": "train", "note": "char LM"}]},
     "card: Toronto sEMG (regime) + Tatoeba en char LM; CRC on cal. The session-calibrated regime also adapts "
     "on cal recordings (cal, not test)"),
    ("emg2qwerty__", {"sources": [{"dataset": "emg2qwerty", "partitions": ["train"], "use": "train"},
                                  {"dataset": "emg2qwerty", "partitions": ["val"], "use": "calibration"},
                                  {"dataset": "tatoeba-en", "use": "train", "note": "LM (P11-12 / P11-14)"}]},
     "card: generic model on other users + personal train sessions (never val or test); guard on val"),
]


def scored_keys(card: dict, name: str, split: dict) -> tuple[list[str], str]:
    t = TR.get_track(card["track"])
    test = [e["h"] for e in split["entries"] if e["u"] == t.scored_set and e["s"] == t.scored_split]
    if not (card.get("coverage") or {}).get("partial"):
        return test, "all test units of the split"
    p = SUBS / name.removesuffix(".json") / "units.jsonl"
    if not p.is_file():
        return [], "partial entry; local submission folder not present"
    keys = [json.loads(x)["unit"] for x in p.read_text(encoding="utf-8").splitlines() if '"unit"' in x]
    return keys, f"units of the local submission folder ({len(keys)})"


def main() -> None:
    out = []
    for f in sorted(RESULTS.glob("*.json")):
        card = json.loads(f.read_text(encoding="utf-8"))
        track = card["track"]
        match = [(d, b) for pre, d, b in DECL if f.name.startswith(pre)]
        if not match:
            out.append({"entry": f.name, "status": "no declaration written"})
            continue
        decl_raw, basis = match[0]
        split = TR.load_split(track)
        keys, how = scored_keys(card, f.name, split)
        ov = OV.check_overlap(track, OV.parse_declaration(decl_raw), keys, None, split=split)
        out.append({"entry": f.name, "track": track, "scored": how, "basis": basis, "declaration": decl_raw,
                    "status": ov["status"], "n_scored_units": ov["n_scored_units"],
                    "n_overlapping_units": ov["n_overlapping_units"], "by_kind": ov.get("by_kind"),
                    "findings": [x for x in ov["findings"] if x["n_units"]], "unchecked": ov["unchecked"],
                    "line": OV.overlap_text(ov)})
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "retro-check.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for r in out:
        print(f"{r['entry']:55s} {r.get('line', r['status'])}")


if __name__ == "__main__":
    main()
