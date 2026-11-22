r"""P13-13 (gap 85): refit, freeze and check the 30 pre-P5-23 trust cards.

The build steps (experiments/2026-11-17-p6-02b-v02-entries/run.py, stages b2t / meg / toronto, and the v0.1
source experiments) fitted a TrustPipeline in memory and kept only the decisions. This script:

1. refits each TrustPipeline with the build-step settings (same data, split, seed, decoder and fit);
2. sets the card's commit threshold (b2t / meg: the v0.1 plug-in, CRC and LTT thresholds, recomputed here from
   the refit calibration scores; toronto: the fitted pipeline itself) and freezes it with
   ``FrozenTrustConfig.from_pipeline`` (numbers and settings only);
3. writes each frozen config to ``<out>/configs/<name>.json`` and loads it back;
4. rebuilds a pipeline from the LOADED file only, decides every test unit (real, shuffled, zeros) and compares
   action, top-1 text and score with the card's submission rows (v0.2, read only) and with the committed v0.1
   per-trial scores or aggregates.

Per-stage results (counts only) go to <derived>/p13-13/stages/<stage>.json (checkpoint: a stage that has a
result file is skipped). Counts, thresholds and ids go to <out>/results.json. No text, no per-unit data in <out>.

  .venv\Scripts\python.exe -m fidetype.utils.isolation run --class background --threads 2 -- \
      .venv\Scripts\python.exe -I experiments/2026-11-21-p13-13-refreeze-cards/run.py --repo . \
      --out experiments/2026-11-21-p13-13-refreeze-cards/results meg toronto b2t summary

Then ``tools/benchmark/add_rerun_recipes.py --refrozen --write`` writes the ids into the cards.
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import argparse  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--derived", default="C:/Users/zhang/bci-data/derived/p13-13")
ap.add_argument("stages", nargs="+")
A = ap.parse_args()

REPO = Path(A.repo).resolve()
OUT = Path(A.out).resolve()
DER_OWN = Path(A.derived)
assert DER_OWN.name == "p13-13", "write only into the own derived folder"
sys.path.insert(0, str(REPO / "src"))
CONFIGS = OUT / "configs"
CONFIGS.mkdir(parents=True, exist_ok=True)
STAGES = DER_OWN / "stages"
STAGES.mkdir(parents=True, exist_ok=True)
LOGF = DER_OWN / "refreeze.log"
SUBS = Path("C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/submissions")  # READ ONLY
V01 = REPO / "benchmark" / "results" / "v0.1"
V02 = REPO / "benchmark" / "results" / "v0.2"
P602B = "experiments/2026-11-17-p6-02b-v02-entries/run.py"
SEED = 0
ALPHA, DELTA = 0.05, 0.1

from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def card(folder: Path, stem: str) -> dict:
    return json.loads((folder / f"{stem}.json").read_text(encoding="utf-8"))


def fnum(x):
    if x is None:
        return None
    x = float(x)
    if math.isnan(x):
        return "nan"
    if math.isinf(x):
        return "inf" if x > 0 else "-inf"
    return x


# ---------------------------------------------------------------------------
# Freeze, save, load, rebuild, decide, compare
# ---------------------------------------------------------------------------


def rc_record(res, combine: str) -> dict:
    """The risk-control record of a threshold that was chosen outside the pipeline fit (M2-13 style)."""
    return {"method": res.method, "alpha": res.alpha, "delta": res.delta, "threshold": res.threshold,
            "feasible": bool(res.feasible), "n": int(res.n), "bound": res.bound, "combine": combine}


def freeze(pipe, name: str, recipe: dict, commit_p: float | None = None, rc: dict | None = None) -> FrozenTrustConfig:
    cfg = FrozenTrustConfig.from_pipeline(pipe, name=name, recipe=recipe)
    if commit_p is not None:
        cfg = cfg.with_policy(commit_p=float(commit_p))
    if rc is not None:
        cfg = replace(cfg, risk_control=rc)
    return cfg


def save_load(cfg: FrozenTrustConfig, cards: list[str]) -> FrozenTrustConfig:
    """Write <out>/configs/<name>.json (config + id + the cards it backs) and load it back from disk."""
    p = CONFIGS / f"{cfg.name}.json"
    doc = {"schema": "fidetype.p13-13.card-config/0.1", "config_id": cfg.config_id, "cards": cards,
           "config": cfg.to_dict()}
    p.write_text(json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n", encoding="utf-8")
    back = FrozenTrustConfig.from_dict(json.loads(p.read_text(encoding="utf-8"))["config"])
    assert back.config_id == cfg.config_id, (cfg.name, back.config_id, cfg.config_id)
    return back


def pipe_from(cfg: FrozenTrustConfig, decode_fn):
    """A TrustPipeline whose fitted state comes ONLY from the loaded frozen config."""
    from fidetype.eval.harness import HarnessConfig, TrustPipeline
    from fidetype.trust.policy import PolicyConfig

    hc = HarnessConfig(use_guard=cfg.use_guard, word_max_alternatives=cfg.word_max_alternatives,
                       policy="always_commit" if cfg.policy_class == "always_commit" else "trust",
                       policy_config=PolicyConfig(**cfg.policy) if cfg.policy else None)
    p = TrustPipeline(decode_fn, hc)
    c = cfg.build()
    p.frame_scaler, p.calibrator, p.conformal, p.guard, p.policy = (c.frame_scaler, c.calibrator, c.conformal,
                                                                   c.guard, c.policy)
    return p


class Decoded:
    """Decode each stream once per frame temperature (the decode does not depend on the policy)."""

    def __init__(self, decode_fn):
        self.fn = decode_fn
        self.cache: dict = {}

    def get(self, pipe, s):
        T = pipe.frame_scaler.temperature
        k = (id(s), round(T, 12))
        if k not in self.cache:
            self.cache[k] = (self.fn(pipe.frame_scaler.transform_stream(s) if T != 1.0 else s), s)
        return self.cache[k][0]


def decide_all(pipe, dec: Decoded, streams) -> list[dict]:
    from fidetype.trust.policy import Action

    out = []
    for s in streams:
        nb = dec.get(pipe, s)
        an = pipe.analyze(nb)
        d = pipe.policy.decide(an.inputs, final_attempt=True)
        act = "commit" if d.action == Action.COMMIT else ("abstain" if d.action == Action.ABSTAIN else "offer")
        texts = [str(t) for t in nb.texts] or [""]
        out.append({"action": act, "top1": texts[0], "p": float(an.inputs.p_top1)})
    return out


def read_rows(path: Path) -> dict:
    rows = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            r = json.loads(line)
            rows[r["unit"]] = r
    return rows


def compare_sub(sub: str, keys: list[str], dec: dict[str, list[dict]]) -> dict:
    """Compare our decisions with the card's submission rows (real + controls). Counts only."""
    out = {}
    for cond, fn in (("real", "units.jsonl"), ("shuffled", "controls/shuffled.jsonl"),
                     ("zeros", "controls/zeros.jsonl")):
        rows = read_rows(SUBS / sub / fn)
        n_act = n_txt = n_score = 0
        max_dp = 0.0
        for k, d in zip(keys, dec[cond]):
            r = rows[k]
            n_act += r["action"] != d["action"]
            n_txt += r["nbest"][0]["text"] != d["top1"]
            sc = r["nbest"][0].get("score")
            if sc is not None and math.isfinite(d["p"]):
                dp = abs(sc - round(d["p"], 6))
                max_dp = max(max_dp, dp)
                n_score += dp > 1e-6
        out[cond] = {"n": len(keys), "commits": sum(d["action"] == "commit" for d in dec[cond]),
                     "commits_card": sum(r["action"] == "commit" for r in rows.values()),
                     "action_mismatch": n_act, "top1_mismatch": n_txt, "score_mismatch": n_score,
                     "max_abs_score_diff": max_dp}
    out["equal"] = all(out[c]["action_mismatch"] == 0 and out[c]["top1_mismatch"] == 0 and
                       out[c]["score_mismatch"] == 0 for c in ("real", "shuffled", "zeros"))
    return out


