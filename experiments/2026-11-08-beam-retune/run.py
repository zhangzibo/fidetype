"""Beam re-tune: diagnose and improve the n-best recall of the CTC prefix beam.

Part ``sweep`` (Tatoeba English, 6-gram LM, as in experiments/2026-11-08-lm-beam):
  1. Reachability: which per-frame pruning rule removes a character of the
     true sentence (static check on the CTC forced alignment of the truth).
  2. Search error vs model error of each setting: is the truth missing
     because the search lost it (its score is higher than the last kept
     hypothesis) or because the model ranks it low?
  3. Parameter sweep on the median test set: recall@k, oracle CER, CER@1, ms.
  4. lm_weight x insertion_bonus tuning on a separate dev set (median).
  5. The chosen setting on the best, median and worst test sets.

Part ``trust`` (template sentences, as in experiments/2026-11-08-m2-trust-sim):
  The M2 harness with three decoders (reference decoder, old LM beam, new LM
  beam), median and worst presets, confidence temperature 0.5 and 1.0.

Run (one process, about 1 h on a laptop CPU in total):

    uv run python experiments/2026-11-08-beam-retune/run.py --part sweep
    uv run python experiments/2026-11-08-beam-retune/run.py --part trust
    uv run python experiments/2026-11-08-beam-retune/run.py --part sweep --quick   # smoke run

Outputs: results/sweep.json, results/trust.json and results/tables.md.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from fidetype.eval.metrics import cer
from fidetype.lm import RETUNED, CharNgramLM, ctc_forced_align, ctc_prefix_beam_search, word_alternatives
from fidetype.streams.vocab import VOCAB

HERE = Path(__file__).parent
OUT = HERE / "results"
LM_DIR = Path("C:/Users/zhang/bci-data/lm")
SIM_SEED = {"best": 101, "median": 102, "worst": 103}  # as in the lm-beam experiment
KS = (1, 5, 10, 20)
OLD = {"beam": 16, "prune_topk": 10, "prune_logp": -6.0, "insertion_bonus": 2.0, "lm_weight": 1.0}
CID = {c: i for i, c in enumerate(VOCAB)}


# --- shared helpers ---------------------------------------------------------


def pick(path: Path, n: int, skip: int = 0, lo: int = 20, hi: int = 80) -> list[str]:
    lines = [s for s in path.read_text(encoding="utf-8").splitlines() if lo <= len(s) <= hi]
    return lines[skip : skip + n]


def simulate(sents, preset, seed, temperature=1.0):
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig

    sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temperature), seed=seed)
    return [sim.simulate(s) for s in sents]


def norm_texts(hyps) -> list[str]:
    """Hypothesis texts with joined spaces, duplicates removed (rank kept)."""
    out, seen = [], set()
    for h in hyps:
        t = " ".join(h.text.split())
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def ctc_logp(lp: np.ndarray, ids: list[int], blank: int = 0) -> float:
    """CTC log-probability of the label sequence ``ids`` (forward algorithm)."""
    L = len(ids)
    ext = np.full(2 * L + 1, blank)
    ext[1::2] = ids
    S = ext.size
    skip = np.zeros(S, dtype=bool)
    skip[3::2] = ext[3::2] != ext[1:-2:2]
    a = np.full(S, -np.inf)
    a[0] = lp[0, ext[0]]
    if S > 1:
        a[1] = lp[0, ext[1]]
    for t in range(1, lp.shape[0]):
        c1 = np.concatenate(([-np.inf], a[:-1]))
        c2 = np.where(skip, np.concatenate(([-np.inf, -np.inf], a[:-2])), -np.inf)
        a = np.logaddexp(np.logaddexp(a, c1), c2) + lp[t, ext]
    return float(np.logaddexp(a[-1], a[-2]) if S > 1 else a[-1])


def fmt(v, nd=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        if math.isnan(v):
            return "-"
        return f"{v:.{nd}f}"
    return str(v)


# --- part 1: sweep ------------------------------------------------------------


def reachability(sims) -> dict:
    """Share of sentences (and characters) that a per-frame rule cuts."""
    out = {}
    for topk, plp in ((10, -6.0), (20, -6.0), (27, -6.0), (27, -9.0), (27, -12.0)):
        cut_s = cut_c = n_c = 0
        for r in sims:
            lp = r.stream.log_probs.astype(np.float64)
            ids = [CID[c] for c in r.text]
            spans = ctc_forced_align(lp, ids)
            order = np.argsort(-lp, axis=1, kind="stable")[:, :topk]
            bad = 0
            for (s, e), i in zip(spans, ids):
                bad += not any((i in order[t]) and lp[t, i] >= plp for t in range(s, e + 1))
            cut_c += bad
            n_c += len(ids)
            cut_s += bad > 0
        out[f"top{topk}/logp{plp:g}"] = {"sentences_cut": cut_s / len(sims), "chars_cut": cut_c / n_c}
    out["sentences_with_deletion"] = float(np.mean(["deletion" in r.char_outcomes for r in sims]))
    out["sentences_with_insertion"] = float(np.mean([(r.peak_targets < 0).any() for r in sims]))
    return out


def truth_scores(sims, lm, w, bonus):
    return [ctc_logp(r.stream.log_probs.astype(np.float64), [CID[c] for c in r.text])
            + w * lm.score_sentence(r.text, normalize=False) + bonus * len(r.text) for r in sims]


def run_setting(sims, lm, kw, truth_sc=None, align=False) -> dict:
    kw = dict(kw)
    kw.setdefault("n_best", 20)
    hyps, ms = [], []
    for r in sims:
        t0 = time.perf_counter()
        hyps.append(ctc_prefix_beam_search(r.stream, lm, align=align, **kw))
        ms.append(1000 * (time.perf_counter() - t0))
    texts = [norm_texts(h) for h in hyps]
    res = {f"recall@{k}": float(np.mean([r.text in t[:k] for r, t in zip(sims, texts)])) for k in KS}
    res["cer@1"] = float(np.mean([cer(r.text, t[0] if t else "") for r, t in zip(sims, texts)]))
    res["oracle_cer@10"] = float(np.mean([min(cer(r.text, x) for x in t[:10]) if t else 1.0 for r, t in zip(sims, texts)]))
    res["ms_mean"] = float(np.mean(ms))
    res["ms_p95"] = float(np.percentile(ms, 95))
    res["mean_list_len"] = float(np.mean([len(t) for t in texts]))
    # Distinct words at the position of the most uncertain word (diversity).
    res["mean_words_changed"] = float(np.mean([_words_changed(t[:10]) for t in texts]))
    if truth_sc is not None:
        se = me = 0
        for r, h, t, ts in zip(sims, hyps, texts, truth_sc):
            if r.text in t:
                continue
            if len(h) < kw["n_best"] or ts > h[-1].score:
                se += 1  # the truth would have entered the list: the search lost it
            else:
                me += 1
        res["search_error"] = se / len(sims)
        res["model_error"] = me / len(sims)
    return res


def _words_changed(texts: list[str]) -> float:
    """Mean number of words of a hypothesis (2..10) that differ from the top-1."""
    if len(texts) < 2:
        return 0.0
    top = texts[0].split()
    from fidetype.eval.metrics import edit_distance

    return float(np.mean([edit_distance(top, x.split()) for x in texts[1:]]))


def part_sweep(quick: bool) -> dict:
    held = LM_DIR / "eng_tatoeba_heldout.txt"
    dev, test = pick(held, 100), pick(held, 200, skip=100)
    assert set(dev).isdisjoint(test)
    if quick:
        dev, test = dev[:15], test[:20]
    lm = CharNgramLM.load(LM_DIR / "eng_tatoeba_6gram_mkn.npz")
    rep: dict = {"n_dev": len(dev), "n_test": len(test), "mean_chars_test": float(np.mean([len(s) for s in test]))}
    test_sims = {p: simulate(test, p, SIM_SEED[p]) for p in SIM_SEED}
    med = test_sims["median"]

    print("== reachability", flush=True)
    rep["reachability"] = {p: reachability(s) for p, s in test_sims.items()}
    print(json.dumps(rep["reachability"], indent=1), flush=True)

    ts_med = truth_scores(med, lm, 1.0, 2.0)
    V = {"search": "vector"}
    B256 = dict(OLD, beam=256, prune_topk=None, **V)
    NEW = dict(RETUNED)
    rows = [
        # 1. Which pruning setting cuts the truth (old lm_weight 1.0, bonus 2.0).
        ("old default (loop)", dict(OLD)),
        ("old default (vector)", dict(OLD, **V)),
        ("prune_topk 20", dict(OLD, prune_topk=20, **V)),
        ("prune_topk None", dict(OLD, prune_topk=None, **V)),
        ("prune_topk None, prune_logp -9", dict(OLD, prune_topk=None, prune_logp=-9.0, **V)),
        ("beam 64, topk 10", dict(OLD, beam=64, **V)),
        ("beam 32, topk None", dict(OLD, beam=32, prune_topk=None, **V)),
        ("beam 64, topk None", dict(OLD, beam=64, prune_topk=None, **V)),
        ("beam 128, topk None", dict(OLD, beam=128, prune_topk=None, **V)),
        ("beam 256, topk None", B256),
        ("beam 512, topk None", dict(B256, beam=512)),
        ("beam 256, topk None, logp -9", dict(B256, prune_logp=-9.0)),
        ("beam 256 + space_rules", dict(B256, space_rules=True)),
        ("beam 256 + space + lm_cand 3", dict(B256, space_rules=True, lm_candidates=3)),
        # 2. The chosen setting and changes around it (w 1.25, bonus 1.0).
        ("RETUNED (beam 256, space, w 1.25, bonus 1.0)", NEW),
        ("RETUNED, beam 64", dict(NEW, beam=64)),
        ("RETUNED, beam 128", dict(NEW, beam=128)),
        ("RETUNED, beam 512", dict(NEW, beam=512)),
        ("RETUNED + lm_cand 3", dict(NEW, lm_candidates=3)),
        ("RETUNED + lm_cand 5", dict(NEW, lm_candidates=5)),
        ("RETUNED + stem cap 4", dict(NEW, max_per_stem=4)),
        ("RETUNED + stem cap 8 (drop 2)", dict(NEW, max_per_stem=8, stem_drop=2)),
        ("RETUNED + beam_logp 12", dict(NEW, beam_logp=12.0)),
        ("RETUNED, no space_rules", dict(NEW, space_rules=False)),
        ("RETUNED, topk 10 (old cut)", dict(NEW, prune_topk=10)),
    ]
    if quick:
        rows = rows[:3] + rows[14:16]
    rep["sweep_median"] = []
    print("== sweep (median test)", flush=True)
    ts_cache = {(1.0, 2.0): ts_med}
    for name, kw in rows:
        wb = (kw.get("lm_weight", 1.0), kw.get("insertion_bonus", 2.0))
        if wb not in ts_cache:
            ts_cache[wb] = truth_scores(med, lm, *wb)
        res = run_setting(med, lm, kw, ts_cache[wb])
        rep["sweep_median"].append({"name": name, "kwargs": kw, **res})
        print(name, json.dumps(res), flush=True)

    # Dev tuning of lm_weight x insertion_bonus (recall@10, then CER@1).
    # The grid is slow (about 35 min), so a cached result is used if present.
    print("== dev tuning", flush=True)
    cache = OUT / "dev_grid.jsonl"
    grid = []
    if cache.exists() and not quick:
        grid = [json.loads(x) for x in cache.read_text(encoding="utf-8").splitlines() if x.strip()]
    else:
        dev_sims = simulate(dev, "median", 7)  # the dev seed of the lm-beam experiment
        base = dict(search="vector", beam=128, n_best=20, prune_topk=None, prune_logp=-6.0, space_rules=True)
        combos = [(lmc, w, b) for lmc in (0, 3) for w in (0.8, 1.0, 1.25) for b in (1.0, 1.5, 2.0, 2.5)]
        combos += [(0, w, b) for w in (1.25, 1.5, 2.0) for b in (0.0, 0.5, 1.0)]
        if quick:
            combos = combos[5:6]
        seen = set()
        for lmc, w, b in combos:
            if (lmc, w, b) in seen:
                continue
            seen.add((lmc, w, b))
            res = run_setting(dev_sims, lm, dict(base, lm_candidates=lmc, lm_weight=w, insertion_bonus=b))
            grid.append({"lmc": lmc, "w": w, "b": b, **{k: round(v, 3) for k, v in res.items()}})
            print(json.dumps(grid[-1]), flush=True)
        if not quick:
            cache.write_text("".join(json.dumps(g) + "\n" for g in grid), encoding="utf-8")
    rep["dev_grid"] = grid
    best = max(grid, key=lambda r: (r["recall@10"], -r["cer@1"]))
    rep["dev_best"] = {k: best[k] for k in ("lmc", "w", "b", "recall@10", "cer@1")}

    # The chosen setting (RETUNED) and the old default on all presets.
    print("== final (all presets)", flush=True)
    rep["final"] = {}
    for p, sims in test_sims.items():
        ts = truth_scores(sims, lm, RETUNED["lm_weight"], RETUNED["insertion_bonus"])
        ts_old = truth_scores(sims, lm, 1.0, 2.0)
        rep["final"][p] = {
            "old": run_setting(sims, lm, OLD, ts_old),
            "new": run_setting(sims, lm, RETUNED, ts),
            "new_align_ms": run_setting(sims[:50], lm, RETUNED, align=True)["ms_mean"],
        }
        print(p, json.dumps(rep["final"][p]), flush=True)

    # Speed on 40-character sentences (as in the lm-beam experiment).
    s40 = pick(held, 5000, lo=40, hi=40)[:50 if not quick else 5]
    sims40 = simulate(s40, "median", 104)
    rep["speed_40"] = {
        "old_noalign": run_setting(sims40, lm, OLD)["ms_mean"],
        "new_noalign": run_setting(sims40, lm, RETUNED)["ms_mean"],
        "new_align": run_setting(sims40, lm, RETUNED, align=True)["ms_mean"],
        "new_noalign_p95": run_setting(sims40, lm, RETUNED)["ms_p95"],
    }
    print("speed40", rep["speed_40"], flush=True)

    # Word-level alternatives on the median test set.
    rep["word_alternatives_median"] = word_alt_stats(med, lm, RETUNED)
    print("word alternatives", rep["word_alternatives_median"], flush=True)
    return rep


def word_reachable(slots, top: str, truth: str, k: int) -> bool:
    """Can the user build ``truth`` by choosing one of the ``k`` best
    alternatives in every word slot of ``top``?"""
    one = word_alternatives([type("H", (), {"text": truth, "score": 0.0})()], reference=top)
    if len(one) != len(slots):
        return False
    for s, t in zip(slots, one):
        want = t.alternatives[0][0]
        if want not in [a for a, _ in s.alternatives[:k]]:
            return False
    return bool(slots) or truth == top


def word_alt_stats(sims, lm, kw, temperature: float = 1.0) -> dict:
    out = {"sentence_recall@3": 0.0, "sentence_recall@5": 0.0, "word_reachable@2": 0.0, "word_reachable@3": 0.0,
           "mean_uncertain_slots": 0.0}
    n = len(sims)
    for r in sims:
        hyps = ctc_prefix_beam_search(r.stream, lm, align=False, **kw)
        texts = norm_texts(hyps)
        out["sentence_recall@3"] += r.text in texts[:3]
        out["sentence_recall@5"] += r.text in texts[:5]
        slots = word_alternatives(hyps, temperature=temperature)
        out["word_reachable@2"] += word_reachable(slots, hyps[0].text, r.text, 2)
        out["word_reachable@3"] += word_reachable(slots, hyps[0].text, r.text, 3)
        out["mean_uncertain_slots"] += sum(len(s.alternatives) > 1 and s.alternatives[0][1] < 0.9 for s in slots)
    return {k: v / n for k, v in out.items()}


# --- part 2: trust pipeline ----------------------------------------------------


def part_trust(quick: bool) -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.streams.corpus import sentences
    from fidetype.streams.simulator import NoisyDecoderSimulator, SimConfig
    from fidetype.trust.testing import RefCharLM, ReferenceDecoder
    from fidetype.trust.types import from_lm_hypotheses

    n_split = 30 if quick else 120
    all_s = sentences(3400, seed=0)
    eval_s = all_s[40 : 40 + 3 * n_split]
    lm_s = all_s[400:]
    ref = ReferenceDecoder(RefCharLM(order=5).fit(lm_s))
    lm6 = CharNgramLM(order=6).train(lm_s)
    new_kw = dict(RETUNED, n_best=10)  # same list length as the reference decoder

    def dec_old(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm6), stream.meta)

    def dec_new(stream):
        return from_lm_hypotheses(ctc_prefix_beam_search(stream, lm6, **new_kw), stream.meta)

    decoders = {"reference": ref, "lm_beam_old": dec_old, "lm_beam_new": dec_new}
    presets = ("median", "worst")
    temps = (0.5, 1.0) if not quick else (1.0,)
    keys = ("ewpm", "wrong_commit_rate", "silent_error_rate", "cer", "top1_sentence_acc", "guard_auroc",
            "guard_auroc_inconsistency", "p_top1_auroc", "coverage", "coverage_in_nbest", "mean_set_size",
            "miss_rate", "word_coverage", "word_mean_set_size", "rate_commit", "rate_offer", "rate_ask",
            "rate_abstain", "fit_temperature_sentence", "seconds")
    res: dict = {"n_split": n_split, "new_kwargs": new_kw, "conditions": {}}
    for preset in presets:
        pi = ("best", "median", "worst").index(preset)
        for temp in temps:
            ti = (0.5, 1.0, 2.0).index(temp)
            sd = pi * 10 + ti  # the M2 seeds
            cond = f"{preset}/T={temp}"
            sim = NoisyDecoderSimulator(SimConfig.preset(preset, confidence_temperature=temp), seed=sd)

            def item(i, s, sim=sim, sd=sd):
                seed = 100_000 * sd + 1000 * i
                return Item(sim.simulate(s, seed=seed).stream, s, regen=lambda a: sim.simulate(s, seed=seed + a).stream)

            items = [item(i, s) for i, s in enumerate(eval_s)]
            cal, val, test = items[:n_split], items[n_split : 2 * n_split], items[2 * n_split :]
            res["conditions"][cond] = {}
            for dname, dec in decoders.items():
                cache: dict = {}
                out = {}
                for pol, cfg in (("b_top1_commit", dict(policy="always_commit", use_calibration=False)),
                                 ("c_trust", dict(max_wrong_commit=0.05))):
                    t0 = time.time()
                    pipe = TrustPipeline(dec, HarnessConfig(**cfg), cache)
                    pipe.fit(cal, val)
                    m = pipe.evaluate(test)
                    m["seconds"] = time.time() - t0
                    out[pol] = {k: (None if isinstance(m.get(k), float) and math.isnan(m[k]) else m.get(k)) for k in keys}
                    if pol == "c_trust":
                        out[pol]["word_level"] = trust_word_stats(pipe, test)
                    print(cond, dname, pol, json.dumps(out[pol]), flush=True)
                res["conditions"][cond][dname] = out
    return res


def trust_word_stats(pipe, test) -> dict:
    """Offline check of per-word OFFER on the fitted pipeline (not in the harness).

    For each test sentence with a wrong top-1: is the truth in the top-3
    sentences, and can it be built from the top-2 / top-3 alternatives of
    each word slot (calibrated sentence posteriors)?
    """
    wrong = in3 = w2 = w3 = 0
    for it in test:
        nb = pipe.decode(it, 0)
        if not len(nb) or nb.texts[0] == it.text:
            continue
        wrong += 1
        post = pipe.calibrator.posteriors(nb)
        in3 += it.text in nb.texts[:3]
        slots = word_alternatives(nb.candidates, posteriors=post)
        w2 += word_reachable(slots, nb.texts[0], it.text, 2)
        w3 += word_reachable(slots, nb.texts[0], it.text, 3)
    d = max(wrong, 1)
    return {"n_wrong_top1": wrong, "sentence_top3": in3 / d, "word_top2": w2 / d, "word_top3": w3 / d}


# --- tables -------------------------------------------------------------------


def write_tables(sweep: dict | None, trust: dict | None) -> None:
    L = ["# Beam re-tune: generated tables (run.py)", ""]
    if sweep:
        L += ["## Reachability (share of test sentences where a per-frame rule cuts a true character)", ""]
        L += ["| preset | " + " | ".join(k for k in next(iter(sweep["reachability"].values())) if k.startswith("top")) + " | with deletion |"]
        L += ["|---" * 7 + "|"]
        for p, r in sweep["reachability"].items():
            L.append(f"| {p} | " + " | ".join(fmt(v["sentences_cut"]) for k, v in r.items() if k.startswith("top"))
                     + f" | {fmt(r['sentences_with_deletion'])} |")
        L += ["", "## Sweep, median test set", ""]
        L += ["| setting | r@1 | r@5 | r@10 | r@20 | oracle CER@10 | CER@1 | search err | model err | ms mean | ms p95 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sweep["sweep_median"]:
            L.append(f"| {r['name']} | {fmt(r['recall@1'])} | {fmt(r['recall@5'])} | {fmt(r['recall@10'])} | {fmt(r['recall@20'])} "
                     f"| {fmt(r['oracle_cer@10'])} | {fmt(r['cer@1'])} | {fmt(r.get('search_error'))} | {fmt(r.get('model_error'))} "
                     f"| {r['ms_mean']:.0f} | {r['ms_p95']:.0f} |")
        L += ["", "## Dev tuning (median dev set, 100 sentences, beam 128, topk None, space rules)", "",
              "| lm_candidates | w | bonus | r@1 | r@10 | r@20 | CER@1 | ms |", "|---|---|---|---|---|---|---|---|"]
        for r in sweep["dev_grid"]:
            L.append(f"| {r['lmc']} | {r['w']} | {r['b']} | {fmt(r['recall@1'])} | {fmt(r['recall@10'])} | {fmt(r['recall@20'])} "
                     f"| {fmt(r['cer@1'])} | {r['ms_mean']:.0f} |")
        L += ["", "## Old default vs RETUNED, test sets", "",
              "| preset | setting | r@1 | r@5 | r@10 | r@20 | oracle CER@10 | CER@1 | search err | model err | ms |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for p, d in sweep["final"].items():
            for s in ("old", "new"):
                r = d[s]
                L.append(f"| {p} | {s} | {fmt(r['recall@1'])} | {fmt(r['recall@5'])} | {fmt(r['recall@10'])} | {fmt(r['recall@20'])} "
                         f"| {fmt(r['oracle_cer@10'])} | {fmt(r['cer@1'])} | {fmt(r.get('search_error'))} | {fmt(r.get('model_error'))} "
                         f"| {r['ms_mean']:.0f} |")
        L += ["", f"Speed, 40-character sentences: {json.dumps(sweep['speed_40'])}", "",
              f"Word alternatives (median): {json.dumps(sweep['word_alternatives_median'])}", ""]
    if trust:
        L += ["## Trust pipeline (template sentences, M2 set-up)", "",
              "| condition | decoder | policy | eWPM | wrong-commit | CER | guard AUROC | coverage | coverage in n-best "
              "| set size | miss rate | word cov. | word set | COMMIT | OFFER | ASK | ABSTAIN |",
              "|---" * 17 + "|"]
        for cond, ds in trust["conditions"].items():
            for dn, ps in ds.items():
                for pn, m in ps.items():
                    L.append(f"| {cond} | {dn} | {pn} | {fmt(m['ewpm'], 2)} | {fmt(m['wrong_commit_rate'])} | {fmt(m['cer'])} "
                             f"| {fmt(m['guard_auroc'])} | {fmt(m['coverage'])} | {fmt(m['coverage_in_nbest'])} "
                             f"| {fmt(m['mean_set_size'], 2)} | {fmt(m['miss_rate'])} | {fmt(m['word_coverage'])} "
                             f"| {fmt(m['word_mean_set_size'], 2)} | {fmt(m['rate_commit'], 2)} | {fmt(m['rate_offer'], 2)} "
                             f"| {fmt(m['rate_ask'], 2)} | {fmt(m['rate_abstain'], 2)} |")
        L += ["", "### Per-word alternatives, sentences with a wrong top-1 (trust pipeline c)", "",
              "| condition | decoder | n | truth in top-3 sentences | built from top-2 words | built from top-3 words |",
              "|---|---|---|---|---|---|"]
        for cond, ds in trust["conditions"].items():
            for dn, ps in ds.items():
                w = ps["c_trust"]["word_level"]
                L.append(f"| {cond} | {dn} | {w['n_wrong_top1']} | {fmt(w['sentence_top3'])} | {fmt(w['word_top2'])} | {fmt(w['word_top3'])} |")
    (OUT / "tables.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("sweep", "trust", "tables"), required=True)
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    sfx = "_quick" if a.quick else ""
    if a.part == "sweep":
        (OUT / f"sweep{sfx}.json").write_text(json.dumps(part_sweep(a.quick), indent=1), encoding="utf-8")
    elif a.part == "trust":
        (OUT / f"trust{sfx}.json").write_text(json.dumps(part_trust(a.quick), indent=1, default=str), encoding="utf-8")
    sw = OUT / f"sweep{sfx}.json"
    tr = OUT / f"trust{sfx}.json"
    write_tables(json.loads(sw.read_text()) if sw.exists() else None, json.loads(tr.read_text()) if tr.exists() else None)
    print("wrote", OUT, flush=True)


if __name__ == "__main__":
    main()
