"""P6-01 side jobs: exact per-trial Toronto sEMG safe WPM + null-commit audits at CRC / LTT thresholds.

CPU only. Reads the inputs of earlier experiments (read only) and writes:

- per-trial files (no text): ``C:/Users/zhang/bci-data/derived/p6-01-tracks/``
- aggregates: ``results/*.json`` next to this file

Stages
------
``toronto``
    Rebuild the composed-sentence test set and the CRC pipeline of
    ``experiments/2026-11-11-emg-toronto/trust.py`` (same seed, plan, LM
    weight tuning and fit) for each condition (calib, xsession, xsubject).
    Keep the per-trial records. Check that the CRC commit rate and
    wrong-commit rate equal the committed aggregates. Then compute safe WPM
    per trial with a participant-cluster bootstrap CI.
``b2t-null``
    Rebuild the B2T '25 trust pipelines exactly as M2-13 (``stage_b2t``) and
    the null-audit set of ``experiments/2026-11-10-b2t25-trust`` (300 test
    trials: other trial, frame shuffled, uniform). Compute the commit score
    of M2-13 (``commit_calibration_data``) on each null stream and apply the
    CRC / LTT threshold of the v0.1 result entry.
``meg-null``
    The same for the SpanishBCBL async MEG trust pipeline of
    ``experiments/2026-11-11-g1-async-meg-trust`` (all 637 test trials:
    zeros MEG, shuffled MEG, frame shuffled, uniform, other sentence).

Run (repo root)::

    .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- ^
        .venv\\Scripts\\python.exe -I experiments/2026-11-16-p6-01-tracks/run.py --stages toronto,b2t-null,meg-null
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

OUT = HERE / "results"
DER = Path("C:/Users/zhang/bci-data/derived/p6-01-tracks")
TRUTH_DIR = Path("C:/Users/zhang/bci-data/benchmark")
RESULTS_V01 = REPO / "benchmark" / "results" / "v0.1"
LOG = OUT / "run.log"


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def dump(obj, path: Path) -> None:
    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.floating, float)):
            v = float(o)
            return None if not math.isfinite(v) else v
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return o

    path.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")


def trial_rows(ids, committed, correct, n_words, n_chars, cpm: float) -> list[dict]:
    """The rows of a Toronto per-trial file (no text): one dict per test trial.

    ``n_words`` is the word count of the target sentence. Before 2026-11-25 the writer unpacked its
    ``zip`` in the wrong order, so the field ``n_words`` held the correct flag (0 or 1). No stored
    number used that field: the v0.1 block was computed from the arrays, and
    ``tools/benchmark/add_safe_wpm_v02_tracks01.py`` takes the counts from the truth file.
    """
    rows = []
    for a, b, ok, w, c in zip(ids, committed, correct, n_words, n_chars, strict=True):
        rows.append({"id": a, "committed": bool(b), "correct": bool(b and ok),
                     "n_words": int(w), "n_chars": int(c), "neural_s": float(c * 60.0 / cpm)})
    return rows


def threshold_of(stem: str) -> tuple[float, dict]:
    d = json.loads((RESULTS_V01 / f"{stem}.json").read_text(encoding="utf-8"))
    g = d["guarantee"]
    return float(g["threshold"]), g


# ---------------------------------------------------------------------------
# Toronto sEMG: per-trial CRC records -> safe WPM with CI
# ---------------------------------------------------------------------------


def stage_toronto() -> dict:
    from fidetype.benchmark.prepare import read_truth
    from fidetype.benchmark.registry import get_track
    from fidetype.benchmark.safe_wpm import safe_wpm
    from fidetype.benchmark.splits import load_split
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    tm = load_module("toronto_trust", REPO / "experiments/2026-11-11-emg-toronto/trust.py")
    C = tm.CONFIG
    track = get_track("toronto-semg-composed")
    split = load_split("toronto-semg-composed")
    truth = read_truth(TRUTH_DIR / "emg-truth.jsonl")
    test_ids = split.ids("test")
    by_pt = {(split.clusters("test")[i]["participant"], truth[i]["text"]): i for i in test_ids}

    y, file_idx, files, info = tm.load_meta()
    period = float(info["inter_key_interval_s"]["median"])
    cpm = 60.0 / period
    user = UserConfig.aac_gaze(chars_per_min=cpm)
    lm = CharNgramLM.load(C["char_lm"])
    texts = tm.sentences()
    nfit, ntest = C["sentences_per_participant"]["fit"], C["sentences_per_participant"]["test"]
    P = tm.pools(y, file_idx, files)
    pids = sorted(P, key=lambda s: int(s[1:]))
    half = len(texts) // 2
    fit_texts, test_texts = texts[:half], texts[half:]
    per_p = len(fit_texts) // len(pids)
    rng = np.random.default_rng(tm.SEED)
    plan = {}
    for k, p in enumerate(pids):
        plan[p] = {"fit": tm.compose(fit_texts[k * per_p:(k + 1) * per_p], P[p]["fit"], rng, nfit),
                   "test": tm.compose(test_texts[k * per_p:(k + 1) * per_p], P[p]["test"], rng, ntest)}
    agg = json.loads((REPO / "experiments/2026-11-11-emg-toronto/results/trust.json").read_text(encoding="utf-8"))
    DER.mkdir(parents=True, exist_ok=True)
    out = {"timing": f"track rate model: len(truth) * 60 / {cpm:.2f} chars/min (composed sentences)",
           "ci_unit": "participant", "conditions": {}}
    for cond in ("calib", "xsession", "xsubject"):
        tc = time.time()
        fit_run, test_run, _desc = tm.CONDITIONS[cond]
        lg_fit, have_fit, _ = tm.load_logits(fit_run, len(y))
        lg_test, have_test, _ = tm.load_logits(test_run, len(y))

        def items_of(which, lg, have):
            its, meta = [], []
            for p in pids:
                for t, idx in plan[p][which]:
                    assert have[idx].all()
                    its.append(Item(tm.make_stream(lg[idx], period, p, cond), t))
                    meta.append((p, t))
            return its, meta

        fit_items, _ = items_of("fit", lg_fit, have_fit)
        test_items, test_meta = items_of("test", lg_test, have_test)
        order = np.random.default_rng(tm.SEED + 7).permutation(len(fit_items))
        fit_items = [fit_items[i] for i in order]
        A, Bv = fit_items[: len(fit_items) // 2], fit_items[len(fit_items) // 2:]
        w_best = agg["conditions"][cond]["lm_weight"]  # tuned on fit-A in M6-07; same plan, so reuse the choice
        kw = {**C["beam"], "lm_weight": w_best}

        def decode_fn(s, kw=kw):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        pipe = TrustPipeline(decode_fn, HarnessConfig(seed=tm.SEED, user_config=user, max_wrong_commit=C["max_wrong_commit"],
                                                      risk_control="crc"), {})
        pipe.fit(A, Bv)
        m = pipe.evaluate(test_items)
        recs = m.pop("records")
        ref = agg["conditions"][cond]["policies"]["c_crc"]
        same = (abs(m["rate_commit"] - ref["rate_commit"]) < 1e-12 and abs(m["wrong_commit_rate"] - ref["wrong_commit_rate"]) < 1e-12
                and abs(m["ewpm"] - ref["ewpm"]) < 1e-9)
        log(f"toronto {cond}: commit {m['rate_commit']:.4f} (ref {ref['rate_commit']:.4f}) wrong {m['wrong_commit_rate']:.4f} "
            f"(ref {ref['wrong_commit_rate']:.4f}) eWPM {m['ewpm']:.3f} (ref {ref['ewpm']:.3f}) same={same}")
        committed = np.array([r.actions[0] == "COMMIT" for r in recs])
        correct = committed & ~np.array([bool(r.wrong_commit) for r in recs])
        ids = [by_pt[(p, t)] for p, t in test_meta]
        assert sorted(ids) == sorted(test_ids), "composed test set differs from the v0.1 split"
        nw = np.array([len(t.split()) for _, t in test_meta], float)
        nc = np.array([len(t) for _, t in test_meta], float)
        ns = nc * 60.0 / cpm
        stem = f"toronto-semg-composed__cnn-{cond}__crc"
        res = json.loads((RESULTS_V01 / f"{stem}.json").read_text(encoding="utf-8"))
        blk = safe_wpm(committed, correct, nw, nc, ns, guarantee=res.get("guarantee"), timing=out["timing"],
                       clusters=[{"participant": p} for p, _ in test_meta], ci_unit="participant",
                       controls=res.get("controls"), gaze_chars_per_min=track.user_model.gaze_chars_per_min, B=2000, seed=0, metric_version="0.1")
        blk["basis"] = ("exact per-trial CRC decisions (P6-01 rerun of the M6-07 pipeline; commit and wrong-commit rates "
                        "equal the committed aggregates)" if same else "per-trial rerun; DIFFERS from committed aggregates")
        with open(DER / f"toronto-{cond}-crc-trials.jsonl", "w", encoding="utf-8") as f:
            for r in trial_rows(ids, committed, correct, nw, nc, cpm):
                f.write(json.dumps(r) + "\n")
        out["conditions"][cond] = {"same_as_committed": same, "lm_weight": w_best, "rate_commit": m["rate_commit"],
                                   "wrong_commit_rate": m["wrong_commit_rate"], "ewpm": m["ewpm"], "safe_wpm": blk,
                                   "seconds": round(time.time() - tc, 1)}
        log(f"toronto {cond}: safe WPM {blk.get('value')} CI {blk.get('ci')} status {blk['status']} ({time.time() - tc:.0f}s)")
        dump(out, OUT / "toronto-safe-wpm.json")
    out["seconds"] = round(time.time() - t0, 1)
    dump(out, OUT / "toronto-safe-wpm.json")
    return out


# ---------------------------------------------------------------------------
# Null audits at a CRC / LTT threshold
# ---------------------------------------------------------------------------


def audit_scores(pipe, decode, null_sets: dict, truths: list[str]) -> dict:
    """M2-13 commit score of each null stream (``-inf`` if another rule blocks the commit)."""
    from fidetype.trust.risk_control import commit_calibration_data

    T = pipe.frame_scaler.temperature
    out = {}
    for cond, ss in null_sets.items():
        inputs, tops = [], []
        for s in ss:
            s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
            nb = decode(s2)
            inputs.append(pipe.analyze(nb).inputs)
            tops.append(nb.top.text if nb.top is not None else "")
        sc, loss, _ = commit_calibration_data(pipe.policy, inputs, truths)
        out[cond] = {"score": sc, "wrong": loss}
    return out


def audit_block(scores: dict, lam: float, n: int) -> dict:
    from fidetype.utils.binomial import clopper_pearson

    res = {}
    for cond, d in scores.items():
        com = d["score"] >= lam
        k = int(com.sum())
        kw = int((com & (d["wrong"] > 0)).sum())
        res[cond] = {"n": n, "commits": k, "commit_rate": k / n, "wrong_commits": kw,
                     "commit_rate_cp95": list(clopper_pearson(k, n))}
    return res


def stage_b2t_null() -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    t0 = time.time()
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    best = tune["best"]
    dec = bt.Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}
    fi = [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in fit]
    items_ref = {n: json.loads((REPO / f"experiments/2026-11-11-m2-13-conformal/results/items-{n}.json").read_text(encoding="utf-8"))
                 for n in ("b2t-ours", "b2t-published")}
    # Audit set: as in experiments/2026-11-10-b2t25-trust stage_trust (word level).
    rng = np.random.default_rng(bt.SEED)
    na = min(len(test), bt.CONFIG["audit_n"])
    aud_idx = sorted(rng.choice(len(test), na, replace=False).tolist())
    atest = [test[i] for i in aud_idx]
    base = [streams[t.index] for t in atest]
    perm = rng.permutation(len(base))
    for i in range(len(perm)):
        if atest[perm[i]].truth_words == atest[i].truth_words:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    nulls = {"real": base, "other_trial": [base[j] for j in perm],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base],
             "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
    truths = [t.truth_words for t in atest]
    out = {"n_audit": na, "audit_rule": "300 test trials, seed 0, as experiments/2026-11-10-b2t25-trust", "entries": {}}
    for name, fn, stems in (("b2t-ours", dec.words_fn, ("b2t25-t15-copytask__ours__crc", "b2t25-t15-copytask__ours__ltt")),
                            ("b2t-published", dec.published_plus_fn,
                             ("b2t25-t15-copytask__published__crc", "b2t25-t15-copytask__published__ltt"))):
        ts = time.time()
        pipe = TrustPipeline(fn, HarnessConfig(seed=bt.SEED, user_config=user, max_wrong_commit=bt.CONFIG["max_wrong_commit"]))
        pipe.fit(fi, fi)
        if name == "b2t-published":
            # The published sentence of the audited trial on top of the null stream's n-best:
            # published_plus_fn reads the trial index from the meta, so set it per audited trial.
            decode, sets = dec.published_plus_fn, {}
            for cond, ss in nulls.items():
                sets[cond] = [NeuralTextStream(s.log_probs, s.frame_times, s.vocab, s.blank_id, s.source,
                                               {**s.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s.vocab_type)
                              for i, s in enumerate(ss)]
        else:
            decode, sets = dec.words_fn, nulls
        sc = audit_scores(pipe, decode, sets, truths)
        ref = np.array([float(x) for x in items_ref[name]["test"]["score"]])[aud_idx]
        real_ok = bool(np.allclose(np.nan_to_num(sc["real"]["score"], neginf=-9), np.nan_to_num(ref, neginf=-9), atol=1e-9))
        for stem in stems:
            lam, g = threshold_of(stem)
            blk = audit_block(sc, lam, na)
            out["entries"][stem] = {"threshold": lam, "method": g["method"], "real_scores_match_m2_13": real_ok,
                                    "audit": blk}
            log(f"{stem}: lam {lam:.4f} real-match {real_ok} " + " ".join(
                f"{c} {v['commits']}/{na}" for c, v in blk.items()))
        log(f"{name}: {time.time() - ts:.0f}s")
        dump(out, OUT / "null-audit-b2t.json")
    out["seconds"] = round(time.time() - t0, 1)
    dump(out, OUT / "null-audit-b2t.json")
    return out


def stage_meg_null() -> dict:
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    t0 = time.time()
    g1 = load_module("g1meg", REPO / "experiments/2026-11-11-g1-async-meg-trust/run.py")
    g1.Logger.path = OUT / "run-meg-g1.log"  # never write into the other experiment's folder
    root = Path(g1.CONFIG["streams"]["async"])
    dec, kw = g1.make_decoder()
    val_raw, test_raw = g1.load_split(root, "val"), g1.load_split(root, "test")
    val = [g1.Item(s, r["target_text"]) for s, r in val_raw]
    test = [g1.Item(s, r["target_text"]) for s, r in test_raw]
    from fidetype.eval.harness import TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    specs = g1.M2.policy_specs(UserConfig.aac_gaze(), g1.M2.MAX_WRONG_COMMIT, False)
    pipe = TrustPipeline(dec, specs["trust"], {})
    pipe.fit(val, val)
    truths = [it.text for it in test]
    part = [r["participant"] for _, r in test_raw]
    rng = np.random.default_rng(g1.SEED)
    base = [s for s, _ in test_raw]
    ctl = np.load(g1.CONFIG["controls_npz"])
    n = len(base)
    other = []
    for i in range(n):
        same_p = [j for j in range(n) if part[j] == part[i] and truths[j] != truths[i]]
        pool = same_p or [j for j in range(n) if truths[j] != truths[i]]
        other.append(int(rng.choice(pool)))
    nulls = {
        "real": base,
        "shuffled_meg": [g1.with_logprobs(s, ctl["shuffled__" + r["file"]], "shuffled_meg") for s, r in test_raw],
        "zeros_meg": [g1.with_logprobs(s, ctl["zeros__" + r["file"]], "zeros_meg") for s, r in test_raw],
        "other_sentence": [base[j] for j in other],
        "frame_shuffled": [shuffle_stream(s, rng) for s in base],
        "uniform": [uniform_stream(s, rng, 0.05) for s in base],
    }
    sc = audit_scores(pipe, dec, nulls, truths)
    ref = json.loads((REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json").read_text(encoding="utf-8"))
    refs = np.array([float(x) if x is not None else -math.inf for x in ref["test"]["score"]])
    real_ok = bool(np.allclose(np.nan_to_num(sc["real"]["score"], neginf=-9), np.nan_to_num(refs, neginf=-9), atol=1e-9))
    out = {"n_audit": n, "audit_rule": "all 637 test trials, as experiments/2026-11-11-g1-async-meg-trust stage_null",
           "entries": {}}
    for stem in ("spanishbcbl-meg-async__convctc-m-async__crc", "spanishbcbl-meg-async__convctc-m-async__ltt"):
        lam, g = threshold_of(stem)
        blk = audit_block(sc, lam, n)
        out["entries"][stem] = {"threshold": lam, "method": g["method"], "real_scores_match_items": real_ok, "audit": blk}
        log(f"{stem}: lam {lam:.4f} real-match {real_ok} " + " ".join(f"{c} {v['commits']}/{n}" for c, v in blk.items()))
    out["seconds"] = round(time.time() - t0, 1)
    dump(out, OUT / "null-audit-meg.json")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="toronto,b2t-null,meg-null")
    ap.add_argument("--out", default=None, help="folder for the aggregates and the log (default: results/ here)")
    ap.add_argument("--der", default=None, help="folder for the per-trial files (default: the local derived folder)")
    a = ap.parse_args()
    global OUT, DER, LOG
    if a.out:
        OUT = Path(a.out)
        LOG = OUT / "run.log"
    if a.der:
        DER = Path(a.der)
    OUT.mkdir(exist_ok=True)
    DER.mkdir(parents=True, exist_ok=True)
    for st in a.stages.split(","):
        log(f"stage {st} start")
        {"toronto": stage_toronto, "b2t-null": stage_b2t_null, "meg-null": stage_meg_null}[st]()
    log("done")


if __name__ == "__main__":
    main()
