"""M3-02 ablations on Brain-to-Text '25 (T15): fixed splits A / B, controls, declaration check, repeated splits.

Plan: plan.md (committed before this run). Decodes come from the Paper 1
caches (R1 + R4); new decodes go to C:/Users/zhang/bci-data/cache/m3-02-ablations.

Run (repo root), one process per decoder:
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-m3-01-02-ablations/run_b2t.py --which ours
  ... --which published ; ... --stage splits
"""

from __future__ import annotations

import argparse
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abl as A  # noqa: E402

C, K, Q = A.C, A.K, A.Q


def b2t_context():
    ctx = C.b2t_ctx()
    cd = ctx.cached[0]
    for extra in (Q.CACHE4 / "decode-b2t-words-main.pkl", A.CACHE5 / "decode-b2t-words-main.pkl"):
        if extra.exists():
            try:
                cd.d.update(pickle.loads(extra.read_bytes()))
            except Exception:  # noqa: BLE001
                pass
    cd.path = A.CACHE5 / "decode-b2t-words-main.pkl"
    return ctx


def split_idx(ctx, split: str):
    by_day: dict = {}
    for i, t in enumerate(ctx.fit):
        by_day.setdefault(t.post_implant_day, []).append(i)
    a, b = [], []
    for _, idx in sorted(by_day.items()):
        if split == "A":
            a += idx[0::2]
            b += idx[1::2]
        else:
            h = (len(idx) + 1) // 2
            a += idx[:h]
            b += idx[h:]
    return sorted(a), sorted(b)


def controls(ctx):
    """The 300-trial Paper 1 audit draw (same seed and RNG order as R4 no-guard / v4-derived) + zero stand-in."""
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    bt = ctx.bt
    rng = np.random.default_rng(bt.SEED)
    na = min(len(ctx.test), bt.CONFIG["audit_n"])
    aud_idx = sorted(rng.choice(len(ctx.test), na, replace=False).tolist())
    atest = [ctx.test[i] for i in aud_idx]
    base = [bt.B.to_symbol_stream(bt.B.trial_stream(t)) for t in atest]
    perm = rng.permutation(len(base))
    for i in range(len(perm)):
        if atest[perm[i]].truth_words == atest[i].truth_words:
            perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
    nulls = {"real": base, "intent_mismatch": [base[j] for j in perm],
             "frame_shuffled": [shuffle_stream(s, rng) for s in base], "uniform": [uniform_stream(s, rng, 0.05) for s in base],
             "zero_standin": [A.zero_standin(s) for s in base]}
    return atest, nulls


