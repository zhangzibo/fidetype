"""Trust core on Brain-to-Text '25 copy-task logits (intracortical, T15).

First test of the NeuralTextStream spec and the trust layer on a second
device type. CPU only. Stages (each saves JSON; later stages reuse it):

1. ``prep``: load the pickle safely, build streams, split, score the
   published online decoder (WER, PER), build the word unigram counts.
2. ``tune``: tune our phoneme -> word decoder on part of the fit split.
3. ``trust``: the M2 harness on word-level and phoneme-level streams;
   bootstrap CIs; null-input audit; AUROCs.
4. ``tables``: write results/tables.md.

Run (repo root, CPU, 2 threads):

    set HIP_VISIBLE_DEVICES=-1
    .venv\\Scripts\\python.exe -I experiments/2026-11-10-b2t25-trust/run.py
    ... run.py --stages trust,tables   # reuse prep and tune
"""

from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ[_v] = "2"
os.environ["HIP_VISIBLE_DEVICES"] = "-1"

import argparse
import bz2
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from fidetype.adapters import b2t25 as B
from fidetype.eval.ewpm import summarize
from fidetype.eval.metrics import ctc_greedy_decode, edit_distance
from fidetype.lm import CharNgramLM, ctc_prefix_beam_search
from fidetype.lm.phoneme_words import PhonemeWordDecoder, PronLexicon, unigram_logprobs
from fidetype.streams.spec import NeuralTextStream

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
SEED = CONFIG["seed"]
LOG = None


def log(*a) -> None:
    msg = time.strftime("%H:%M:%S") + " " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    if LOG is not None:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


def dump(obj, path: Path) -> None:
    def clean(o):
        if isinstance(o, (np.floating, np.integer)):
            o = o.item()
        if isinstance(o, float) and not math.isfinite(o):
            return None if math.isnan(o) else str(o)
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
        return o

    path.write_text(json.dumps(clean(obj), indent=1), encoding="utf-8")


