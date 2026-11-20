"""Tutorial 2: add the trust guard to a decoder and read the safe WPM (10 minutes, CPU, no hardware).

Walk-through: docs/tutorials-02-trust.md

Two modes:

    python tutorials/02_trust_and_safe_wpm.py                    # synthetic: no download, about 30 s
    python tutorials/02_trust_and_safe_wpm.py --model t15-m4-13 \
        --weights <folder with the release files> \
        --data <b2t25>/t15.2023.08.1[38]/data_val.hdf5           # real: the packaged T15 guard

Synthetic mode: a small simulated CTC decoder makes noisy scores for 16 short phrases.
We calibrate a guard on 400 labelled outputs, decide on 300 new ones and compute the
safe WPM. The numbers are toy numbers: they show the API, not a BCI result.

Real mode: the packaged T15 decoder and its committed guard (alpha 0.05, delta 0.1) on the
odd "val" trials of one session (the val_eval half, not used for calibration).

Licence: Apache-2.0. Synthetic data only, unless you pass --data.
"""

from __future__ import annotations

import argparse
import string
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

import fidetype.trust as ft
from fidetype.benchmark import safe_wpm as sw


def step(n: int, text: str) -> None:
    print(f"\n--- step {n}: {text}")


# ------------------------------------------------------------------------------------------
# A stand-in for YOUR decoder (synthetic mode). Replace it with your own model output.
# ------------------------------------------------------------------------------------------

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]  # "_" = CTC blank
FRAME_S = 0.1  # toy timing: 4 rows per character x 100 ms = 150 characters per minute (T15 speech: about 159)
PHRASES = [
    "yes", "no thanks", "thank you", "i am thirsty", "please call my wife", "turn on the light",
    "i need help", "open the window", "i am in pain", "good morning", "how are you",
    "i want to sleep", "turn off the tv", "more water please", "see you later", "i love you",
]


def toy_decoder(text: str, rng: np.random.Generator) -> np.ndarray:
    """Fake CTC logits (T, V). A random noise level per utterance makes some outputs wrong."""
    noise = rng.uniform(0.0, 1.0)
    rows = []
    for ch in text:
        target = VOCAB.index(ch)
        if rng.random() < 0.25 * noise:  # a substitution error
            target = int(rng.integers(1, len(VOCAB)))
        for k in range(4):  # 1 peak frame + 3 blank frames per character
            row = rng.normal(0.0, 1.0, len(VOCAB))
            row[target if k == 0 else 0] += (9.0 - 6.0 * noise) if k == 0 else 7.0
            rows.append(row)
    return np.array(rows)


def run_synthetic(out: Path) -> dict:
    rng = np.random.default_rng(1)

    step(1, "collect labelled decoder output (calibration set: 400 utterances)")
    cal_texts = [str(rng.choice(PHRASES)) for _ in range(400)]
    cal_logits = [toy_decoder(t, rng) for t in cal_texts]
    print(f"  {len(cal_logits)} utterances, first one {cal_logits[0].shape} (frames x tokens)")

    step(2, "calibrate the guard (the null controls run here)")
    lexicon = sorted({w for p in PHRASES for w in p.split()})
    guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, blank="_", lexicon=lexicon, alpha=0.05, delta=0.1,
                         decoder_name="tutorial-toy-ctc", modality="other", null_trials=100)
    print("  " + str(guard.sheet).replace("\n", "\n  "))

    step(3, "decide on 300 new utterances: commit / offer / withhold")
    test_texts = [str(rng.choice(PHRASES)) for _ in range(300)]
    test_logits = [toy_decoder(t, rng) for t in test_texts]
    results = [guard.decide(x, utterance_id=f"test-{i}") for i, x in enumerate(test_logits)]
    counts = {a: sum(r.action == a for r in results) for a in ("commit", "offer", "withhold")}
    print(f"  {counts}")
    print(f"  example: action={results[0].action} reason={results[0].reason!r}")

    step(4, "compute the safe WPM from the decisions")
    neural_s = [x.shape[0] * FRAME_S for x in test_logits]
    rep = safe_wpm_of(results, test_texts, neural_s, guard, timing="toy: 4 rows x 100 ms per character")

    step(5, "keep the audit log and the guard")
    guard.write_audit(out / "audit.jsonl")
    guard.save(out / "guard.json")
    again = ft.load(out / "guard.json")
    print(f"  wrote audit.jsonl and guard.json; reloaded config {again.config_id} "
          f"(same: {again.config_id == guard.config_id})")
    return {"mode": "synthetic", "report": rep}


