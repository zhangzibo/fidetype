"""R3 item 5: MEG CRC with calibration / test split by sentence (and by participant).

Stats review M4(a). The MEG test pool has 637 instances of 17 sentences
typed by 19 participants. Instances of one sentence are dependent, so the
exchangeable unit for a guarantee on new sentences is the sentence.

1. Guarantee status. Sentence-level CRC (loss = mean loss of the
   sentence's instances, one value per sentence) needs n >= 1/alpha - 1 = 19
   calibration sentences at alpha = 0.05. The clean calibration set has 5
   sentences, the whole test pool 17, the val set 11: sentence-level CRC is
   infeasible on this data set at any split (it never commits). The same
   holds for participants (19 in all; a calibration set needs >= 19).
2. What instance-level CRC does when calibration and test sentences are
   disjoint: grouped splits of the G1 item table (trust gate fitted on val),
   k calibration sentences (5, 8, 11 of 17) or participants (6, 12 of 19),
   R = 1000; compared with random instance splits of the same size.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/meg-grouped/run.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
ALPHA = CONFIG["alpha"]


def group_crc(a: dict, groups: np.ndarray, alpha: float = ALPHA):
    """CRC with one loss per group (mean over its instances): bound (n_g R + 1)/(n_g + 1)."""
    ug = np.unique(groups)
    s_inst = a["s"]
    lams = np.concatenate([np.unique(s_inst[np.isfinite(s_inst)]), [math.inf]])
    n = ug.size
    for lam in lams:  # ascending; the loss is non-increasing in lam
        on = s_inst >= lam
        loss = np.where(on, a["c"], a["f"])
        r = np.mean([loss[groups == g].mean() for g in ug])
        if (n * r + 1) / (n + 1) <= alpha + 1e-12:
            return float(lam), True
    return math.inf, False


def run_splits(a: dict, mk, reps: int, rng, groups_for_gcrc=None) -> dict:
    rows = {k: [] for k in ("CRC instance", "CRC instance max-rule", "LTT instance", "CRC group-level")}
    feas = []
    for _ in range(reps):
        cal, tst = mk(rng)
        ca, te = K.take(a, cal), K.take(a, tst)
        rc, rl = K.crc(ca), K.ltt(ca)
        lp = a["lam_old"]
        lam = {"CRC instance": rc.threshold, "CRC instance max-rule": max(lp, rc.threshold), "LTT instance": rl.threshold}
        if groups_for_gcrc is not None:
            lg, ok = group_crc(ca, groups_for_gcrc[cal])
            lam["CRC group-level"] = lg
            feas.append(ok)
        for k, v in lam.items():
            rows[k].append(K.outcome(te, v))
    out = {}
    for k, v in rows.items():
        if not v:
            continue
        wc = np.array([x["wrong_commit"] for x in v])
        nc = sum(x["n_commit"] for x in v)
        out[k] = {"wrong_commit": K.summ(wc), "share_gt_alpha": float(np.mean(wc > ALPHA + 1e-12)),
                  "commit_rate": K.summ([x["commit_rate"] for x in v]), "share_no_commit": float(np.mean([x["n_commit"] == 0 for x in v])),
                  "error_among_commits_pooled": (sum(x["n_commit_wrong"] for x in v) / nc) if nc else None,
                  "ewpm": K.summ([x["ewpm"] for x in v])}
    if feas:
        out["group_level_feasible_share"] = float(np.mean(feas))
    return out


def main() -> None:
    d = json.loads((K.REPO / "experiments/2026-11-11-g1-async-meg-trust/results/items-meg-async.json").read_text(encoding="utf-8"))
    a = K.arr(d["test"])
    sent = np.asarray(d["sentence_ids_test"])
    part = np.unique(d["participants_test"], return_inverse=True)[1]
    n = a["s"].size
    rng = np.random.default_rng(CONFIG["seed"])
    res = {"n_test_pool": n, "n_sentences": int(np.unique(sent).size), "n_participants": int(np.unique(part).size),
           "eligible_rate": float(np.isfinite(a["s"]).mean()), "top1_right_rate": float(1 - a["c"].mean()),
           "lam_old": a["lam_old"], "min_groups_for_crc": math.ceil(1 / ALPHA - 1),
           "min_groups_for_ltt_zero_loss": math.ceil(math.log(CONFIG["delta"]) / math.log(1 - ALPHA)),
           "guarantee_status": {
               "clean calibration (5 val sentences)": "sentence-level CRC infeasible (5 < 19): never commits; instance-level CRC has no guarantee for new sentences",
               "val (11 sentences)": "sentence-level CRC infeasible (11 < 19)",
               "whole test pool (17 sentences)": "sentence-level CRC infeasible (17 < 19)",
               "participants (19)": "participant-level CRC needs all 19 for calibration: no test participants left"},
           "splits": {}}
    R = CONFIG["reps"]
    for k in CONFIG["sentence_k"]:
        ug = np.unique(sent)

        def mk(rng, k=k, ug=ug):
            cg = rng.choice(ug, k, replace=False)
            m = np.isin(sent, cg)
            return np.where(m)[0], np.where(~m)[0]
        g = run_splits(a, mk, R, rng, groups_for_gcrc=sent)
        ncal = int(round(np.mean([np.isin(sent, rng.choice(ug, k, replace=False)).sum() for _ in range(200)])))

        def mkr(rng, ncal=ncal):
            p = rng.permutation(n)
            return p[:ncal], p[ncal:]
        res["splits"][f"sentence-grouped {k} of 17"] = g
        res["splits"][f"random instances, n_cal {ncal} (same size as {k} sentences)"] = run_splits(a, mkr, R, rng)
        C.log(f"sentence k={k}: grouped CRC wc {g['CRC instance']['wrong_commit']['mean']:.4f} p95 {g['CRC instance']['wrong_commit']['p95']:.4f} "
              f">a {g['CRC instance']['share_gt_alpha']:.3f} commit {g['CRC instance']['commit_rate']['mean']:.3f}; group-level feasible "
              f"{g['group_level_feasible_share']:.2f}")
    for k in CONFIG["participant_k"]:
        up = np.unique(part)

        def mkp(rng, k=k, up=up):
            cg = rng.choice(up, k, replace=False)
            m = np.isin(part, cg)
            return np.where(m)[0], np.where(~m)[0]
        g = run_splits(a, mkp, R, rng, groups_for_gcrc=part)
        res["splits"][f"participant-grouped {k} of 19"] = g
        C.log(f"participant k={k}: grouped CRC wc {g['CRC instance']['wrong_commit']['mean']:.4f} p95 {g['CRC instance']['wrong_commit']['p95']:.4f} "
              f">a {g['CRC instance']['share_gt_alpha']:.3f}")
    C.dump(res, OUT / "meg_grouped.json")
    L = ["# MEG: CRC with calibration and test split by sentence / participant", "",
         f"G1 item table (trust gate fitted on val; 637 test instances, 17 sentences x 19 participants); eligible {res['eligible_rate']:.3f}; "
         f"top-1 right {res['top1_right_rate']:.4f}. R = {R} splits per row. alpha = {ALPHA}.", "",
         "## Guarantee status", ""]
    L += [f"- {k}: {v}" for k, v in res["guarantee_status"].items()]
    L += [f"- Minimum calibration groups: CRC {res['min_groups_for_crc']}, LTT (zero loss, delta 0.1) {res['min_groups_for_ltt_zero_loss']}.", "",
          "## Splits", "", "| split | rule | wrong-commit mean [p05, p95] | share > α | commit rate mean | no-commit share | error among commits (pooled) | eWPM mean |",
          "|---|---|---|---|---|---|---|---|"]
    for sname, g in res["splits"].items():
        for rule, v in g.items():
            if not isinstance(v, dict):
                continue
            eac = v["error_among_commits_pooled"]
            L.append(f"| {sname} | {rule} | {v['wrong_commit']['mean']:.4f} [{v['wrong_commit']['p05']:.4f}, {v['wrong_commit']['p95']:.4f}] | "
                     f"{v['share_gt_alpha']:.3f} | {v['commit_rate']['mean']:.4f} | {v['share_no_commit']:.3f} | {C.fmt(eac, 3)} | {v['ewpm']['mean']:.3f} |")
        if "group_level_feasible_share" in g:
            L.append(f"| {sname} | group-level CRC feasible share | {g['group_level_feasible_share']:.2f} | | | | | |")
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    C.log("done")


if __name__ == "__main__":
    main()