def load_json(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def pooled(refs, hyps, words: bool) -> float:
    if words:
        refs, hyps = [r.split() for r in refs], [h.split() for h in hyps]
    n = sum(len(r) for r in refs)
    return sum(edit_distance(r, h) for r, h in zip(refs, hyps)) / n if n else math.nan


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def load_trials():
    return B.load_copytask(CONFIG["pkl"], verify=True)


def split(trials):
    main = [t for t in trials if t.vocab_size == CONFIG["vocab_size_main"]]
    by_day = defaultdict(list)
    for t in main:
        by_day[t.post_implant_day].append(t)
    fit, test = [], []
    for d in sorted(by_day):
        ts = by_day[d]
        h = len(ts) // 2
        fit += ts[:h]
        test += ts[h:]
    return fit, test


def word_counts() -> Counter:
    p = Path(CONFIG["word_counts_cache"])
    if p.exists():
        return Counter(json.loads(p.read_text(encoding="utf-8")))
    c: Counter = Counter()
    with bz2.open(CONFIG["tatoeba_eng"], "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                c.update(B.normalize_words(parts[-1]).split())
    p.write_text(json.dumps(dict(c)), encoding="utf-8")
    return c


def tatoeba_sentences() -> set[str]:
    out = set()
    with bz2.open(CONFIG["tatoeba_eng"], "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts:
                out.add(B.normalize_words(parts[-1]))
    return out


def build_lexicon():
    keep = lambda w: re.fullmatch(r"[a-z']+", w) is not None  # noqa: E731
    return PronLexicon.from_cmudict(CONFIG["cmudict"], B.phonemes_to_symbols, keep=keep)


# ---------------------------------------------------------------------------
# Stage 1: prep
# ---------------------------------------------------------------------------


def stage_prep() -> dict:
    t0 = time.time()
    trials = load_trials()
    fit, test = split(trials)
    pub: dict = {}
    groups = {"all_1718": trials, "vocab_50": [t for t in trials if t.vocab_size == 50],
              "vocab_125k": [t for t in trials if t.vocab_size == 125000], "fit": fit, "test": test}
    for g, ts in groups.items():
        refs = [t.truth_words for t in ts]
        hyps = [B.normalize_words(t.decoded_sentence) for t in ts]
        pub[g] = {
            "n": len(ts),
            "wer_published": pooled(refs, hyps, True),
            "sentence_exact_published": float(np.mean([a == b for a, b in zip(refs, hyps)])),
            "per_raw_greedy": pooled([t.cue_phonemes for t in ts], [t.decoded_phonemes_raw for t in ts], False),
            "per_published_sentence": pooled([t.cue_phonemes for t in ts], [t.decoded_sentence_phonemes for t in ts], False),
        }
    by_day = {}
    for d in sorted({t.post_implant_day for t in trials}):
        ts = [t for t in trials if t.post_implant_day == d]
        by_day[d] = {"n": len(ts), "vocab_sizes": sorted({t.vocab_size for t in ts}),
                     "wer_published": pooled([t.truth_words for t in ts], [B.normalize_words(t.decoded_sentence) for t in ts], True),
                     "per_raw_greedy": pooled([t.cue_phonemes for t in ts], [t.decoded_phonemes_raw for t in ts], False)}
    # Greedy path of our streams vs the stored raw phonemes (vocab-order check).
    same = sum(ctc_greedy_decode(B.to_symbol_stream(B.trial_stream(t))).split() == B.phonemes_to_symbols(t.decoded_phonemes_raw).split()
               for t in trials)
    main = groups["vocab_125k"]
    dur = sum(t.speech_duration_s for t in main)
    rate = {"chars_per_min": sum(len(t.truth_words) for t in main) / dur * 60,
            "words_per_min": sum(len(t.truth_words.split()) for t in main) / dur * 60}
    T = np.array([t.n_frames for t in trials])
    wc = word_counts()
    lex = build_lexicon()
    cue_words = Counter(w for t in main for w in t.truth_words.split())
    oov = {w: c for w, c in cue_words.items() if w not in lex.prons}
    tat = tatoeba_sentences()
    overlap = sorted({t.truth_words for t in main if t.truth_words in tat})
    res = {
        "n_trials": len(trials), "n_fit": len(fit), "n_test": len(test),
        "n_fit_sentences": len({t.truth_words for t in fit}), "n_test_sentences": len({t.truth_words for t in test}),
        "fit_test_sentence_overlap": len({t.truth_words for t in fit} & {t.truth_words for t in test}),
        "days": sorted({t.post_implant_day for t in trials}),
        "frames": {"min": int(T.min()), "median": float(np.median(T)), "max": int(T.max())},
        "greedy_equals_raw": int(same),
        "speech_rate_125k": rate,
        "published": pub, "published_by_day": by_day,
        "lexicon_words": len(lex), "tatoeba_word_types": len(wc),
        "cue_word_tokens_125k": sum(cue_words.values()), "cue_word_oov_tokens": sum(oov.values()),
        "cue_oov_words": sorted(oov)[:60],
        "cue_sentences_in_tatoeba": len(overlap), "cue_sentences_in_tatoeba_examples": overlap[:20],
        "seconds": round(time.time() - t0, 1),
    }
    dump(res, OUT / "prep.json")
    log("prep", {k: v for k, v in res.items() if k not in ("published_by_day", "cue_oov_words", "cue_sentences_in_tatoeba_examples")})
    return res


# ---------------------------------------------------------------------------
# Decoders
# ---------------------------------------------------------------------------


class Decoders:
    def __init__(self, trials, wkw: dict | None = None):
        self.trials = {t.index: t for t in trials}
        self.lex = build_lexicon()
        wc = word_counts()
        self.uni = unigram_logprobs(wc, self.lex.words)
        self.lex.set_fallback_words(w for w in self.lex.words if wc.get(w, 0) >= CONFIG["fallback_min_count"])
        self.lm = CharNgramLM.load(CONFIG["char_lm"])
        self.beam_kw = dict(CONFIG["phoneme_beam"])
        self.wkw = {**CONFIG["word_decoder_fixed"], **(wkw or {})}
        self.wdec = self.make_wdec(self.wkw)
        self._wcache: dict = {}

    def make_wdec(self, kw) -> PhonemeWordDecoder:
        d = PhonemeWordDecoder(self.lex, self.uni, sentence_lm=self.lm.score_sentence, **kw)
        if hasattr(self, "wdec"):  # share the caches
            d._lm_cache, d._cand_cache = self.wdec._lm_cache, self.wdec._cand_cache
        return d

    def phonemes(self, stream):
        return ctc_prefix_beam_search(stream, None, **self.beam_kw)

    def words_fn(self, stream):
        from fidetype.trust.types import from_lm_hypotheses

        key = (stream.meta.get("fidetype.trial_index"), stream.meta.get("audit"), stream.source,
               round(float(stream.log_probs.astype(np.float64).sum()), 4))
        hit = self._wcache.get(key)
        if hit is None:
            hit = from_lm_hypotheses(self.wdec.decode(self.phonemes(stream)), stream.meta, confidence_variant=None)
            self._wcache[key] = hit
        return hit

    def greedy_words_fn(self, stream):
        """Greedy phonemes -> lexicon top-1 words (no beam, no n-best)."""
        from fidetype.trust.types import from_lm_hypotheses

        txt = ctc_greedy_decode(stream)

        class H:
            text = txt
            logp_acoustic = 0.0
            confidence_variants = {"frame": np.ones(len(txt))}

        w = self.wdec.decode([H()])[:1]
        return from_lm_hypotheses(w, stream.meta, confidence_variant=None)

    def published_fn(self, stream):
        from fidetype.trust.types import Candidate, NBest

        t = self.trials[stream.meta["fidetype.trial_index"]]
        return NBest([Candidate(B.normalize_words(t.decoded_sentence), 0.0)], dict(stream.meta))

    def published_plus_fn(self, stream):
        """The published sentence on top of our word n-best, for the trust gate.

        Score: our best score + ``published_margin``. Character confidences:
        a published word gets the acoustic confidence of the same word in our
        top-1 (word alignment), else 0. So the guard sees how much of the
        published text our neural-evidence decode confirms.
        """
        from fidetype.trust.types import Candidate, NBest

        ours = self.words_fn(stream)
        t = self.trials[stream.meta["fidetype.trial_index"]]
        pub = B.normalize_words(t.decoded_sentence)
        cands = [c for c in ours.candidates if c.text != pub]
        top = ours.top
        conf: list[float] = []
        if top is not None and pub:
            tw, pw = top.text.split(), pub.split()
            wconf, pos = [], 0
            cc = list(top.char_confidences) or [0.0] * len(top.text)
            for w in tw:
                wconf.append(min(cc[pos: pos + len(w)]) if w else 0.0)
                pos += len(w) + 1
            pc = [0.0] * len(pw)
            for i, j in word_align(pw, tw):
                if pw[i] == tw[j]:
                    pc[i] = wconf[j]
            for i, w in enumerate(pw):
                if i:
                    conf.append(min(pc[i], pc[i - 1]))
                conf.extend([pc[i]] * len(w))
        s0 = max([c.score for c in ours.candidates], default=0.0)
        lp_ac = top.logp_acoustic if top is not None else float("nan")
        cands.append(Candidate(pub, s0 + CONFIG["published_margin"], lp_ac, float("nan"), tuple(conf) if pub else ()))
        return NBest(cands, dict(stream.meta))

    def phoneme_nbest_fn(self, stream):
        from fidetype.trust.types import from_lm_hypotheses

        return from_lm_hypotheses(self.phonemes(stream), stream.meta, confidence_variant="frame")

    def greedy_phoneme_fn(self, stream):
        from fidetype.trust.testing import greedy_nbest

        return greedy_nbest(stream)


# ---------------------------------------------------------------------------
# Stage 2: tune the word decoder
# ---------------------------------------------------------------------------


def stage_tune() -> dict:
    t0 = time.time()
    trials = load_trials()
    fit, _ = split(trials)
    rng = np.random.default_rng(SEED)
    sub = [fit[i] for i in sorted(rng.choice(len(fit), min(CONFIG["tune_trials"], len(fit)), replace=False))]
    dec = Decoders(trials)
    ph = {t.index: dec.phonemes(B.to_symbol_stream(B.trial_stream(t))) for t in sub}
    log(f"tune: phoneme beam on {len(sub)} fit trials ({time.time() - t0:.0f}s)")
    g = CONFIG["word_decoder_grid"]
    rows = []
    for lw in g["lm_weight"]:
        for ep in g["edit_penalty"]:
            for wb in g["word_bonus"]:
                kw = {**CONFIG["word_decoder_fixed"], "lm_weight": lw, "edit_penalty": ep, "word_bonus": wb}
                wd = dec.make_wdec(kw)
                tops, inn = [], []
                for t in sub:
                    hs = wd.decode(ph[t.index])
                    tops.append(hs[0].text if hs else "")
                    inn.append(t.truth_words in [h.text for h in hs])
                refs = [t.truth_words for t in sub]
                r = {"lm_weight": lw, "edit_penalty": ep, "word_bonus": wb, "wer": pooled(refs, tops, True),
                     "sentence_exact": float(np.mean([a == b for a, b in zip(refs, tops)])), "truth_in_nbest": float(np.mean(inn))}
                rows.append(r)
                log("tune", r)
    best = min(rows, key=lambda r: (r["wer"], -r["truth_in_nbest"]))
    phon_top = [" ".join(ph[t.index][0].text.split()) if ph[t.index] else "" for t in sub]
    res = {"n": len(sub), "rows": rows, "best": best,
           "phoneme_beam_per": pooled([t.truth_symbols for t in sub], phon_top, False),
           "phoneme_greedy_per": pooled([t.truth_symbols for t in sub], [" ".join(ctc_greedy_decode(B.to_symbol_stream(B.trial_stream(t))).split()) for t in sub], False),
           "seconds": round(time.time() - t0, 1)}
    dump(res, OUT / "tune.json")
    log("tune best", best)
    return res


# ---------------------------------------------------------------------------
# Stage 3: trust
# ---------------------------------------------------------------------------


def gaze_ewpm(truths, cpm) -> float:
    t = sum(len(s) for s in truths) * 60.0 / cpm
    return 60.0 * sum(len(s.split()) for s in truths) / t


def bootstrap(per: dict[str, list], truths: list[str], clusters: np.ndarray | None, B_: int, seed: int, cpm: float) -> dict:
    rng = np.random.default_rng(seed)
    keys = ("ewpm", "wrong_commit_rate", "silent_error_rate", "rate_commit", "abstain_rate")
    samples = {p: defaultdict(list) for p in per}
    samples["gaze_only"] = defaultdict(list)
    diffs = defaultdict(list)
    n = len(truths)
    uc = np.unique(clusters) if clusters is not None else None
    members = {c: np.where(clusters == c)[0] for c in uc} if uc is not None else None
    pairs = [("w_c_trust", "w_b_top1_commit"), ("w_c_trust", "w_p_published_commit"), ("w_c_trust", "gaze_only"),
             ("w_q_published_trust", "w_p_published_commit"), ("w_q_published_trust", "gaze_only"),
             ("w_p_published_commit", "gaze_only"), ("w_b_top1_commit", "gaze_only")]
    for _ in range(B_):
        idx = rng.integers(0, n, n) if uc is None else np.concatenate([members[c] for c in rng.choice(uc, len(uc))])
        vals = {}
        for p, recs in per.items():
            m = summarize([recs[i] for i in idx])
            vals[p] = m
            for k in keys:
                samples[p][k].append(m[k])
        g = gaze_ewpm([truths[i] for i in idx], CONFIG["gaze_chars_per_min"])
        vals["gaze_only"] = {"ewpm": g, "wrong_commit_rate": 0.0, "silent_error_rate": 0.0}
        samples["gaze_only"]["ewpm"].append(g)
        for a, b in pairs:
            if a in vals and b in vals:
                for k in ("ewpm", "wrong_commit_rate", "silent_error_rate"):
                    diffs[f"{a}-{b}:{k}"].append(vals[a][k] - vals[b][k])

    def ci(v):
        v = np.array([x for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))], float)
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size else None

    return {"policies": {p: {k: ci(v) for k, v in d.items()} for p, d in samples.items()},
            "diffs": {k: {"ci": ci(v), "p_le_0": float(np.mean(np.array(v) <= 0))} for k, v in diffs.items()}}


def word_align(ref: list[str], hyp: list[str]) -> list[tuple[int, int]]:
    n, m = len(ref), len(hyp)
    D = np.zeros((n + 1, m + 1), dtype=np.int64)
    D[:, 0] = np.arange(n + 1)
    D[0, :] = np.arange(m + 1)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]))
    i, j, out = n, m, []
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (ref[i - 1] != hyp[j - 1]):
            out.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif D[i, j] == D[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    return out[::-1]


def word_conf_auroc(analyses, truths, auroc) -> dict:
    """AUROC of the per-word acoustic confidence (min over its characters) for 'word wrong'."""
    confs, wrong = [], []
    for an, truth in zip(analyses, truths):
        if not len(an.nbest):
            continue
        c = an.nbest.candidates[0]
        hw = c.text.split()
        cc = list(c.char_confidences)
        if len(cc) != len(c.text):
            continue
        pos, wc = 0, []
        for w in hw:
            wc.append(min(cc[pos : pos + len(w)]) if w else 0.0)
            pos += len(w) + 1
        ok = [False] * len(hw)
        for i, j in word_align(truth.split(), hw):
            if truth.split()[i] == hw[j]:
                ok[j] = True
        confs += wc
        wrong += [not o for o in ok]
    return {"word_conf_auroc": auroc([-x for x in confs], wrong), "n_words_top1": len(wrong),
            "top1_word_error_share": float(np.mean(wrong)) if wrong else math.nan}


def extra_word_metrics(ans, truths, test, pub_wrong, auroc) -> dict:
    """Word-confidence AUROC, and how well our risk predicts errors of the published sentence."""
    m = word_conf_auroc(ans, truths, auroc)
    risk = np.array([a.guard.risk for a in ans])
    ptop = np.array([a.inputs.p_top1 for a in ans])
    m["auroc_published_wrong_risk"] = auroc(risk, pub_wrong)
    m["auroc_published_wrong_neg_p_top1"] = auroc(-ptop, pub_wrong)
    # Selective commit of the published sentence by our -p_top1 (low risk first): coverage vs WER.
    order = np.argsort(-ptop, kind="stable")
    sel = []
    for frac in (0.5, 0.7, 0.8, 0.9, 1.0):
        k = max(1, int(round(frac * len(order))))
        ii = order[:k]
        sel.append({"coverage": frac, "published_wer": pooled([test[i].truth_words for i in ii],
                    [B.normalize_words(test[i].decoded_sentence) for i in ii], True),
                    "published_sentence_error": float(pub_wrong[ii].mean())})
    m["published_selective_by_our_p_top1"] = sel
    return m


def stage_extra() -> None:
    """Recompute the w_c_trust extra metrics (they were skipped by an `is` test) and merge them."""
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.trust.guard import auroc

    tr = load_json("trust.json")
    prep = load_json("prep.json")
    best = load_json("tune.json")["best"]
    trials = load_trials()
    fit, test = split(trials)
    dec = Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    user = UserConfig.aac_gaze(chars_per_min=prep["speech_rate_125k"]["chars_per_min"])
    streams = {t.index: B.to_symbol_stream(B.trial_stream(t)) for t in fit + test}
    mk = lambda ts: [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in ts]  # noqa: E731
    pipe = TrustPipeline(dec.words_fn, HarnessConfig(seed=SEED, user_config=user, max_wrong_commit=CONFIG["max_wrong_commit"]))
    fi, ti = mk(fit), mk(test)
    pipe.fit(fi, fi)
    ans = [pipe.analyze(pipe.decode(it, 0)) for it in ti]
    pub_wrong = np.array([B.normalize_words(t.decoded_sentence) != t.truth_words for t in test])
    m = extra_word_metrics(ans, [it.text for it in ti], test, pub_wrong, auroc)
    m["extra_check_ewpm"] = summarize(pipe.run_items(ti))["ewpm"]
    tr["levels"]["word"]["policies"]["w_c_trust"].update(m)
    dump(tr, OUT / "trust.json")
    log("extra", {k: v for k, v in m.items() if k != "published_selective_by_our_p_top1"})


def stage_trust(tune_res: dict, quick: bool) -> dict:
    from fidetype.eval.harness import HarnessConfig, Item, TrustPipeline
    from fidetype.interact.simulated_user import UserConfig
    from fidetype.trust.guard import auroc, lexicon_fluency, shuffle_stream, uniform_stream
    from fidetype.trust.policy import Action

    t0 = time.time()
    prep = load_json("prep.json")
    trials = load_trials()
    fit, test = split(trials)
    if quick:
        fit, test = fit[:60], test[:60]
    best = tune_res["best"]
    dec = Decoders(trials, {k: best[k] for k in ("lm_weight", "edit_penalty", "word_bonus")})
    cpm = prep["speech_rate_125k"]["chars_per_min"]
    user = UserConfig.aac_gaze(chars_per_min=cpm)
    streams = {t.index: B.to_symbol_stream(B.trial_stream(t)) for t in fit + test}
    mwc = CONFIG["max_wrong_commit"]

    def items(ts, level):
        if level == "word":
            return [Item(streams[t.index], t.truth_words, stream_text=t.truth_symbols) for t in ts]
        return [Item(streams[t.index], t.truth_symbols) for t in ts]

    levels = {
        "word": {
            "w_a_greedy_commit": (dec.greedy_words_fn, dict(policy="always_commit", use_calibration=False)),
            "w_p_published_commit": (dec.published_fn, dict(policy="always_commit", use_calibration=False)),
            "w_b_top1_commit": (dec.words_fn, dict(policy="always_commit")),
            "w_c_trust": (dec.words_fn, dict(max_wrong_commit=mwc)),
            "w_d_trust_no_calib": (dec.words_fn, dict(max_wrong_commit=mwc, use_calibration=False)),
            "w_e_trust_no_guard": (dec.words_fn, dict(max_wrong_commit=mwc, use_guard=False)),
            "w_q_published_trust": (dec.published_plus_fn, dict(max_wrong_commit=mwc)),
        },
        "phoneme": {
            "p_a_greedy_commit": (dec.greedy_phoneme_fn, dict(policy="always_commit", use_calibration=False)),
            "p_b_top1_commit": (dec.phoneme_nbest_fn, dict(policy="always_commit")),
            "p_c_trust": (dec.phoneme_nbest_fn, dict(max_wrong_commit=mwc)),
        },
    }
    res: dict = {"n_fit": len(fit), "n_test": len(test), "word_decoder": dec.wkw, "phoneme_beam": dec.beam_kw,
                 "user_chars_per_min": cpm, "levels": {}}
    test_truth_words = [t.truth_words for t in test]
    pub_wrong = np.array([B.normalize_words(t.decoded_sentence) != t.truth_words for t in test])
    for level, specs in levels.items():
        fit_items, test_items = items(fit, level), items(test, level)
        caches: dict = {}
        metrics, per, pipes = {}, {}, {}
        for name, (fn, cfg) in specs.items():
            ts = time.time()
            pipe = TrustPipeline(fn, HarnessConfig(seed=SEED, user_config=user, **cfg), caches.setdefault(fn.__name__, {}))
            pipe.fit(fit_items, fit_items)
            m = pipe.evaluate(test_items)
            recs = m.pop("records")
            per[name] = recs
            ans = [pipe.analyze(pipe.decode(it, 0)) for it in test_items]
            truths = [it.text for it in test_items]
            m["truth_in_nbest"] = float(np.mean([an.nbest.index_of(t) >= 0 for an, t in zip(ans, truths)]))
            if level == "word" and fn == dec.words_fn:  # bound methods: use ==, not is
                m.update(extra_word_metrics(ans, truths, test, pub_wrong, auroc))
            if level == "word":
                tops = [an.nbest.texts[0] if len(an.nbest) else "" for an in ans]
                by_day = defaultdict(lambda: [[], []])
                for t, h in zip(test, tops):
                    by_day[t.post_implant_day][0].append(t.truth_words)
                    by_day[t.post_implant_day][1].append(h)
                m["wer_by_day"] = {d: pooled(r, h, True) for d, (r, h) in sorted(by_day.items())}
            m["seconds"] = round(time.time() - ts, 1)
            metrics[name] = m
            pipes[name] = pipe
            log(f"{name}: eWPM {m['ewpm']:.2f} wrong-commit {m['wrong_commit_rate']:.3f} silent {m['silent_error_rate']:.3f} "
                f"WER {m['wer']:.3f} CER {m['cer']:.3f} exact {m['top1_sentence_acc']:.3f} commit {m['rate_commit']:.2f} "
                f"offer {m['rate_offer']:.2f} abstain {m['rate_abstain']:.2f} guardAUROC {m.get('guard_auroc', float('nan')):.3f} ({m['seconds']}s)")
        day = np.array([t.post_implant_day for t in test])
        truths = [it.text for it in test_items]
        bt = bootstrap(per, truths, None, CONFIG["bootstrap_B"], SEED, cpm) if level == "word" else \
            bootstrap(per, truths, None, CONFIG["bootstrap_B"], SEED, cpm)
        bd = bootstrap(per, truths, day, CONFIG["bootstrap_B"], SEED + 1, cpm)
        lv = {"policies": metrics, "bootstrap_trials": bt, "bootstrap_days": bd,
              "gaze_only_ewpm": gaze_ewpm(truths, CONFIG["gaze_chars_per_min"])}
        # Null-input audit (word level only): other-trial swap, frame shuffle, uniform.
        if level == "word":
            lex = dec.lex.words
            fluent = lexicon_fluency(lex)
            rng = np.random.default_rng(SEED)
            na = min(len(test), CONFIG["audit_n"])
            aud_idx = sorted(rng.choice(len(test), na, replace=False).tolist())
            atest = [test[i] for i in aud_idx]
            base = [streams[t.index] for t in atest]
            perm = rng.permutation(len(base))
            for i in range(len(perm)):  # make sure the swapped trial has another sentence
                if atest[perm[i]].truth_words == atest[i].truth_words:
                    perm[i], perm[(i + 1) % len(perm)] = perm[(i + 1) % len(perm)], perm[i]
            nulls = {"real": base, "other_trial": [base[j] for j in perm],
                     "frame_shuffled": [shuffle_stream(s, rng) for s in base],
                     "uniform": [uniform_stream(s, rng, 0.05) for s in base]}
            audit: dict = {}
            dcache: dict = {}
            for name in ("w_b_top1_commit", "w_c_trust", "w_d_trust_no_calib", "w_q_published_trust"):
                pipe = pipes[name]
                T = pipe.frame_scaler.temperature
                audit[name] = {}
                sig = {}
                for cond, ss in nulls.items():
                    fl, com, fc, wrong_c = [], [], [], []
                    for i, s in enumerate(ss):
                        key = (name == "w_q_published_trust", cond, i, round(T, 9))
                        nb = dcache.get(key)
                        if nb is None:
                            s2 = pipe.frame_scaler.transform_stream(s) if T != 1.0 else s
                            if name == "w_q_published_trust":
                                # The published sentence of THIS trial on top of the null stream's n-best.
                                s2 = NeuralTextStream(s2.log_probs, s2.frame_times, s2.vocab, s2.blank_id, s2.source,
                                                      {**s2.meta, "fidetype.trial_index": atest[i].index}, vocab_type=s2.vocab_type)
                                nb = dec.published_plus_fn(s2)
                            else:
                                nb = dec.words_fn(s2)
                            dcache[key] = nb
                        an = pipe.analyze(nb)
                        d = pipe.policy.decide(an.inputs, final_attempt=True)
                        top = nb.top.text if nb.top is not None else ""
                        f = fluent(top)
                        c = d.action == Action.COMMIT
                        fl.append(f)
                        com.append(c)
                        fc.append(f and c)
                        wrong_c.append(c and top != atest[i].truth_words)
                        sig.setdefault(cond, []).append(an.guard.risk)
                    audit[name][cond] = {"fluent_rate": float(np.mean(fl)), "commit_rate": float(np.mean(com)),
                                         "fluent_commit_rate": float(np.mean(fc)), "wrong_commit_rate": float(np.mean(wrong_c))}
                audit[name]["risk_auroc_null_vs_real"] = {
                    c: auroc(np.r_[sig[c], sig["real"]], np.r_[np.ones(len(sig[c])), np.zeros(len(sig["real"]))])
                    for c in nulls if c != "real"}
                log(f"audit {name}: " + " ".join(f"{c}: commit {v['commit_rate']:.2f} fluent+commit {v['fluent_commit_rate']:.2f}"
                                                  for c, v in audit[name].items() if c in nulls))
            lv["null_audit"] = audit
            lv["null_audit_n"] = na
        res["levels"][level] = lv
        dump(res, OUT / ("trust_quick.json" if quick else "trust.json"))
    res["seconds"] = round(time.time() - t0, 1)
    dump(res, OUT / ("trust_quick.json" if quick else "trust.json"))
    return res


# ---------------------------------------------------------------------------
# Stage 4: tables
# ---------------------------------------------------------------------------


def f3(v, nd=3):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "-"
    if isinstance(v, str):
        return v
    return f"{v:.{nd}f}"


def stage_tables(quick: bool) -> None:
    prep = load_json("prep.json")
    tune = load_json("tune.json") if (OUT / "tune.json").exists() else None
    tr = load_json("trust_quick.json" if quick else "trust.json")
    L = ["# Brain-to-Text '25 trust run: generated tables (run.py)", ""]
    L += [f"Trials: {prep['n_trials']} (125k-vocab: fit {prep['n_fit']}, test {prep['n_test']}; "
          f"{prep['n_test_sentences']} test sentences, fit/test sentence overlap {prep['fit_test_sentence_overlap']}). "
          f"Greedy path == stored raw phonemes: {prep['greedy_equals_raw']} / {prep['n_trials']}.", ""]
    L += ["## Published online decoder (Card et al.; from the pickle)", "",
          "| group | n | WER | sentence exact | PER raw greedy | PER of published sentence |", "|---|---|---|---|---|---|"]
    for g, v in prep["published"].items():
        L.append(f"| {g} | {v['n']} | {f3(v['wer_published'], 4)} | {f3(v['sentence_exact_published'])} | {f3(v['per_raw_greedy'], 4)} | {f3(v['per_published_sentence'], 4)} |")
    L += ["", "| day | n | vocab | WER published | PER raw |", "|---|---|---|---|---|"]
    for d, v in prep["published_by_day"].items():
        L.append(f"| {d} | {v['n']} | {v['vocab_sizes']} | {f3(v['wer_published'], 4)} | {f3(v['per_raw_greedy'], 4)} |")
    if tune:
        L += ["", f"## Word decoder tuning ({tune['n']} fit trials; phoneme beam PER {f3(tune['phoneme_beam_per'], 4)}, greedy PER {f3(tune['phoneme_greedy_per'], 4)})", "",
              "| lm_weight | edit_penalty | word_bonus | WER | sentence exact | truth in n-best |", "|---|---|---|---|---|---|"]
        for r in tune["rows"]:
            mark = " **(best)**" if r == tune["best"] else ""
            L.append(f"| {r['lm_weight']} | {r['edit_penalty']} | {r['word_bonus']}{mark} | {f3(r['wer'], 4)} | {f3(r['sentence_exact'])} | {f3(r['truth_in_nbest'])} |")
    for level, lv in tr["levels"].items():
        bt, bd = lv["bootstrap_trials"]["policies"], lv["bootstrap_days"]["policies"]

        def wci(p, k, nd=3):
            v = lv["policies"][p].get(k) if p in lv["policies"] else lv.get("gaze_only_ewpm")
            s = f3(v, nd)
            c1, c2 = bt.get(p, {}).get(k), bd.get(p, {}).get(k)
            if c1:
                s += f" [{f3(c1[0], nd)}, {f3(c1[1], nd)}]"
            if c2:
                s += f" {{{f3(c2[0], nd)}, {f3(c2[1], nd)}}}"
            return s

        L += ["", f"## {level}-level trust harness (test {tr['n_test']} trials; fit on {tr['n_fit']})", "",
              "Values: point [trial bootstrap 95% CI] {day-cluster bootstrap 95% CI}.", "",
              "| policy | eWPM | wrong-commit | silent error | WER | CER | sentence exact | truth in n-best | COMMIT / OFFER / ASK / ABSTAIN |",
              "|---|---|---|---|---|---|---|---|---|"]
        for p, m in lv["policies"].items():
            L.append(f"| {p} | {wci(p, 'ewpm', 2)} | {wci(p, 'wrong_commit_rate')} | {wci(p, 'silent_error_rate')} | {f3(m['wer'], 4)} | {f3(m['cer'], 4)} "
                     f"| {f3(m['top1_sentence_acc'])} | {f3(m.get('truth_in_nbest'))} | {f3(m['rate_commit'], 2)} / {f3(m['rate_offer'], 2)} / {f3(m['rate_ask'], 2)} / {f3(m['rate_abstain'], 2)} |")
        L.append(f"| gaze_only | {wci('gaze_only', 'ewpm', 2)} | 0 | 0 | - | - | - | - | - |")
        L += ["", "| policy | T frame | T sentence | ECE token before | after | ECE sentence before | after | coverage | set size | guard AUROC | low-evidence AUROC | inconsistency AUROC | p_top1 AUROC | word-conf AUROC |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for p, m in lv["policies"].items():
            L.append(f"| {p} | {f3(m.get('fit_temperature_frame'))} | {f3(m.get('fit_temperature_sentence'))} | {f3(m.get('ece_char_before'))} | {f3(m.get('ece_char_after'))} "
                     f"| {f3(m.get('ece_sentence_before'))} | {f3(m.get('ece_sentence_after'))} | {f3(m.get('coverage'))} | {f3(m.get('mean_set_size'))} "
                     f"| {f3(m.get('guard_auroc'))} | {f3(m.get('guard_auroc_low_evidence'))} | {f3(m.get('guard_auroc_inconsistency'))} | {f3(m.get('p_top1_auroc'))} | {f3(m.get('word_conf_auroc'))} |")
        L += ["", "| paired difference | trial CI | P(diff <= 0) | day CI |", "|---|---|---|---|"]
        for k, v in lv["bootstrap_trials"]["diffs"].items():
            vd = lv["bootstrap_days"]["diffs"].get(k, {})
            c = vd.get("ci") or [None, None]
            L.append(f"| {k} | [{f3(v['ci'][0])}, {f3(v['ci'][1])}] | {f3(v['p_le_0'])} | [{f3(c[0])}, {f3(c[1])}] |")
        if "w_c_trust" in lv["policies"]:
            m = lv["policies"]["w_c_trust"]
            L += ["", f"Our risk vs 'published sentence wrong' (test): AUROC risk {f3(m.get('auroc_published_wrong_risk'))}, "
                  f"-p_top1 {f3(m.get('auroc_published_wrong_neg_p_top1'))}.", "",
                  "| coverage (highest our p_top1 first) | published WER | published sentence error |", "|---|---|---|"]
            for r in m.get("published_selective_by_our_p_top1", []):
                L.append(f"| {r['coverage']} | {f3(r['published_wer'], 4)} | {f3(r['published_sentence_error'])} |")
            L += ["", "| day | WER our top-1 (test) |", "|---|---|"]
            for d, v in m.get("wer_by_day", {}).items():
                L.append(f"| {d} | {f3(v, 4)} |")
        if "null_audit" in lv:
            L += ["", "## Null-input audit (word level, test streams)", "",
                  "| policy | input | fluent top-1 | COMMIT | fluent and committed | wrong commit |", "|---|---|---|---|---|---|"]
            for p, d in lv["null_audit"].items():
                for c, v in d.items():
                    if c.startswith("risk_"):
                        continue
                    L.append(f"| {p} | {c} | {f3(v['fluent_rate'])} | {f3(v['commit_rate'])} | {f3(v['fluent_commit_rate'])} | {f3(v['wrong_commit_rate'])} |")
                L.append(f"| {p} | risk AUROC null vs real | " + ", ".join(f"{c} {f3(a)}" for c, a in d["risk_auroc_null_vs_real"].items()) + " | | | |")
    (OUT / ("tables_quick.md" if quick else "tables.md")).write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    global LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="prep,tune,trust,tables")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    LOG = OUT / ("run_quick.log" if a.quick else "run.log")
    st = a.stages.split(",")
    if "prep" in st:
        stage_prep()
    if "tune" in st:
        stage_tune()
    if "trust" in st:
        stage_trust(load_json("tune.json"), a.quick)
    if "extra" in st:
        stage_extra()
    if "tables" in st:
        stage_tables(a.quick)
    log("done")


if __name__ == "__main__":
    main()
