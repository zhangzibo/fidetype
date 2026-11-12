r"""Build a stream submission for the B2T '25 track from the published decoder output.

Each test trial becomes one NeuralTextStream (JSON Lines): the phoneme
logits of the dataset (adapter ``fidetype.adapters.b2t25``) plus one final
hypothesis event that holds the published online sentence of Card et al.
(2024), with the benchmark action ``commit``. No decoding runs here. This
is the reference "stream submission" of benchmark v0.1: it shows that a
text-only result can enter the board through NTS files.

The files are written OUTSIDE the repository (they are large, about 60 MB).

    .venv\Scripts\python.exe -I tools/benchmark/make_b2t25_published.py \
        --pkl C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl \
        --out C:/Users/zhang/bci-data/benchmark/submissions/b2t25-published-commit
    .venv\Scripts\python.exe -m fidetype.benchmark score <out> --truth <truth.jsonl> --out result.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from fidetype.adapters import b2t25 as B  # noqa: E402
from fidetype.benchmark.splits import load_split  # noqa: E402
from fidetype.benchmark.submission import Manifest, write_manifest, write_trial  # noqa: E402

TRACK = "b2t25-t15-copytask"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkl", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    trials = {f"t15-copytask-{t.index:04d}": t for t in B.load_copytask(a.pkl, verify=True)}
    ids = load_split(TRACK).ids("test")
    for i in ids:
        t = trials[i]
        write_trial(out / "streams" / f"{i}.jsonl", B.trial_stream(t), [B.normalize_words(t.decoded_sentence)],
                    [0.0], action="commit", score_semantics="none")
    write_manifest(out, Manifest(
        track=TRACK,
        decoder={"name": "Card et al. 2024 online decoder (published sentence)", "version": "t15-copytask-online",
                 "url": "https://doi.org/10.5061/dryad.dncjsxm85",
                 "weights_licence": "not released (outputs in the CC0 dataset)",
                 "training_data": ["T15 sessions (Card et al. 2024)"], "training_regime": "online, per-user"},
        policy={"name": "always-commit", "description": "commit the published sentence on every trial"},
        guarantee={"method": "none"},
        submitter={"name": "Fidetype maintainers (reference submission)"},
        notes="Text-only result: the published decoder cannot be rerun on shuffled or zero input, so the controls "
              "are missing.",
    ))
    print(f"wrote {len(ids)} trials to {out}")


if __name__ == "__main__":
    main()