def stage_fixed(which: str) -> None:
    from fidetype.streams.spec import NeuralTextStream
    ctx = b2t_context()
    fn = ctx.dec.words_fn if which == "ours" else ctx.dec.published_plus_fn
    T = ctx.items(ctx.test)
    days = np.array(ctx.days_test)
    res: dict = {"which": which, "env": A.env_note(), "splits": {}}
    keep = {}
    for split in ("A", "B"):
        t0 = time.time()
        ia, ib = split_idx(ctx, split)
        fa = ctx.items([ctx.fit[i] for i in ia])
        cal = ctx.items([ctx.fit[i] for i in ib])
        A.log(f"b2t-{which} split {split}: fit-A {len(fa)}, cal {len(cal)}, test {len(T)}")
        ft = A.fit_four(fn, ctx.user, (fa, fa), cal, T)
        pipes, tabs = ft["pipes"], ft["tabs"]
        blk = A.gate_block(pipes["c1g1"], T)
        rows = A.arm_rows(tabs, test_groups=days, gate_blk=blk)
        lam_v4 = A.lambdas(tabs["c1g1"]["cal"])["LTT max"]
        mm = A.mismatch(pipes["c1g1"])
        tab_mm = Q.M13.item_table(mm, T)
        a, _ = A.arrays(tab_mm, lam_v4)
        rows["declaration off: raw-decoded hypotheses"] = {**A.summarise(a), "lambda": C.clean(lam_v4), "pipe": "mismatch",
                                                          "rule": "LTT max (v4)"}
        rows["declaration abstain: raw-decoded hypotheses"] = None  # filled by the streaming check (split A)
        res["splits"][split] = {"rows": rows, "T": {k: v["T"] for k, v in tabs.items()},
                                "policy": {k: v["policy"] for k, v in tabs.items()},
                                "gate_blocked_test_items": int(blk.sum()),
                                "lambdas": {k: C.clean(A.lambdas(v["cal"])) for k, v in tabs.items()}}
        keep[split] = (pipes, tabs, mm, lam_v4, tab_mm)
        ctx.cached[0].save()
        A.log(f"  split {split} done ({time.time() - t0:.0f}s): v4 wc {rows['v4 (baseline)']['wrong_commit']:.4f} "
              f"commit {rows['v4 (baseline)']['commit_rate']:.3f} eWPM {rows['v4 (baseline)']['ewpm']:.2f}; gate blocks {int(blk.sum())}")
        A.dump(res, A.OUT / f"b2t-{which}.json")

    # --- controls (split A, as Paper 1) -------------------------------------------------
    t0 = time.time()
    pipes, tabs, mm, lam_v4, tab_mm = keep["A"]
    atest, nulls = controls(ctx)
    truths = [t.truth_words for t in atest]
    groups = [t.post_implant_day for t in atest]

    def decode(s2, i):
        if which == "published":
            s3 = NeuralTextStream(s2.log_probs, s2.frame_times, s2.vocab, s2.blank_id, s2.source,
                                  {**s2.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s2.vocab_type)
            return ctx.dec.published_plus_fn(s3)
        return ctx.dec.words_fn(s2)

    lams = {k: A.lambdas(v["cal"]) for k, v in tabs.items()}
    res["controls"] = A.control_rows(pipes, lams, nulls, decode, truths, groups=groups,
                                     extra_pipes={"declaration off: raw-decoded hypotheses": (mm, lam_v4)})
    ctx.cached[0].save()
    A.log(f"  controls ({time.time() - t0:.0f}s): " + "; ".join(
        f"{arm}: " + ",".join(f"{c} {v['n_commit']}" for c, v in d.items()) for arm, d in res["controls"].items()))
    A.dump(res, A.OUT / f"b2t-{which}.json")

    # --- declaration check through the streaming layer (hypothesis route, split A) ---------
    t0 = time.time()
    v4 = pipes["c1g1"]
    fz = A.frozen_v4(v4, lam_v4, f"b2t25-{which}-splitA-v4")
    sids = [f"day-{d}" for d in ctx.days_test]
    good = {"decoder": "fidetype-b2t-" + which, "frame_temperature": float(v4.frame_scaler.temperature), "config_id": fz.config_id}
    bad = {"decoder": "fidetype-b2t-" + which}  # no temperature declared = 1.0 (raw decode)
    nb_good = [v4.decode(it, 0) for it in T]
    nb_raw = [mm.decode(it, 0) for it in T]
    streams = [it.stream(0) for it in T]
    out = {}
    for label, nbs, decl, check in (("matched, check abstain", nb_good, good, "abstain"),
                                    ("matched, check off", nb_good, None, "off"),
                                    ("raw-decoded, check off", nb_raw, bad, "off"),
                                    ("raw-decoded, check warn", nb_raw, bad, "warn"),
                                    ("raw-decoded, check abstain", nb_raw, bad, "abstain")):
        decs = A.replay(fz, [(sid, s, nb, decl) for sid, s, nb in zip(sids, streams, nbs)], "hypothesis",
                        declaration_check=check)
        tab = tabs["c1g1"]["test"] if nbs is nb_good else tab_mm
        pp = v4 if nbs is nb_good else mm
        out[label] = A.stream_metrics(pp, T, decs, tab, lam_v4)
        out[label]["n_declaration_mismatch"] = int(sum(1 for d in decs if (d.provenance.get("declaration") or {}).get("status") == "mismatch"))
        A.log(f"  stream {label}: commits {out[label]['n_commit']}, wrong {out[label]['n_wrong_commit']}, "
              f"equal-to-batch {out[label]['commit_equal_to_batch']}/{len(decs)}, mismatches {out[label]['n_declaration_mismatch']}")
    res["declaration_stream"] = out
    res["splits"]["A"]["rows"]["declaration abstain: raw-decoded hypotheses"] = {
        "n": len(T), "n_commit": out["raw-decoded, check abstain"]["n_commit"],
        "n_wrong_commit": out["raw-decoded, check abstain"]["n_wrong_commit"],
        "commit_rate": out["raw-decoded, check abstain"]["commit_rate"], "wrong_commit": out["raw-decoded, check abstain"]["wrong_commit"],
        "ewpm": out["raw-decoded, check abstain"]["ewpm"], "pipe": "stream", "rule": "LTT max (v4) + declaration abstain",
        "wrong_commit_cp95": list(K.clopper_pearson(out["raw-decoded, check abstain"]["n_wrong_commit"], len(T))),
        "wrong_commit_cp95_one_sided_upper": K.upper_one_sided(out["raw-decoded, check abstain"]["n_wrong_commit"], len(T))}
    res["splits"]["B"]["rows"].pop("declaration abstain: raw-decoded hypotheses", None)
    A.log(f"  declaration stream checks ({time.time() - t0:.0f}s)")
    ctx.cached[0].save()
    A.dump(res, A.OUT / f"b2t-{which}.json")


def stage_splits() -> None:
    res = {"env": A.env_note()}
    for cond, R in (("b2t-ours", 200), ("b2t-published", 200), ("emg-calib", 50), ("emg-xsession", 50), ("emg-xsubject", 50)):
        t0 = time.time()
        res[cond] = A.split_arm_outcomes(cond, R)
        A.log(f"splits {cond}: R {res[cond]['R']}, v4 mean {res[cond]['v4 (baseline)']['wrong_commit_mean']:.4f} ({time.time() - t0:.0f}s)")
    A.dump(res, A.OUT / "splits.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", default=None)
    ap.add_argument("--stage", default="fixed")
    a = ap.parse_args()
    A.set_log(A.OUT / f"run-b2t-{a.which or a.stage}.log")
    if a.stage == "splits":
        stage_splits()
    else:
        stage_fixed(a.which)
    A.log("done")


if __name__ == "__main__":
    main()