# ------------------------------------------------------------------------------------------
# Safe WPM from TrustGuard decisions (both modes)
# ------------------------------------------------------------------------------------------


def safe_wpm_of(results, truths, neural_s, guard, *, timing: str, normalise=lambda t: t) -> dict:
    committed = [r.action == "commit" for r in results]
    correct = [c and normalise(r.text or "") == normalise(t) for c, r, t in zip(committed, results, truths)]
    sheet = guard.sheet.to_dict()
    rep = sw.safe_wpm(committed, correct,
                      n_words=[len(normalise(t).split()) for t in truths],
                      n_chars=[len(normalise(t)) for t in truths],
                      neural_s=neural_s,
                      guarantee=sw.guarantee_from_sheet(sheet), controls=sw.controls_from_sheet(sheet),
                      timing=timing)
    print("  " + sw.format_line(rep))
    print(f"  status {rep['status']}: value {rep['value']}, unguarded {rep['unguarded_wpm']:.2f}, "
          f"no-BCI reference {rep['no_bci_wpm']:.2f} WPM")
    print(f"  measured wrong-commit rate {rep['measured_wrong_commit']:.4f}, "
          f"CP95 {[round(x, 4) for x in rep['measured_wrong_commit_cp95']]} (alpha {rep['alpha']})")
    return rep


def run_real(a: argparse.Namespace, out: Path) -> dict:
    import fidetype.pretrained as ftp
    from fidetype.benchmark.registry import normalize

    step(1, f"load {a.model} and its committed guard")
    model = ftp.load(a.model, weights=a.weights)
    guard = model.guard()
    print(f"  {model!r}; guard {guard.config_id}, alpha {guard.alpha}, delta {guard.delta}")

    step(2, "decode the odd 'val' trials (val_eval: not used to calibrate the guard)")
    import h5py  # the API has no trial count, and an index past the end raises a bare IndexError

    pairs = []
    for path in a.data:
        with h5py.File(path, "r") as f:
            n_trials = len(f.keys())
        odd = list(range(1, n_trials, 2))[: a.n]
        pairs += model.decode_file(path, with_items=True, indices=odd)
        print(f"  {Path(path).parent.name}: {len(odd)} of {n_trials} trials")

    step(3, "decide on each trial")
    results = [guard.decide(st.log_probs, utterance_id=it.key) for it, st in pairs]
    counts = {k: sum(r.action == k for r in results) for k in ("commit", "offer", "withhold")}
    print(f"  {counts}")

    step(4, "safe WPM (neural time = trial length in 20 ms bins)")
    truths = [it.truth or "" for it, _ in pairs]
    neural_s = [it.x.shape[0] * 0.02 for it, _ in pairs]
    rep = safe_wpm_of(results, truths, neural_s, guard, timing="measured: trial length (20 ms bins)",
                      normalise=lambda t: normalize(t, "words"))
    guard.write_audit(out / "audit.jsonl")
    print(f"  wrote {out / 'audit.jsonl'}")
    return {"mode": "real", "report": rep}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tutorial 2: trust guard + safe WPM.")
    ap.add_argument("--model", help="t15-m4-13 (the model with a packaged guard and logits input)")
    ap.add_argument("--data", nargs="+", help="one or more B2T '25 data_val.hdf5 files")
    ap.add_argument("--weights", help="folder with the release files")
    ap.add_argument("--n", type=int, default=25, help="at most this many odd trials per file")
    ap.add_argument("--out", type=Path, help="output folder (default: a temporary folder)")
    a = ap.parse_args(argv)
    if bool(a.model) != bool(a.data):
        ap.error("give --model and --data together (or neither, for the synthetic mode)")
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="fidetype-tut2-") as tmp:
        out = a.out or Path(tmp)
        out.mkdir(parents=True, exist_ok=True)
        res = run_real(a, out) if a.model else run_synthetic(out)
    r = res["report"]
    ok = r["status"] in ("certified", "vacuous", "above-alpha") and r["controls"]["passed"]
    print(f"\nTUTORIAL 2 {'PASS' if ok else 'FAIL'} ({res['mode']}): safe WPM status {r['status']}, "
          f"{time.perf_counter() - t0:.1f} s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
