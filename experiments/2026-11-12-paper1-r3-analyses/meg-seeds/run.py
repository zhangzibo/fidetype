"""R3 item 10: MEG decoder seeds 0 / 1 / 2 (CER) and the trust harness on seeds 1 and 2.

Stats review M5 (seeds TODO), editor M8. Seeds 1 and 2 of the Paper 1 MEG
decoder (m1-09 r4a -> r4b full-medium) were trained by the round-1 GPU queue
(``../2026-11-12-paper1-r1-analyses/gpu-seeds``). Here (CPU only):

1. ``cer``: per-seed test CER (greedy, beam no LM, beam + LM as is, beam +
   LM val-tuned; real, shuffled and zeros MEG) from each seed's beam
   ``results.json``; mean +- SD over seeds 0 / 1 / 2.
2. ``trust``: the G1 trust harness (``experiments/2026-11-11-g1-async-meg-trust/run.py``,
   stages harness (no sensitivity), items, splits) on the seed-1 and seed-2
   streams, with the G1 settings (fit on val, test 637 instances, RETUNED
   beam, lm_weight 0.5). Outputs go to ``results/seed-<k>/`` (the G1 folder
   is not touched). Seed 0 = the committed G1 results.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r3-analyses/meg-seeds/run.py --stage cer
                 ... --stage trust --seed 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common3 as K  # noqa: E402

C = K.C
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
G1 = K.REPO / "experiments/2026-11-11-g1-async-meg-trust"
BEAM = {0: K.REPO / "experiments/2026-11-11-m1-09-async-full/results/beam-m1-09-r4b-full-medium/results.json",
        1: K.R1 / "gpu-seeds/results/beam-m1-09-r4b-full-medium-s1/results.json",
        2: K.R1 / "gpu-seeds/results/beam-m1-09-r4b-full-medium-s2/results.json"}
STREAMS = {0: "C:/Users/zhang/bci-data/streams/m1-09-r4b-full-medium",
           1: "C:/Users/zhang/bci-data/streams/m1-09-r4b-full-medium-s1",
           2: "C:/Users/zhang/bci-data/streams/m1-09-r4b-full-medium-s2"}
DECS = ("greedy", "beam_nolm", "beam_lm_retuned", "beam_lm_valtuned")


def stage_cer() -> None:
    C.Log.path = OUT / "run-cer.log"
    per = {}
    for s, p in BEAM.items():
        if not p.exists():
            C.log(f"seed {s}: {p} missing")
            continue
        r = json.loads(p.read_text(encoding="utf-8"))["splits"]["test"]["results"]
        per[s] = {cond: {d: (r[cond][d]["cer_target"]["mean"] if isinstance(r[cond][d]["cer_target"], dict) else r[cond][d]["cer_target"])
                         for d in DECS if d in r.get(cond, {})} for cond in r}
        C.log(f"seed {s}: " + "; ".join(f"{d} {per[s]['real'][d]:.4f}" for d in DECS if d in per[s]["real"]))
    summ = {}
    for cond in ("real", "shuffled", "zeros"):
        for d in DECS:
            v = [per[s][cond][d] for s in sorted(per) if cond in per[s] and d in per[s][cond]]
            if v:
                summ[f"{cond}/{d}"] = {"values": v, "seeds": sorted(per), "mean": float(np.mean(v)),
                                       "sd": float(np.std(v, ddof=1)) if len(v) > 1 else None}
    C.dump({"per_seed": per, "summary": summ}, OUT / "seed_cer.json")
    L = ["# MEG decoder seeds: test CER (637 instances, mean over sentences)", "", f"Seeds: {sorted(per)}.", "",
         "| condition / decoder | " + " | ".join(f"seed {s}" for s in sorted(per)) + " | mean ± SD |", "|---|" + "---|" * (len(per) + 1)]
    for k, v in summ.items():
        L.append(f"| {k} | " + " | ".join(f"{x:.3f}" for x in v["values"]) + f" | {v['mean']:.3f} ± {C.fmt(v['sd'], 3)} |")
    (OUT / "cer.md").write_text("\n".join(L), encoding="utf-8")


def stage_trust(seed: int) -> None:
    g = C.load_module("g1run", G1 / "run.py")
    out = OUT / f"seed-{seed}"
    out.mkdir(exist_ok=True)
    g.Logger.path = out / "run.log"
    root = Path(STREAMS[seed])
    dec, kw = g.make_decoder()
    val_raw, test_raw = g.load_split(root, "val"), g.load_split(root, "test")
    val = [g.Item(s, r["target_text"]) for s, r in val_raw]
    test = [g.Item(s, r["target_text"]) for s, r in test_raw]
    sid = {t: i for i, t in enumerate(sorted({it.text for it in test}))}
    part_names = [r["participant"] for _, r in test_raw]
    ctx = {"name": f"seed{seed}", "root": root, "out": out, "dec": dec, "kw": kw, "val": val, "test": test,
           "test_raw": test_raw, "cache": {}, "sent": np.array([sid[it.text] for it in test]),
           "part": np.unique(part_names, return_inverse=True)[1], "part_names": part_names}
    g.stage_harness(ctx, sensitivity=False)
    g.stage_items(ctx)
    g.stage_splits(ctx)
    g.log("done")


def stage_table() -> None:
    C.Log.path = OUT / "run-table.log"
    rows = {}
    srcs = {0: (G1 / "results/harness-async.json", G1 / "results/items-meg-async.json", G1 / "results/crc-splits-async.json")}
    for s in (1, 2):
        d = OUT / f"seed-{s}"
        srcs[s] = (d / f"harness-seed{s}.json", d / f"items-meg-seed{s}.json", d / f"crc-splits-seed{s}.json")
        if srcs[s][0].exists():  # keep only numbers: drop the example sentences
            H = json.loads(srcs[s][0].read_text(encoding="utf-8"))
            if "examples" in H:
                H.pop("examples")
                C.dump(H, srcs[s][0])
    for s, (h, it, sp) in srcs.items():
        if not h.exists():
            continue
        H = json.loads(h.read_text(encoding="utf-8"))
        I = json.loads(it.read_text(encoding="utf-8"))
        S = json.loads(sp.read_text(encoding="utf-8"))
        pol = H["policies"]
        a = K.arr(I["test"])
        g = S["splits"].get("grouped_sentence_11of17", {})
        rows[s] = {"policies": {k: {"ewpm": pol[k]["ewpm"], "wrong_commit": pol[k]["wrong_commit_rate"],
                                    "commit_rate": pol[k].get("rate_commit", pol[k].get("commit_rate"))} for k in pol},
                   "trust_minus_gaze_ci_two_way": H["bootstrap"].get("two_way", {}).get("diffs", {}).get("trust-gaze_only", {}).get("ewpm"),
                   "eligible_rate": float(np.isfinite(a["s"]).mean()), "top1_right": float(1 - a["c"].mean()),
                   "nbest": H.get("nbest"),
                   "grouped_sentence_crc_wrong_commit_mean": (g.get("crc", {}).get("wrong_commit", {}) or {}).get("mean"),
                   "grouped_sentence_crc_commit_mean": (g.get("crc", {}).get("commit_rate", {}) or {}).get("mean")}
        C.log(f"seed {s}: " + "; ".join(f"{k} eWPM {v['ewpm']:.3f} wc {v['wrong_commit']:.4f}" for k, v in rows[s]["policies"].items()))
    C.dump(rows, OUT / "seed_trust.json")
    L = ["# MEG seeds: trust harness (G1 settings; fit on val, 637 test instances)", "",
         "| seed | always commit eWPM / WC | trust eWPM / WC / commit | gaze eWPM | trust − gaze (two-way CI) | eligible | top-1 right | grouped-sentence CRC WC (11 of 17) |",
         "|---|---|---|---|---|---|---|---|"]
    for s, r in sorted(rows.items()):
        p = r["policies"]
        gz = p.get("gaze_only", {}).get("ewpm")
        L.append(f"| {s} | {p['commit']['ewpm']:.3f} / {p['commit']['wrong_commit']:.3f} | {p['trust']['ewpm']:.3f} / {p['trust']['wrong_commit']:.4f} / "
                 f"{C.fmt(p['trust']['commit_rate'], 3)} | {C.fmt(gz, 3)} | {C.fci(r['trust_minus_gaze_ci_two_way'], 2)} | {r['eligible_rate']:.3f} | "
                 f"{r['top1_right']:.4f} | {C.fmt(r['grouped_sentence_crc_wrong_commit_mean'], 4)} |")
    (OUT / "trust.md").write_text("
".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    if a.stage == "cer":
        stage_cer()
    elif a.stage == "trust":
        stage_trust(a.seed)
    else:
        stage_table()


if __name__ == "__main__":
    main()
