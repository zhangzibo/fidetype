"""P6-02b: v0.2-format entries for b2t25-t15, toronto-semg and spanishbcbl-meg (closes open gap 27 = P6-08).

The v0.1 entries of these three tracks were scored from committed per-trial arrays or aggregates, with no
per-unit text. A v0.2 submission needs per-unit text, a decision and the two control runs. So this script
reruns the SAME pipelines (same decoders, same fits, same seeds, same thresholds as v0.1) on the existing
decoder outputs (read only), writes v0.2 submissions, and scores each one with the one command
``python -m fidetype.benchmark score <track> <submission> --truth <truth>``. CPU only.

Stages (repo root; heavy ones through the CPU isolation wrapper):

  b2t        b2t25-t15: our phoneme-beam word decoder (m6-06) and the published decoder (Card et al. 2024),
             policies always-commit / plug-in trust gate / CRC / LTT; thresholds = the v0.1 entries
  meg        spanishbcbl-meg (RESEARCH ONLY): ConvCTC-M async + char 6-gram beam, same four policies
  toronto    toronto-semg: key-press CNN + char 6-gram beam, 3 regimes x (always-commit, trust gate, CRC)
  t15-m4-12  b2t25-t15, PARTIAL: M4-12 + drop-in guard (P14-03 recipe) on the 103 test units that are in the
             decoder's held-out val_eval partition; guard calibrated on val_select minus every track test unit
  t15-m4-13  the same for M4-13 (run when the M4-13 queue and the trust-reruns val_select decode exist)
  score      score every submission with the CLI -> benchmark/results/v0.2/<entry>.json
  table      results/tables.md from the score cards

  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p6-02b-v02-entries/run.py b2t meg toronto t15-m4-12 score table

Per-unit files (submissions with text, truth): C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/ only.
Repo: score cards (aggregates, no text) in benchmark/results/v0.2/ and results/*.json.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import datetime  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

from fidetype.benchmark import scorecard as SC  # noqa: E402
from fidetype.benchmark import tracks as TR  # noqa: E402
from fidetype.benchmark.scoring import to_jsonable  # noqa: E402

DER = Path("C:/Users/zhang/bci-data/derived")
OWN = DER / "p6-02b-v02-entries"  # the only place this task writes per-unit files
assert OWN.name == "p6-02b-v02-entries"
OWN.mkdir(parents=True, exist_ok=True)
SUBS = OWN / "submissions"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
BOARD = REPO / "benchmark" / "results" / "v0.2"
V01 = REPO / "benchmark" / "results" / "v0.1"
LOGF = OWN / "run.log"
SEED = 0
ALPHA, DELTA = 0.05, 0.1
PY = sys.executable


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(obj), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def truth_path(track: str) -> Path:
    return OWN / "truth" / f"{track}.jsonl"


def load_truth(track: str) -> dict:
    p = truth_path(track)
    if not p.exists():
        raise SystemExit(f"missing {p}: run `python -m fidetype.benchmark truth {track} --data ... --out {p}` first")
    return SC.read_truth(p, track)


def v01(stem: str) -> dict:
    return json.loads((V01 / f"{stem}.json").read_text(encoding="utf-8"))


def save_info(name: str, info: dict) -> None:
    p = OUT / "stages.json"
    allr = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    allr[name] = info
    save_json(allr, p)


# ---------------------------------------------------------------------------
# Shared: one TrustPipeline -> per-unit decisions at fixed commit thresholds
# ---------------------------------------------------------------------------


def unit_outputs(pipe, decode, streams, truths) -> list[dict]:
    """Per unit: n-best texts, the M2-13 commit score and the fallback action (policy with commit_p = +inf).

    Commit iff score >= lambda reproduces the v0.1 entries (tools/benchmark/import_baselines.py, Items.arrays).
    """
    from fidetype.trust.policy import Action, DecisionPolicy
    from fidetype.trust.risk_control import commit_calibration_data

    T = pipe.frame_scaler.temperature
    pol = pipe.policy
    hi = DecisionPolicy(replace(pol.config, commit_p=math.inf), use_guard=pol.use_guard)
    inputs, texts, fb = [], [], []
    for s in streams:
        s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
        nb = decode(s2)
        an = pipe.analyze(nb)
        inputs.append(an.inputs)
        texts.append([str(t) for t in nb.texts] or [""])
        d = hi.decide(an.inputs, final_attempt=True)
        fb.append("abstain" if d.action == Action.ABSTAIN else "offer")
    sc, _loss, _ = commit_calibration_data(pol, inputs, truths)
    return [{"texts": t, "score": float(s), "fallback": f, "p_top1": float(i.p_top1)}
            for t, s, f, i in zip(texts, sc, fb, inputs)]


def top1_outputs(pipe, decode, streams) -> list[dict]:
    """Top-1 texts of an always-commit pipeline (frame scaler applied as in the harness)."""
    T = pipe.frame_scaler.temperature
    out = []
    for s in streams:
        nb = decode(pipe.frame_scaler.transform_stream(s) if T != 1.0 else s)
        out.append({"texts": [str(t) for t in nb.texts] or [""], "score": math.inf, "fallback": "offer",
                    "p_top1": float("nan")})
    return out


def rows_at(keys, outs, lam: float | None) -> list[dict]:
    """``lam`` None = always commit the top-1."""
    rows = []
    for k, o in zip(keys, outs):
        if lam is None or o["score"] >= lam:
            rows.append(SC.unit_row(k, o["texts"][:1], [o["p_top1"]], action="commit",
                                    score_semantics="calibrated_prob"))
        else:
            tx = o["texts"][:3]
            rows.append(SC.unit_row(k, tx, [o["p_top1"]] + [None] * (len(tx) - 1), action=o["fallback"],
                                    offer_k=3, score_semantics="calibrated_prob"))
    return rows


def guarantee_v01(card: dict, calibration_split: str) -> dict:
    g = dict(card.get("guarantee") or {"method": "none"})
    if g.get("method") not in ("crc", "ltt"):
        return {"method": "none"}
    out = {k: g[k] for k in ("method", "alpha", "delta", "n_cal", "scope", "threshold") if g.get(k) is not None}
    out["calibration_split"] = calibration_split
    return out


def write_entry(name: str, track: str, decoder: dict, policy: dict, guarantee: dict, regime: str, controls_basis: dict,
                rows, shuf, zer, notes: str = "", coverage: dict | None = None) -> None:
    man = SC.manifest_dict(track, decoder, policy=policy, guarantee=guarantee, regime=regime, controls=controls_basis,
                           coverage=coverage, notes=notes)
    man["entry_id"] = f"{track}/{name.split('__', 1)[1].replace('__', '/')}"
    SC.write_submission(SUBS / name, man, rows, {"shuffled": shuf, "zeros": zer})
    commits = sum(r["action"] == "commit" for r in rows)
    log(f"wrote {name}: {len(rows)} units, {commits} commits")


def commit_check(name: str, keys, outs, lam: float, items_test: dict | None) -> dict:
    """Compare the rerun commit decisions with the committed v0.1 per-trial scores (when they exist)."""
    on = np.array([o["score"] >= lam for o in outs])
    info = {"threshold": lam, "commits": int(on.sum())}
    if items_test is not None:
        ref = np.array([float(x) if x not in (None, "-inf") else -math.inf for x in items_test["score"]])
        same = np.allclose(np.nan_to_num([o["score"] for o in outs], neginf=-9), np.nan_to_num(ref, neginf=-9),
                           atol=1e-9)
        info["scores_equal_v01_items"] = bool(same)
        info["commits_v01"] = int((ref >= lam).sum())
    log(f"{name}: {info}")
    return info


# ---------------------------------------------------------------------------
# b2t25-t15: ours (m6-06) and published decoder
# ---------------------------------------------------------------------------


def stage_b2t() -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    t0 = time.time()
    track = "b2t25-t15"
    truth = load_truth(track)
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    best = tune["best"]
    dec = bt.Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}
    fi = [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in fit]
    keys = [TR.id_hash(track, f"t15-copytask-{t.index:04d}") for t in test]
    assert sorted(keys) == sorted(truth), "test trials != track test units"
    for k, t in zip(keys, test):
        assert truth[k]["text"] == t.truth_words, "truth text differs"
    truths = [t.truth_words for t in test]
    rng = np.random.default_rng(SEED)
    base = [streams[t.index] for t in test]
    nulls = {"real": base, "shuffled": [shuffle_stream(s, rng) for s in base],
             "zeros": [uniform_stream(s, rng, 0.05) for s in base]}
    info: dict = {"n_fit": len(fi), "n_test": len(test)}
    for tag, fn, items_name in (("ours", dec.words_fn, "b2t-ours"), ("published", dec.published_plus_fn,
                                                                       "b2t-published")):
        ts = time.time()
        items = json.loads((REPO / f"experiments/2026-11-11-m2-13-conformal/results/items-{items_name}.json")
                           .read_text(encoding="utf-8"))
        pipe = TrustPipeline(fn, HarnessConfig(seed=bt.SEED, user_config=user,
                                               max_wrong_commit=bt.CONFIG["max_wrong_commit"]))
        pipe.fit(fi, fi)
        outs = {}
        for cond, ss in nulls.items():
            if tag == "published":  # published_plus_fn reads the trial index from the stream meta
                ss = [NeuralTextStream(s.log_probs, s.frame_times, s.vocab, s.blank_id, s.source,
                                       {**s.meta, "fidetype.trial_index": t.index}, vocab_type=s.vocab_type)
                      for s, t in zip(ss, test)]
            outs[cond] = unit_outputs(pipe, fn, ss, truths)
        lams = {"trust": float(items["fit"]["lam_old"]),
                "crc": float(v01(f"b2t25-t15-copytask__{tag}__crc")["guarantee"]["threshold"]),
                "ltt": float(v01(f"b2t25-t15-copytask__{tag}__ltt")["guarantee"]["threshold"])}
        chk = {p: commit_check(f"b2t {tag} {p}", keys, outs["real"], lam, items["test"]) for p, lam in lams.items()}
        if tag == "ours":
            decoder = dict(v01("b2t25-t15-copytask__ours__crc")["decoder"])
            decoder["training_regime"] = "no training: decoding of the published RNN logits (CC0)"
            basis = {"shuffled": "decoder input level for our word decoder (the published RNN logit frames of each "
                     "test trial permuted in time, fidetype.trust.guard.shuffle_stream, seed 0); the RNN itself is "
                     "not ours and was not rerun",
                     "zeros": "near-uniform logits of the same length (uniform_stream, 0.05 noise) stand in for "
                     "zero neural input (the published RNN cannot be rerun on zero input)"}
        else:
            decoder = dict(v01("b2t25-t15-copytask__published__crc")["decoder"])
            basis = {"shuffled": "text-only decoder: the published sentence is fixed; only our gate score sees the "
                     "frame-shuffled logits. The CER cannot rise, so this control cannot pass (it shows that the "
                     "text does not depend on our input)",
                     "zeros": "text-only decoder: the published sentence on top of near-uniform logits (gate test "
                     "only; the CER cannot rise)"}
        notes = ("Same pipeline, fit and thresholds as the v0.1 entry (experiments/2026-11-10-b2t25-trust, M2-13 "
                 "items, tools/benchmark/import_baselines.py). cal = first half of each day, test = second half: "
                 "the test trials are later in the day, so cal and test are not exchangeable.")
        pol = {"always-commit": ({"name": "always-commit", "description": "commit the top-1 text on every trial"},
                                 None, {"method": "none"}),
               "trust": ({"name": "trust gate (plug-in fit)", "description": "commit threshold fitted on cal "
                          "(plug-in, no guarantee)"}, lams["trust"], {"method": "none"}),
               "crc": ({"name": "trust gate + CRC", "description": "commit threshold by conformal risk control, "
                        "alpha 0.05"}, lams["crc"], guarantee_v01(v01(f"b2t25-t15-copytask__{tag}__crc"), "cal")),
               "ltt": ({"name": "trust gate + LTT", "description": "commit threshold by Learn then Test, alpha "
                        "0.05, delta 0.1"}, lams["ltt"], guarantee_v01(v01(f"b2t25-t15-copytask__{tag}__ltt"),
                                                                        "cal"))}
        for p, (policy, lam, g) in pol.items():
            write_entry(f"b2t25-t15__{tag}__{p}", track, decoder, policy, g, "other" if tag == "ours" else
                        "personalised", basis, rows_at(keys, outs["real"], lam), rows_at(keys, outs["shuffled"], lam),
                        rows_at(keys, outs["zeros"], lam), notes)
        info[tag] = {"temperature": pipe.frame_scaler.temperature, "checks": chk,
                     "seconds": round(time.time() - ts, 1)}
    info["seconds"] = round(time.time() - t0, 1)
    save_info("b2t", info)
    return info


# ---------------------------------------------------------------------------
# spanishbcbl-meg (RESEARCH ONLY)
# ---------------------------------------------------------------------------


def stage_meg() -> dict:
    from fidetype.benchmark.registry import normalize
    from fidetype.benchmark.splits import load_split as load_split_v01
    from fidetype.eval.harness import TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    t0 = time.time()
    track = "spanishbcbl-meg"
    truth = load_truth(track)
    g1 = load_module("g1meg", REPO / "experiments/2026-11-11-g1-async-meg-trust/run.py")
    g1.Logger.path = OWN / "g1-meg.log"  # never write into the other experiment's folder
    root = Path(g1.CONFIG["streams"]["async"])
    dec, _kw = g1.make_decoder()
    val_raw, test_raw = g1.load_split(root, "val"), g1.load_split(root, "test")
    val = [g1.Item(s, r["target_text"]) for s, r in val_raw]
    test = [g1.Item(s, r["target_text"]) for s, r in test_raw]
    ids = load_split_v01("spanishbcbl-meg-async").ids("test")
    assert len(ids) == len(test)
    keys = [TR.id_hash(track, i) for i in ids]
    assert sorted(keys) == sorted(truth), "v0.1 test ids != v0.2 scored units"
    for k, it in zip(keys, test):
        assert normalize(truth[k]["text"], "char28") == normalize(it.text, "char28"), "truth text differs"
    truths = [it.text for it in test]
    ctl = np.load(g1.CONFIG["controls_npz"])
    base = [s for s, _ in test_raw]
    nulls = {"real": base,
             "shuffled": [g1.with_logprobs(s, ctl["shuffled__" + r["file"]], "shuffled_meg") for s, r in test_raw],
             "zeros": [g1.with_logprobs(s, ctl["zeros__" + r["file"]], "zeros_meg") for s, r in test_raw]}
    specs = g1.M2.policy_specs(UserConfig.aac_gaze(), g1.M2.MAX_WRONG_COMMIT, False)
    cache: dict = {}
    pipes = {}
    for name in ("commit", "trust"):
        pipes[name] = TrustPipeline(dec, specs[name], cache)
        pipes[name].fit(val, val)
    outs = {"commit": {c: top1_outputs(pipes["commit"], dec, ss) for c, ss in nulls.items()},
            "trust": {c: unit_outputs(pipes["trust"], dec, ss, truths) for c, ss in nulls.items()}}
    items = json.loads((REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json")
                       .read_text(encoding="utf-8"))
    stem = "spanishbcbl-meg-async__convctc-m-async__"
    lams = {"trust": float(items["fit"]["lam_old"]), "crc": float(v01(stem + "crc")["guarantee"]["threshold"]),
            "ltt": float(v01(stem + "ltt")["guarantee"]["threshold"])}
    chk = {p: commit_check(f"meg {p}", keys, outs["trust"]["real"], lam, items["test"]) for p, lam in lams.items()}
    decoder = dict(v01(stem + "crc")["decoder"])
    decoder.setdefault("training_regime", "trained on the train sentences of all participants (split by sentence)")
    basis = {"shuffled": "input level: the ConvCTC network rerun on time-shuffled MEG of each test trial (M1-09 "
             "`infer --control shuffled` outputs)",
             "zeros": "input level: the ConvCTC network rerun on all-zero MEG (M1-09 `infer --control zeros`)"}
    notes = ("RESEARCH ONLY (CC BY-NC 4.0 data). Same pipeline, fit (val) and thresholds as the v0.1 entry "
             "(experiments/2026-11-11-g1-async-meg-trust, tools/benchmark/import_baselines.py).")
    pol = {"always-commit": ("commit", {"name": "always-commit", "description": "commit the top-1 text on every "
                             "trial"}, None, {"method": "none"}),
           "trust": ("trust", {"name": "trust gate (plug-in fit)", "description": "commit threshold fitted on val "
                     "(plug-in, no guarantee)"}, lams["trust"], {"method": "none"}),
           "crc": ("trust", {"name": "trust gate + CRC", "description": "commit threshold by conformal risk "
                   "control, alpha 0.05"}, lams["crc"], guarantee_v01(v01(stem + "crc"), "val")),
           "ltt": ("trust", {"name": "trust gate + LTT", "description": "commit threshold by Learn then Test, "
                   "alpha 0.05, delta 0.1"}, lams["ltt"], guarantee_v01(v01(stem + "ltt"), "val"))}
    for p, (pn, policy, lam, g) in pol.items():
        o = outs[pn]
        write_entry(f"spanishbcbl-meg__convctc-m-async__{p}", track, decoder, policy, g, "other", basis,
                    rows_at(keys, o["real"], lam), rows_at(keys, o["shuffled"], lam), rows_at(keys, o["zeros"], lam),
                    notes)
    info = {"n_val": len(val), "n_test": len(test), "checks": chk,
            "temperatures": {n: p.frame_scaler.temperature for n, p in pipes.items()},
            "seconds": round(time.time() - t0, 1)}
    save_info("meg", info)
    return info


# ---------------------------------------------------------------------------
# toronto-semg
# ---------------------------------------------------------------------------

TORONTO_REGIME = {"calib": "session-calibrated", "xsession": "cross-session", "xsubject": "cross-subject"}


def stage_toronto() -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.guard import shuffle_stream
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    track = "toronto-semg"
    truth = load_truth(track)
    by_pt = {(r["group"], r["text"]): k for k, r in truth.items()}
    tm = load_module("toronto_trust", REPO / "experiments/2026-11-11-emg-toronto/trust.py")
    C = tm.CONFIG
    y, file_idx, files, minfo = tm.load_meta()
    period = float(minfo["inter_key_interval_s"]["median"])
    user = UserConfig.aac_gaze(chars_per_min=60.0 / period)
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
    for k, p in enumerate(pids):  # same plan as experiments/2026-11-11-emg-toronto/trust.py (seed, draw order)
        plan[p] = {"fit": tm.compose(fit_texts[k * per_p:(k + 1) * per_p], P[p]["fit"], rng, nfit),
                   "test": tm.compose(test_texts[k * per_p:(k + 1) * per_p], P[p]["test"], rng, ntest)}
    agg = json.loads((REPO / "experiments/2026-11-11-emg-toronto/results/trust.json").read_text(encoding="utf-8"))
    info: dict = {"conditions": {}}
    for cond in ("calib", "xsession", "xsubject"):
        tc = time.time()
        fit_run, test_run, desc = tm.CONDITIONS[cond]
        lg_fit, have_fit, _ = tm.load_logits(fit_run, len(y))
        lg_test, have_test, zeros_t = tm.load_logits(test_run, len(y))
        zero_vec = next(iter(zeros_t.values()))

        def items_of(which, lg, have):
            its, meta = [], []
            for p in pids:
                for t, idx in plan[p][which]:
                    assert have[idx].all()
                    its.append(Item(tm.make_stream(lg[idx], period, p, cond), t))
                    meta.append((p, t, idx))
            return its, meta

        fit_items, _ = items_of("fit", lg_fit, have_fit)
        test_items, test_meta = items_of("test", lg_test, have_test)
        order = np.random.default_rng(tm.SEED + 7).permutation(len(fit_items))
        fit_items = [fit_items[i] for i in order]
        A, Bv = fit_items[: len(fit_items) // 2], fit_items[len(fit_items) // 2:]
        kw = {**C["beam"], "lm_weight": agg["conditions"][cond]["lm_weight"]}  # tuned on fit-A in M6-07

        def decode_fn(s, kw=kw):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        keys = [by_pt[(p, t)] for p, t, _ in test_meta]
        assert sorted(keys) == sorted(truth), "composed test set != track test units"
        truths = [t for _, t, _ in test_meta]
        arng = np.random.default_rng(SEED)
        base = [it.stream(0) for it in test_items]
        nulls = {"real": base, "shuffled": [shuffle_stream(s, arng) for s in base],
                 "zeros": [tm.make_stream(np.repeat(zero_vec[None, :], len(idx), axis=0), period, p, cond)
                           for p, _, idx in test_meta]}
        cache: dict = {}
        cfgs = {"commit": dict(policy="always_commit"),
                "trust": dict(max_wrong_commit=C["max_wrong_commit"]),
                "crc": dict(max_wrong_commit=C["max_wrong_commit"], risk_control="crc")}
        res_c: dict = {"lm_weight": kw["lm_weight"]}
        decoder = dict(v01(f"toronto-semg-composed__cnn-{cond}__crc")["decoder"])
        basis = {"shuffled": "the key-window logit frames of each composed sentence permuted (shuffle_stream, seed "
                 "0); the CNN classifies each key window alone, so this equals shuffling the key windows of the "
                 "input",
                 "zeros": "input level: the CNN logits of an all-zero EMG window for every key"}
        notes = (f"{desc}. Composed sentences from isolated key presses: not natural typing. Same plan, decoder, "
                 "LM weight and fits as the v0.1 entry (experiments/2026-11-11-emg-toronto/trust.py).")
        for name, cfg in cfgs.items():
            pipe = TrustPipeline(decode_fn, HarnessConfig(seed=tm.SEED, user_config=user, **cfg), cache)
            pipe.fit(A, Bv)
            outs = {c: (top1_outputs(pipe, decode_fn, ss) if name == "commit" else
                        unit_outputs(pipe, decode_fn, ss, truths)) for c, ss in nulls.items()}
            if name == "commit":
                lam, policy, g = None, {"name": "always-commit", "description": "commit the top-1 text"}, \
                    {"method": "none"}
            else:
                lam = float(pipe.policy.config.commit_p)
                policy = ({"name": "trust gate (plug-in fit)", "description": "commit threshold fitted on fit half "
                           "B (plug-in, no guarantee)"} if name == "trust" else
                          {"name": "trust gate + CRC", "description": "commit threshold by conformal risk control, "
                           "alpha 0.05"})
                g = guarantee_v01(v01(f"toronto-semg-composed__cnn-{cond}__crc"), "cal") if name == "crc" else \
                    {"method": "none"}
                ref = agg["conditions"][cond]["policies"]["c_trust" if name == "trust" else "c_crc"]
                on = sum(o["score"] >= lam for o in outs["real"])
                res_c[name] = {"threshold": lam, "commits": on, "commit_rate": on / len(keys),
                               "commit_rate_v01": ref["rate_commit"]}
                log(f"toronto {cond} {name}: lam {lam} commits {on}/{len(keys)} (v0.1 rate {ref['rate_commit']:.4f})")
            write_entry(f"toronto-semg__cnn-{cond}__{'always-commit' if name == 'commit' else name}", track,
                        decoder, policy, g, TORONTO_REGIME[cond], basis, rows_at(keys, outs["real"], lam),
                        rows_at(keys, outs["shuffled"], lam), rows_at(keys, outs["zeros"], lam), notes)
        res_c["seconds"] = round(time.time() - tc, 1)
        info["conditions"][cond] = res_c
    info["seconds"] = round(time.time() - t0, 1)
    save_info("toronto", info)
    return info


# ---------------------------------------------------------------------------
# b2t25-t15 PARTIAL: M4-12 / M4-13 + drop-in guard on the val_eval trials that are track test units
# ---------------------------------------------------------------------------


def _day_offset(texts: dict, truth_rows: list[dict], norm) -> int:
    """Days between 2023-01-01 and the B2T '25 session date minus the copy-task post-implant day (majority)."""
    by = {}
    for r in truth_rows:
        by.setdefault(norm(r["text"]), []).append(int(r["group"][3:]))
    c: Counter = Counter()
    for s, parts in texts.items():
        d = (datetime.date(*map(int, s[4:].split("."))) - datetime.date(2023, 1, 1)).days
        for w in parts.get("val_eval", []):
            for day in by.get(norm(w), []):
                c[d - day] += 1
    (off, n), = c.most_common(1)
    return off


