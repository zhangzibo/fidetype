"""P14-15: re-tune the B2T word-decoder settings without evaluation trials (plan.md, pre-registered).

Stages:
  grid     decode all 1,628 main-vocabulary trials (raw streams) at the 12 grid points with the
           original b2t25-trust classes; per trial + grid point: word edits, truth words, truth in n-best.
           Local file only (derived/p14-15-retune/grid.pkl; it also holds top-1 texts). Checkpoints.
  tune     sanity checks (original tune.json, R3 b2t-retune fit-A rows), then the choice on
           T1 (fit-A of the 200 R4 re-splits), T2a (400 tune minus val_eval), T2b (minus val_eval + val_select).
           Writes results/tune.json (choices, WER values, counts; no text, no trial ids).
  rebuild  (step 2, only if T1 changes a choice) b2t-ours item tables of those splits with their own setting.
  analyze  (step 2) R3 aggregation for R = 50 and R = 200, decision rule; results/step2.json.

  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 -- \\
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p14-15-retune/run.py --stage grid
"""

from __future__ import annotations

import argparse
import json
import math
import pickle
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
R3 = REPO / "experiments/2026-11-12-paper1-r3-analyses"
R4 = REPO / "experiments/2026-11-12-paper1-r4-analyses"
sys.path.insert(0, str(R3))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
DER = Path("C:/Users/zhang/bci-data/derived/p14-15-retune")
DER.mkdir(parents=True, exist_ok=True)
GRID_PKL = DER / "grid.pkl"
SPLITS200 = Path("C:/Users/zhang/bci-data/cache/paper1-r4/splits-b2t-200.json")
MATCH = Path("C:/Users/zhang/bci-data/derived/t15-split-audit/match.json")
PAPER = (1.0, 12.0, 3.0)
ALPHA = 0.05


def grid_points(bt):
    g = bt.CONFIG["word_decoder_grid"]
    return [(lw, ep, wb) for lw in g["lm_weight"] for ep in g["edit_penalty"] for wb in g["word_bonus"]]


# ---------------------------------------------------------------------------
# grid
# ---------------------------------------------------------------------------

def stage_grid() -> None:
    from fidetype.eval.metrics import edit_distance
    ctx = C.b2t_ctx()
    bt, dec = ctx.bt, ctx.dec
    trials = ctx.fit + ctx.test
    pts = grid_points(bt)
    wds = {p: dec.make_wdec({**bt.CONFIG["word_decoder_fixed"], "lm_weight": p[0], "edit_penalty": p[1], "word_bonus": p[2]})
           for p in pts}
    st = pickle.loads(GRID_PKL.read_bytes()) if GRID_PKL.exists() else {"points": pts, "trials": {}}
    t0 = time.time()
    done0 = len(st["trials"])
    for n, t in enumerate(trials):
        if t.index in st["trials"]:
            continue
        ph = dec.phonemes(bt.B.to_symbol_stream(bt.B.trial_stream(t)))
        ref = t.truth_words.split()
        row = {}
        for p in pts:
            hs = wds[p].decode(ph)
            top = hs[0].text if hs else ""
            row[p] = (edit_distance(ref, top.split()), len(ref), t.truth_words in [h.text for h in hs], top)
        st["trials"][t.index] = row
        if (len(st["trials"]) - done0) % 100 == 0:
            GRID_PKL.write_bytes(pickle.dumps(st))
            C.log(f"grid {len(st['trials'])}/{len(trials)} ({time.time() - t0:.0f}s)")
    GRID_PKL.write_bytes(pickle.dumps(st))
    C.log(f"grid done {len(st['trials'])} trials ({time.time() - t0:.0f}s)")


# ---------------------------------------------------------------------------
# tune
# ---------------------------------------------------------------------------

def tune_rows(G: dict, pts, idx) -> list[dict]:
    rows = []
    for p in pts:
        e = sum(G[i][p][0] for i in idx)
        n = sum(G[i][p][1] for i in idx)
        rows.append({"lm_weight": p[0], "edit_penalty": p[1], "word_bonus": p[2], "wer": e / n if n else math.nan,
                     "truth_in_nbest": float(np.mean([G[i][p][2] for i in idx]))})
    return rows


