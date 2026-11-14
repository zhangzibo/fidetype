"""M3-01: the trust layer end to end on SpanishBCBL MEG provenance streams (+ the M3-02 arms).

Plan: plan.md. SpanishBCBL is CC BY-NC 4.0: this script writes aggregated
numbers only (no text, no per-trial rows, no participant ids).

Per run (provenance streams of M5-13, ``<run>_provenance``):
1. Fit the four pipelines on the Paper 1 clean split (val-A = 6 random val
   sentences, seed 0; calibration = the other val sentences), item tables on
   calibration and test (637 instances); all arms of plan.md.
2. Freeze the v4 pipeline (``FrozenTrustConfig``) and replay every test
   stream through ``StreamingTrustLayer`` (frames route, one session per
   participant). Check that the streaming commits equal the batch commits;
   eWPM from the user simulation driven by the streaming decisions.
3. Controls: shuffled MEG and zero MEG (the decoder's real outputs, from
   ``<run>_beam-controls``), another sentence of the same participant
   (intent mismatch), frame-shuffled, uniform.
4. Decoder strength: top-1 sentence accuracy, top-1 CER, truth in the n-best.

Run (repo root):
  python -m fidetype.utils.isolation run --class background --threads 1 -- \
    .venv/Scripts/python.exe -I experiments/2026-11-14-m3-01-02-ablations/run_meg.py [--runs a,b]
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
STREAMS = Path("C:/Users/zhang/bci-data/streams")
RUNS = ("m1-09-r4b-full-medium", "m1-09-r4b-full-medium-s1", "m1-09-r4b-full-medium-s2", "m1-09-r4b-full", "m1-09-r5-medium")
VAL_A_SENTENCES = 6  # Paper 1 (r1 baselines/config.json: meg_val_a_sentences)
SPLIT_SEED = 0  # Paper 1 (r1 baselines/config.json: seed)
CONTROL_SEED = 0  # the G1 audit seed (experiments/2026-11-11-g1-async-meg-trust/config.json)
GAZE_CPM = 20.0


def with_logprobs(s, lp, tag):
    from fidetype.streams.spec import NeuralTextStream
    assert lp.shape == s.log_probs.shape, (lp.shape, s.log_probs.shape)
    return NeuralTextStream(log_probs=lp.astype(np.float32), frame_times=s.frame_times, vocab=s.vocab, blank_id=s.blank_id,
                            source=s.source + "+" + tag, meta={**s.meta, "audit": tag}, vocab_type=s.vocab_type)


def decoder_stats(pipe, items) -> dict:
    from fidetype.eval.metrics import cer
    acc, cers, inn = [], [], []
    for it in items:
        nb = pipe.decode(it, 0)
        top = nb.top.text if nb.top is not None else ""
        acc.append(top == it.text)
        cers.append(cer(top, it.text))
        inn.append(it.text in list(nb.texts))
    return {"top1_sentence_acc": float(np.mean(acc)), "top1_cer_mean": float(np.mean(cers)), "truth_in_nbest": float(np.mean(inn)),
            "n_top1_correct": int(np.sum(acc)), "n_truth_in_nbest": int(np.sum(inn)), "n": len(items)}


def run_one(run: str) -> dict:
    from fidetype.trust.guard import shuffle_stream, uniform_stream
    t0 = time.time()
    root = STREAMS / f"{run}_provenance"
    from fidetype.streams.spec import NeuralTextStream
    orig = NeuralTextStream.__dict__["from_npz"]

    def from_npz(cls, path, _o=orig):
        st = _o.__func__(cls, path)
        st.meta.setdefault("participant", st.meta.get("spanishbcbl.participant"))
        return st

    NeuralTextStream.from_npz = classmethod(from_npz)
    try:
        cond = C.meg_ctx(root=str(root))
    finally:
        NeuralTextStream.from_npz = orig
    # Provenance streams carry the participant as "spanishbcbl.participant" (labels: "subject").
    pn = [rr.get("subject") or s.meta.get("spanishbcbl.participant") for s, rr in cond.test_raw]
    assert all(pn), "participant missing"
    cond.part_names = pn
    cond.cluster = np.unique(pn, return_inverse=True)[1]
    for d in cond.cached:
        ex = A.CACHE5 / d.path.name
        if ex.exists():
            try:
                d.d.update(pickle.loads(ex.read_bytes()))
            except Exception:  # noqa: BLE001
                pass
        d.path = A.CACHE5 / d.path.name
    rng = np.random.default_rng(SPLIT_SEED)
    us = rng.permutation(int(cond.val_sent.max()) + 1)
    a_s = set(us[:VAL_A_SENTENCES].tolist())
    fitA = [it for it, s in zip(cond.val, cond.val_sent) if s in a_s]
    cal = [it for it, s in zip(cond.val, cond.val_sent) if s not in a_s]
    T = cond.test
    A.log(f"meg {run}: val {len(cond.val)} ({int(cond.val_sent.max()) + 1} sentences), fit-A {len(fitA)}, cal {len(cal)}, test {len(T)}")
    ft = A.fit_four(cond.decode, cond.user, (fitA, fitA), cal, T, base={"grid": cond.base["grid"]})
    pipes, tabs = ft["pipes"], ft["tabs"]
    groups = np.asarray(cond.cluster)
    blk = A.gate_block(pipes["c1g1"], T)
    rows = A.arm_rows(tabs, test_groups=groups, gate_blk=blk)
    gz = C.metrics(C.gaze_arrays([it.text for it in T], GAZE_CPM))
    lam_v4 = A.lambdas(tabs["c1g1"]["cal"])["LTT max"]
    r = {"run": run, "n_val": len(cond.val), "n_fitA": len(fitA), "n_cal": len(cal), "n_test": len(T),
         "n_participants_test": int(groups.max()) + 1, "rows": rows, "gaze_ewpm": gz["ewpm"],
         "T": {k: v["T"] for k, v in tabs.items()}, "policy": {k: v["policy"] for k, v in tabs.items()},
         "lambdas": {k: C.clean(A.lambdas(v["cal"])) for k, v in tabs.items()}, "gate_blocked_test_items": int(blk.sum()),
         "decoder_test": decoder_stats(pipes["c1g1"], T), "decoder_cal": decoder_stats(pipes["c1g1"], cal),
         "decoder_test_raw": decoder_stats(pipes["c0g1"], T)}
    # calibration-set commit data: how many calibration items would LTT need?
    ca = K.arr(tabs["c1g1"]["cal"])
    r["cal_eligible"] = int(np.isfinite(ca["s"]).sum())
    r["cal_wrong_if_all_commit"] = int(round(ca["c"][np.isfinite(ca["s"])].sum()))
    # end to end: frozen config through the streaming layer (frames route)
    fz = A.frozen_v4(pipes["c1g1"], lam_v4, f"spanishbcbl-{run}-v4")
    jobs = [(f"p{g}", it.stream(0), None, None) for it, g in zip(T, groups)]
    decs = A.replay(fz, jobs, "frames", decode_fn=cond.decode)
    r["stream"] = {"config_id": fz.config_id, **A.stream_metrics(pipes["c1g1"], T, decs, tabs["c1g1"]["test"], lam_v4)}
    fzg = A.frozen_v4(pipes["c1g1"], lam_v4, f"spanishbcbl-{run}-v4-gateB", gate=True)
    decs_g = A.replay(fzg, jobs, "frames", decode_fn=cond.decode)
    r["stream_gate"] = {"config_id": fzg.config_id, **A.stream_metrics(pipes["c1g1"], T, decs_g, tabs["c1g1"]["test"], lam_v4)}
    A.log(f"  stream: commits {r['stream']['n_commit']} (equal to batch {r['stream']['commit_equal_to_batch']}/{len(decs)}), "
          f"wrong {r['stream']['n_wrong_commit']}, eWPM {r['stream']['ewpm']:.2f}; gate B commits {r['stream_gate']['n_commit']}")
    # controls (G1 audit draw)
    truths = [it.text for it in T]
    part = cond.part_names
    crng = np.random.default_rng(CONTROL_SEED)
    base = [s for s, _ in cond.test_raw]
    ctl = np.load(STREAMS / f"{run}_beam-controls" / "logprobs_test.npz")
    n = len(base)
    other = []
    for i in range(n):
        same_p = [j for j in range(n) if part[j] == part[i] and truths[j] != truths[i]]
        pool = same_p or [j for j in range(n) if truths[j] != truths[i]]
        other.append(int(crng.choice(pool)))
    nulls = {"real": base,
             "shuffled_meg": [with_logprobs(s, ctl["shuffled__" + rr["file"]], "shuffled_meg") for s, rr in cond.test_raw],
             "zero_input": [with_logprobs(s, ctl["zeros__" + rr["file"]], "zeros_meg") for s, rr in cond.test_raw],
             "intent_mismatch": [base[j] for j in other],
             "frame_shuffled": [shuffle_stream(s, crng) for s in base],
             "uniform": [uniform_stream(s, crng, 0.05) for s in base]}
    lams = {k: A.lambdas(v["cal"]) for k, v in tabs.items()}
    r["controls"] = A.control_rows(pipes, lams, nulls, lambda s, i: cond.decode(s), truths, groups=groups)
    C.save_caches(cond)
    v = rows["v4 (baseline)"]
    A.log(f"  {run} done ({time.time() - t0:.0f}s): v4 wc {v['wrong_commit']:.4f} commits {v['n_commit']} eWPM {v['ewpm']:.2f} "
          f"(gaze {gz['ewpm']:.2f}); top-1 acc {r['decoder_test']['top1_sentence_acc']:.3f}, CER {r['decoder_test']['top1_cer_mean']:.3f}; "
          f"no-RC commits {rows['no risk control']['n_commit']}, always-commit wrong {rows['always commit']['n_wrong_commit']}")
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=",".join(RUNS))
    ap.add_argument("--out", default="meg.json")
    a = ap.parse_args()
    A.set_log(A.OUT / f"run-{Path(a.out).stem}.log")
    out_p = A.OUT / a.out
    res = A.load_json(out_p) if out_p.exists() else {"env": A.env_note(), "runs": {}}
    for run in a.runs.split(","):
        res["runs"][run] = run_one(run)
        A.dump(res, out_p)
    A.log("done")


if __name__ == "__main__":
    main()