def stage_t15_model(model: str) -> dict:
    import fidetype.trust as ft

    t0 = time.time()
    track = "b2t25-t15"
    truth = load_truth(track)
    p1403 = load_module("p1403run", REPO / "experiments/2026-11-16-p14-03-replay-validation/run.py")
    p1405 = load_module("p1405run", REPO / "experiments/2026-11-16-p14-05-safe-wpm/run.py")
    p602 = load_module("p602run", REPO / "experiments/2026-11-16-p6-02-scorer/run.py")
    Bm = p1403.B
    norm = Bm.normalize_words
    d_in = DER / "m4-01-02-lookahead"
    sessions = json.loads((d_in / "sessions.json").read_text(encoding="utf-8"))
    texts = json.loads((d_in / "texts.json").read_text(encoding="utf-8"))
    if model == "m4-13":
        cal_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_select.npz"
        held_p = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
        if not held_p.exists():
            held_p = DER / "trust-reruns-m4-13" / "logprobs-m4-13-long0-val_eval.npz"
    else:
        cal_p = DER / "m2-19-trust-retune" / "logprobs-m2-19-m4-12-fixed0.npz"
        held_p = d_in / "logprobs-m4-12-fixed0.npz"
    for p in (cal_p, held_p):
        if not p.exists():
            raise SystemExit(f"missing {p}: has the decoder (and the trust-reruns CPU decode) finished?")
    rows_t = list(truth.values())
    off = _day_offset(texts, rows_t, norm)
    test_by: dict = {}
    for k, r in truth.items():
        test_by.setdefault((int(r["group"][3:]), norm(r["text"])), []).append(k)

    def day_of(sess: str) -> int:
        return (datetime.date(*map(int, sess[4:].split("."))) - datetime.date(2023, 1, 1)).days - off

    npz: dict = {}

    def part(path: Path, name: str):
        z = np.load(path)
        keys = p1405.t15_keys(path, sessions, name)
        out = []
        for k in keys:
            s, pp, i, _ = k.split("|")
            w = texts[s][pp][int(i)]
            out.append((k, z[k].astype(np.float32), w, p1403.ph_symbols(npz, d_in, s, pp, int(i)),
                        test_by.get((day_of(s), norm(w)), [])))
        return out

    cal = part(cal_p, "val_select")
    held = part(held_p, "val_eval")
    held_count = Counter((day_of(k.split("|")[0]), norm(w)) for k, _, w, _, _ in held)
    cal_keep = [c for c in cal if not c[4]]
    scored = [h for h in held if len(h[4]) == 1 and held_count[(day_of(h[0].split("|")[0]), norm(h[2]))] == 1]
    log(f"t15-{model}: day offset {off}; val_select {len(cal)} -> {len(cal_keep)} after dropping "
        f"{len(cal) - len(cal_keep)} track test trials; val_eval {len(held)} -> {len(scored)} scored track test units")
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    tune = bt.load_json("tune.json")
    dec = bt.Decoders([], {k: tune["best"][k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    fn = p1403.make_decode_fn(dec)
    guard = ft.calibrate([c[1] for c in cal_keep], [c[2] for c in cal_keep], alpha=ALPHA, delta=DELTA,
                         vocab=list(Bm.SYMBOL_VOCAB), blank=0, input_scale="log_probs", frame_period=0.08,
                         decode_fn=fn, stream_texts=[c[3] for c in cal_keep], decoder_name=f"p6-02b-t15-{model}",
                         modality="intracortical", name=f"p6-02b-t15-{model}", seed=SEED)
    log(f"t15-{model}: guard {guard.config_id} ({time.time() - t0:.0f}s)\n{guard.sheet}")
    guard.save(OUT / f"guard-t15-{model}.json")
    uni = math.log(1.0 / len(Bm.SYMBOL_VOCAB))
    rows, shuf, zer = [], [], []
    for n, (k, x, w, _, units) in enumerate(scored):
        u = units[0]
        rows.append(p602.guard_row(u, p602.decide(guard, x, f"{model}-{n}")))
        shuf.append(p602.guard_row(u, p602.decide(guard, p602.shuffled_frames(x, u), f"{model}-s{n}")))
        zer.append(p602.guard_row(u, p602.decide(guard, np.full_like(x, uni), f"{model}-z{n}")))
    sh = guard.sheet.to_dict()
    ckpt = {"m4-12": "runs/m4-12-fixed0/best.pt", "m4-13": "runs/m4-13-long0/best.pt"}[model]
    decoder = {"name": f"{model.upper()} causal T15 GRU-CTC + phoneme-to-word decoder (ours)", "version": model,
               "url": {"m4-12": "experiments/2026-11-14-m4-12-decoder-retrain",
                       "m4-13": "experiments/2026-11-15-m4-13-long-train"}[model],
               "weights_licence": "not released", "training_data": [
                   "B2T '25 HDF5 train partition (CC0); it holds about 368 of the 816 b2t25-t15 test trials, so "
                   "only the val_eval trials are scored"],
               "training_regime": "one participant; held-out trials of training sessions", "checkpoint": ckpt}
    man_g = {"method": "ltt", "alpha": sh.get("alpha"), "delta": sh.get("delta"), "n_cal": int(sh.get("n_ltt") or 0),
             "scope": "marginal over the scored val_eval trials; exchangeable val_select / val_eval",
             "calibration_split": "decoder val_select partition minus every b2t25-t15 test trial",
             "config_id": guard.config_id, "feasible": sh.get("feasible", True)}
    cov = {"subset": f"{len(scored)} of 816 test trials: only trials in the decoder's held-out val_eval partition "
           "(matched by day and sentence, one-to-one) are scored. The other test trials are in the decoder's train "
           "(about 368) or val_select (about 106) partitions, or have no match."}
    basis = {"shuffled": "decoder output level: the frames of each val_eval log-prob matrix permuted in time (seeded "
             "by the unit hash); the network was not rerun",
             "zeros": "decoder output level: uniform log-probs of the same length; the network was not run on zero "
             "input"}
    notes = (f"Drop-in guard (P14-03 recipe, as P14-05) calibrated on {len(cal_keep)} val_select trials (the "
             f"{len(cal) - len(cal_keep)} val_select trials that are track test units are removed). Checkpoint "
             "chosen on val_select PER. Not comparable with full-coverage entries.")
    write_entry(f"b2t25-t15__{model}__guard", track, decoder,
                {"name": "drop-in guard (P14-03 recipe)", "description": "fidetype.trust.calibrate, alpha 0.05, "
                 "delta 0.1, decode_fn = the T15 phoneme-to-word decoder"}, man_g, "other", basis, rows, shuf, zer,
                notes, coverage=cov)
    info = {"model": model, "day_offset": off, "n_val_select": len(cal), "n_cal_used": len(cal_keep),
            "n_val_eval": len(held), "n_scored": len(scored), "config_id": guard.config_id,
            "sheet": {k: sh.get(k) for k in ("n_items", "n_fit", "n_ltt", "feasible", "commit_threshold")},
            "commits": sum(r["action"] == "commit" for r in rows), "seconds": round(time.time() - t0, 1)}
    save_info(f"t15-{model}", info)
    return info


# ---------------------------------------------------------------------------
# Score with the one CLI command; table
# ---------------------------------------------------------------------------


def stage_score(only: str | None = None) -> dict:
    out = {}
    BOARD.mkdir(parents=True, exist_ok=True)
    for sub in sorted(SUBS.iterdir()):
        if not (sub / "submission.json").is_file() or (only and not sub.name.startswith(only)):
            continue
        track = json.loads((sub / "submission.json").read_text(encoding="utf-8"))["track"]
        card = BOARD / f"{sub.name}.json"
        cmd = [PY, "-m", "fidetype.benchmark", "score", track, str(sub), "--truth", str(truth_path(track)),
               "--out", str(card)]
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(REPO / "src")})
        log(f"score {sub.name}: exit {r.returncode}\n{r.stdout.strip()}\n{r.stderr.strip()[-400:]}")
        if r.returncode == 2 or not card.exists():
            raise SystemExit(f"score failed for {sub.name}")
        res = json.loads(card.read_text(encoding="utf-8"))
        out[sub.name] = {"exit": r.returncode, "status": res["status"], "certification": res.get("certification")}
    save_json(out, OUT / f"score{'-' + only if only else ''}.json")
    return out


def stage_table() -> str:
    def f(m, k, nd=3):
        x = (m.get(k) or {}).get("value")
        ci = (m.get(k) or {}).get("ci")
        if x is None:
            return "n/a"
        s = f"{x:.{nd}f}"
        if ci and None not in ci:
            s += f" [{ci[0]:.{nd}f}, {ci[1]:.{nd}f}]"
        return s

    L = ["| Entry | Units | CER | WER | eWPM [CI] | no-BCI | Safe WPM @ 0.05 | Wrong-commit [CI] | Error among commits "
         "| Commit rate | Controls (shuf / zeros / null) | Status |", "|" + "---|" * 12]
    for sub in sorted(SUBS.iterdir()):
        p = BOARD / f"{sub.name}.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        m, sw, c, cov = r["metrics"], r.get("safe_wpm") or {}, r["controls"], r["coverage"]
        swv = "n/a" if sw.get("value") is None else f"{sw['value']:.2f}"
        nc = c["null_commit"].get("commit_rate_zeros")
        L.append(f"| `{p.stem}` | {cov['n_covered']}/{cov['n_scored_units']} | {f(m, 'cer')} | {f(m, 'wer')} | "
                 f"{f(m, 'ewpm', 2)} | {f(m, 'gaze_ewpm', 2).split(' ')[0]} | {swv} ({sw.get('status')}; "
                 f"{sw.get('n_commits')} commits, {sw.get('n_wrong_commits')} wrong) | {f(m, 'wrong_commit_rate')} | "
                 f"{f(m, 'error_among_commits')} | {f(m, 'commit_rate')} | {c['shuffled']['status']} / "
                 f"{c['zeros']['status']} / {c['null_commit']['status']}" + (f" ({nc:.3f})" if nc is not None else "")
                 + f" | {r['status']} |")
    txt = "\n".join(L) + "\n"
    (OUT / "tables.md").write_text("# P6-02b v0.2 score cards (generated by run.py table)\n\n" + txt, encoding="utf-8")
    print(txt)
    return txt


STAGES = {"b2t": stage_b2t, "meg": stage_meg, "toronto": stage_toronto,
          "t15-m4-12": lambda: stage_t15_model("m4-12"), "t15-m4-13": lambda: stage_t15_model("m4-13"),
          "score": stage_score, "score-m4-13": lambda: stage_score("b2t25-t15__m4-13"), "table": stage_table}


def main() -> None:
    bad = [s for s in sys.argv[1:] if s not in STAGES]
    if bad or not sys.argv[1:]:
        raise SystemExit(f"stages: {list(STAGES)}")
    for st in sys.argv[1:]:
        t0 = time.time()
        log(f"stage {st} start")
        STAGES[st]()
        log(f"stage {st} done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
