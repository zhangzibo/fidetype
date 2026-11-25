r"""Add the adopted safe-wpm/0.2 block to the tracks-v0.1 score cards (gap 204).

The tracks-v0.2 cards got their v0.2 block from ``add_safe_wpm_v02.py`` (a new scoring of their submission
folders). The tracks-v0.1 cards have no submission folder: their ``safe_wpm`` block (safe-wpm/0.1) was computed
from per-trial arrays by ``experiments/2026-11-16-p14-05-safe-wpm/run.py tracks`` (B2T '25 copy task, SpanishBCBL
MEG) and ``experiments/2026-11-16-p6-01-tracks/run.py`` (Toronto sEMG CRC). This tool rebuilds the same arrays from
the same local sources, and then, as ``add_safe_wpm_v02.py`` does:

- computes the v0.1 block again with the recorded settings (B = 2000, seed 0) and checks that it is identical to
  the stored block (else it stops for that card);
- computes the v0.2 block from the same arrays (default ``metric_version="0.2"``: the adopted reading cost);
- adds ``safe_wpm_v02`` (right after ``safe_wpm``) and ``safe_wpm_headline``, and the v0.2 metric in the recipe's
  ``scorer.metrics``. Every other key keeps its value and order. A v0.1 number keeps its value and its label.

Cards whose policy has no certified bound (always-commit, plug-in trust fit without CRC / LTT) have the value
"n/a" under v0.1 and v0.2 alike; their v0.1 block holds no per-trial numbers. Their v0.2 block states the same
status from the card alone (no per-trial source is needed for "no certified bound").

Local sources (read only, never committed): ``--truth-dir`` (b2t25-truth.jsonl, meg-truth.jsonl, emg-truth.jsonl),
``--b2t-pkl`` (t15_copyTask.pkl, for the measured speech durations), ``--toronto-dir`` (the P6-01 per-trial CRC
decisions ``toronto-<cond>-crc-trials.jsonl``). The committed items files are in ``experiments/``. CPU only.

    python -I tools/benchmark/add_safe_wpm_v02_tracks01.py            # dry run: print a summary
    python -I tools/benchmark/add_safe_wpm_v02_tracks01.py --write    # update the cards
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark.hub.recipe import card_json  # noqa: E402
from fidetype.benchmark.prepare import read_truth  # noqa: E402
from fidetype.benchmark.registry import get_track  # noqa: E402
from fidetype.benchmark.safe_wpm import (DEFINITION_V02, V02_STATUS, model_neural_s,  # noqa: E402
                                         safe_wpm)
from fidetype.benchmark.scoring import to_jsonable  # noqa: E402
from fidetype.benchmark.splits import load_split  # noqa: E402

B, SEED = 2000, 0
#: Keys that a later step added to a stored v0.1 block (not part of the scorer output); they are carried over.
CARRIED = ("note", "basis")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


AV = load_module("add_safe_wpm_v02", REPO / "tools/benchmark/add_safe_wpm_v02.py")

#: card stem -> (track, committed items file, truth file) for the per-trial B2T / MEG cards (p14-05 ``per_trial``).
PER_TRIAL = {
    "b2t25-t15-copytask__ours": ("b2t25-t15-copytask", "2026-11-11-m2-13-conformal/results/items-b2t-ours.json",
                                 "b2t25-truth.jsonl"),
    "b2t25-t15-copytask__published": ("b2t25-t15-copytask",
                                      "2026-11-11-m2-13-conformal/results/items-b2t-published.json",
                                      "b2t25-truth.jsonl"),
    "spanishbcbl-meg-async__convctc-m-async": ("spanishbcbl-meg-async",
                                               "2026-11-11-g1-async-meg-trust/results/items-meg-async.json",
                                               "meg-truth.jsonl"),
}
B2T_TIMING = "measured per-trial speech duration (t15_copyTask.pkl speech_duration_s)"


def b2t_durations(pkl: Path) -> dict[str, float]:
    from fidetype.adapters.b2t25 import load_copytask

    return {f"t15-copytask-{t.index:04d}": float(t.speech_duration_s) for t in load_copytask(pkl, verify=True)}


def check_counts(name: str, rows: list[dict], n_chars, n_words) -> None:
    """Stop if the character or word counts of a Toronto per-trial file differ from the truth file."""
    if not np.allclose(n_chars, [r["n_chars"] for r in rows]):
        raise SystemExit(f"{name}: character counts differ from the truth file")
    if not np.allclose(n_words, [r["n_words"] for r in rows]):
        raise SystemExit(f"{name}: word counts differ from the truth file (a per-trial file written before "
                         "2026-11-25 holds the correct flag in n_words; rebuild it with "
                         "experiments/2026-11-16-p6-01-tracks/run.py --stages toronto)")


def per_trial_inputs(a, results: Path) -> dict[str, dict]:
    """card file name -> the safe_wpm arguments that produced its stored v0.1 block."""
    ib = load_module("import_baselines", REPO / "tools/benchmark/import_baselines.py")
    out: dict[str, dict] = {}
    dur = None
    for stem, (track, items_rel, truth_name) in PER_TRIAL.items():
        t = get_track(track)
        split = load_split(track)
        ids = split.ids("test")
        clusters = [r["clusters"] for r in split.trials("test")]
        tr = read_truth(Path(a.truth_dir) / truth_name)
        nc = np.array([len(tr[i]["text"]) for i in ids], float)
        nw = np.array([len(tr[i]["text"].split()) for i in ids], float)
        if track.startswith("b2t25"):
            dur = dur if dur is not None else b2t_durations(Path(a.b2t_pkl))
            ns, timing = np.array([dur[i] for i in ids], float), B2T_TIMING
        else:
            cpm = t.user_model.config["chars_per_min"]
            ns = model_neural_s(nc, cpm)
            timing = (f"track rate model: len(truth) * 60 / {cpm:g} chars/min (no per-trial timing in the "
                      "committed data)")
        d = ib.load(items_rel)
        fit, test = ib.Items(d["fit"]), ib.Items(d["test"])
        th = ib.thresholds(fit)
        for kind in ("trust", "crc", "ltt"):
            name = f"{stem}__{kind}.json"
            card = json.loads((results / name).read_text(encoding="utf-8"))
            on = test.s >= th[kind]
            cr = card["metrics"]["commit_rate"]["value"]
            if abs(float(on.mean()) - cr) > 1e-9:
                raise SystemExit(f"{name}: commit rate {float(on.mean())} differs from the card ({cr})")
            g = card.get("guarantee") or {"method": "none"}
            if g.get("method", "none") == "none":
                g = {"method": "none"}
            out[name] = dict(committed=on, correct=on & (test.wc_c == 0), n_words=nw, n_chars=nc, neural_s=ns,
                             guarantee=g, timing=timing, clusters=clusters, ci_unit=t.ci_unit,
                             controls=card.get("controls"), gaze_chars_per_min=t.user_model.gaze_chars_per_min)
    # Toronto sEMG CRC: the P6-01 per-trial decisions (committed / correct by trial id). Word and character counts
    # come from the truth file; check_counts checks the per-trial file against them. (Files written before
    # 2026-11-25 held the correct flag in n_words: rebuild them with experiments/2026-11-16-p6-01-tracks/run.py
    # --stages toronto.)
    track = "toronto-semg-composed"
    t = get_track(track)
    split = load_split(track)
    test_rows = split.trials("test")
    tr = read_truth(Path(a.truth_dir) / "emg-truth.jsonl")
    cpm = t.user_model.config["chars_per_min"]
    for cond in ("calib", "xsession", "xsubject"):
        name = f"{track}__cnn-{cond}__crc.json"
        card = json.loads((results / name).read_text(encoding="utf-8"))
        rows = [json.loads(x) for x in (Path(a.toronto_dir) / f"toronto-{cond}-crc-trials.jsonl")
                .read_text(encoding="utf-8").splitlines() if x.strip()]
        ids = [r["id"] for r in rows]
        if sorted(ids) != sorted(r["id"] for r in test_rows):
            raise SystemExit(f"{name}: the per-trial ids differ from the test split")
        by_id = {r["id"]: r for r in test_rows}
        nc = np.array([len(tr[i]["text"]) for i in ids], float)
        nw = np.array([len(tr[i]["text"].split()) for i in ids], float)
        check_counts(name, rows, nc, nw)
        out[name] = dict(committed=np.array([r["committed"] for r in rows], bool),
                         correct=np.array([r["correct"] for r in rows], bool), n_words=nw, n_chars=nc,
                         # the P6-01 rate-model times (the median inter-key interval of the recordings)
                         neural_s=np.array([r["neural_s"] for r in rows], float), guarantee=card.get("guarantee"),
                         timing=f"track rate model: len(truth) * 60 / {cpm:.2f} chars/min (composed sentences)",
                         clusters=[{"participant": by_id[i]["clusters"]["participant"]} for i in ids],
                         ci_unit="participant", controls=card.get("controls"),
                         gaze_chars_per_min=t.user_model.gaze_chars_per_min)
    return out


def block(inp: dict, version: str) -> dict:
    x = dict(inp)
    return to_jsonable(safe_wpm(x.pop("committed"), x.pop("correct"), x.pop("n_words"), x.pop("n_chars"),
                                x.pop("neural_s"), B=B, seed=SEED, metric_version=version, **x))


def no_bound_v02(v1: dict) -> dict:
    """The v0.2 block of a card whose policy has no certified bound: "n/a" under both versions."""
    out = {"definition": DEFINITION_V02, "definition_status": V02_STATUS, "adopted_headline": True}
    out.update({k: v for k, v in v1.items() if k != "definition"})
    out["basis"] = ("no certified bound: the value is n/a under safe-wpm/0.1 and safe-wpm/0.2 alike; the status "
                    "follows from the card's policy (no per-trial data needed)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=str(REPO / "benchmark" / "results" / "v0.1"))
    ap.add_argument("--truth-dir", default="C:/Users/zhang/bci-data/benchmark")
    ap.add_argument("--b2t-pkl", default="C:/Users/zhang/bci-data/brain-to-text-25/t15_copyTask.pkl")
    ap.add_argument("--toronto-dir", default="C:/Users/zhang/bci-data/derived/p6-01-tracks")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    results = Path(a.results)
    inputs = per_trial_inputs(a, results)
    done, failed = [], []
    for f in sorted(results.glob("*.json")):
        text = f.read_text(encoding="utf-8")
        card = json.loads(text)
        if card_json(card) != text:
            failed.append((f.name, "the card is not in the scorer's JSON form"))
            continue
        v1 = card["safe_wpm"]
        if f.name in inputs:
            fresh = block(inputs[f.name], "0.1")
            stored = {k: v for k, v in v1.items() if k not in CARRIED}
            if json.dumps(fresh, sort_keys=True) != json.dumps(stored, sort_keys=True):
                diff = sorted(k for k in set(fresh) | set(stored) if fresh.get(k) != stored.get(k))
                failed.append((f.name, f"the fresh v0.1 block differs from the stored one in {diff}"))
                continue
            v2 = block(inputs[f.name], "0.2")
            v2.update({k: v1[k] for k in CARRIED if k in v1})
            source = "per-trial"
        elif v1.get("status") == "not-certified" and v1.get("value") is None and v1.get("method") == "none":
            v2, source = no_bound_v02(v1), "no bound"
        else:
            failed.append((f.name, "no per-trial source and the policy has a bound"))
            continue
        if v1.get("status") != v2.get("status"):
            failed.append((f.name, f"status differs: v0.1 {v1.get('status')} vs v0.2 {v2.get('status')}"))
            continue
        out = AV.with_v02(card, {"safe_wpm_v02": v2, "safe_wpm_headline": "safe_wpm_v02"})
        new = card_json(out)
        changed = new != text
        if a.write and changed:
            f.write_text(new, encoding="utf-8", newline="\n")
        done.append((f.name, v1.get("value"), v2.get("value"), v2.get("ci"), v2.get("status"), source, changed))
    fx = (lambda x: "n/a" if x is None else f"{x:.3f}")
    for name, x1, x2, ci, status, source, changed in done:
        c = f" [{ci[0]:.3f}, {ci[1]:.3f}]" if ci else ""
        print(f"{'WRITE' if a.write and changed else 'ok   ' if not changed else 'would'} {name}: v0.1 {fx(x1)}"
              f" -> v0.2 {fx(x2)}{c} ({status}; {source})")
    for name, why in failed:
        print(f"FAIL  {name}: {why}")
    print(f"{len(done)} cards with a v0.2 block, {len(failed)} failed", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
