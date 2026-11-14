"""P5-07 on Brain-to-Text '25 (T15): fixed splits A / B, controls, stability, end-to-end v5, declaration
check (e), and the 240-trial fit sets. Plan: plan.md (committed before this run).

Run (repo root), one process per decoder and stage:
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_b2t.py --which ours --stage fixed
  ... --which published --stage fixed ; ... --stage small
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V
_spec = importlib.util.spec_from_file_location("m302_run_b2t", X.REPO / "experiments/2026-11-14-m3-01-02-ablations/run_b2t.py")
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)
SMALL_N, SMALL_DRAWS, SMALL_SEED = 240, 10, 240


def context():
    ctx = M.b2t_context()
    cd = ctx.cached[0]
    p6 = X.CACHE6 / "decode-b2t-words-main.pkl"
    if p6.exists():
        import pickle
        try:
            cd.d.update(pickle.loads(p6.read_bytes()))
        except Exception:  # noqa: BLE001
            pass
    cd.path = p6
    return ctx


def decoders(ctx, which: str, atest=None):
    from fidetype.streams.spec import NeuralTextStream
    fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn

    def null_decode(s2, i):
        if which == "published":
            s3 = NeuralTextStream(s2.log_probs, s2.frame_times, s2.vocab, s2.blank_id, s2.source,
                                  {**s2.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s2.vocab_type)
            return ctx.dec.published_plus_fn(s3)
        return ctx.dec.words_fn(s2)
    return fn, null_decode


def stage_fixed(which: str) -> None:
    ctx = context()
    T = ctx.items(ctx.test)
    days = np.array(ctx.days_test)
    atest, nulls = M.controls(ctx)
    truths = [t.truth_words for t in atest]
    fn, null_decode = decoders(ctx, which, atest)
    m302 = A.load_json(A.OUT / f"b2t-{which}.json")
    res: dict = {"which": which, "env": A.env_note(), "splits": {}}
    for split in ("A", "B"):
        t0 = time.time()
        ia, ib = M.split_idx(ctx, split)
        fa = ctx.items([ctx.fit[i] for i in ia])
        cal = ctx.items([ctx.fit[i] for i in ib])
        X.log(f"b2t-{which} split {split}: fit-A {len(fa)}, cal {len(cal)}, test {len(T)}")
        pipe = X.fit_sweep(fn, ctx.user, (fa, fa))
        ev = X.evaluate_split(pipe, cal, T, days, nulls, truths, null_decode)
        v4_old = m302["splits"][split]["rows"]["v4 (baseline)"]
        v4_new = ev["arms"]["v4"]
        same = (v4_old["n_wrong_commit"], v4_old["n_commit"]) == (v4_new["n_wrong_commit"], v4_new["n_commit"])
        ev["v4_reproduces_m302"] = bool(same)
        assert same, f"v4 differs from M3-02: {v4_old['n_wrong_commit']}/{v4_old['n_commit']} vs {v4_new['n_wrong_commit']}/{v4_new['n_commit']}"
        ev["stability"] = X.stability(pipe)
        lam_of = ev.pop("_lam_of")
        if split == "A":
            ev["end_to_end"] = end_to_end(ctx, which, fn, fa, cal, T, ev, lam_of)
        res["splits"][split] = X.clean_eval(ev)
        ctx.cached[0].save()
        v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
        X.log(f"  split {split} done ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
              f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f} lam {v5['lambda']}; "
              f"controls v5: " + ",".join(f"{c} {d['v5']['n_commit']}" for c, d in ev["controls"].items()))
        X.dump(res, X.OUT / f"b2t-{which}.json")
    X.log("done")


def end_to_end(ctx, which, fn, fa, cal, T, ev, lam_of) -> dict:
    """fit_trust_v5 (library) = arm v5; frozen v5 through the streaming layer; declaration check (e)."""
    t0 = time.time()
    p5 = V.fit_trust_v5(fn, fa, cal, V.V5Options(), user_config=ctx.user, seed=C.SEED)
    cfg5, lam5, _ = lam_of["v5"]
    out = {"lib_commit_p": C.clean(p5.policy.config.commit_p), "arm_lambda": C.clean(lam5),
           "lib_policy_equals_arm": {k: v for k, v in p5.policy.config.__dict__.items() if k != "commit_p"}
           == {k: v for k, v in cfg5.items() if k != "commit_p"}}
    out["lib_commit_p_equals_arm"] = bool(p5.policy.config.commit_p == lam5)
    # batch commits of the library pipeline (gate applied)
    blk = X.item_meta(p5, T)["block"]
    tab5 = Q.M13.item_table(X.with_policy(p5, p5.policy.config.__dict__), T)
    a, _ = A.arrays(tab5, p5.policy.config.commit_p, blk)
    out["lib_n_commit"], out["arm_n_commit"] = int(a["com"].sum()), ev["arms"]["v5"]["n_commit"]
    out["lib_n_wrong_commit"], out["arm_n_wrong_commit"] = int(round(a["wc"].sum())), ev["arms"]["v5"]["n_wrong_commit"]
    fz = V.freeze_v5(p5, f"b2t25-{which}-splitA-v5")
    fz4 = A.frozen_v4(X.with_policy(p5, {**cfg5, "commit_p": lam5}), lam5, f"b2t25-{which}-splitA-v4")
    out["config_id_v5"], out["config_id_same_numbers_v4_recipe"] = fz.config_id, fz4.config_id
    sids = [f"day-{d}" for d in ctx.days_test]
    streams = [it.stream(0) for it in T]
    nb_good = [p5.decode(it, 0) for it in T]
    good = {"decoder": "fidetype-b2t-" + which, "frame_temperature": float(p5.frame_scaler.temperature), "config_id": fz.config_id}
    pol_plain = X.with_policy(p5, p5.policy.config.__dict__)
    decs = A.replay(fz, [(s, st, nb, good) for s, st, nb in zip(sids, streams, nb_good)], "hypothesis", declaration_check="offer-only")
    m = A.stream_metrics(pol_plain, T, decs, tab5, p5.policy.config.commit_p)
    from fidetype.trust.policy import Action
    com = np.array([d.action == Action.COMMIT for d in decs])
    out["stream_matched"] = {"n_commit": int(com.sum()), "equal_to_batch_with_gate": int((com == a["com"].astype(bool)).sum()),
                             "n": len(decs), "ewpm": m["ewpm"], "n_wrong_commit": m["n_wrong_commit"],
                             "n_declaration_mismatch": int(sum((d.provenance.get("declaration") or {}).get("status") == "mismatch" for d in decs))}
    # (e) raw-decoding producer, declaration without temperature (= 1.0) -> mismatch
    mm = A.mismatch(pol_plain)
    tab_mm = Q.M13.item_table(mm, T)
    nb_raw = [mm.decode(it, 0) for it in T]
    bad = {"decoder": "fidetype-b2t-" + which}
    out["declaration"] = {}
    for mode in ("warn", "abstain", "offer-only"):
        d2 = A.replay(fz, [(s, st, nb, bad) for s, st, nb in zip(sids, streams, nb_raw)], "hypothesis", declaration_check=mode)
        mt = A.stream_metrics(mm, T, d2, tab_mm, p5.policy.config.commit_p)
        out["declaration"][mode] = {k: mt[k] for k in ("n", "n_commit", "n_wrong_commit", "ewpm", "commit_rate", "wrong_commit")}
        out["declaration"][mode]["n_mismatch"] = int(sum((d.provenance.get("declaration") or {}).get("status") == "mismatch" for d in d2))
        out["declaration"][mode]["actions"] = {k: int(v) for k, v in zip(*np.unique([d.action.value for d in d2], return_counts=True))}
    X.log(f"  end to end ({time.time() - t0:.0f}s): lib commit_p {out['lib_commit_p']} arm {out['arm_lambda']}; commits lib "
          f"{out['lib_n_commit']} arm {out['arm_n_commit']}; stream equal {out['stream_matched']['equal_to_batch_with_gate']}/{len(T)}; "
          f"decl " + ", ".join(f"{k}: {v['n_commit']} commits eWPM {v['ewpm']:.2f}" for k, v in out["declaration"].items()))
    return out


def stage_small(which: str) -> None:
    ctx = context()
    T = ctx.items(ctx.test)
    days = np.array(ctx.days_test)
    fn, _ = decoders(ctx, which)
    ia, ib = M.split_idx(ctx, "A")
    cal = ctx.items([ctx.fit[i] for i in ib])
    rng = np.random.default_rng(SMALL_SEED)
    draws = [sorted(rng.choice(len(ia), SMALL_N, replace=False).tolist()) for _ in range(SMALL_DRAWS)]
    out_p = X.OUT / f"b2t-small-{which}.json"
    res = A.load_json(out_p) if out_p.exists() else {"which": which, "env": A.env_note(), "n_fit": SMALL_N, "draws": {}}
    for d, sub in enumerate(draws):
        if str(d) in res["draws"]:
            continue
        t0 = time.time()
        fa = ctx.items([ctx.fit[ia[j]] for j in sub])
        pipe = X.fit_sweep(fn, ctx.user, (fa, fa))
        ev = X.evaluate_split(pipe, cal, T, days)
        ev.pop("_lam_of")
        res["draws"][str(d)] = X.split_row(ev) | {"stability": X.stability(pipe)}
        ctx.cached[0].save()
        X.dump(res, out_p)
        v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
        X.log(f"  small {which} draw {d} ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
              f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f}; never {ev['arms']['never commit']['ewpm']:.2f}")
    X.log("done")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True)
    ap.add_argument("--stage", default="fixed")
    a = ap.parse_args()
    X.set_log(X.OUT / f"run-b2t-{a.stage}-{a.which}.log")
    {"fixed": stage_fixed, "small": stage_small}[a.stage](a.which)


if __name__ == "__main__":
    main()
