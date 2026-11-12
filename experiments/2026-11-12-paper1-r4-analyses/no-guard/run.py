"""R4 item 5: the no-guard configuration (plain threshold) in every row of Tables 1-2, and on the control streams.

Editor M6 (frozen configuration), stats review. The frozen configuration for a
confirmatory test uses the plain threshold on the calibrated p_top1 (guard
off). Rows per condition, guard off, with the R3 recipes:

- Tab. 1, full fit: plain-threshold plug-in fitted on all fit data
  (``policies.build(cond, "no_guard")``; B2T fit(fit, fit), sEMG fit(A, B),
  MEG fit(val, val)).
- Tab. 1, guaranteed rows: fit-A pipeline with the guard off, clean
  calibration, plug-in / LTT max / CRC max / joint LTT (beta 0.10, 0.20):
  B2T splits A (alternate) and B (chrono), sEMG fit-A / fit-B1 grid / fit-B2
  calibration, MEG val-A (6 sentences) / val-B (5 sentences, instance level).
  The same rules with the guard on come from the committed clean-drift items.
- Tab. 2: the repeated splits with the guard off (split-tables; B2T R = 50
  and 200, sEMG R = 50).
- Controls (Sec. 7.6): the R3 / source null audits (B2T: 300 test trials,
  other trial, frame shuffled, uniform; sEMG: 200 sentences, other sentence,
  frame shuffled, zeros input, permuted-label decoder; MEG: 637 instances,
  shuffled MEG, zero MEG, other sentence, frame shuffled, uniform) with the
  plain-threshold policies (full fit; split A / fit-A + LTT max; + joint LTT).

CIs: unified percentile bootstrap (seed 20261112, B 2000) at the condition's
unit, conditional on the fitted pipeline and threshold. New decodes go to the
R4 cache (r1 caches are read, not written).

Run (repo root):
  .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r4-analyses/no-guard/run.py --stage b2t
  ... --stage emg ; ... --stage meg ; ... --stage tables
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import replace
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
CLEAN = K.R1 / "clean-drift" / "results"
RULES = ("plug-in", "LTT max", "CRC max", "LTT pure", "CRC pure", "joint LTT b0.10", "joint LTT b0.20")


def redirect(cached_list) -> None:
    for d in cached_list:
        d.path = Q.CACHE4 / d.path.name


def ns(cluster, scheme="cluster", sent=None):
    return SimpleNamespace(cluster=np.asarray(cluster), sent=sent, scheme=scheme)


def rows(ca: dict | None, te_tab: dict, cns, plug: float) -> dict:
    te = K.arr(te_tab)
    lams = Q.rule_lambdas(ca, plug) if ca is not None else {"plug-in": plug}
    arrs = {k: C.item_arrays(te_tab, v) for k, v in lams.items()}
    pt = {}
    for k, a in arrs.items():
        m = C.metrics(a)
        nw = int(round(a["wc"].sum()))
        pt[k] = {**m, "n": int(a["wc"].size), "n_commit": int(a["com"].sum()), "n_commit_wrong": int(round(a["wcc"].sum())),
                 "n_wrong_commit": nw, "wrong_commit_cp95_one_sided_upper": K.upper_one_sided(nw, int(a["wc"].size)),
                 "threshold": lams[k]}
    bs = C.bootstrap(arrs, cns, B=K.UNIFIED_B, seed=K.UNIFIED_SEED)
    return {"point": pt, "ci": bs["policies"], "lambda": {k: C.clean(v) for k, v in lams.items()}}


def policy_at(pipe, lam: float):
    from fidetype.trust.policy import DecisionPolicy
    return DecisionPolicy(replace(pipe.policy.config, commit_p=lam), use_guard=pipe.policy.use_guard)


def audit(pipe, policies: dict, nulls: dict, decode, truths: list[str]) -> dict:
    """Commit / wrong-commit rate of each named policy (commit threshold) on each control stream set."""
    from fidetype.trust.policy import Action
    T = pipe.frame_scaler.temperature
    out = {name: {} for name in policies}
    pols = {name: policy_at(pipe, lam) for name, lam in policies.items()}
    for cond, ss in nulls.items():
        com = {n: [] for n in policies}
        wr = {n: [] for n in policies}
        for i, s in enumerate(ss):
            s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
            nb = decode(s2, i)
            an = pipe.analyze(nb)
            top = nb.top.text if nb.top is not None else ""
            for n, pol in pols.items():
                c = pol.decide(an.inputs, final_attempt=True).action == Action.COMMIT
                com[n].append(c)
                wr[n].append(c and top != truths[i])
        for n in policies:
            k = int(np.sum(com[n]))
            out[n][cond] = {"n": len(ss), "commit_rate": float(np.mean(com[n])), "n_commit": k,
                            "wrong_commit_rate": float(np.mean(wr[n])),
                            "commit_cp95_one_sided_upper": K.upper_one_sided(k, len(ss))}
    return out


# ---------------------------------------------------------------------------
# B2T
# ---------------------------------------------------------------------------

def stage_b2t() -> None:
    from fidetype.streams.spec import NeuralTextStream
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    ctx = C.b2t_ctx()
    redirect(ctx.cached)
    res: dict = {}
    T = ctx.items(ctx.test)
    cl = np.unique(ctx.days_test, return_inverse=True)[1]
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    bt = ctx.bt
    # control streams (same draw as the source audit: seed, audit_n)
    rng = np.random.default_rng(bt.SEED)
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
    for which in ("ours", "published"):
        t0 = time.time()
        cond = C.b2t_condition(ctx, which)
        cond.cached = ctx.cached
        full = P.build(cond, "no_guard", {})
        tab_full = Q.M13.item_table(full, T)
        r = {"full_fit": rows(None, tab_full, ns(cl), full.policy.config.commit_p),
             "full_fit_policy": C.clean(full.policy.config.__dict__), "full_fit_T": full.frame_scaler.temperature}
        fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
        pipes = {}
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
            pa = C.TrustPipeline(fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=C.ALPHA, use_guard=False), {})
            fa = ctx.items([ctx.fit[i] for i in sorted(A)])
            pa.fit(fa, fa)
            tab_b = Q.M13.item_table(pa, ctx.items([ctx.fit[i] for i in sorted(Bi)]))
            tab_t = Q.M13.item_table(pa, T)
            ca = K.arr(tab_b)
            r[f"split {lab}"] = rows(ca, tab_t, ns(cl), pa.policy.config.commit_p)
            r[f"split {lab}"]["policy"] = C.clean(pa.policy.config.__dict__)
            pipes[lab] = (pa, r[f"split {lab}"]["lambda"])
            C.save_caches(ctx)
        # guard-on reference (committed clean-drift items)
        for split, lab in (("alternate", "A"), ("chrono", "B")):
            it = json.loads((CLEAN / f"items-{which}-{split}.json").read_text(encoding="utf-8"))
            r[f"split {lab} (guard on, committed items)"] = rows(K.arr(it["items_cal"]), it["items_test"], ns(cl), it["items_test"]["lam_old"])

        def decode(s2, i, which=which):
            if which == "published":
                s3 = NeuralTextStream(s2.log_probs, s2.frame_times, s2.vocab, s2.blank_id, s2.source,
                                      {**s2.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s2.vocab_type)
                return ctx.dec.published_plus_fn(s3)
            return ctx.dec.words_fn(s2)

        pa, lamA = pipes["A"]
        r["controls"] = {
            "plain threshold (full fit)": audit(full, {"plain threshold (full fit)": full.policy.config.commit_p}, nulls, decode, truths)[
                "plain threshold (full fit)"],
            **audit(pa, {"split A plug-in": C.fnum(lamA["plug-in"]), "split A LTT max": C.fnum(lamA["LTT max"]),
                         "split A CRC max": C.fnum(lamA["CRC max"]), "split A joint LTT b0.10": C.fnum(lamA["joint LTT b0.10"]),
                         "split A joint LTT b0.20": C.fnum(lamA["joint LTT b0.20"])}, nulls, decode, truths)}
        C.save_caches(ctx)
        res[f"b2t-{which}"] = r
        C.log(f"b2t-{which}: full plain {r['full_fit']['point']['plug-in']['wrong_commit']:.4f}/{r['full_fit']['point']['plug-in']['commit_rate']:.3f}; "
              f"A LTT max {r['split A']['point']['LTT max']['wrong_commit']:.4f}; B LTT max {r['split B']['point']['LTT max']['wrong_commit']:.4f}; "
              f"controls " + "; ".join(f"{k}: " + ",".join(f"{c} {v['n_commit']}" for c, v in d.items()) for k, d in r["controls"].items())
              + f" ({time.time() - t0:.0f}s)")
        C.dump(res, OUT / "no_guard_b2t.json")


# ---------------------------------------------------------------------------
# sEMG
# ---------------------------------------------------------------------------

def stage_emg() -> None:
    from fidetype.trust.guard import shuffle_stream
    res: dict = {}
    for cname in ("calib", "xsession", "xsubject"):
        t0 = time.time()
        cond = C.emg_condition(cname)
        redirect(cond.cached)
        E, b = cond.E, C.emg_base()
        cl = np.asarray(cond.cluster)
        full = P.build(cond, "no_guard", {})
        tab_full = Q.M13.item_table(full, cond.test)
        r = {"full_fit": rows(None, tab_full, ns(cl), full.policy.config.commit_p), "full_fit_policy": C.clean(full.policy.config.__dict__)}
        h = len(cond.Bv) // 2
        B1, B2 = cond.Bv[:h], cond.Bv[h:]
        pa = C.make_pipe(cond, use_guard=False)
        pa.fit(cond.A, B1)
        tab_b, tab_t = Q.M13.item_table(pa, B2), Q.M13.item_table(pa, cond.test)
        r["fit-A guaranteed"] = rows(K.arr(tab_b), tab_t, ns(cl), pa.policy.config.commit_p)
        it = json.loads((CLEAN / f"items-emg-{cname}.json").read_text(encoding="utf-8"))
        r["fit-A guaranteed (guard on, committed items)"] = rows(K.arr(it["items_cal"]), it["items_test"], ns(cl), it["items_test"]["lam_old"])
        # controls (source audit: seed 0, audit_n 200)
        truths_all = [x.text for x in cond.test]
        arng = np.random.default_rng(E.SEED)
        na = min(len(cond.test), E.CONFIG["audit_n"])
        aud = sorted(arng.choice(len(cond.test), na, replace=False).tolist())
        base = [cond.test[i].stream(0) for i in aud]
        aperm = arng.permutation(na)
        for i in range(na):
            if truths_all[aud[aperm[i]]] == truths_all[aud[i]]:
                aperm[i], aperm[(i + 1) % na] = aperm[(i + 1) % na], aperm[i]
        zero_vec = next(iter(cond.zeros.values()))
        pids = cond.test_who
        nulls = {"real": base, "other_sentence": [base[j] for j in aperm], "frame_shuffled": [shuffle_stream(s, arng) for s in base],
                 "zeros_input": [E.make_stream(np.repeat(zero_vec[None, :], len(cond.test_idx[i]), axis=0), b.period, pids[i], cname) for i in aud]}
        perm_lg, perm_have, _ = E.load_logits("xsession_permuted", len(b.y))
        if perm_have[np.concatenate([cond.test_idx[i] for i in aud])].all():
            nulls["permuted_label_decoder"] = [E.make_stream(perm_lg[cond.test_idx[i]], b.period, pids[i], cname) for i in aud]
        truths = [truths_all[i] for i in aud]
        lam = r["fit-A guaranteed"]["lambda"]
        r["controls"] = {
            "plain threshold (full fit)": audit(full, {"x": full.policy.config.commit_p}, nulls, lambda s, i: cond.decode(s), truths)["x"],
            **audit(pa, {"fit-A plug-in": C.fnum(lam["plug-in"]), "fit-A LTT max": C.fnum(lam["LTT max"]),
                         "fit-A joint LTT b0.10": C.fnum(lam["joint LTT b0.10"])}, nulls, lambda s, i: cond.decode(s), truths)}
        C.save_caches(cond)
        res[f"emg-{cname}"] = r
        C.log(f"emg-{cname}: full plain {r['full_fit']['point']['plug-in']['wrong_commit']:.4f}/{r['full_fit']['point']['plug-in']['commit_rate']:.3f}; "
              f"LTT max {r['fit-A guaranteed']['point']['LTT max']['wrong_commit']:.4f}/{r['fit-A guaranteed']['point']['LTT max']['commit_rate']:.3f}; "
              f"controls " + "; ".join(f"{k}: " + ",".join(f"{c} {v['n_commit']}" for c, v in d.items()) for k, d in r["controls"].items())
              + f" ({time.time() - t0:.0f}s)")
        C.dump(res, OUT / "no_guard_emg.json")


# ---------------------------------------------------------------------------
# MEG
# ---------------------------------------------------------------------------

def stage_meg() -> None:
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    cond = C.meg_ctx()
    redirect(cond.cached)
    B = json.loads((K.R1 / "baselines/config.json").read_text(encoding="utf-8"))
    cns = ns(cond.cluster, "two_way", cond.sent)
    full = P.build(cond, "no_guard", {})
    tab_full = Q.M13.item_table(full, cond.test)
    r = {"full_fit": rows(None, tab_full, cns, full.policy.config.commit_p), "full_fit_policy": C.clean(full.policy.config.__dict__)}
    rng = np.random.default_rng(B["seed"])
    us = rng.permutation(int(cond.val_sent.max()) + 1)
    a_s = set(us[: B["meg_val_a_sentences"]].tolist())
    A = [it for it, s in zip(cond.val, cond.val_sent) if s in a_s]
    Bv = [it for it, s in zip(cond.val, cond.val_sent) if s not in a_s]
    pa = C.make_pipe(cond, {}, use_guard=False)
    pa.fit(A, A)
    tab_b, tab_t = Q.M13.item_table(pa, Bv), Q.M13.item_table(pa, cond.test)
    r["clean split (instance level)"] = rows(K.arr(tab_b), tab_t, cns, pa.policy.config.commit_p)
    meg = K.CACHE3 / "meg-clean-items.json"
    if meg.exists():
        it = json.loads(meg.read_text(encoding="utf-8"))
        r["clean split (guard on, R3 items)"] = rows(K.arr(it["items_cal"]), it["items_test"], cns, it["items_test"]["lam_old"])
    # controls (G1 audit draw)
    g1 = C.load_module("g1run", Q.REPO / "experiments/2026-11-11-g1-async-meg-trust/run.py")
    truths = [it.text for it in cond.test]
    part = cond.part_names
    rng = np.random.default_rng(g1.SEED)
    base = [s for s, _ in cond.test_raw]
    ctl = np.load(g1.CONFIG["controls_npz"])
    n = len(base)
    other = []
    for i in range(n):
        same_p = [j for j in range(n) if part[j] == part[i] and truths[j] != truths[i]]
        pool = same_p or [j for j in range(n) if truths[j] != truths[i]]
        other.append(int(rng.choice(pool)))
    nulls = {"real": base,
             "shuffled_meg": [g1.with_logprobs(s, ctl["shuffled__" + rr["file"]], "shuffled_meg") for s, rr in cond.test_raw],
             "zeros_meg": [g1.with_logprobs(s, ctl["zeros__" + rr["file"]], "zeros_meg") for s, rr in cond.test_raw],
             "other_sentence": [base[j] for j in other],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base],
             "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
    lam = r["clean split (instance level)"]["lambda"]
    r["controls"] = {"plain threshold (full fit)": audit(full, {"x": full.policy.config.commit_p}, nulls, lambda s, i: cond.decode(s), truths)["x"],
                     **audit(pa, {"clean-split plug-in": C.fnum(lam["plug-in"]), "clean-split LTT max": C.fnum(lam["LTT max"])},
                             nulls, lambda s, i: cond.decode(s), truths)}
    C.save_caches(cond)
    C.log(f"meg: full plain {r['full_fit']['point']['plug-in']['wrong_commit']:.4f}/{r['full_fit']['point']['plug-in']['commit_rate']:.3f}; controls "
          + "; ".join(f"{k}: " + ",".join(f"{c} {v['n_commit']}" for c, v in d.items()) for k, d in r["controls"].items()))
    C.dump({"meg-async": r}, OUT / "no_guard_meg.json")


# ---------------------------------------------------------------------------
# Tables (incl. Tab. 2 rows from the guard-off split tables)
# ---------------------------------------------------------------------------

TAB2_RULES = ("plug-in", "CRC pure", "CRC max", "LTT pure", "LTT max", "joint LTT b0.10", "joint LTT b0.20")


def tab2() -> dict:
    out = {}
    for cond in Q.CONDS:
        for guard in (0, 1):
            Rm = 200 if cond.startswith("b2t") else 50
            allrows = Q.load_all(cond, Rm, guard)
            for tag, rr in ((f"R{len(allrows)}", allrows),) + ((("R50", allrows[:50]),) if len(allrows) > 50 else ()):
                per = []
                for sp in rr:
                    lam = Q.rule_lambdas(sp["cal"], sp["cal"]["lam_old"])
                    per.append({k: K.outcome(sp["test"], lam[k]) for k in TAB2_RULES})
                d = {}
                for k in TAB2_RULES:
                    v = [p[k] for p in per]
                    wc = np.array([x["wrong_commit"] for x in v])
                    nk = int(np.sum(wc > Q.ALPHA + 1e-12))
                    nc = sum(x["n_commit"] for x in v)
                    d[k] = {"wrong_commit_mean": float(wc.mean()), "p05": float(np.quantile(wc, 0.05)), "p95": float(np.quantile(wc, 0.95)),
                            "share_gt_alpha": nk / len(v), "share_gt_alpha_cp95": Q.cp(nk, len(v)),
                            "commit_rate_mean": float(np.mean([x["commit_rate"] for x in v])),
                            "eac_pooled": sum(x["n_commit_wrong"] for x in v) / nc if nc else None,
                            "share_no_commit": float(np.mean([x["n_commit"] == 0 for x in v])),
                            "ewpm_mean": float(np.mean([x["ewpm"] for x in v]))}
                out[f"{cond}/{'guard' if guard else 'no guard'}/{tag}"] = {"R": len(rr), "rules": d}
    return out


def stage_tables() -> None:
    res = {"config": CONFIG}
    for f in ("no_guard_b2t.json", "no_guard_emg.json", "no_guard_meg.json"):
        p = OUT / f
        if p.exists():
            res.update(json.loads(p.read_text(encoding="utf-8")))
    res["tab2"] = tab2()
    C.dump(res, OUT / "no_guard.json")
    L = ["# No-guard configuration (plain threshold): tables", "",
         "Guard off unless marked. 95 % unified bootstrap CIs (seed 20261112, B 2000), conditional on the fitted pipeline and threshold. "
         "Zero counts: one-sided 95 % CP upper bound.", "", "## Table 1 rows (fixed test sets)", "",
         "| condition | row | rule | eWPM [CI] | wrong-commit [CI] | commit | EAC (wrong/commits) | λ |", "|---|---|---|---|---|---|---|---|"]
    for cname, r in res.items():
        if cname in ("config", "tab2"):
            continue
        for row, v in r.items():
            if not isinstance(v, dict) or "point" not in v:
                continue
            for rule, pt in v["point"].items():
                if rule not in ("plug-in", "LTT max", "CRC max", "joint LTT b0.10"):
                    continue
                ci = v["ci"][rule]
                wc = f"{pt['wrong_commit']:.4f} {Q.fci(ci['wrong_commit'])}" if pt["n_wrong_commit"] else f"0 (≤ {pt['wrong_commit_cp95_one_sided_upper']:.4f})"
                eac = f"{pt['n_commit_wrong']}/{pt['n_commit']}"
                L.append(f"| {cname} | {row} | {rule} | {pt['ewpm']:.2f} {Q.fci(ci['ewpm'], 2)} | {wc} | {pt['commit_rate']:.3f} | {eac} | "
                         f"{Q.fmt(pt['threshold'], 2)} |")
    L += ["", "## Controls (commits / n; one-sided 95 % CP upper bound of the commit rate)", "",
          "| condition | policy | " + " | ".join(["control: commits/n (bound)"]) + " |", "|---|---|---|"]
    for cname, r in res.items():
        if not isinstance(r, dict) or "controls" not in r:
            continue
        for pol, d in r["controls"].items():
            cells = "; ".join(f"{c}: {v['n_commit']}/{v['n']} (≤ {v['commit_cp95_one_sided_upper']:.4f}) wrong {v['wrong_commit_rate']:.3f}"
                              for c, v in d.items())
            L.append(f"| {cname} | {pol} | {cells} |")
    L += ["", "## Table 2 rows (repeated splits; guard off vs on)", "",
          "| condition / guard / R | rule | wrong-commit mean (p05–p95) | >α [CP95] | commit | EAC pooled | no-commit splits | eWPM |",
          "|---|---|---|---|---|---|---|---|"]
    for key, v in res["tab2"].items():
        for rule, d in v["rules"].items():
            L.append(f"| {key} | {rule} | {d['wrong_commit_mean']:.4f} ({d['p05']:.3f}–{d['p95']:.3f}) | {d['share_gt_alpha']:.2f} "
                     f"{Q.fci(d['share_gt_alpha_cp95'], 2)} | {d['commit_rate_mean']:.3f} | {Q.fmt(d['eac_pooled'], 3)} | {d['share_no_commit']:.2f} | "
                     f"{d['ewpm_mean']:.2f} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    a = ap.parse_args()
    C.Log.path = OUT / f"run-{a.stage}.log"
    {"b2t": stage_b2t, "emg": stage_emg, "meg": stage_meg, "tables": stage_tables}[a.stage]()
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