def compare_v01_items(dec_real: list[dict], items_test: dict, lam: float) -> dict:
    ref = np.array([float(x) if x not in (None, "-inf") else -math.inf for x in items_test["score"]])
    ref_c = ref >= lam
    ours = np.array([d["action"] == "commit" for d in dec_real])
    return {"n": int(len(ref)), "commits": int(ours.sum()), "commits_v01": int(ref_c.sum()),
            "decision_mismatch": int((ours != ref_c).sum()), "equal": bool((ours == ref_c).all())}


def card_numbers(stem_v01: str, stem_v02: str) -> dict:
    out = {}
    for tag, folder, stem in (("v0.1", V01, stem_v01), ("v0.2", V02, stem_v02)):
        c = card(folder, stem)
        g, s, m = c.get("guarantee") or {}, c.get("safe_wpm") or {}, c["metrics"]
        out[tag] = {"card": f"{folder.name}/{stem}", "threshold": g.get("threshold"), "n_cal": g.get("n_cal"),
                    "n_trials": c.get("n_trials"), "n_commits": s.get("n_commits"),
                    "commit_rate": (m.get("commit_rate") or {}).get("value")}
    return out


def save_stage(name: str, info: dict) -> None:
    (STAGES / f"{name}.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")


def thresholds_from(pipe, items, truths):
    """(scores, crc result, ltt result) on the calibration items, as tools/benchmark/import_baselines.py."""
    from fidetype.trust.risk_control import commit_calibration_data, crc_threshold, ltt_threshold

    inputs = [pipe.analyze(pipe.decode(it, 0)).inputs for it in items]
    s, c, f = commit_calibration_data(pipe.policy, inputs, truths)
    return s, crc_threshold(s, c, ALPHA, f), ltt_threshold(s, c, ALPHA, DELTA, f)


