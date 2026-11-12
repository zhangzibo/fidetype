"""R1 item 5 (gap G9), step 1: leakage-cleaned LMs (CPU, outside the repo).

Rebuilds the English Tatoeba char 6-gram LM exactly as
``experiments/2026-11-08-lm-beam/build_lms.py`` (same reading, de-duplication,
seed, block list, held-out slice and 600,000-sentence training slice) and then
removes from the TRAINING slice only:

- ``b2t``: every training sentence equal to, or a near variant of, a
  Brain-to-Text '25 cue sentence (all 1,718 trials). Near variant = character
  edit distance <= 0.25 x the cue length (the MEG rule), both sides in
  ``normalize_text`` form. The B2T word unigram counts are rebuilt from all
  Tatoeba English sentences without the exact cue matches (``normalize_words``)
  and without the near variants found in the training slice.
- ``emg``: every training sentence that is a near variant (same rule) of one
  of the 551 sEMG test sentences (they come from the held-out slice, so exact
  matches are already excluded) or of a sEMG fit sentence.

Outputs (outside the repo, C:/Users/zhang/bci-data/lm/): eng_tatoeba_6gram_mkn_noB2T.npz,
eng_tatoeba_word_counts_noB2T.json, eng_tatoeba_6gram_mkn_noEMG.npz.
Report (committed, counts and up to 10 Tatoeba examples): results/build_report.json.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-12-paper1-r1-analyses/leakage/build_lms.py
"""

from __future__ import annotations

import bz2
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import common as C  # noqa: E402
from fidetype.lm.ngram import CharNgramLM, exclude_sentences  # noqa: E402
from fidetype.streams.corpus import sentences as toy_sentences  # noqa: E402
from fidetype.streams.vocab import normalize_text  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
C.Log.path = OUT / "build.log"
LM_DIR = Path("C:/Users/zhang/bci-data/lm")
CORPUS = Path("C:/Users/zhang/bci-data/corpora/tatoeba/eng_sentences.tsv.bz2")
SEED, N_HELDOUT, MAX_TRAIN, ORDER = 20261108, 5000, 600_000, 6
MAX_CER = 0.25


