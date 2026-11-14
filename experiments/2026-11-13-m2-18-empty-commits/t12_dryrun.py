"""M2-18: why the Paper 1 v4 recipe committed empty texts in the T12 v2 validation dry run, and the fix.

Stage ``dryrun`` repeats the M3-28 validation dry run (decoder-validation blocks only;
``experiments/2026-11-13-confirmatory-t12-v2/run.py --stage dryrun``) in memory, with
the same code path, the same seeds and the same control draws. It checks that the frozen
config id equals the M3-28 one (tcfg-845934f0792ad9fc), then:

1. traces every COMMIT on the test blocks and on each control: empty / short top-1 text,
   number of n-best candidates, calibrated p_top1, guard risk and its two terms;
2. counts what each policy rule would do to those commits (commit_max_risk values of the
   default grid, abstain_risk values);
3. runs the same pipeline with the opt-in commit gate (M2-18; variants A, B, C) and reports
   commits, wrong commits and control commits before and after.

Stage ``pool`` explains why the trust-pool run did NOT commit the uniform controls: it
loads the frozen trust-pool config (results/trust-config-t12.json, tcfg-9fb4c81c5931e00c),
rebuilds the uniform controls with the same draw as run.py and records the reason of
every decision. No new test decision is made; the confirmatory result does not change.

Writes only aggregate numbers to results/ (no text, no signals). Reads the derived
files of M3-28 (outside the repo). CPU only, 2 threads.

  .venv\\Scripts\\python.exe -I experiments/2026-11-13-m2-18-empty-commits/t12_dryrun.py --stage dryrun
  .venv\\Scripts\\python.exe -I experiments/2026-11-13-m2-18-empty-commits/t12_dryrun.py --stage pool
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import importlib.util
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
T12 = REPO / "experiments" / "2026-11-13-confirmatory-t12-v2"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(REPO / "src"))


def load_run():
    spec = importlib.util.spec_from_file_location("t12v2run", T12 / "run.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = load_run()
from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline  # noqa: E402
from fidetype.interact.simulated_user import UserConfig  # noqa: E402
from fidetype.trust.content import CommitGate, GatedPolicy  # noqa: E402
from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig  # noqa: E402
from fidetype.trust.guard import shuffle_stream, uniform_stream  # noqa: E402
from fidetype.trust.policy import Action, DecisionPolicy  # noqa: E402

CFG = R.CFG
ALPHA, DELTA = R.ALPHA, R.DELTA
LOGF = OUT / "t12.log"
DRYRUN_ID = "tcfg-845934f0792ad9fc"
POOL_ID = "tcfg-9fb4c81c5931e00c"
RULES = {"gate A: no empty text": CommitGate(1, 0), "gate B: no empty text, guard risk < 1": CommitGate(1, 0, 1.0),
         "gate C: >= 2 words": CommitGate(1, 2)}


def log(*a) -> None:
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def dump(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=1, default=str, allow_nan=True) + "\n", encoding="utf-8")


def controls(test: list, seed: int) -> dict[str, list]:
    """The M3-28 control items, same draw order as run.py (P3)."""
    crng = np.random.default_rng(seed)
    out = {"frame_shuffled": [], "uniform": [], "intent_mismatch": []}
    perm = crng.permutation(len(test))
    for i in range(len(perm)):
        if test[perm[i]].text == test[i].text:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    for i, it in enumerate(test):
        st = it.stream(0)
        out["frame_shuffled"].append(Item(shuffle_stream(st, crng), it.text))
        out["uniform"].append(Item(uniform_stream(st, crng, CFG["uniform_jitter"]), it.text))
        out["intent_mismatch"].append(Item(test[perm[i]].stream(0), it.text))
    return out


def trace(pipe, items, cache) -> dict:
    """Signals of the top-1 for every item, and what the v4 policy did with it (aggregates only)."""
    pol = pipe.policy
    rows = []
    for it in items:
        key = (id(it), 0)
        an = cache.get(key)
        if an is None:
            an = pipe.analyze(pipe.decode(it, 0))
            cache[key] = an
        x = an.inputs
        top = x.texts[0] if x.texts else ""
        d = pol.decide(x, final_attempt=True)
        rows.append({
            "commit": d.action == Action.COMMIT, "empty": top.strip() == "", "n_words": len(top.split()),
            "n_chars": sum(not c.isspace() for c in top), "n_cand": len(x.texts), "p_top1": float(x.p_top1),
            "risk": float(x.guard_risk), "low_term": float(an.guard.low_evidence_frac) if math.isfinite(an.guard.low_evidence_frac) else None,
            "consistency": float(an.guard.consistency), "set_size": x.set_size, "action": d.action.value,
            "wrong": top != it.text,
        })
    return summarize_trace(rows)


def q(v, p):
    return float(np.percentile(v, p)) if len(v) else None


def summarize_trace(rows: list[dict]) -> dict:
    n = len(rows)
    emp = [r for r in rows if r["empty"]]
    com = [r for r in rows if r["commit"]]
    com_e = [r for r in com if r["empty"]]
    out = {
        "n": n, "n_top1_empty": len(emp), "n_commit": len(com), "n_commit_empty": len(com_e),
        "n_commit_1word": sum(r["n_words"] == 1 for r in com), "n_commit_le3chars": sum(r["n_chars"] <= 3 for r in com),
        "actions": dict(Counter(r["action"] for r in rows)),
        "empty_top1": {
            "n_cand_counts": dict(Counter(r["n_cand"] for r in emp)),
            "p_top1_min_median_max": [q([r["p_top1"] for r in emp], 0), q([r["p_top1"] for r in emp], 50), q([r["p_top1"] for r in emp], 100)],
            "guard_risk_values": dict(Counter(round(r["risk"], 4) for r in emp)),
            "consistency_min_median": [q([r["consistency"] for r in emp], 0), q([r["consistency"] for r in emp], 50)],
            "set_size_counts": dict(Counter(r["set_size"] for r in emp)),
        },
        "nonempty_commits": {
            "guard_risk_min_median_max": [q([r["risk"] for r in com if not r["empty"]], p) for p in (0, 50, 100)],
            "n_words_counts": dict(Counter(r["n_words"] for r in com if not r["empty"])),
        },
    }
    # what other grid values would have done with the committed items
    for cmr in (0.1, 0.2, 0.3, 0.5, 0.99):
        out[f"commits_kept_if_commit_max_risk_{cmr}"] = sum(r["risk"] <= cmr for r in com)
    for ar in (0.6, 0.8):
        out[f"commits_abstained_if_abstain_risk_{ar}"] = sum(r["risk"] >= ar for r in com)
    return out


def rule_rows(pipe, sets: dict, caches: dict) -> dict:
    """rec_summary of the v4 policy and of each gated variant on each item set."""
    pols = {"v4 (no rule)": pipe.policy}
    for name, rule in RULES.items():
        pols[name] = GatedPolicy.wrap(pipe.policy, rule)
    res = {}
    for sname, its in sets.items():
        res[sname] = {}
        for pname, pol in pols.items():
            m = R.rec_summary(pipe.run_items(its, pol, caches[sname]))
            res[sname][pname] = {k: m[k] for k in ("n", "n_commit", "n_wrong_commit", "n_commit_empty", "n_commit_nonempty",
                                                   "n_wrong_commit_nonempty", "wrong_commit", "commit_rate",
                                                   "error_among_commits", "ewpm", "rate_offer", "abstain_rate")}
    return res


def stage_dryrun() -> None:
    t0 = time.time()
    D = R.Data("logprobs-val")
    bt = R.load_b2t25()
    dec = R.decoders(bt)
    S = D.sessions
    fit_s = [s for s in S if D.role[s] == "fit_a"]
    cal_s = [s for s in S if D.role[s] == "calibration"]
    test_s = [s for s in S if D.role[s] == "test"]
    fitA, _ = D.items("val", fit_s)
    cal, _ = D.items("val", cal_s)
    test, _ = D.items("val", test_s)
    cpm = D.prep["speech_rate_decoder_train"]["chars_per_min"]
    user = UserConfig.aac_gaze(chars_per_min=cpm)
    cfg = HarnessConfig(seed=CFG["trust"]["seed"], user_config=user, max_wrong_commit=ALPHA, use_guard=True)
    pipe = TrustPipeline(dec.words_fn, cfg, {})
    pipe.fit(fitA, fitA)
    r = pipe.calibrate_commit(cal, method="ltt", alpha=ALPHA, delta=DELTA, combine="max")
    frozen = FrozenTrustConfig.from_pipeline(pipe, name="t12-confirmatory-m3-28", recipe=PAPER1_V4_RECIPE)
    log("dryrun refit", frozen.config_id, "policy", json.dumps(frozen.policy), "ltt", r.threshold)
    assert frozen.config_id == DRYRUN_ID, f"refit differs from M3-28 dry run: {frozen.config_id}"
    sets = {"test": test, **controls(test, CFG["controls_seed"])}
    caches = {k: {} for k in sets}
    traces = {k: trace(pipe, v, caches[k]) for k, v in sets.items()}
    for k, v in traces.items():
        log("trace", k, json.dumps({kk: v[kk] for kk in ("n_top1_empty", "n_commit", "n_commit_empty")}))
    rows = rule_rows(pipe, sets, caches)
    # the same rule also on the calibration half: the LTT bound is not touched (loss can only go down)
    cal_cache: dict = {}
    cal_rows = rule_rows(pipe, {"calibration": cal}, {"calibration": cal_cache})
    gated = frozen.with_commit_gate(1, 0, 1.0)
    res = {
        "what": "M3-28 T12 v2 validation dry run (decoder-validation blocks), refitted in memory; M2-18 trace and fix",
        "frozen_config_id": frozen.config_id, "frozen_config_id_expected": DRYRUN_ID,
        "gated_config_id": gated.config_id, "policy": frozen.policy, "ltt_threshold": r.threshold,
        "n": {k: len(v) for k, v in sets.items()}, "trace": traces, "rules": rows, "calibration_rules": cal_rows,
        "seconds": round(time.time() - t0, 1),
    }
    dump(res, OUT / "t12-dryrun.json")
    for s, d in rows.items():
        log("rules", s, json.dumps({p: (m["n_commit"], m["n_wrong_commit"], m["n_commit_empty"]) for p, m in d.items()}))


def stage_pool() -> None:
    """Why the trust-pool run did not commit the uniform controls (diagnosis only)."""
    t0 = time.time()
    D = R.Data("logprobs")
    bt = R.load_b2t25()
    dec = R.decoders(bt)
    test_s = [s for s in D.sessions if D.role[s] == "test"]
    # same global trial index as run.py: items of fit_a and calibration first
    for role in ("fit_a", "calibration"):
        for s in [s for s in D.sessions if D.role[s] == role]:
            D.gidx += len(D.texts[s]["pool"])
    test, _ = D.items("pool", test_s)
    fz = FrozenTrustConfig.load(T12 / "results" / "trust-config-t12.json")
    assert fz.config_id == POOL_ID, fz.config_id
    comp = fz.build()
    cpm = D.prep["speech_rate_decoder_train"]["chars_per_min"]
    pipe = TrustPipeline(dec.words_fn, HarnessConfig(seed=CFG["trust"]["seed"], user_config=UserConfig.aac_gaze(chars_per_min=cpm)), {})
    pipe.frame_scaler, pipe.calibrator, pipe.conformal, pipe.guard, pipe.policy = (
        comp.frame_scaler, comp.calibrator, comp.conformal, comp.guard, comp.policy)
    uni = controls(test, CFG["controls_seed"])["uniform"]
    cache: dict = {}
    tr = trace(pipe, uni, cache)
    # the reasons of the frozen policy, and the same inputs under commit_max_risk 1.0 (the dry-run value)
    loose = DecisionPolicy(fz.with_policy(commit_max_risk=1.0).build().policy.config, use_guard=True)
    reasons, loose_commit, loose_empty = Counter(), 0, 0
    for it in uni:
        x = cache[(id(it), 0)].inputs
        d = pipe.policy.decide(x, final_attempt=True)
        reasons[f"{d.action.value}: {re.sub(r'[0-9][0-9.]*', '#', d.reason)}"] += 1
        dl = loose.decide(x, final_attempt=True)
        if dl.action == Action.COMMIT:
            loose_commit += 1
            loose_empty += (x.texts[0].strip() == "")
    res = {"what": "trust-pool uniform controls under the frozen trust-pool config (diagnosis; no new test decision)",
           "config_id": fz.config_id, "policy": fz.policy, "trace": tr, "decision_reasons": dict(reasons),
           "same_inputs_commit_max_risk_1.0": {"n_commit": loose_commit, "n_commit_empty": loose_empty},
           "seconds": round(time.time() - t0, 1)}
    dump(res, OUT / "t12-pool-uniform.json")
    log("pool uniform", json.dumps({"trace": {k: tr[k] for k in ("n_top1_empty", "n_commit")}, "reasons": dict(reasons),
                                    "loose": [loose_commit, loose_empty]}))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["dryrun", "pool"])
    a = ap.parse_args()
    {"dryrun": stage_dryrun, "pool": stage_pool}[a.stage]()


if __name__ == "__main__":
    main()
