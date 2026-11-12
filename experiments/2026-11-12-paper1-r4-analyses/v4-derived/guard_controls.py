"""v4-derived: the frozen v4 configuration (guard on + LTT max, fit-A pipeline, clean calibration) on the B2T control streams.

Why: review round 4 (editor M6) asked that the configuration carried forward is
run on the signal-destroying control streams. The R4 no-guard run showed that
the plain threshold + LTT max commits 198/300 uniform streams on our decoder.
v4 therefore freezes the guarded configuration. This script gives the control
result of exactly that configuration: split A (alternate trials of each day's
fit data) fit-A pipeline with the guard ON, LTT max / CRC max / plug-in /
joint LTT thresholds from the clean calibration half, and the same 300-trial
control streams (same seed and draw) as the R4 no-guard run.

Re-uses the R4 no-guard helpers (same recipe; only use_guard differs).
Consistency check: the split-A LTT max test rate must equal the committed
clean-drift guard-on value (0.0245 ours, 0.0294 published).

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/v4-derived/guard_controls.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
R4 = HERE.parent
sys.path.insert(0, str(R4))
sys.path.insert(0, str(R4 / "no-guard"))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
NG = C.load_module("r4noguard", R4 / "no-guard" / "run.py")
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)


def main() -> None:
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    ctx = C.b2t_ctx()
    NG.redirect(ctx.cached)
    T = ctx.items(ctx.test)
    cl = np.unique(ctx.days_test, return_inverse=True)[1]
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    bt = ctx.bt
    rng = np.random.default_rng(bt.SEED)  # same draw as the R4 no-guard audit
    na = min(len(ctx.test), bt.CONFIG["audit_n"])
    aud_idx = sorted(rng.choice(len(ctx.test), na, replace=False).tolist())
    atest = [ctx.test[i] for i in aud_idx]
    streams = {t.index: bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in atest}
    base = [streams[t.index] for t in atest]
    perm = rng.permutation(len(base))
    for i in range(len(perm)):
        if atest[perm[i]].truth_words == atest[i].truth_words:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    nulls = {"real": base, "other_trial": [base[j] for j in perm],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base], "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
    truths = [t.truth_words for t in atest]
    res: dict = {"description": __doc__.strip().splitlines()[0], "alpha": Q.ALPHA,
                 "n_control_trials": na, "conditions": {}}
    for which in ("ours", "published"):
        t0 = time.time()
        fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
        A, Bi = [], []
        for d, idx in sorted(by_day.items()):
            A += idx[0::2]
            Bi += idx[1::2]
        pa = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA, use_guard=True), {})
        fa = ctx.items([ctx.fit[i] for i in sorted(A)])
        pa.fit(fa, fa)
        tab_b = Q.M13.item_table(pa, ctx.items([ctx.fit[i] for i in sorted(Bi)]))
        tab_t = Q.M13.item_table(pa, T)
        ca = K.arr(tab_b)
        r = {"split A (guard on, refitted)": NG.rows(ca, tab_t, NG.ns(cl), pa.policy.config.commit_p)}
        lam = r["split A (guard on, refitted)"]["lambda"]
        C.save_caches(ctx)

        def decode(s2, i, which=which):
            if which == "published":
                s3 = NeuralTextStream(s2.log_probs, s2.frame_times, s2.vocab, s2.blank_id, s2.source,
                                      {**s2.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s2.vocab_type)
                return ctx.dec.published_plus_fn(s3)
            return ctx.dec.words_fn(s2)

        names = {"split A guard plug-in": "plug-in", "split A guard LTT max": "LTT max", "split A guard CRC max": "CRC max",
                 "split A guard joint LTT b0.10": "joint LTT b0.10", "split A guard joint LTT b0.20": "joint LTT b0.20"}
        r["controls"] = NG.audit(pa, {n: C.fnum(lam[k]) for n, k in names.items()}, nulls, decode, truths)
        C.save_caches(ctx)
        res["conditions"][f"b2t-{which}"] = r
        C.log(f"b2t-{which} guard: A LTT max test {r['split A (guard on, refitted)']['point']['LTT max']['wrong_commit']:.4f}; controls "
              + "; ".join(f"{k}: " + ",".join(f"{c} {v['n_commit']}" for c, v in d.items()) for k, d in r["controls"].items())
              + f" ({time.time() - t0:.0f}s)")
        C.dump(res, OUT / "guard_controls.json")
    L = ["# v4-derived: frozen v4 configuration (guard + LTT max) on the B2T control streams", "",
         "Split A fit-A pipeline, guard on, clean calibration; 300 control trials (same draw as R4 no-guard). Commits / n (one-sided 95 % CP upper bound of the commit rate).", "",
         "| condition | policy | split-A test wrong-commit | controls |", "|---|---|---|---|"]
    for cond, r in res["conditions"].items():
        pt = r["split A (guard on, refitted)"]["point"]
        for name, d in r["controls"].items():
            rule = name.replace("split A guard ", "")
            ctl = "; ".join(f"{c}: {v['n_commit']}/{v['n']} (<= {v['commit_cp95_one_sided_upper']:.4f})" for c, v in d.items())
            L.append(f"| {cond} | {name} | {pt[rule]['wrong_commit']:.4f} (commit {pt[rule]['commit_rate']:.3f}) | {ctl} |")
    (OUT / "guard_controls.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