def score_match(s: np.ndarray, ref_list) -> dict:
    ref = np.array([float(x) if x not in (None, "-inf") else -math.inf for x in ref_list])
    a, b = np.nan_to_num(s, neginf=-9.0), np.nan_to_num(ref, neginf=-9.0)
    return {"n": int(len(ref)), "equal_1e-9": bool(len(a) == len(b) and np.allclose(a, b, atol=1e-9)),
            "max_abs_diff": float(np.max(np.abs(a - b))) if len(a) == len(b) else None}


# ---------------------------------------------------------------------------
# Stage b2t (b2t25-t15 and b2t25-t15-copytask: ours / published x trust / crc / ltt = 12 cards)
# ---------------------------------------------------------------------------


def stage_b2t() -> dict:
    from fidetype.benchmark import tracks as TR
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream

    t0 = time.time()
    track = "b2t25-t15"
    bt = load_module("b2t25run", REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    prep, tune = bt.load_json("prep.json"), bt.load_json("tune.json")
    trials = bt.load_trials()
    fit, test = bt.split(trials)
    best = tune["best"]
    decs = bt.Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in fit + test}
    fi = [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in fit]
    keys = [TR.id_hash(track, f"t15-copytask-{t.index:04d}") for t in test]
    fit_truths = [t.truth_words for t in fit]
    rng = np.random.default_rng(SEED)
    base = [streams[t.index] for t in test]
    nulls = {"real": base, "shuffled": [shuffle_stream(s, rng) for s in base],
             "zeros": [uniform_stream(s, rng, 0.05) for s in base]}
    info: dict = {"n_fit": len(fi), "n_test": len(test)}
    for tag, fn, items_name in (("ours", decs.words_fn, "b2t-ours"),
                                ("published", decs.published_plus_fn, "b2t-published")):
        ts = time.time()
        items = json.loads((REPO / f"experiments/2026-11-11-m2-13-conformal/results/items-{items_name}.json")
                           .read_text(encoding="utf-8"))
        hc = HarnessConfig(seed=bt.SEED, user_config=user, max_wrong_commit=bt.CONFIG["max_wrong_commit"])
        pipe = TrustPipeline(fn, hc)
        pipe.fit(fi, fi)
        s_cal, crc, ltt = thresholds_from(pipe, fi, fit_truths)
        lam_trust = float(pipe.policy.config.commit_p)
        v01 = {p: card(V01, f"b2t25-t15-copytask__{tag}__{p}") for p in ("crc", "ltt")}
        thr = {"trust": {"refit": lam_trust, "card": float(items["fit"]["lam_old"])},
               "crc": {"refit": crc.threshold, "card": v01["crc"]["guarantee"]["threshold"]},
               "ltt": {"refit": ltt.threshold, "card": v01["ltt"]["guarantee"]["threshold"]}}
        for p in thr:
            thr[p]["equal"] = bool(thr[p]["refit"] == thr[p]["card"])
        log(f"b2t {tag}: T {pipe.frame_scaler.temperature} thresholds {thr}")
        ss_by = {}
        for cond, ss in nulls.items():
            if tag == "published":
                ss = [NeuralTextStream(s.log_probs, s.frame_times, s.vocab, s.blank_id, s.source,
                                       {**s.meta, "fidetype.trial_index": t.index}, vocab_type=s.vocab_type)
                      for s, t in zip(ss, test)]
            ss_by[cond] = ss
        dec = Decoded(fn)
        recipe_base = {"refit": "P13-13 (gap 85)", "build": f"{P602B} stage b2t (v0.2) = M2-13 items "
                       "(experiments/2026-11-11-m2-13-conformal) + tools/benchmark/import_baselines.py (v0.1)",
                       "decoder": f"experiments/2026-11-10-b2t25-trust {tag}",
                       "fit": "TrustPipeline.fit(fit, fit): first half of each day, plug-in policy grid, "
                              "max_wrong_commit 0.05, seed 0"}
        res_tag = {"temperature": pipe.frame_scaler.temperature, "thresholds": thr,
                   "cal_scores_vs_items": score_match(s_cal, items["fit"]["score"]), "policies": {}}
        for p in ("trust", "crc", "ltt"):
            name = f"p13-13-b2t25-t15-{tag}-{p}"
            if p == "trust":
                cfg = freeze(pipe, name, {**recipe_base, "commit_threshold": "plug-in grid commit_p (lam_old)"})
            else:
                res = crc if p == "crc" else ltt
                cfg = freeze(pipe, name, {**recipe_base, "commit_threshold": f"{p.upper()} lambda on the fit half, "
                             f"alpha 0.05{', delta 0.1' if p == 'ltt' else ''} (replaces the grid commit_p)"},
                             commit_p=res.threshold, rc=rc_record(res, "replace"))
            stems = (f"b2t25-t15-copytask__{tag}__{p}", f"b2t25-t15__{tag}__{p}")
            loaded = save_load(cfg, [f"v0.1/{stems[0]}", f"v0.2/{stems[1]}"])
            lp = pipe_from(loaded, fn)
            dd = {c: decide_all(lp, dec, ss_by[c]) for c in ("real", "shuffled", "zeros")}
            lam = float(loaded.policy["commit_p"])
            r = {"config_id": loaded.config_id, "commit_p": fnum(lam),
                 "v0.2": compare_sub(stems[1], keys, dd), "v0.1": compare_v01_items(dd["real"], items["test"], lam),
                 "cards": card_numbers(*stems)}
            log(f"b2t {tag} {p}: {loaded.config_id} v0.2 equal {r['v0.2']['equal']} v0.1 equal {r['v0.1']['equal']}"
                f" commits {r['v0.2']['real']['commits']}/{r['v0.2']['real']['commits_card']}")
            res_tag["policies"][p] = r
        res_tag["seconds"] = round(time.time() - ts, 1)
        info[tag] = res_tag
    info["seconds"] = round(time.time() - t0, 1)
    return info


