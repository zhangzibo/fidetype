"""R3 item 6: sEMG main rows without the 295 near-variant test sentences.

Editor M6. 295 of the 551 sEMG test sentences have a near variant in the
character-LM training text (round-1 leakage analysis). Here every main sEMG
policy row (baselines arrays: always commit, always offer, plain thresholds,
trust plug-in, clean CRC / LTT, fit-A plug-in, gaze typing; plus the
deployable max-rule CRC / LTT from the clean item tables) is recomputed on the
256 kept test sentences, next to the full 551. The LM itself is unchanged
(original LM); this is a test-set sensitivity row, not a re-fit.

CIs: participant-cluster percentile bootstrap, unified seed and B.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/emg-exclusion/run.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "run.log"
POL = ("always_commit", "never_commit", "raw_no_guard", "no_guard", "trust", "clean_plugin", "crc", "ltt",
       "crc_maxrule", "ltt_maxrule", "gaze_only")
DIFFS = [("trust", "never_commit"), ("trust", "gaze_only"), ("trust", "always_commit"), ("crc_maxrule", "gaze_only"),
         ("crc_maxrule", "never_commit")]


def main() -> None:
    rep = json.loads((K.R1 / "leakage/results/build_report.json").read_text(encoding="utf-8"))
    leaked = set(rep["emg"]["test_sentences_with_near_variant"])
    b = C.emg_base()
    texts = [t for p in b.pids for t, _ in b.plan[p]["test"]]
    who = [p for p in b.pids for _ in b.plan[p]["test"]]
    keep = np.array([t not in leaked for t in texts])
    res = {"n_test": len(texts), "n_kept": int(keep.sum()), "n_removed": int((~keep).sum()),
           "bootstrap": {"seed": K.UNIFIED_SEED, "B": K.UNIFIED_B, "unit": "participant cluster"}, "conditions": {}}
    for c in ("calib", "xsession", "xsubject"):
        a = json.loads((K.R1 / f"baselines/results/arrays-emg-{c}.json").read_text(encoding="utf-8"))
        arrs = {p: {k: np.asarray(v, float) for k, v in d.items()} for p, d in a["arrays"].items()}
        items = json.loads((K.R1 / f"clean-drift/results/items-emg-{c}.json").read_text(encoding="utf-8"))
        assert items["participants_test"] == who, "test order differs"
        ca = K.arr(items["items_cal"])
        lp = float(C.fnum(items["items_test"]["lam_old"]))
        rc, rl = K.crc(ca), K.ltt(ca)
        arrs["crc_maxrule"] = C.item_arrays(items["items_test"], max(lp, rc.threshold))
        arrs["ltt_maxrule"] = C.item_arrays(items["items_test"], max(lp, rl.threshold))
        # sanity: the committed arrays reproduce the paper's trust eWPM
        cl_all = np.unique(who, return_inverse=True)[1]
        out = {}
        for lab, m in (("all 551", np.ones(len(texts), bool)), ("near variants removed (256)", keep),
                       ("near variants only (295)", ~keep)):
            sub = {p: {k: v[m] for k, v in arrs[p].items()} for p in POL}
            ns = SimpleNamespace(cluster=np.unique(np.asarray(who)[m], return_inverse=True)[1], sent=None, scheme="cluster")
            pt = C.point(sub)
            for p in POL:
                pt[p]["n_commit"] = int(sub[p]["com"].sum())
                pt[p]["n_wrong_commit"] = int(round(sub[p]["wc"].sum()))
                pt[p]["wrong_commit_cp95_upper"] = K.upper_one_sided(pt[p]["n_wrong_commit"], int(m.sum()))
            out[lab] = {"n": int(m.sum()), "point": pt,
                        "ci": C.bootstrap(sub, ns, B=K.UNIFIED_B, seed=K.UNIFIED_SEED, diffs=DIFFS)}
        res["conditions"][f"emg-{c}"] = out
        C.log(f"emg-{c}: trust eWPM {out['all 551']['point']['trust']['ewpm']:.3f} -> {out['near variants removed (256)']['point']['trust']['ewpm']:.3f}; "
              f"always commit wc {out['all 551']['point']['always_commit']['wrong_commit']:.3f} -> "
              f"{out['near variants removed (256)']['point']['always_commit']['wrong_commit']:.3f}")
        del cl_all
    C.dump(res, OUT / "emg_exclusion.json")
    L = ["# sEMG: main rows with and without the 295 near-variant test sentences", "",
         f"Original LM; test-set exclusion only. 95 % CIs: participant-cluster bootstrap, seed {K.UNIFIED_SEED}, B = {K.UNIFIED_B}. "
         "Counts for small commit numbers. CP95 = exact one-sided upper bound of the wrong-commit rate (items independent).", ""]
    for c, out in res["conditions"].items():
        L += [f"## {c}", "", "| policy | eWPM all 551 | eWPM 256 kept [CI] | wrong-commit all | wrong-commit kept [CI] (CP95) | commits kept (wrong) | eWPM near-variants only |",
              "|---|---|---|---|---|---|---|"]
        A, Kp, N = out["all 551"], out["near variants removed (256)"], out["near variants only (295)"]
        for p in POL:
            ci = Kp["ci"]["policies"][p]
            L.append(f"| {p} | {A['point'][p]['ewpm']:.2f} | {Kp['point'][p]['ewpm']:.2f} {C.fci(ci['ewpm'], 2)} | {A['point'][p]['wrong_commit']:.4f} | "
                     f"{Kp['point'][p]['wrong_commit']:.4f} {C.fci(ci['wrong_commit'], 3)} ({Kp['point'][p]['wrong_commit_cp95_upper']:.4f}) | "
                     f"{Kp['point'][p]['n_commit']} ({Kp['point'][p]['n_wrong_commit']}) | {N['point'][p]['ewpm']:.2f} |")
        L += ["", "Paired differences on the 256 kept sentences (eWPM CI): " + "; ".join(
            f"{k} {C.fci(v['ewpm'], 2)}" for k, v in Kp["ci"]["diffs"].items()), ""]
    (OUT / "tables.md").write_text("\n".join(L), encoding="utf-8")
    C.log("done")


if __name__ == "__main__":
    main()
