"""Benchmark: greedy vs CTC beam vs CTC beam + 6-gram char LM on simulator streams.

Needs the LMs from build_lms.py (C:/Users/zhang/bci-data/lm/).

Steps
1. Tune lm_weight x insertion_bonus (beam 16), then beam, on a DEV set
   (100 held-out Tatoeba sentences, median preset).
2. Evaluate on a TEST set (200 other held-out Tatoeba sentences) for the
   best, median and worst presets: CER, WER, speed, n-best oracle CER,
   calibration (ECE) of the 1-best character confidences.
3. Extra checks: 200 corpus.py sentences (out of domain for the LM), and
   Spanish (Tatoeba held-out, SpanishBCBL targets) with the Spanish LM.

Run: uv run python experiments/2026-11-08-lm-beam/run_sim_benchmark.py
Output: results/benchmark.json and printed markdown tables.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from fidetype.eval.metrics import cer, ctc_greedy_decode, expected_calibration_error, wer
from fidetype.lm import CharNgramLM, align_pairs, ctc_prefix_beam_search, n_best_to_posteriors
from fidetype.lm.beam import _nbest_marginal
from fidetype.streams.corpus import sentences as toy_sentences
from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig

LM_DIR = Path("C:/Users/zhang/bci-data/lm")
HERE = Path(__file__).parent
OUT = HERE / "results"
PRESETS = ("best", "median", "worst")
SIM_SEED = {"best": 101, "median": 102, "worst": 103}


def pick(path: Path, n: int, skip: int = 0, lo: int = 20, hi: int = 80) -> list[str]:
    lines = [s for s in path.read_text(encoding="utf-8").splitlines() if lo <= len(s) <= hi]
    return lines[skip : skip + n]


def simulate(sents, preset, seed):
    sim = NoisyDecoderSimulator(SimConfig.preset(preset), seed=seed)
    return [sim.simulate(s) for s in sents]


def char_correct(ref: str, hyp: str) -> np.ndarray:
    ok = np.zeros(len(hyp), dtype=bool)
    for i, j in align_pairs(hyp, ref):
        if i is not None and j is not None and hyp[i] == ref[j]:
            ok[i] = True
    return ok


def mean(x):
    return float(np.mean(x)) if len(x) else float("nan")


def decode_set(sims, lm, **kw):
    hyps, times = [], []
    for r in sims:
        t0 = time.perf_counter()
        h = ctc_prefix_beam_search(r.stream, lm=lm, **kw)
        times.append(time.perf_counter() - t0)
        hyps.append(h)
    return hyps, times


def rates(sims, texts):
    return mean([cer(r.text, t) for r, t in zip(sims, texts)]), mean([wer(r.text, t) for r, t in zip(sims, texts)])


def tune(lm, dev_sims):
    rows = []
    for w in (0.5, 1.0, 1.5, 2.0, 3.0):
        for b in (0.0, 1.0, 2.0, 3.0):
            hyps, _ = decode_set(dev_sims, lm, lm_weight=w, insertion_bonus=b, beam=16, n_best=1, align=False)
            c, wr = rates(dev_sims, [h[0].text for h in hyps])
            rows.append({"lm_weight": w, "insertion_bonus": b, "beam": 16, "cer": c, "wer": wr})
            print(f"dev w={w} b={b} cer={c:.4f} wer={wr:.4f}", flush=True)
    best = min(rows, key=lambda r: (r["cer"], r["wer"]))
    beam_rows = []
    for bm in (4, 8, 16, 32, 64):
        hyps, times = decode_set(dev_sims, lm, lm_weight=best["lm_weight"], insertion_bonus=best["insertion_bonus"], beam=bm, n_best=1, align=False)
        c, wr = rates(dev_sims, [h[0].text for h in hyps])
        beam_rows.append({"beam": bm, "cer": c, "wer": wr, "ms_per_sentence": 1000 * mean(times)})
        print(f"dev beam={bm} cer={c:.4f} {1000*mean(times):.1f} ms", flush=True)
    return rows, beam_rows, best


def evaluate(sims, lm, cfg, label):
    """Return metrics for greedy, beam (no LM) and beam + LM."""
    res: dict = {"label": label, "n": len(sims), "mean_chars": mean([len(r.text) for r in sims]),
                 "mean_frames": mean([r.stream.n_frames for r in sims])}
    greedy = [ctc_greedy_decode(r.stream) for r in sims]
    res["greedy"] = dict(zip(("cer", "wer"), rates(sims, greedy)))
    # Greedy calibration: the simulator peak confidence vs correct (reference point).
    conf = np.concatenate([r.peak_confidence for r in sims])
    corr = np.concatenate([r.peak_correct for r in sims])
    res["greedy"]["ece_peak_conf"] = expected_calibration_error(conf, corr)

    h0, t0 = decode_set(sims, None, beam=cfg["beam"], n_best=10, align=True)
    res["beam_nolm"] = dict(zip(("cer", "wer"), rates(sims, [h[0].text for h in h0])))
    res["beam_nolm"]["ms_mean"] = 1000 * mean(t0)
    res["beam_nolm"].update(calib(sims, h0))

    h1, t1 = decode_set(sims, lm, lm_weight=cfg["lm_weight"], insertion_bonus=cfg["insertion_bonus"],
                        beam=cfg["beam"], n_best=10, align=True)
    _, t1n = decode_set(sims, lm, lm_weight=cfg["lm_weight"], insertion_bonus=cfg["insertion_bonus"],
                        beam=cfg["beam"], n_best=10, align=False)
    res["beam_lm"] = dict(zip(("cer", "wer"), rates(sims, [h[0].text for h in h1])))
    res["beam_lm"]["ms_mean_align"] = 1000 * mean(t1)
    res["beam_lm"]["ms_p95_align"] = 1000 * float(np.percentile(t1, 95))
    res["beam_lm"]["ms_mean_noalign"] = 1000 * mean(t1n)
    res["beam_lm"]["ms_p95_noalign"] = 1000 * float(np.percentile(t1n, 95))
    res["beam_lm"].update(calib(sims, h1))
    # n-best oracle: the best CER among the top-k hypotheses.
    res["oracle_cer"] = {}
    for k in (1, 3, 5, 10):
        res["oracle_cer"][k] = mean([min(cer(r.text, x.text) for x in h[:k]) for r, h in zip(sims, h1)])
    res["oracle_cer_nolm"] = {k: mean([min(cer(r.text, x.text) for x in h[:k]) for r, h in zip(sims, h0)]) for k in (1, 3, 5, 10)}
    # How often the truth is in the top-k list (exact sentence).
    res["truth_in_topk"] = {k: mean([any(x.text == r.text for x in h[:k]) for r, h in zip(sims, h1)]) for k in (1, 3, 5, 10)}
    res["mean_nbest_len"] = mean([len(h) for h in h1])
    # Sentence-level: is the n-best posterior of the 1-best calibrated for "exact match"?
    for T in (1.0, 2.0, 4.0):
        p1 = [float(n_best_to_posteriors(h, T)[0]) for h in h1]
        ok = [h[0].text == r.text for r, h in zip(sims, h1)]
        res["beam_lm"][f"sent_ece_T{T:g}"] = expected_calibration_error(p1, ok, n_bins=10)
    print(label, json.dumps({k: res[k] for k in ("greedy", "beam_nolm", "beam_lm", "oracle_cer")}, indent=None), flush=True)
    return res


def calib(sims, hyps):
    """ECE of each confidence variant of the 1-best, vs the ground truth."""
    out: dict = {}
    corr = np.concatenate([char_correct(r.text, h[0].text) for r, h in zip(sims, hyps)])
    out["char_acc_1best"] = float(corr.mean())
    for key in ("fused", "nbest", "frame"):
        c = np.concatenate([h[0].confidence_variants[key] for h in hyps])
        m = np.isfinite(c)
        out[f"ece_{key}"] = expected_calibration_error(c[m], corr[m])
        out[f"meanconf_{key}"] = float(c[m].mean())
    # n-best marginal at other temperatures (recomputed from the n-best list only).
    for T in (2.0, 4.0, 8.0):
        cs = []
        for h in hyps:
            post = n_best_to_posteriors(h, T)
            cs.append(_nbest_marginal(h[0].text, [x.text for x in h], post))
        out[f"ece_nbest_T{T:g}"] = expected_calibration_error(np.concatenate(cs), corr)
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    eng = CharNgramLM.load(LM_DIR / "eng_tatoeba_6gram_mkn.npz")
    spa = CharNgramLM.load(LM_DIR / "spa_tatoeba_6gram_mkn.npz")
    held = LM_DIR / "eng_tatoeba_heldout.txt"
    dev = pick(held, 100)
    test = pick(held, 200, skip=100)
    assert set(dev).isdisjoint(test)
    report: dict = {"lm": {"eng": eng.meta, "spa": spa.meta}}

    dev_sims = simulate(dev, "median", 7)
    grid, beam_rows, best = tune(eng, dev_sims)
    cfg = {"lm_weight": best["lm_weight"], "insertion_bonus": best["insertion_bonus"]}
    # Smallest beam within 0.002 CER of the best beam.
    bmin = min(r["cer"] for r in beam_rows)
    cfg["beam"] = min(r["beam"] for r in beam_rows if r["cer"] <= bmin + 0.002)
    report.update(dev_grid=grid, dev_beam=beam_rows, chosen=cfg)
    print("chosen", cfg, flush=True)

    report["test"] = {}
    for p in PRESETS:
        sims = simulate(test, p, SIM_SEED[p])
        report["test"][p] = evaluate(sims, eng, cfg, f"eng-tatoeba-{p}")
        # Weight sweep on the test set too (for the record, not for tuning).
        sweep = {}
        for w in (0.5, 1.0, 2.0, 3.0):
            hyps, _ = decode_set(sims, eng, lm_weight=w, insertion_bonus=cfg["insertion_bonus"], beam=cfg["beam"], n_best=1, align=False)
            sweep[w] = rates(sims, [h[0].text for h in hyps])[0]
        report["test"][p]["cer_by_lm_weight"] = sweep

    toy = toy_sentences(200, seed=0)
    report["toy_median"] = evaluate(simulate(toy, "median", 104), eng, cfg, "eng-corpus.py-median")

    spa_test = pick(LM_DIR / "spa_tatoeba_heldout.txt", 200)
    report["spa_median"] = evaluate(simulate(spa_test, "median", 105), spa, cfg, "spa-tatoeba-median")
    bl = [s for s in (LM_DIR / "spanishbcbl_blocklist.txt").read_text(encoding="utf-8").splitlines() if s]
    if bl:
        report["spanishbcbl_median"] = evaluate(simulate(bl, "median", 106), spa, cfg, "spanishbcbl-targets-median")

    # Speed on 40-character sentences (about 400 frames).
    s40 = [s for s in pick(held, 5000, lo=40, hi=40)][:50]
    sims = simulate(s40, "median", 108)
    _, t = decode_set(sims, eng, lm_weight=cfg["lm_weight"], insertion_bonus=cfg["insertion_bonus"], beam=16, n_best=10, align=False)
    _, ta = decode_set(sims, eng, lm_weight=cfg["lm_weight"], insertion_bonus=cfg["insertion_bonus"], beam=16, n_best=10, align=True)
    report["speed_40char"] = {"n": len(sims), "mean_frames": mean([r.stream.n_frames for r in sims]),
                              "ms_mean_noalign": 1000 * mean(t), "ms_max_noalign": 1000 * max(t),
                              "ms_mean_align": 1000 * mean(ta), "ms_max_align": 1000 * max(ta)}
    print("speed", report["speed_40char"], flush=True)
    (OUT / "benchmark.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