def choose(rows):
    best = min(rows, key=lambda r: (r["wer"], -r["truth_in_nbest"]))
    rank = sorted(rows, key=lambda r: (r["wer"], -r["truth_in_nbest"]))
    pp = next(r for r in rows if (r["lm_weight"], r["edit_penalty"], r["word_bonus"]) == PAPER)
    return {"choice": [best["lm_weight"], best["edit_penalty"], best["word_bonus"]],
            "same_as_paper": (best["lm_weight"], best["edit_penalty"], best["word_bonus"]) == PAPER,
            "wer_choice": best["wer"], "wer_paper_point": pp["wer"],
            "paper_point_rank": 1 + next(i for i, r in enumerate(rank) if r is pp)}


def stage_tune() -> None:
    ctx = C.b2t_ctx()
    bt = ctx.bt
    trials = ctx.fit + ctx.test
    st = pickle.loads(GRID_PKL.read_bytes())
    pts = [tuple(p) for p in st["points"]]
    G = st["trials"]
    assert len(G) == len(trials) == 1628, len(G)
    pos2idx = [t.index for t in trials]
    res: dict = {"paper_point": list(PAPER), "grid": [list(p) for p in pts], "checks": {}}

    # sanity (a): the original 400 tune trials
    rng = np.random.default_rng(bt.SEED)
    sub_pos = sorted(rng.choice(len(ctx.fit), min(bt.CONFIG["tune_trials"], len(ctx.fit)), replace=False))
    tune_idx = [ctx.fit[i].index for i in sub_pos]
    orig = bt.load_json("tune.json")
    rows = tune_rows(G, pts, tune_idx)
    dev = max(max(abs(a["wer"] - b["wer"]), abs(a["truth_in_nbest"] - b["truth_in_nbest"])) for a, b in zip(rows, orig["rows"]))
    okp = all((a["lm_weight"], a["edit_penalty"], a["word_bonus"]) == (b["lm_weight"], b["edit_penalty"], b["word_bonus"])
              for a, b in zip(rows, orig["rows"]))
    res["checks"]["original_400"] = {"max_abs_dev": dev, "grid_order_same": okp, "choice": choose(rows)["choice"],
                                     "pass": bool(okp and dev < 1e-12 and choose(rows)["same_as_paper"])}
    # sanity (b): R3 b2t-retune fit-A rows of the fixed splits A and B
    rt = json.loads((R3 / "b2t-retune/results/retune.json").read_text(encoding="utf-8"))
    for split, lab in (("alternate", "split A"), ("chrono", "split B")):
        by_day: dict = {}
        for i, t in enumerate(ctx.fit):
            by_day.setdefault(t.post_implant_day, []).append(i)
        A = []
        for d, idx in sorted(by_day.items()):
            A += idx[0::2] if split == "alternate" else idx[: (len(idx) + 1) // 2]
        rows = tune_rows(G, pts, [ctx.fit[i].index for i in A])
        ref = rt["splits"][lab]["rows"]
        dev = max(max(abs(a["wer"] - b["wer"]), abs(a["truth_in_nbest"] - b["truth_in_nbest"])) for a, b in zip(rows, ref))
        res["checks"][f"r3_retune_{lab.replace(' ', '_')}"] = {"n": len(A), "max_abs_dev": dev, "pass": bool(dev < 1e-12)}
    res["checks"]["all_pass"] = all(v["pass"] for v in res["checks"].values() if isinstance(v, dict))
    C.log("checks", res["checks"])
    if not res["checks"]["all_pass"]:
        C.dump(res, OUT / "tune.json")
        raise SystemExit("sanity check failed: stop (plan.md)")

    # T1: fit-A of each of the 200 re-splits
    sp = json.loads(SPLITS200.read_text(encoding="utf-8"))["splits"]
    sp50 = json.loads((R3 / "repeated-splits/results/splits-b2t.json").read_text(encoding="utf-8"))["splits"]
    assert all(sp[r]["A"] == sp50[r]["A"] and sp[r]["test"] == sp50[r]["test"] for r in range(50))
    tset = set(tune_idx)
    t1 = []
    for s in sp:
        assert not (set(s["A"]) & set(s["test"])) and not (set(s["A"]) & set(s["cal"]))
        idx = [pos2idx[i] for i in s["A"]]
        c = choose(tune_rows(G, pts, idx))
        c.update({"r": s["r"], "n_fitA": len(idx), "tune400_in_fitA": len(tset & set(idx)),
                  "tune400_in_test": len(tset & {pos2idx[i] for i in s["test"]})})
        t1.append(c)
    res["T1"] = {"n_splits": len(t1), "n_changed": sum(not c["same_as_paper"] for c in t1),
                 "n_changed_r_lt_50": sum(not c["same_as_paper"] for c in t1 if c["r"] < 50),
                 "changed_r": [c["r"] for c in t1 if not c["same_as_paper"]],
                 "choices": {}, "paper_point_rank_counts": {}, "splits": t1}
    for c in t1:
        k = "lm {} edit {} bonus {}".format(*c["choice"])
        res["T1"]["choices"][k] = res["T1"]["choices"].get(k, 0) + 1
        res["T1"]["paper_point_rank_counts"][str(c["paper_point_rank"])] = res["T1"]["paper_point_rank_counts"].get(str(c["paper_point_rank"]), 0) + 1
    gap = [c["wer_paper_point"] - c["wer_choice"] for c in t1]
    res["T1"]["wer_gap_paper_minus_choice"] = {"max": max(gap), "mean": float(np.mean(gap))}
    C.log("T1", {k: v for k, v in res["T1"].items() if k != "splits"})

    # T2: tune trials without M4 val_eval (and val_select)
    match = json.loads(MATCH.read_text(encoding="utf-8"))
    part = {m["pkl_index"]: m["m4_part"] for m in match}
    from collections import Counter
    res["tune400_m4_parts"] = dict(Counter(part.get(i) or "unmatched" for i in tune_idx))
    for name, drop in (("T2a_minus_val_eval", {"val_eval"}), ("T2b_minus_val_eval_val_select", {"val_eval", "val_select"})):
        idx = [i for i in tune_idx if part.get(i) not in drop]
        rows = tune_rows(G, pts, idx)
        res[name] = {"n": len(idx), **choose(rows), "rows": rows}
        C.log(name, {k: v for k, v in res[name].items() if k != "rows"})
    res["step1_no_effect"] = bool(res["T1"]["n_changed"] == 0 and res["T2a_minus_val_eval"]["same_as_paper"]
                                  and res["T2b_minus_val_eval_val_select"]["same_as_paper"])
    C.dump(res, OUT / "tune.json")
    C.log("step 1 no effect:", res["step1_no_effect"])


# ---------------------------------------------------------------------------
# step 2: rebuild tables of changed splits, aggregate, decide
# ---------------------------------------------------------------------------

def stage_rebuild(worker: int = 0, nworkers: int = 1, validate: bool = False) -> None:
    """Rebuild b2t-ours tables of the changed splits. ``validate``: split 0 with the paper setting, first 100
    test items, compared with the committed R3 table (checks this code path before any rebuilt table is used)."""
    tune = json.loads((OUT / "tune.json").read_text(encoding="utf-8"))
    changed = [c for c in tune["T1"]["splits"] if not c["same_as_paper"]]
    if validate:
        changed = [{"r": 0, "choice": list(PAPER)}]
    if not changed:
        C.log("no changed split: nothing to rebuild")
        return
    K.install_snap(0.02)
    sp = json.loads(SPLITS200.read_text(encoding="utf-8"))["splits"]
    ctx = C.b2t_ctx()
    bt = ctx.bt
    trials = ctx.fit + ctx.test
    items = ctx.items(trials)
    M13 = C.load_module("m213run", REPO / "experiments/2026-11-11-m2-13-conformal/run.py")
    TABD = DER / "tables"
    TABD.mkdir(exist_ok=True)
    decs: dict = {}
    todo = sorted(changed, key=lambda c: (tuple(c["choice"]), sp[c["r"]]["T_used"]))
    # group (choice, T) pairs so one worker keeps one decode cache per pair
    groups = sorted({(tuple(c["choice"]), sp[c["r"]]["T_used"]) for c in todo})
    mine = {g for j, g in enumerate(groups) if j % nworkers == worker}
    for c in todo:
        if (tuple(c["choice"]), sp[c["r"]]["T_used"]) not in mine:
            continue
        p = TABD / (f"validate-b2t-ours-{c['r']:03d}.json" if validate else f"b2t-ours-{c['r']:03d}.json")
        if p.exists():
            continue
        t0 = time.time()
        key = tuple(c["choice"])
        if key not in decs:
            dec = bt.Decoders(ctx.trials, {"lm_weight": key[0], "edit_penalty": key[1], "word_bonus": key[2]})
            decs.clear()
            decs[key] = dec
        dec = decs[key]
        s = sp[c["r"]]
        A = [items[i] for i in s["A"]]
        pipe = C.TrustPipeline(dec.words_fn, C.HarnessConfig(seed=C.SEED, user_config=ctx.user, max_wrong_commit=ALPHA), {})
        pipe.fit(A, A)
        if validate:
            Q = C.load_module("common4", R4 / "common4.py")
            ref = json.loads(Q.split_path("b2t-ours", 0).read_text(encoding="utf-8"))
            te = M13.item_table(pipe, [items[i] for i in s["test"][:100]])
            keys = [k for k in te if isinstance(te[k], list)]
            same = {k: te[k] == ref["test"][k][:100] for k in keys}
            res = {"r": 0, "T_used": K.TState.used, "T_used_ref": ref["T_used"], "lam_old": te["lam_old"],
                   "lam_old_ref": ref["test"]["lam_old"], "same": same, "all_same": all(same.values()) and te["lam_old"] == ref["test"]["lam_old"],
                   "seconds": round(time.time() - t0, 1)}
            C.dump(res, p)
            C.log("validate", res)
            return
        res = {"r": s["r"], "which": "ours", "decoder": list(key), "T_fitted": K.TState.fitted, "T_used": K.TState.used,
               "T_used_original": s["T_used"], "fit_report": C.clean(pipe.fit_report),
               "reuse": M13.item_table(pipe, A), "cal": M13.item_table(pipe, [items[i] for i in s["cal"]]),
               "test": M13.item_table(pipe, [items[i] for i in s["test"]]), "test_idx": s["test"]}
        C.dump(res, p)
        C.log(f"rebuilt split {s['r']} decoder {key} T {K.TState.used:.2f} (orig {s['T_used']:.2f}) ({time.time() - t0:.0f}s)")


def wilson_half(p: float, n: int) -> float:
    z = 1.96
    den = 1 + z * z / n
    return z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den


def stage_analyze() -> None:
    sys.path.insert(0, str(R3 / "repeated-splits"))
    RS = C.load_module("r3rs", R3 / "repeated-splits/run.py")
    Q = C.load_module("common4", R4 / "common4.py")
    tune = json.loads((OUT / "tune.json").read_text(encoding="utf-8"))
    changed = {c["r"] for c in tune["T1"]["splits"] if not c["same_as_paper"]}
    out: dict = {"changed_splits": sorted(changed), "R": {}}
    for R in (50, 200):
        orig, new = [], []
        for r in range(R):
            tab = json.loads(Q.split_path("b2t-ours", r).read_text(encoding="utf-8"))
            orig.append(RS.split_policies(tab))
            if r in changed:
                tab = json.loads((DER / "tables" / f"b2t-ours-{r:03d}.json").read_text(encoding="utf-8"))
            new.append(RS.split_policies(tab))
        rows = []
        for p in RS.POL:
            for m in ("wrong_commit", "commit_rate", "ewpm"):
                a = np.array([x["test"][p][m] for x in orig], float)
                b = np.array([x["test"][p][m] for x in new], float)
                hw = 1.96 * a.std(ddof=1) / math.sqrt(R)
                rows.append({"policy": p, "metric": f"mean {m}", "orig": float(a.mean()), "new": float(b.mean()),
                             "delta": float(b.mean() - a.mean()), "ci_half": hw, "effect": bool(abs(b.mean() - a.mean()) >= hw and hw >= 0 and abs(b.mean() - a.mean()) > 0)})
            nco = sum(x["test"][p]["n_commit"] for x in orig)
            nwo = sum(x["test"][p]["n_commit_wrong"] for x in orig)
            ncn = sum(x["test"][p]["n_commit"] for x in new)
            nwn = sum(x["test"][p]["n_commit_wrong"] for x in new)
            po, pn = (nwo / nco if nco else 0.0), (nwn / ncn if ncn else 0.0)
            hw = wilson_half(po, max(nco, 1))
            rows.append({"policy": p, "metric": "pooled error among commits", "orig": po, "new": pn, "delta": pn - po,
                         "ci_half": hw, "effect": bool(abs(pn - po) >= hw and abs(pn - po) > 0)})
            so = float(np.mean([x["test"][p]["wrong_commit"] > ALPHA + 1e-12 for x in orig]))
            sn = float(np.mean([x["test"][p]["wrong_commit"] > ALPHA + 1e-12 for x in new]))
            hw = wilson_half(so, R)
            rows.append({"policy": p, "metric": "share wrong-commit > alpha", "orig": so, "new": sn, "delta": sn - so,
                         "ci_half": hw, "effect": bool(abs(sn - so) >= hw and abs(sn - so) > 0)})
        out["R"][str(R)] = {"n_changed": sum(r in changed for r in range(R)), "rows": rows,
                            "n_effect": sum(x["effect"] for x in rows), "n_metrics": len(rows)}
        C.log(f"R={R}: changed {out['R'][str(R)]['n_changed']}; metrics with effect {out['R'][str(R)]['n_effect']}/{len(rows)}")
    out["decision"] = "effect" if any(v["n_effect"] for v in out["R"].values()) else "no effect"
    C.dump(out, OUT / "step2.json")
    C.log("decision", out["decision"])


def stage_posthoc() -> None:
    """NOT pre-registered (found while this item ran): the R4 forward chain tests on whole days (V1, V2, V4),
    so the tune trials of a test day are in its test set. Re-tune on each fit prefix (all trials of days 1..j)."""
    ctx = C.b2t_ctx()
    trials = ctx.fit + ctx.test
    st = pickle.loads(GRID_PKL.read_bytes())
    pts = [tuple(p) for p in st["points"]]
    days = sorted({int(t.post_implant_day) for t in trials})
    out = {"note": "post hoc, not pre-registered", "prefixes": []}
    for j in range(1, len(days)):
        idx = [t.index for t in trials if int(t.post_implant_day) <= days[j - 1]]
        c = choose(tune_rows(st["trials"], pts, idx))
        out["prefixes"].append({"fit_days": j, "n": len(idx), **c})
    out["n_changed"] = sum(not c["same_as_paper"] for c in out["prefixes"])
    C.dump(out, OUT / "posthoc-forward-chain.json")
    C.log("posthoc forward chain", [(c["fit_days"], c["choice"], c["same_as_paper"]) for c in out["prefixes"]])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=("grid", "tune", "rebuild", "validate", "analyze", "posthoc"))
    ap.add_argument("--worker", default="0/1")
    a = ap.parse_args()
    w, n = (int(x) for x in a.worker.split("/"))
    C.Log.path = DER / f"run-{a.stage}{'-w%dof%d' % (w, n) if a.stage == 'rebuild' else ''}.log"
    if a.stage == "rebuild":
        stage_rebuild(w, n)
    elif a.stage == "validate":
        stage_rebuild(validate=True)
    else:
        {"grid": stage_grid, "tune": stage_tune, "analyze": stage_analyze, "posthoc": stage_posthoc}[a.stage]()
    C.log("done", a.stage)


if __name__ == "__main__":
    main()