def original_split() -> tuple[list[str], list[str]]:
    """The held-out and training slices of the original English LM build."""
    seen: set[str] = set()
    sents: list[str] = []
    with bz2.open(CORPUS, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            s = normalize_text(parts[2])
            if s and s not in seen:
                seen.add(s)
                sents.append(s)
    perm = np.random.default_rng(SEED).permutation(len(sents))
    sents = [sents[i] for i in perm]
    kept = exclude_sentences(sents, [normalize_text(s) for s in toy_sentences(2000)])
    return kept[:N_HELDOUT], kept[N_HELDOUT:][:MAX_TRAIN]


def near_variants(targets: list[str], corpus: list[str], max_cer: float = MAX_CER) -> dict[str, list[int]]:
    """For each target, the corpus indices with edit distance <= max_cer x len(target).

    Exact banded search: length filter, then a Levenshtein DP vectorised over the
    candidates, with candidates pruned as soon as their row minimum exceeds k.
    """
    cap = int(max(len(t) for t in targets) * (1 + max_cer)) + 1
    sub = np.array([i for i, s in enumerate(corpus) if len(s) <= cap])  # longer sentences can never match
    lens = np.array([len(corpus[i]) for i in sub])
    L = int(lens.max())
    codes = np.full((len(sub), L), -1, np.int16)
    for r, i in enumerate(sub):
        codes[r, : lens[r]] = np.frombuffer(corpus[i].encode("latin-1", "replace"), np.uint8)
    out: dict[str, list[int]] = {}
    for ti, t in enumerate(targets):
        n = len(t)
        k = int(np.floor(max_cer * n))
        cand = np.where(np.abs(lens - n) <= k)[0]
        if cand.size == 0:
            out[t] = []
            continue
        lc = lens[cand]
        Lm = int(lc.max())
        X = codes[cand, :Lm]
        tc = np.frombuffer(t.encode("latin-1", "replace"), np.uint8).astype(np.int16)
        prev = np.tile(np.arange(Lm + 1, dtype=np.int16), (cand.size, 1))
        for i in range(1, n + 1):
            cur = np.empty_like(prev)
            cur[:, 0] = i
            diag = prev[:, :-1] + (X != tc[i - 1])
            up = prev[:, 1:] + 1
            best = np.minimum(diag, up)
            for j in range(1, Lm + 1):  # left dependency
                np.minimum(best[:, j - 1], cur[:, j - 1] + 1, out=cur[:, j])
            keep = cur.min(axis=1) <= k
            if not keep.all():
                cand, lc, X, cur = cand[keep], lc[keep], X[keep], cur[keep]
                if cand.size == 0:
                    break
            prev = cur
        if cand.size == 0:
            out[t] = []
            continue
        d = prev[np.arange(cand.size), lc]
        out[t] = sub[cand[d <= k]].tolist()
        if ti % 200 == 0:
            C.log(f"  near variants: {ti}/{len(targets)}")
    return out


def train_lm(train: list[str], path: Path, meta: dict) -> dict:
    lm = CharNgramLM(order=ORDER, smoothing="mkn")
    lm.meta.update(meta)
    lm.train(train, normalize=False)
    lm.save(path)
    return {"file": str(path), "n_train": len(train), "n_grams_per_order": lm.meta["n_grams_per_order"]}


def main() -> None:
    t0 = time.time()
    held, train = original_split()
    C.log(f"original split: held-out {len(held)}, train {len(train)} ({time.time() - t0:.0f}s)")
    rep: dict = {"rule": f"edit distance <= {MAX_CER} x target length (normalize_text form)", "n_train_original": len(train)}
    # Check: the rebuilt slice is the original one (same 6-gram count as build_report.json).
    orig = json.loads((LM_DIR / "build_report.json").read_text(encoding="utf-8"))["eng"]
    rep["check_n_train_matches_original"] = len(train) == orig["n_train"]

    # ---- B2T
    ctx_b = C.load_module("b2t25run", C.REPO / "experiments/2026-11-10-b2t25-trust/run.py")
    trials = ctx_b.load_trials()
    cues_w = sorted({t.truth_words for t in trials})
    cues_t = sorted({normalize_text(t.cue_sentence) for t in trials})
    tset = set(train)
    nv = near_variants(cues_t, train)
    hit_idx = sorted({i for v in nv.values() for i in v})
    exact_train = sum(1 for c in cues_t if c in tset)
    rep["b2t"] = {"n_cue_sentences": len(cues_t), "cues_with_exact_match_in_lm_train": exact_train,
                  "cues_with_near_variant_in_lm_train": sum(1 for v in nv.values() if v),
                  "lm_train_sentences_removed": len(hit_idx),
                  "examples": [[c, train[v[0]]] for c, v in nv.items() if v][:10]}
    removed = {train[i] for i in hit_idx}
    train_b = [s for s in train if s not in removed]
    rep["b2t"]["lm"] = train_lm(train_b, LM_DIR / "eng_tatoeba_6gram_mkn_noB2T.npz",
                                {"note": "R1 G9: original English LM minus B2T cue sentences and near variants"})
    # Word unigram counts: all Tatoeba English minus exact cue matches and the removed near variants.
    cue_set = set(cues_w)
    wc: Counter = Counter()
    n_ex = 0
    with bz2.open(CORPUS, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if not parts:
                continue
            w = ctx_b.B.normalize_words(parts[-1])
            if w in cue_set or normalize_text(parts[-1]) in removed:
                n_ex += 1
                continue
            wc.update(w.split())
    (LM_DIR / "eng_tatoeba_word_counts_noB2T.json").write_text(json.dumps(dict(wc)), encoding="utf-8")
    rep["b2t"]["word_count_sentences_removed"] = n_ex
    rep["b2t"]["word_types"] = len(wc)
    C.log(f"b2t: {rep['b2t']['cues_with_exact_match_in_lm_train']} exact / {rep['b2t']['cues_with_near_variant_in_lm_train']} near; "
          f"removed {len(hit_idx)} train sentences, {n_ex} word-count sentences ({time.time() - t0:.0f}s)")

    # ---- sEMG
    b = C.emg_base()
    test_t = sorted({t for p in b.pids for t, _ in b.plan[p]["test"]})
    fit_t = sorted({t for p in b.pids for t, _ in b.plan[p]["fit"]})
    nv_t = near_variants(test_t, train)
    nv_f = near_variants(fit_t, train)
    hit = sorted({i for v in list(nv_t.values()) + list(nv_f.values()) for i in v})
    rep["emg"] = {"n_test_sentences": len(test_t), "n_fit_sentences": len(fit_t),
                  "test_with_exact_match_in_lm_train": sum(1 for t in test_t if t in tset),
                  "test_with_near_variant_in_lm_train": sum(1 for v in nv_t.values() if v),
                  "fit_with_near_variant_in_lm_train": sum(1 for v in nv_f.values() if v),
                  "lm_train_sentences_removed": len(hit),
                  "test_sentences_with_near_variant": [t for t, v in nv_t.items() if v],
                  "examples": [[t, train[v[0]]] for t, v in nv_t.items() if v][:10]}
    rm = {train[i] for i in hit}
    rep["emg"]["lm"] = train_lm([s for s in train if s not in rm], LM_DIR / "eng_tatoeba_6gram_mkn_noEMG.npz",
                                {"note": "R1 G9: original English LM minus near variants of the sEMG fit and test sentences"})
    C.log(f"emg: test near {rep['emg']['test_with_near_variant_in_lm_train']} / {len(test_t)}; removed {len(hit)} ({time.time() - t0:.0f}s)")
    rep["b2t"]["test_trial_sentences_with_near_variant"] = sorted({c for c, v in nv.items() if v})
    C.dump(rep, OUT / "build_report.json")
    C.log("done")


if __name__ == "__main__":
    main()