# ---------------------------------------------------------------------------
# Stage meg (spanishbcbl-meg and spanishbcbl-meg-async: trust / crc / ltt = 6 cards)
# ---------------------------------------------------------------------------


def stage_meg() -> dict:
    from fidetype.benchmark import tracks as TR
    from fidetype.benchmark.splits import load_split as load_split_v01
    from fidetype.eval.harness import TrustPipeline
    from fidetype.interact.simulated_user import UserConfig

    t0 = time.time()
    track = "spanishbcbl-meg"
    g1 = load_module("g1meg", REPO / "experiments/2026-11-11-g1-async-meg-trust/run.py")
    g1.Logger.path = DER_OWN / "g1-meg.log"  # never write into another experiment's folder
    root = Path(g1.CONFIG["streams"]["async"])
    fn, _kw = g1.make_decoder()
    val_raw, test_raw = g1.load_split(root, "val"), g1.load_split(root, "test")
    val = [g1.Item(s, r["target_text"]) for s, r in val_raw]
    ids = load_split_v01("spanishbcbl-meg-async").ids("test")
    assert len(ids) == len(test_raw)
    keys = [TR.id_hash(track, i) for i in ids]
    ctl = np.load(g1.CONFIG["controls_npz"])
    nulls = {"real": [s for s, _ in test_raw],
             "shuffled": [g1.with_logprobs(s, ctl["shuffled__" + r["file"]], "shuffled_meg") for s, r in test_raw],
             "zeros": [g1.with_logprobs(s, ctl["zeros__" + r["file"]], "zeros_meg") for s, r in test_raw]}
    specs = g1.M2.policy_specs(UserConfig.aac_gaze(), g1.M2.MAX_WRONG_COMMIT, False)
    pipe = TrustPipeline(fn, specs["trust"], {})
    pipe.fit(val, val)
    s_cal, crc, ltt = thresholds_from(pipe, val, [it.text for it in val])
    items = json.loads((REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json")
                       .read_text(encoding="utf-8"))
    stem1 = "spanishbcbl-meg-async__convctc-m-async__"
    v01 = {p: card(V01, stem1 + p) for p in ("crc", "ltt")}
    lam_trust = float(pipe.policy.config.commit_p)
    thr = {"trust": {"refit": lam_trust, "card": float(items["fit"]["lam_old"])},
           "crc": {"refit": crc.threshold, "card": v01["crc"]["guarantee"]["threshold"]},
           "ltt": {"refit": ltt.threshold, "card": v01["ltt"]["guarantee"]["threshold"]}}
    for p in thr:
        thr[p]["equal"] = bool(thr[p]["refit"] == thr[p]["card"])
    log(f"meg: T {pipe.frame_scaler.temperature} thresholds {thr}")
    dec = Decoded(fn)
    recipe_base = {"refit": "P13-13 (gap 85)", "build": f"{P602B} stage meg (v0.2) = "
                   "experiments/2026-11-11-g1-async-meg-trust items + tools/benchmark/import_baselines.py (v0.1)",
                   "decoder": "ConvCTC-M async (M1-09 r4b-full-medium) + Spanish char 6-gram beam",
                   "fit": "TrustPipeline.fit(val, val), M2 policy spec 'trust' (aac_gaze, max_wrong_commit 0.05)"}
    info: dict = {"n_val": len(val), "n_test": len(test_raw), "temperature": pipe.frame_scaler.temperature,
                  "thresholds": thr, "cal_scores_vs_items": score_match(s_cal, items["fit"]["score"]),
                  "policies": {}}
    for p in ("trust", "crc", "ltt"):
        name = f"p13-13-spanishbcbl-meg-convctc-m-async-{p}"
        if p == "trust":
            cfg = freeze(pipe, name, {**recipe_base, "commit_threshold": "plug-in grid commit_p (lam_old)"})
        else:
            res = crc if p == "crc" else ltt
            cfg = freeze(pipe, name, {**recipe_base, "commit_threshold": f"{p.upper()} lambda on val, alpha 0.05"
                         f"{', delta 0.1' if p == 'ltt' else ''} (replaces the grid commit_p)"},
                         commit_p=res.threshold, rc=rc_record(res, "replace"))
        stems = (stem1 + p, f"spanishbcbl-meg__convctc-m-async__{p}")
        loaded = save_load(cfg, [f"v0.1/{stems[0]}", f"v0.2/{stems[1]}"])
        lp = pipe_from(loaded, fn)
        dd = {c: decide_all(lp, dec, nulls[c]) for c in ("real", "shuffled", "zeros")}
        lam = float(loaded.policy["commit_p"])
        r = {"config_id": loaded.config_id, "commit_p": fnum(lam), "v0.2": compare_sub(stems[1], keys, dd),
             "v0.1": compare_v01_items(dd["real"], items["test"], lam), "cards": card_numbers(*stems)}
        log(f"meg {p}: {loaded.config_id} v0.2 equal {r['v0.2']['equal']} v0.1 equal {r['v0.1']['equal']}")
        info["policies"][p] = r
    info["seconds"] = round(time.time() - t0, 1)
    return info


# ---------------------------------------------------------------------------
# Stage toronto (toronto-semg and toronto-semg-composed: 3 regimes x trust / crc = 12 cards)
# ---------------------------------------------------------------------------

TORONTO_REGIME = {"calib": "session-calibrated", "xsession": "cross-session", "xsubject": "cross-subject"}


def stage_toronto() -> dict:
    from fidetype.benchmark import scorecard as SC
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
    from fidetype.trust.guard import shuffle_stream
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    track = "toronto-semg"
    truth = SC.read_truth(Path("C:/Users/zhang/bci-data/derived/p6-02b-v02-entries/truth") / f"{track}.jsonl",
                          track)  # read only
    by_pt = {(r["group"], r["text"]): k for k, r in truth.items()}
    tm = load_module("toronto_trust", REPO / "experiments/2026-11-11-emg-toronto/trust.py")
    tm.LOG = DER_OWN / "toronto-trust.log"  # never write into another experiment's folder
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
    for k, p in enumerate(pids):
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

        def items_of(which, lg, have, cond=cond):
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
        Af, Bv = fit_items[: len(fit_items) // 2], fit_items[len(fit_items) // 2:]
        kw = {**C["beam"], "lm_weight": agg["conditions"][cond]["lm_weight"]}

        def decode_fn(s, kw=kw):
            return from_lm_hypotheses(ctc_prefix_beam_search(s, lm, **kw), s.meta, confidence_variant="frame")

        keys = [by_pt[(p, t)] for p, t, _ in test_meta]
        assert sorted(keys) == sorted(truth)
        arng = np.random.default_rng(SEED)
        base = [it.stream(0) for it in test_items]
        nulls = {"real": base, "shuffled": [shuffle_stream(s, arng) for s in base],
                 "zeros": [tm.make_stream(np.repeat(zero_vec[None, :], len(idx), axis=0), period, p, cond)
                           for p, _, idx in test_meta]}
        cache: dict = {}
        # the commit pipeline is fitted first in the build step; it shares the decode cache only (no state)
        cfgs = {"trust": dict(max_wrong_commit=C["max_wrong_commit"]),
                "crc": dict(max_wrong_commit=C["max_wrong_commit"], risk_control="crc")}
        dec = Decoded(decode_fn)
        res_c: dict = {"lm_weight": kw["lm_weight"], "policies": {}}
        stages_ref = json.loads((REPO / "experiments/2026-11-17-p6-02b-v02-entries/results/stages.json")
                                .read_text(encoding="utf-8"))["toronto"]["conditions"][cond]
        for name, cfgd in cfgs.items():
            pipe = TrustPipeline(decode_fn, HarnessConfig(seed=tm.SEED, user_config=user, **cfgd), cache)
            pipe.fit(Af, Bv)
            cname = f"p13-13-toronto-semg-cnn-{cond}-{name}"
            recipe = {"refit": "P13-13 (gap 85)", "build": f"{P602B} stage toronto (v0.2) = "
                      "experiments/2026-11-11-emg-toronto/trust.py (v0.1)",
                      "decoder": f"key-press CNN ({cond}) + English char 6-gram beam, lm_weight {kw['lm_weight']}",
                      "fit": "TrustPipeline.fit(fit half A, fit half B), composed sentences, seed 0, "
                             "max_wrong_commit 0.05" + (", risk_control crc (combine max)" if name == "crc" else "")}
            cfg = freeze(pipe, cname, recipe)
            p_stem = "trust" if name == "trust" else "crc"
            stems = (f"toronto-semg-composed__cnn-{cond}__{p_stem}", f"toronto-semg__cnn-{cond}__{p_stem}")
            loaded = save_load(cfg, [f"v0.1/{stems[0]}", f"v0.2/{stems[1]}"])
            lp = pipe_from(loaded, decode_fn)
            dd = {c: decide_all(lp, dec, nulls[c]) for c in ("real", "shuffled", "zeros")}
            commits = sum(d["action"] == "commit" for d in dd["real"])
            v01c = card(V01, stems[0])
            v01_rate = (v01c["metrics"].get("commit_rate") or {}).get("value") or 0.0
            ref_thr = stages_ref[name]["threshold"]
            fr = pipe.fit_report
            r = {"config_id": loaded.config_id, "commit_p": fnum(loaded.policy["commit_p"]),
                 "commit_p_build": ref_thr,
                 "commit_p_equal": (ref_thr is None and not math.isfinite(loaded.policy["commit_p"])) or
                                   (ref_thr is not None and float(loaded.policy["commit_p"]) == float(ref_thr)),
                 "risk_control": {k: fnum(v) if isinstance(v, float) else v for k, v in loaded.risk_control.items()},
                 "v0.2": compare_sub(stems[1], keys, dd),
                 "v0.1": {"n": len(keys), "commits": commits, "commit_rate": commits / len(keys),
                          "commit_rate_v01": v01_rate, "commits_v01": round(v01_rate * len(keys)),
                          "equal": abs(commits / len(keys) - v01_rate) < 1e-12},
                 "cards": card_numbers(*stems)}
            if name == "crc":
                thr_card = (v01c.get("guarantee") or {}).get("threshold")
                got = fr.get("risk_control_threshold")
                r["crc_threshold"] = {"refit": fnum(got), "card_v01": thr_card,
                                      "equal": (thr_card is None and (got is None or not math.isfinite(got))) or
                                               (thr_card is not None and got is not None and float(got) == thr_card)}
            log(f"toronto {cond} {name}: {loaded.config_id} v0.2 equal {r['v0.2']['equal']} v0.1 equal "
                f"{r['v0.1']['equal']} commits {commits}")
            res_c["policies"][name] = r
        res_c["seconds"] = round(time.time() - tc, 1)
        info["conditions"][cond] = res_c
    info["seconds"] = round(time.time() - t0, 1)
    return info


# ---------------------------------------------------------------------------
# Summary: <out>/results.json (counts, thresholds, ids)
# ---------------------------------------------------------------------------


def stage_summary() -> dict:
    allr = {}
    for st in ("b2t", "meg", "toronto"):
        p = STAGES / f"{st}.json"
        if p.exists():
            allr[st] = json.loads(p.read_text(encoding="utf-8"))
    cards = []

    def add(pol: dict, thr_equal: bool | None):
        for tag in ("v0.1", "v0.2"):
            c = pol["cards"][tag]
            eq = pol["v0.2"]["equal"] if tag == "v0.2" else pol["v0.1"]["equal"]
            cards.append({"card": c["card"], "config_id": pol["config_id"], "decisions_equal": bool(eq),
                          "threshold_equal": thr_equal})

    for tag in ("ours", "published"):
        if "b2t" in allr:
            for p, pol in allr["b2t"][tag]["policies"].items():
                add(pol, allr["b2t"][tag]["thresholds"][p]["equal"])
    if "meg" in allr:
        for p, pol in allr["meg"]["policies"].items():
            add(pol, allr["meg"]["thresholds"][p]["equal"])
    if "toronto" in allr:
        for cond, rc in allr["toronto"]["conditions"].items():
            for name, pol in rc["policies"].items():
                add(pol, bool(pol["commit_p_equal"] and pol.get("crc_threshold", {"equal": True})["equal"]))
    summ = {"n_cards": len(cards), "n_configs": len({c["config_id"] for c in cards}),
            "n_decisions_equal": sum(c["decisions_equal"] for c in cards),
            "n_threshold_equal": sum(bool(c["threshold_equal"]) for c in cards), "cards": cards, "stages": allr}
    (OUT / "results.json").write_text(json.dumps(summ, indent=1) + "\n", encoding="utf-8")
    log(f"summary: {summ['n_cards']} cards, {summ['n_configs']} configs, decisions equal {summ['n_decisions_equal']}"
        f", thresholds equal {summ['n_threshold_equal']}")
    return summ


RUN = {"b2t": stage_b2t, "meg": stage_meg, "toronto": stage_toronto}

for st in A.stages:
    if st == "summary":
        stage_summary()
        continue
    if (STAGES / f"{st}.json").exists():
        log(f"stage {st}: result exists, skipped (checkpoint)")
        continue
    t = time.time()
    log(f"stage {st} start")
    save_stage(st, RUN[st]())
    log(f"stage {st} done ({time.time() - t:.0f}s)")
