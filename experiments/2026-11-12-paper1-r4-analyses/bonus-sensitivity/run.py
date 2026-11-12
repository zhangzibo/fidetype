"""R4 item 6: published-gate bonus (``published_margin``) sensitivity and a "published stream alone" variant.

Editor M2. The published-sentence gate puts the published sentence on top of
our phoneme-to-word n-best with score = (our best score + published_margin)
and gives each published word the acoustic confidence of the aligned word in
our top-1 (``Decoders.published_plus_fn``, experiments/2026-11-10-b2t25-trust/run.py).

Provenance of 2.0 (git history, config): ``published_margin: 2.0`` was set by
hand in ``experiments/2026-11-10-b2t25-trust/config.json`` in its first commit
(3fb8154, 2026-11-10, M6-06) and never changed; no grid, tuning stage or
selection record exists in the code, results or wiki. It was not tuned on test
data, and it was also not tuned on fit data.

Runs (guard on, the paper configuration), margin in {0, 0.5, 1, 2, 4}:
- full fit (Tab. 1 "trust gate, plug-in"; fit(fit, fit));
- fixed splits A / B (fit-A pipeline, clean calibration: plug-in, LTT max,
  CRC max, joint LTT);
- repeated splits r = 0..49 (split-tables; 2.0 = the R3 tables).
"Published stream alone": ``Decoders.published_fn`` (one candidate, the
published sentence, score 0, no character confidences): no confidence that is
independent of our decoder exists in the data set (the pickle holds the
published sentence, not its scores or logits), so the gate cannot rank trials.

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/bonus-sensitivity/run.py --stage fixed
  ... --stage tables
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
P = C.load_module("r1policies", K.R1 / "policies.py")
RULES = ("plug-in", "LTT max", "CRC max", "joint LTT b0.10", "joint LTT b0.20")


def ns(cluster):
    return SimpleNamespace(cluster=np.asarray(cluster), sent=None, scheme="cluster")


def rows(ca, te_tab, cl, plug):
    lams = Q.rule_lambdas(ca, plug) if ca is not None else {"plug-in": plug}
    arrs = {k: C.item_arrays(te_tab, v) for k, v in lams.items() if k in RULES}
    pt = {k: {**C.metrics(a), "n_commit": int(a["com"].sum()), "n_commit_wrong": int(round(a["wcc"].sum())), "threshold": lams[k]}
          for k, a in arrs.items()}
    bs = C.bootstrap(arrs, ns(cl), B=K.UNIFIED_B, seed=K.UNIFIED_SEED)
    return {"point": pt, "ci": bs["policies"]}


def stage_fixed() -> None:
    ctx = C.b2t_ctx()
    for d in ctx.cached:
        d.path = Q.CACHE4 / d.path.name
    T = ctx.items(ctx.test)
    cl = np.unique(ctx.days_test, return_inverse=True)[1]
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    res: dict = {"provenance": {"value": 2.0, "file": "experiments/2026-11-10-b2t25-trust/config.json", "commit": "3fb8154",
                                "date": "2026-11-10", "note": "set by hand in the first commit; never tuned or changed"}}
    variants = [(f"margin {m:g}", "published", m) for m in CONFIG["margins"]] + [("published alone", "published_alone", None)]
    for name, which, m in variants:
        t0 = time.time()
        old = ctx.bt.CONFIG["published_margin"]
        if m is not None:
            ctx.bt.CONFIG["published_margin"] = float(m)
        try:
            fn = Q.decoder_fn(ctx, which)
            cond = SimpleNamespace(**{**C.b2t_condition(ctx, "published").__dict__, "decode": fn})
            full = P.build(cond, "trust", {})
            tab = Q.M13.item_table(full, T)
            r = {"full_fit": rows(None, tab, cl, full.policy.config.commit_p), "full_fit_policy": C.clean(full.policy.config.__dict__),
                 "full_fit_eligible_share": float(np.isfinite(K.arr(tab)["s"]).mean())}
            for split, lab in (("alternate", "A"), ("chrono", "B")):
                A, Bi = [], []
                for d, idx in sorted(by_day.items()):
                    if split == "alternate":
                        A += idx[0::2]
                        Bi += idx[1::2]
                    else:
                        h = (len(idx) + 1) // 2
                        A += idx[:h]
                        Bi += idx[h:]
                pa = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA), {})
                fa = ctx.items([ctx.fit[i] for i in sorted(A)])
                pa.fit(fa, fa)
                tb = Q.M13.item_table(pa, ctx.items([ctx.fit[i] for i in sorted(Bi)]))
                tt = Q.M13.item_table(pa, T)
                r[f"split {lab}"] = rows(K.arr(tb), tt, cl, pa.policy.config.commit_p)
            C.save_caches(ctx)
        finally:
            ctx.bt.CONFIG["published_margin"] = old
        res[name] = r
        C.log(f"{name}: full plug-in wc {r['full_fit']['point']['plug-in']['wrong_commit']:.4f} commit {r['full_fit']['point']['plug-in']['commit_rate']:.3f} "
              f"eWPM {r['full_fit']['point']['plug-in']['ewpm']:.2f}; A LTT max {r['split A']['point']['LTT max']['wrong_commit']:.4f}/"
              f"{r['split A']['point']['LTT max']['commit_rate']:.3f}; B LTT max {r['split B']['point']['LTT max']['wrong_commit']:.4f}/"
              f"{r['split B']['point']['LTT max']['commit_rate']:.3f} ({time.time() - t0:.0f}s)")
        C.dump(res, OUT / "bonus_fixed.json")


def repeated() -> dict:
    out = {}
    for m in [0.0, 0.5, 1.0, 2.0, 4.0]:
        rr = Q.load_all("b2t-published", 50, 1, m)
        per = []
        for sp in rr:
            lam = Q.rule_lambdas(sp["cal"], sp["cal"]["lam_old"])
            per.append({k: K.outcome(sp["test"], lam[k]) for k in RULES})
        d = {}
        for k in RULES:
            v = [p[k] for p in per]
            wc = np.array([x["wrong_commit"] for x in v])
            nk = int(np.sum(wc > Q.ALPHA + 1e-12))
            nc = sum(x["n_commit"] for x in v)
            d[k] = {"wrong_commit_mean": float(wc.mean()), "share_gt_alpha": nk / len(v), "share_gt_alpha_cp95": Q.cp(nk, len(v)),
                    "commit_rate_mean": float(np.mean([x["commit_rate"] for x in v])),
                    "eac_pooled": sum(x["n_commit_wrong"] for x in v) / nc if nc else None, "ewpm_mean": float(np.mean([x["ewpm"] for x in v]))}
        out[f"margin {m:g}"] = {"R": len(rr), "rules": d}
    return out


def stage_tables() -> None:
    res = json.loads((OUT / "bonus_fixed.json").read_text(encoding="utf-8"))
    res["repeated"] = repeated()
    C.dump(res, OUT / "bonus.json")
    L = ["# Published-gate bonus sensitivity: tables", "",
         f"Provenance: published_margin = 2.0 set by hand in {res['provenance']['file']} (commit {res['provenance']['commit']}, "
         f"{res['provenance']['date']}); never tuned or changed. Guard on. CIs: unified day-cluster bootstrap.", "",
         "## Fixed test set (816 trials)", "", "| variant | row | rule | eWPM [CI] | wrong-commit [CI] | commit | EAC | λ |", "|---|---|---|---|---|---|---|---|"]
    for name, r in res.items():
        if name in ("provenance", "repeated"):
            continue
        for row in ("full_fit", "split A", "split B"):
            for rule, pt in r[row]["point"].items():
                ci = r[row]["ci"][rule]
                L.append(f"| {name} | {row} | {rule} | {pt['ewpm']:.2f} {Q.fci(ci['ewpm'], 2)} | {pt['wrong_commit']:.4f} {Q.fci(ci['wrong_commit'])} | "
                         f"{pt['commit_rate']:.3f} | {pt['n_commit_wrong']}/{pt['n_commit']} | {Q.fmt(pt['threshold'], 2)} |")
    L += ["", "## Repeated splits (R = 50)", "", "| margin | rule | wrong-commit mean | >α [CP95] | commit | EAC pooled | eWPM |", "|---|---|---|---|---|---|---|"]
    for name, v in res["repeated"].items():
        for rule, d in v["rules"].items():
            L.append(f"| {name} (R {v['R']}) | {rule} | {d['wrong_commit_mean']:.4f} | {d['share_gt_alpha']:.2f} {Q.fci(d['share_gt_alpha_cp95'], 2)} | "
                     f"{d['commit_rate_mean']:.3f} | {Q.fmt(d['eac_pooled'], 3)} | {d['ewpm_mean']:.2f} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    a = ap.parse_args()
    C.Log.path = OUT / f"run-{a.stage}.log"
    {"fixed": stage_fixed, "tables": stage_tables}[a.stage]()
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
