r"""Write the committed split files of benchmark v0.1 (maintainers only).

Needs the downloaded data and the local caches. Writes only ids, cluster
labels and text hashes to ``src/fidetype/benchmark/splits/v0.1/``. Run
it once per benchmark version; a later run must give the same files.

    .venv\Scripts\python.exe -I tools/benchmark/make_splits.py \
        --meg-cache C:/Users/zhang/bci-data/cache/spanishbcbl/v1 \
        --b2t-pkl C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl \
        --emg-cache C:/Users/zhang/bci-data/cache/toronto-semg/v1 \
        --emg-sentences C:/Users/zhang/bci-data/lm/eng_tatoeba_heldout.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.benchmark import prepare as P  # noqa: E402
from fidetype.benchmark.splits import make_split, split_path  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meg-cache")
    ap.add_argument("--b2t-pkl")
    ap.add_argument("--emg-cache")
    ap.add_argument("--emg-sentences")
    a = ap.parse_args()
    jobs = []
    if a.meg_cache:
        tr = P.spanishbcbl_trials(a.meg_cache)
        jobs.append(make_split(
            "spanishbcbl-meg-async", tr, ("val", "test"),
            rule="Cached typing blocks of tools/data/preprocess_spanishbcbl.py (80 of 81 blocks; S1/ses1_block1 "
                 "fails). Practice trials and trials with no typed key are dropped. Split = SHA-1 bucket of the "
                 "normalised target text (fidetype.data.preprocess.assign_split, 80/10/10), so all repetitions "
                 "of a sentence share a split. Trial id = <subject>_<session>_<block>_<trial_idx>. "
                 "Cluster 'sentence' = first 12 hex of the text SHA-256."))
    if a.b2t_pkl:
        tr = P.b2t25_trials(a.b2t_pkl)
        jobs.append(make_split(
            "b2t25-t15-copytask", tr, ("cal", "test"),
            rule="t15_copyTask.pkl (Dryad 2025-07-03), 125k-vocabulary trials (1,628 of 1,718). Per post-implant "
                 "day, in file order: first half -> cal, second half -> test. Trial id = t15-copytask-<file index>. "
                 "Truth = fidetype.adapters.b2t25.normalize_words(cue_sentence)."))
    if a.emg_cache:
        tr = P.toronto_trials(a.emg_cache, a.emg_sentences)
        jobs.append(make_split(
            "toronto-semg-composed", tr, ("cal", "test"),
            rule="Composed sentences (see recipe). Trial id = <participant>-<split>-<nn>. detail_sha256 hashes "
                 "the press ids (<recording key>#<press index>) of each character.",
            open_rules={
                "train-day1": "Cross-session regime: all session T1 recordings of all 19 participants.",
                "train-calibrated": "Session-calibrated regime: T1 plus half of the T2 recordings, cross-fitted "
                                    "(the other half is predicted); see experiments/2026-11-11-emg-toronto/train.py.",
                "train-xsubject": "Cross-subject regime: 4 folds leave participants out (no data of the user).",
            },
            extra={"recipe": P.TORONTO_RECIPE}))
    for sf in jobs:
        out = split_path(sf.track)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.save(out)
        print(sf.track, sf.counts, "->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
