"""M3-01 / M3-02 on the simulator: all arms, controls, declaration mismatch, streaming replay.

Plan: plan.md. ``NoisyDecoderSimulator`` presets median and worst x
``confidence_temperature`` 0.5 / 1.0 / 2.0 (seeds as M2: 10 * preset index +
temperature index). Template sentences ``sentences(3400, seed=0)``: eval =
sentences 40..839 (fit-A 200, calibration 300, test 300); the 6-gram char LM
is trained on sentences 1000.. (no overlap by index; template sentences can
repeat, so the LM is in-domain and optimistic, as in M2). Decoder:
``ctc_prefix_beam_search`` RETUNED, n_best 10.

Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-m3-01-02-ablations/run_sim.py --conds median/0.5,median/1.0
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abl as A  # noqa: E402

C, K, Q = A.C, A.K, A.Q
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
    cached.path = A.CACHE5 / f"decode-{tag}.pkl"
    if cached.path.exists():
        import pickle
        cached.d = pickle.loads(cached.path.read_bytes())
    sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temp), seed=sd)

    def item(i, s):
        seed = 100_000 * sd + 1000 * i
        return Item(sim.simulate(s, seed=seed).stream, s, regen=lambda a, s=s, seed=seed: sim.simulate(s, seed=seed + a).stream)

    items = [item(i, s) for i, s in enumerate(eval_s)]
    fitA, cal, test = items[:N_FIT], items[N_FIT:N_FIT + N_CAL], items[N_FIT + N_CAL:]
    user = UserConfig()
    A.log(f"sim {preset}/T={temp}: fit-A {len(fitA)}, cal {len(cal)}, test {len(test)}")
    # One attempt per item (as the real-data runs and the streaming layer with max_attempts=1):
    # the item tables assume the commit / fallback mix of a single attempt.
    ft = A.fit_four(cached, user, (fitA, fitA), cal, test, base={"max_attempts": 1})
    pipes, tabs = ft["pipes"], ft["tabs"]
    groups = np.zeros(len(test), int)  # one session per condition
    blk = A.gate_block(pipes["c1g1"], test)
    rows = A.arm_rows(tabs, test_groups=groups, gate_blk=blk)
    lam_v4 = A.lambdas(tabs["c1g1"]["cal"])["LTT max"]
    mm = A.mismatch(pipes["c1g1"])
    tab_mm = Q.M13.item_table(mm, test)
    a, _ = A.arrays(tab_mm, lam_v4)
    rows["declaration off: raw-decoded hypotheses"] = {**A.summarise(a), "lambda": C.clean(lam_v4), "pipe": "mismatch",
                                                      "rule": "LTT max (v4)"}
    cached.save()
    # end to end: frozen v4 through the streaming layer (frames route), and the declaration check (hypothesis route)
    fz = A.frozen_v4(pipes["c1g1"], lam_v4, f"sim-{preset}-T{temp}-v4")
    jobs = [("sim", it.stream(0), None, None) for it in test]
    decs = A.replay(fz, jobs, "frames", decode_fn=cached)
    stream = {"config_id": fz.config_id, **A.stream_metrics(pipes["c1g1"], test, decs, tabs["c1g1"]["test"], lam_v4)}
    nb_raw = [mm.decode(it, 0) for it in test]
    decs_a = A.replay(fz, [("sim", it.stream(0), nb, {"decoder": "sim-beam"}) for it, nb in zip(test, nb_raw)], "hypothesis",
                      declaration_check="abstain")
    stream_decl = A.stream_metrics(mm, test, decs_a, tab_mm, lam_v4)
    rows["declaration abstain: raw-decoded hypotheses"] = {
        "n": len(test), "n_commit": stream_decl["n_commit"], "n_wrong_commit": stream_decl["n_wrong_commit"],
        "commit_rate": stream_decl["commit_rate"], "wrong_commit": stream_decl["wrong_commit"], "ewpm": stream_decl["ewpm"],
        "wrong_commit_cp95": list(K.clopper_pearson(stream_decl["n_wrong_commit"], len(test))),
        "wrong_commit_cp95_one_sided_upper": K.upper_one_sided(stream_decl["n_wrong_commit"], len(test)),
        "pipe": "stream", "rule": "LTT max (v4) + declaration abstain"}
    # controls
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
    lams = {k: A.lambdas(v["cal"]) for k, v in tabs.items()}
    controls = A.control_rows(pipes, lams, nulls, lambda s, i: cached(s), truths, groups=np.zeros(N_CTL, int),
                              extra_pipes={"declaration off: raw-decoded hypotheses": (mm, lam_v4)})
    cached.save()
    v = rows["v4 (baseline)"]
    A.log(f"  {preset}/T={temp} done ({time.time() - t0:.0f}s): T fit {tabs['c1g1']['T']:.3f}; v4 wc {v['wrong_commit']:.4f} "
          f"commit {v['commit_rate']:.3f} eWPM {v['ewpm']:.2f}; stream commits {stream['n_commit']} equal "
          f"{stream['commit_equal_to_batch']}/{len(test)}; decl-off wc {rows['declaration off: raw-decoded hypotheses']['wrong_commit']:.4f}")
    return {"rows": rows, "T": {k: x["T"] for k, x in tabs.items()}, "policy": {k: x["policy"] for k, x in tabs.items()},
            "lambdas": {k: C.clean(A.lambdas(x["cal"])) for k, x in tabs.items()}, "gate_blocked_test_items": int(blk.sum()),
            "stream": stream, "declaration_stream_abstain": stream_decl, "controls": controls}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conds", default="median/0.5,median/1.0,median/2.0,worst/0.5,worst/1.0,worst/2.0")
    ap.add_argument("--out", default="sim.json")
    a = ap.parse_args()
    A.set_log(A.OUT / f"run-{Path(a.out).stem}.log")
    out_p = A.OUT / a.out
    res = A.load_json(out_p) if out_p.exists() else {"env": A.env_note(), "conditions": {}}
    for c in a.conds.split(","):
        p, t = c.split("/")
        res["conditions"][c] = run_cond(p, float(t))
        A.dump(res, out_p)
    A.log("done")


if __name__ == "__main__":
    main()
