"""R4 item 9: sentence ECE and AUROC with bootstrap CIs per condition, and reliability-diagram data.

Stats m10. The paper's full-fit trust pipelines (``policies.build(cond,
"trust")``, as in the R1 ablation ``decoder_stats``) on the fixed test sets:

- sentence ECE (15 equal-width bins, ``fidetype.eval.metrics``) of the raw and
  the calibrated top-1 probability;
- AUROC for a wrong top-1 sentence of 1 - p_top1 (calibrated, raw) and of the
  guard risk;
- percentile bootstrap CIs at the condition's unit (B2T: 14 days; sEMG: 19
  participants; MEG: sentences x participants), unified seed 20261112, B 2000;
- reliability data: 10 equal-width bins of calibrated p_top1 (count, mean
  confidence, accuracy, exact CP 95 % CI of the accuracy) -> results/reliability.json
  and results/reliability.png.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/ece-auroc/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common4 as Q  # noqa: E402

K, C = Q.K, Q.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
P = C.load_module("r1policies", K.R1 / "policies.py")

from fidetype.eval.metrics import expected_calibration_error as ECE  # noqa: E402
from fidetype.trust.guard import auroc  # noqa: E402


def collect(pipe, items) -> dict:
    p_raw, p_cal, ok, risk = [], [], [], []
    for it in items:
        an = pipe.analyze(pipe.decode(it, 0))
        t = an.nbest.texts[0] if len(an.nbest) else ""
        ok.append(t == it.text)
        p_raw.append(float(an.raw_posteriors[0]) if len(an.raw_posteriors) else 0.0)
        p_cal.append(float(an.posteriors[0]) if len(an.posteriors) else 0.0)
        risk.append(float(an.guard.risk))
    return {"p_raw": np.clip(p_raw, 0, 1), "p_cal": np.clip(p_cal, 0, 1), "ok": np.array(ok, bool), "risk": np.array(risk)}


def stats(d: dict, idx=None) -> dict:
    g = (lambda k: d[k]) if idx is None else (lambda k: d[k][idx])
    wrong = ~g("ok")
    return {"ece_raw": float(ECE(g("p_raw"), g("ok"))), "ece_cal": float(ECE(g("p_cal"), g("ok"))),
            "auroc_1mp_cal": float(auroc(1 - g("p_cal"), wrong)), "auroc_1mp_raw": float(auroc(1 - g("p_raw"), wrong)),
            "auroc_guard_risk": float(auroc(g("risk"), wrong)), "top1_acc": float(g("ok").mean())}


def boot(d: dict, cond) -> dict:
    rng = np.random.default_rng(K.UNIFIED_SEED)
    n = d["ok"].size
    vals = {k: [] for k in stats(d)}
    for _ in range(K.UNIFIED_B):
        w = C.boot_weights(rng, cond.scheme, n, cond.cluster, cond.sent).astype(int)
        if w.sum() == 0:
            continue
        idx = np.repeat(np.arange(n), w)
        for k, v in stats(d, idx).items():
            vals[k].append(v)
    out = {}
    for k, v in vals.items():
        v = np.asarray(v, float)
        v = v[np.isfinite(v)]
        out[k] = [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size >= 20 else None
    return out


def reliability(d: dict, bins: int = 10) -> list[dict]:
    b = np.clip(np.ceil(d["p_cal"] * bins).astype(int) - 1, 0, bins - 1)
    rows = []
    for i in range(bins):
        m = b == i
        k, n = int(d["ok"][m].sum()), int(m.sum())
        rows.append({"bin": [i / bins, (i + 1) / bins], "n": n, "mean_conf": float(d["p_cal"][m].mean()) if n else None,
                     "accuracy": (k / n) if n else None, "accuracy_cp95": Q.cp(k, n)})
    return rows


def conditions():
    ctx = C.b2t_ctx()
    for dd in ctx.cached:
        dd.path = Q.CACHE4 / dd.path.name
    for which in ("ours", "published"):
        cond = C.b2t_condition(ctx, which)
        cond.cached = ctx.cached
        yield f"b2t-{which}", cond, ctx
    for c in ("calib", "xsession", "xsubject"):
        cond = C.emg_condition(c)
        for dd in cond.cached:
            dd.path = Q.CACHE4 / dd.path.name
        yield f"emg-{c}", cond, cond
    cond = C.meg_ctx()
    for dd in cond.cached:
        dd.path = Q.CACHE4 / dd.path.name
    yield "meg-async", cond, cond


def main() -> None:
    res = {"config": CONFIG, "conditions": {}}
    for name, cond, holder in conditions():
        pipe = P.build(cond, "trust", {})
        d = collect(pipe, cond.test)
        C.save_caches(holder)
        st = stats(d)
        res["conditions"][name] = {"n": int(d["ok"].size), "point": st, "ci95": boot(d, cond), "unit": cond.scheme,
                                   "frame_T": pipe.frame_scaler.temperature, "reliability": reliability(d)}
        C.log(f"{name}: " + ", ".join(f"{k} {v:.3f}" for k, v in st.items()))
        C.dump(res, OUT / "ece_auroc.json")
    C.dump({k: v["reliability"] for k, v in res["conditions"].items()}, OUT / "reliability.json")
    plot(res)
    write(res)


def plot(res: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = list(res["conditions"])
    fig, axs = plt.subplots(1, len(names), figsize=(2.6 * len(names), 2.8), sharey=True)
    for ax, n in zip(axs, names):
        rel = [r for r in res["conditions"][n]["reliability"] if r["n"]]
        x = [r["mean_conf"] for r in rel]
        y = [r["accuracy"] for r in rel]
        lo = [r["accuracy"] - r["accuracy_cp95"][0] for r in rel]
        hi = [r["accuracy_cp95"][1] - r["accuracy"] for r in rel]
        ax.plot([0, 1], [0, 1], ":", color="0.5", lw=1)
        ax.errorbar(x, y, yerr=[lo, hi], fmt="o", ms=3, color="#2a6fbb", ecolor="#2a6fbb", lw=1, capsize=0)
        for xi, yi, r in zip(x, y, rel):
            ax.annotate(str(r["n"]), (xi, yi), fontsize=6, xytext=(2, 2), textcoords="offset points", color="0.3")
        p = res["conditions"][n]["point"]
        ax.set_title(f"{n}\nECE {p['ece_cal']:.3f}", fontsize=8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel("calibrated p_top1", fontsize=7)
        ax.tick_params(labelsize=6)
    axs[0].set_ylabel("top-1 sentence accuracy", fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT / "reliability.png", dpi=150, metadata={"Software": None})
    plt.close(fig)


def write(res: dict) -> None:
    L = ["# Sentence ECE and AUROC with bootstrap CIs", "",
         "Full-fit trust pipelines on the fixed test sets. 95 % percentile bootstrap at the condition's unit (seed 20261112, B 2000). "
         "AUROC: positive class = wrong top-1 sentence.", "",
         "| condition | n | top-1 acc | ECE raw [CI] | ECE calibrated [CI] | AUROC 1 − p̂ calibrated [CI] | AUROC 1 − p̂ raw [CI] | AUROC guard risk [CI] |",
         "|---|---|---|---|---|---|---|---|"]
    for n, c in res["conditions"].items():
        p, ci = c["point"], c["ci95"]
        L.append(f"| {n} | {c['n']} | {p['top1_acc']:.3f} | {p['ece_raw']:.3f} {Q.fci(ci['ece_raw'])} | {p['ece_cal']:.3f} {Q.fci(ci['ece_cal'])} | "
                 f"{p['auroc_1mp_cal']:.3f} {Q.fci(ci['auroc_1mp_cal'])} | {p['auroc_1mp_raw']:.3f} {Q.fci(ci['auroc_1mp_raw'])} | "
                 f"{p['auroc_guard_risk']:.3f} {Q.fci(ci['auroc_guard_risk'])} |")
    L += ["", "Reliability data: `reliability.json` (10 bins of calibrated p_top1; count, mean confidence, accuracy, CP 95 %). Plot: `reliability.png`.", ""]
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
