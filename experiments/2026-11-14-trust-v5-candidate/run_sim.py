"""P5-07 on the simulator: all arms, controls, stability, end-to-end v5 (frames route), declaration check (e).

Plan: plan.md. Same 6 conditions, items, decoder and control draws as M3-01
(experiments/2026-11-14-m3-01-02-ablations/run_sim.py). Synthetic data only.
Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-trust-v5-candidate/run_sim.py --conds median/0.5,median/1.0 --out sim-a.json
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v5x as X  # noqa: E402

A, C, K, Q, V = X.A, X.C, X.K, X.Q, X.V
PRESETS = ("best", "median", "worst")
TEMPS = (0.5, 1.0, 2.0)
N_FIT, N_CAL, N_TEST, N_CTL = 200, 300, 300, 100
CTL_SEED = 20261114


def run_cond(preset: str, temp: float) -> dict:
    from fidetype.eval.harness import Item
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.lm import RETUNED, CharNgramLM, ctc_prefix_beam_search
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    from fidetype.trust.policy import Action
    from fidetype.trust.types import from_lm_hypotheses

    t0 = time.time()
    all_s = sentences(3400, seed=0)
    eval_s = all_s[40: 40 + N_FIT + N_CAL + N_TEST]
    lm = CharNgramLM(order=6).train(all_s[1000:])
    kw = dict(RETUNED, n_best=10)

    def dec(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm, **kw), stream.meta)

    pi, ti = PRESETS.index(preset), TEMPS.index(temp)
    sd = pi * 10 + ti
    tag = f"sim-{preset}-T{temp}"
    cached = C.DiskCachedDecoder(dec, tag)
    cached.d = {}
    for src in (A.CACHE5 / f"decode-{tag}.pkl", X.CACHE6 / f"decode-{tag}.pkl"):
        if src.exists():
            cached.d.update(pickle.loads(src.read_bytes()))
    cached.path = X.CACHE6 / f"decode-{tag}.pkl"
    sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temp), seed=sd)

    def item(i, s):
        seed = 100_000 * sd + 1000 * i
        return Item(sim.simulate(s, seed=seed).stream, s, regen=lambda a, s=s, seed=seed: sim.simulate(s, seed=seed + a).stream)

    items = [item(i, s) for i, s in enumerate(eval_s)]
    fitA, cal, test = items[:N_FIT], items[N_FIT:N_FIT + N_CAL], items[N_FIT + N_CAL:]
    user = UserConfig()
    X.log(f"sim {preset}/T={temp}: fit-A {len(fitA)}, cal {len(cal)}, test {len(test)}")
    # test-time controls: the M3-01 draw
    rng = np.random.default_rng(CTL_SEED + sd)
    idx = sorted(rng.choice(len(test), N_CTL, replace=False).tolist())
    base = [test[i].stream(0) for i in idx]
    truths = [test[i].text for i in idx]
    perm = rng.permutation(N_CTL)
    for i in range(N_CTL):
        if truths[perm[i]] == truths[i]:
            perm[i], perm[(i + 1) % N_CTL] = perm[(i + 1) % N_CTL], perm[i]
    nulls = {"real": base, "intent_mismatch": [base[j] for j in perm], "frame_shuffled": [shuffle_stream(s, rng) for s in base],
             "uniform": [uniform_stream(s, rng, 0.05) for s in base], "zero_standin": [A.zero_standin(s) for s in base]}
    pipe = X.fit_sweep(cached, user, (fitA, fitA), base={"max_attempts": 1})
    ev = X.evaluate_split(pipe, cal, test, np.zeros(len(test), int), nulls, truths, lambda s, i: cached(s))
    lam_of = ev.pop("_lam_of")
    ev["stability"] = X.stability(pipe)
    cached.save()
    # end to end: library fit = arm v5; frozen v5 through the streaming layer (frames route)
    p5 = V.fit_trust_v5(cached, fitA, cal, V.V5Options(), user_config=user, seed=C.SEED, max_attempts=1)
    cfg5, lam5, _ = lam_of["v5"]
    e2e = {"lib_commit_p": C.clean(p5.policy.config.commit_p), "arm_lambda": C.clean(lam5),
           "lib_commit_p_equals_arm": bool(p5.policy.config.commit_p == lam5),
           "lib_policy_equals_arm": {k: v for k, v in p5.policy.config.__dict__.items() if k != "commit_p"}
           == {k: v for k, v in cfg5.items() if k != "commit_p"}}
    blk = X.item_meta(p5, test)["block"]
    plain = X.with_policy(p5, p5.policy.config.__dict__)
    tab5 = Q.M13.item_table(plain, test)
    a, _ = A.arrays(tab5, p5.policy.config.commit_p, blk)
    fz = V.freeze_v5(p5, f"sim-{preset}-T{temp}-v5")
    decs = A.replay(fz, [("sim", it.stream(0), None, None) for it in test], "frames", decode_fn=cached)
    com = np.array([d.action == Action.COMMIT for d in decs])
    e2e.update({"config_id_v5": fz.config_id, "lib_n_commit": int(a["com"].sum()), "arm_n_commit": ev["arms"]["v5"]["n_commit"],
                "stream_n_commit": int(com.sum()), "stream_equal_to_batch_with_gate": int((com == a["com"].astype(bool)).sum()),
                "n": len(test)})
    # (e): raw-decoding producer on the hypothesis route
    mm = A.mismatch(plain)
    tab_mm = Q.M13.item_table(mm, test)
    nb_raw = [mm.decode(it, 0) for it in test]
    e2e["declaration"] = {}
    for mode in ("warn", "abstain", "offer-only"):
        d2 = A.replay(fz, [("sim", it.stream(0), nb, {"decoder": "sim-beam"}) for it, nb in zip(test, nb_raw)], "hypothesis",
                      declaration_check=mode)
        mt = A.stream_metrics(mm, test, d2, tab_mm, p5.policy.config.commit_p)
        e2e["declaration"][mode] = {k: mt[k] for k in ("n", "n_commit", "n_wrong_commit", "ewpm", "commit_rate", "wrong_commit")}
        e2e["declaration"][mode]["actions"] = {k: int(v) for k, v in zip(*np.unique([d.action.value for d in d2], return_counts=True))}
    ev["end_to_end"] = e2e
    cached.save()
    v4, v5 = ev["arms"]["v4"], ev["arms"]["v5"]
    X.log(f"  {preset}/T={temp} done ({time.time() - t0:.0f}s): v4 {v4['n_wrong_commit']}/{v4['n_commit']} eWPM {v4['ewpm']:.2f}; "
          f"v5 {v5['n_wrong_commit']}/{v5['n_commit']} eWPM {v5['ewpm']:.2f}; controls v5: "
          + ",".join(f"{c} {d['v5']['n_commit']}" for c, d in ev["controls"].items())
          + f"; e2e lib=arm {e2e['lib_commit_p_equals_arm']}, stream equal {e2e['stream_equal_to_batch_with_gate']}/{len(test)}")
    return X.clean_eval(ev)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="median/0.5,median/1.0,median/2.0,worst/0.5,worst/1.0,worst/2.0")
    ap.add_argument("--out", default="sim.json")
    a = ap.parse_args()
    X.set_log(X.OUT / f"run-{Path(a.out).stem}.log")
    out_p = X.OUT / a.out
    res = A.load_json(out_p) if out_p.exists() else {"env": A.env_note(), "conditions": {}}
    for c in a.conds.split(","):
        if c in res["conditions"]:
            continue
        p, t = c.split("/")
        res["conditions"][c] = run_cond(p, float(t))
        X.dump(res, out_p)
    X.log("done")


if __name__ == "__main__":
    main()
