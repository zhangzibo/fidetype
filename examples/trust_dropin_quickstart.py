"""Add the Fidetype trust layer to your own decoder (P14-03 quickstart).

Runs in about a minute on a laptop CPU. It needs no data and no network:
a small synthetic "decoder" makes CTC logits and n-best lists. Replace
``my_decoder_logits`` / ``my_decoder_nbest`` with the output of your own
decoder. Docs: docs/trust-quickstart.md and docs/trust-guarantee.md.

    python examples/trust_dropin_quickstart.py               # both routes
    python examples/trust_dropin_quickstart.py --route logits
    python examples/trust_dropin_quickstart.py --out out/    # also write guard.json + audit.jsonl

Licence: Apache-2.0. Synthetic data only.
"""

from __future__ import annotations

import argparse
import string
from pathlib import Path

import numpy as np

import fidetype.trust as ft

# --- a stand-in for YOUR decoder -----------------------------------------------------------

VOCAB = ["_"] + list(string.ascii_lowercase) + [" "]  # column order of the logits; "_" = CTC blank
PHRASES = [
    "yes", "no thanks", "thank you", "i am thirsty", "please call my wife", "turn on the light",
    "i need help", "open the window", "i am in pain", "good morning", "how are you",
    "i want to sleep", "turn off the tv", "more water please", "see you later", "i love you",
]


def my_decoder_logits(text: str, rng: np.random.Generator) -> np.ndarray:
    """Fake CTC logits (T, V) for one utterance. Some utterances are noisy, so the decoder makes errors."""
    noise = rng.uniform(0.0, 1.0)  # 0 = clean signal, 1 = very noisy
    rows = []
    for ch in text:
        target = VOCAB.index(ch)
        if rng.random() < 0.25 * noise:  # a substitution error
            target = int(rng.integers(1, len(VOCAB)))
        for k in range(4):  # 1 peak frame + 3 blank frames per character
            row = rng.normal(0.0, 1.0, len(VOCAB))
            if k == 0:
                row[target] += 9.0 - 6.0 * noise
            else:
                row[0] += 7.0
            rows.append(row)
    return np.array(rows)


def my_decoder_nbest(text: str, rng: np.random.Generator) -> list[tuple[str, float]]:
    """Fake n-best list [(text, log score), ...], best first. Noisy utterances get a wrong top-1."""
    noise = rng.uniform(0.0, 1.0)
    others = [p for p in PHRASES if p != text]
    cands = [text] + [str(p) for p in rng.choice(others, size=3, replace=False)]
    gap = 6.0 * (1.0 - noise)  # a clean signal gives a large score gap
    scores = [0.0] + [float(-gap * rng.uniform(0.5, 1.5)) for _ in range(3)]
    if rng.random() < 0.3 * noise:  # a decoder error: a wrong text gets the best score
        scores[1] = 0.5
    order = np.argsort(scores)[::-1]
    return [(cands[i], scores[i]) for i in order]


def my_decoder_nbest_on_noise(rng: np.random.Generator) -> list[tuple[str, float]]:
    """Fake n-best list of your decoder on a no-signal (or time-shuffled) recording: no clear winner."""
    return [(str(p), float(-rng.uniform(0.0, 0.5))) for p in rng.choice(PHRASES, size=4, replace=False)]


# --- the quickstart ---------------------------------------------------------------------------


def run_logits(out: Path | None) -> None:
    rng = np.random.default_rng(1)
    # 1. Labelled calibration data from YOUR decoder: logits + what the user meant.
    cal_texts = [str(rng.choice(PHRASES)) for _ in range(400)]
    cal_logits = [my_decoder_logits(t, rng) for t in cal_texts]

    # 2. Calibrate. The null controls run here; a failing guard raises ft.NullControlError.
    lexicon = sorted({w for p in PHRASES for w in p.split()})  # the words your users can say
    guard = ft.calibrate(cal_logits, cal_texts, vocab=VOCAB, blank="_", lexicon=lexicon, alpha=0.05, delta=0.1,
                         decoder_name="synthetic-ctc", modality="other", null_trials=100)
    print(guard.sheet)

    # 3. Decide on new utterances.
    test_texts = [str(rng.choice(PHRASES)) for _ in range(200)]
    results = [guard.decide(my_decoder_logits(t, rng), utterance_id=f"test-{i}") for i, t in enumerate(test_texts)]
    report("logits", results, test_texts)
    if out is not None:
        guard.save(out / "guard-logits.json")
        guard.write_audit(out / "audit-logits.jsonl")
        print(f"wrote {out / 'guard-logits.json'} and {out / 'audit-logits.jsonl'}")


def run_nbest(out: Path | None) -> None:
    rng = np.random.default_rng(2)
    cal_texts = [str(rng.choice(PHRASES)) for _ in range(400)]
    cal_nbest = [my_decoder_nbest(t, rng) for t in cal_texts]
    # n-best input needs your decoder's output on null input (no-signal or time-shuffled recordings).
    null_nbest = [my_decoder_nbest_on_noise(rng) for _ in range(100)]
    guard = ft.calibrate(cal_nbest, cal_texts, null_inputs=null_nbest, alpha=0.05, delta=0.1,
                         decoder_name="synthetic-nbest", null_trials=100)
    print(guard.sheet)
    test_texts = [str(rng.choice(PHRASES)) for _ in range(200)]
    results = [guard(my_decoder_nbest(t, rng)) for t in test_texts]
    report("nbest", results, test_texts)
    if out is not None:
        guard.save(out / "guard-nbest.json")
        guard.write_audit(out / "audit-nbest.jsonl")


def report(route: str, results: list[ft.TrustResult], truths: list[str]) -> None:
    n = len(results)
    commits = [r for r, t in zip(results, truths) if r.action == "commit"]
    wrong = sum(r.text != t for r, t in zip(results, truths) if r.action == "commit")
    offers = sum(r.action == "offer" for r in results)
    print(f"[{route}] {n} test utterances: {len(commits)} commit, {offers} offer, "
          f"{n - len(commits) - offers} withhold; wrong commits {wrong}/{n} = {wrong / n:.3f} "
          f"(target: <= alpha over many utterances)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--route", choices=("logits", "nbest", "both"), default="both")
    ap.add_argument("--out", type=Path, default=None, help="folder for guard.json and audit.jsonl")
    a = ap.parse_args()
    if a.out is not None:
        a.out.mkdir(parents=True, exist_ok=True)
    if a.route in ("logits", "both"):
        run_logits(a.out)
    if a.route in ("nbest", "both"):
        run_nbest(a.out)


if __name__ == "__main__":
    main()
