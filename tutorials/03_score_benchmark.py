"""Tutorial 3: score a decoder on the open benchmark (10 minutes, CPU, no hardware).

Walk-through: docs/tutorials-03-benchmark.md

Two modes:

    python tutorials/03_score_benchmark.py                       # synthetic: no download, about 10 s
    python tutorials/03_score_benchmark.py --data <kt-semg folder> \
        --weights <kt-semg-lda release files> --runs run28        # real: KT-sEMG track, pretrained LDA

Synthetic mode: we write a tiny fake KT-sEMG folder (key logs only, no EMG), make its own
split, and score a SIMULATED decoder: it copies the true keys and changes some of them at
random. So the tutorial shows the submission format, the controls, the score card and the
leaderboard row. The numbers are toy numbers and are not comparable with the leaderboard.

Real mode: the committed kt-semg split, the truth rebuilt from your own KT-sEMG download,
and the pretrained kt-semg-lda decoder on one or more test runs (a declared partial entry).

Licence: Apache-2.0. Synthetic data only, unless you pass --data.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from fidetype.benchmark import leaderboard as LB
from fidetype.benchmark import scorecard as SC
from fidetype.benchmark import tracks as TR
from fidetype.benchmark.scoring import to_jsonable

TRACK = "kt-semg"


def step(n: int, text: str) -> None:
    print(f"\n--- step {n}: {text}")


# ------------------------------------------------------------------------------------------
# Synthetic mode
# ------------------------------------------------------------------------------------------

PHRASES = ["hello world", "thank you", "good morning", "see you soon", "i am fine", "call me later",
           "open the door", "more water please"]
KEYS = [f"Key{c}" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] + ["Space"]


def write_fake_kt(root: Path, n_runs: int = 12, bursts: int = 10, seed: int = 0) -> Path:
    """A fake KT-sEMG folder: runN_ts.txt + runN_keys.txt only (no EMG files: the truth needs only the key logs)."""
    rng = np.random.default_rng(seed)
    root.mkdir(parents=True, exist_ok=True)
    for r in range(1, n_runs + 1):
        (root / f"run{r}_ts.txt").write_text(f"2020-09-{r:02d} 10:00:00.000", encoding="ascii")
        t = 1_600_000_000.0 + r * 100_000 + 5
        lines = []
        for _ in range(bursts):
            for ch in str(rng.choice(PHRASES)):
                lines.append(f"{ch} {t:.6f}")
                t += float(rng.uniform(0.2, 0.4))
            t += 5.0  # a pause > 2 s ends a typing burst (one scored unit)
        (root / f"run{r}_keys.txt").write_bytes(("\n".join(lines) + "\n").encode("latin-1"))
    return root


def simulated_decoder(codes: list[str], error_rate: float, rng: np.random.Generator) -> list[str]:
    """NOT a real decoder: it copies the true keys and replaces each one with prob. error_rate."""
    return [str(rng.choice(KEYS)) if rng.random() < error_rate else c for c in codes]


def run_synthetic(out: Path) -> dict:
    step(1, "make a fake KT-sEMG folder and its split (a real entry uses the committed split)")
    data = write_fake_kt(out / "fake-kt")
    units = TR.local_units(TRACK, data, keys_only=True)  # keys_only: no runN.csv EMG files needed
    split = TR.make_split(TRACK, units)
    print(f"  {split['counts']}")

    step(2, "the truth of the scored test units (local only: never commit or share it)")
    truth = {r["unit"]: r for r in SC.build_truth(TRACK, data, split=split)}  # default split: the committed one
    print(f"  {len(truth)} test units; unit key example {next(iter(truth))}")

    step(3, "run the decoder on real input and on the two control inputs")
    rng = np.random.default_rng(1)
    rows, shuffled, zeros = [], [], []
    for key, t in truth.items():
        codes = t["text"].split()
        noise = float(rng.uniform(0.0, 0.4))  # per-unit signal quality
        hyp = simulated_decoder(codes, noise, rng)
        alt = simulated_decoder(codes, noise, rng)
        action = "commit" if noise < 0.08 else "offer"  # a simple policy: commit only on clean units
        rows.append(SC.unit_row(key, [" ".join(hyp), " ".join(alt)], [-noise, -noise - 1.0], action=action,
                                offer_k=2, score_semantics="logprob"))
        shuf = simulated_decoder(codes, 0.9, rng)  # time-shuffled input: almost every key is wrong
        shuffled.append(SC.unit_row(key, [" ".join(shuf)], [-5.0], action="offer"))
        zeros.append(SC.unit_row(key, ["KeyQ"], [-9.0], action="abstain"))  # no signal: say nothing
    print(f"  {len(rows)} rows; actions {sorted({r['action'] for r in rows})}")

    step(4, "write the submission folder")
    manifest = SC.manifest_dict(
        TRACK, decoder={"name": "tutorial-simulated", "version": "0", "weights_licence": "none"},
        policy={"name": "commit-if-clean"}, guarantee={"method": "none"}, regime="other",
        controls={"shuffled": "simulated: 90 % of keys replaced", "zeros": "simulated: abstain"},
        notes="Tutorial 3, synthetic mode: simulated decoder on a fake split. Toy numbers.")
    sub = SC.write_submission(out / "submission", manifest, rows, {"shuffled": shuffled, "zeros": zeros})
    print(f"  {sorted(p.relative_to(sub).as_posix() for p in sub.rglob('*') if p.is_file())}")
    return score_and_rank(sub, truth, split, out, compare=False, first=5)


# ------------------------------------------------------------------------------------------
# Real mode: kt-semg-lda on KT-sEMG test runs
# ------------------------------------------------------------------------------------------


def run_real(a: argparse.Namespace, out: Path) -> dict:
    import fidetype.pretrained as ftp
    from fidetype.benchmark.safe_wpm import guarantee_from_sheet
    from fidetype.pretrained.readers import read_kt_run

    step(1, "rebuild the truth from your download (key logs + start times only; checked against the split)")
    truth_rows = SC.build_truth(TRACK, a.data)
    truth = {r["unit"]: r for r in truth_rows}
    by_id = {r["id"]: r for r in truth_rows}
    test_runs = sorted({r["id"].split("#")[0] for r in truth_rows})
    print(f"  {len(truth)} scored units in test runs {test_runs}")
    runs = a.runs or test_runs[:1]

    step(2, f"decode the test runs {runs} with kt-semg-lda and its guard")
    model = ftp.load("kt-semg-lda", weights=a.weights)
    guard = model.guard()
    rows, shuffled, zeros = [], [], []
    for run in runs:
        csv = Path(a.data) / f"{run}.csv"
        pairs = model.decode_file(csv, with_items=True)
        emg, _ = read_kt_run(csv)  # the raw EMG, to make the control inputs
        shifted = np.roll(emg, emg.shape[0] // 2, axis=0)
        for it, st in pairs:
            r = by_id.get(f"{run}#{it.extra['segment']}")
            if r is None or r["payload"] != " ".join(c or "?" for c in it.extra["codes"]):
                continue  # this burst is not a scored unit
            # track_nbest(): the n-best in the track text space (key codes); the guard reads model.nbest() itself.
            rows.append(_row(r["unit"], guard, model, st))
            t = it.extra["times"]
            shuffled.append(_row(r["unit"], guard, model, model.decode_array(shifted, times=t)))
            zeros.append(_row(r["unit"], guard, model, model.decode_array(np.zeros_like(emg), times=t)))
        del emg, shifted
        print(f"  {run}: {len(pairs)} bursts decoded")
    print(f"  {len(rows)} scored units covered")

    step(3, "write the submission folder (a partial entry: declared with coverage.subset)")
    manifest = SC.manifest_dict(
        TRACK, decoder={"name": "kt-semg-lda (tutorial 3)", "version": model.manifest.version,
                        "weights_licence": "not released", "weights_sha256": model.weights_sha256},
        policy={"name": "packaged guard", "config_id": guard.config_id},
        guarantee=guarantee_from_sheet(guard, calibration_split="cal"),  # a valid submission guarantee
        regime="cross-session",
        controls={"shuffled": "EMG circularly shifted by half the run", "zeros": "all-zero EMG"},
        coverage={"subset": f"tutorial: test runs {', '.join(runs)} only"} if len(runs) < len(test_runs) else None,
        notes="Tutorial 3, real mode.")
    sub = SC.write_submission(out / "submission", manifest, rows, {"shuffled": shuffled, "zeros": zeros})
    return score_and_rank(sub, truth, None, out, compare=True, first=4)


def _row(unit: str, guard, model, st) -> dict:
    """One units.jsonl row: the track-space n-best and the guard action (withhold -> abstain)."""
    nb = model.track_nbest(st, n_best=3)
    act = {"commit": "commit", "offer": "offer"}.get(model.decide(st, guard=guard).action, "abstain")
    return SC.unit_row(unit, [c["text"] for c in nb], [c["score"] for c in nb], action=act, offer_k=3,
                       score_semantics="logprob")


# ------------------------------------------------------------------------------------------
# Check, score, rank (both modes)
# ------------------------------------------------------------------------------------------


def score_and_rank(sub: Path, truth: dict, split: dict | None, out: Path, compare: bool, first: int) -> dict:
    step(first, "check the submission (format, unit keys, controls; no truth needed)")
    rep = SC.check_submission(TRACK, sub, split)
    print(f"  ok {rep['ok']}, controls complete {rep['controls_complete']}, partial {rep['coverage']['partial']}")

    step(first + 1, "score it: the score card")
    card = SC.score(TRACK, sub, truth, B=500, split=split)
    print("  " + SC.score_card_text(card).replace("\n", "\n  "))
    write_card(card, out / "card.json")

    step(first + 2, "the leaderboard row of this card")
    card["_file"] = "card.json"
    rows = [LB.row(card)]
    if compare:  # the committed cards ship in the package: LB.results_dir() works after pip install too
        rows = LB.build_rows(LB.committed_results("v0.2") + [card])[TRACK]
    print("  | " + " | ".join(LB.COLUMNS[:9]) + " |")
    for r in rows:
        print("  | " + " | ".join(LB.cells(r)[:9]) + " |")
    return {"status": card["status"], "card": card}


def write_card(card: dict, path: Path) -> None:
    """Write the card as strict JSON, like `python -m fidetype.benchmark score`: NaN / inf become null.

    (A card with no commits has error_among_commits = NaN; json.dumps would write the invalid token NaN.)
    """
    path.write_text(json.dumps(to_jsonable(card), indent=1, allow_nan=False, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tutorial 3: score a decoder on the benchmark.")
    ap.add_argument("--data", help="your KT-sEMG download (folder with runN.csv, runN_keys.txt, runN_ts.txt)")
    ap.add_argument("--weights", help="folder with the kt-semg-lda release files")
    ap.add_argument("--runs", nargs="*", help="test runs to decode (default: the first test run)")
    ap.add_argument("--out", type=Path, help="output folder (default: a temporary folder)")
    a = ap.parse_args(argv)
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="fidetype-tut3-") as tmp:
        out = a.out or Path(tmp)
        out.mkdir(parents=True, exist_ok=True)
        res = run_real(a, out) if a.data else run_synthetic(out)
    ok = res["status"] == "scored"
    print(f"\nTUTORIAL 3 {'PASS' if ok else 'FAIL'} ({'real' if a.data else 'synthetic'}): card status "
          f"{res['status']}, {time.perf_counter() - t0:.1f} s")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
