"""Build the English and Spanish 6-gram character LMs from Tatoeba.

Inputs (outside the repo, see src/fidetype/lm/corpora.md):
  C:/Users/zhang/bci-data/corpora/tatoeba/{eng,spa}_sentences.tsv.bz2
  C:/Users/zhang/bci-data/SpanishBCBL/MEG/logs/*.mat   (for the blocklist)

Outputs (outside the repo):
  C:/Users/zhang/bci-data/lm/eng_tatoeba_6gram_mkn.npz
  C:/Users/zhang/bci-data/lm/spa_tatoeba_6gram_mkn.npz
  C:/Users/zhang/bci-data/lm/eng_tatoeba_heldout.txt    (benchmark test pool)
  C:/Users/zhang/bci-data/lm/spa_tatoeba_heldout.txt
  C:/Users/zhang/bci-data/lm/spanishbcbl_blocklist.txt  (normalised targets)
  C:/Users/zhang/bci-data/lm/build_report.json

Run: uv run python experiments/2026-11-08-lm-beam/build_lms.py
"""

from __future__ import annotations

import bz2
import json
import time
from pathlib import Path

import numpy as np

from fidetype.lm.ngram import CharNgramLM, exclude_sentences
from fidetype.streams.corpus import sentences as toy_sentences
from fidetype.streams.vocab import normalize_text

DATA = Path("C:/Users/zhang/bci-data")
CORPORA = DATA / "corpora" / "tatoeba"
OUT = DATA / "lm"
LOGS = DATA / "SpanishBCBL" / "MEG" / "logs"
SIDECARS = DATA / "cache" / "spanishbcbl" / "v1"

SEED = 20261108
N_HELDOUT = 5000
MAX_TRAIN = {"eng": 600_000, "spa": None}  # None = all sentences.
ORDER = 6


def read_tatoeba(lang: str) -> list[str]:
    """Return the normalised, de-duplicated sentences (file order)."""
    seen: set[str] = set()
    out: list[str] = []
    with bz2.open(CORPORA / f"{lang}_sentences.tsv.bz2", "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            s = normalize_text(parts[2])
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


def spanishbcbl_targets() -> tuple[list[str], dict]:
    """Return the normalised SpanishBCBL target sentences from the logs
    (and from the sidecar JSONs, if another agent made them)."""
    import scipy.io

    found: set[str] = set()
    info = {"log_files": 0, "log_files_failed": [], "sidecar_dir_exists": SIDECARS.exists(), "sidecar_files": 0}
    for p in sorted(LOGS.glob("*.mat")):
        try:
            mat = scipy.io.loadmat(p, simplify_cells=True)
        except Exception as exc:  # noqa: BLE001
            info["log_files_failed"].append(f"{p.name}: {exc}")
            continue
        info["log_files"] += 1
        pr = mat["pr_trials"]
        for key in ("sequence", "sequences"):
            vals = pr.get(key, [])
            for v in np.atleast_1d(np.asarray(vals, dtype=object)).ravel():
                s = normalize_text(str(v))
                if s:
                    found.add(s)
    if SIDECARS.exists():
        for p in sorted(SIDECARS.rglob("*.json")):
            info["sidecar_files"] += 1
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            stack = [d]
            while stack:  # Take every string under a key that looks like a sentence.
                x = stack.pop()
                if isinstance(x, dict):
                    for k, v in x.items():
                        if isinstance(v, str) and k.lower() in ("sentence", "text", "target", "sequence"):
                            s = normalize_text(v)
                            if s:
                                found.add(s)
                        else:
                            stack.append(v)
                elif isinstance(x, list):
                    stack.extend(x)
    info["n_targets"] = len(found)
    return sorted(found), info


def build(lang: str, blocklist: list[str], report: dict) -> None:
    t0 = time.time()
    sents = read_tatoeba(lang)
    n_all = len(sents)
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(n_all)
    sents = [sents[i] for i in perm]
    # Remove test sentences before the split: exact match, and any corpus
    # sentence that contains a target sentence (or is contained in one).
    block = set(blocklist)
    # Containment check only for the real test set (it is small).
    long_block = [b for b in block if len(b) >= 15] if lang == "spa" else []
    before = len(sents)
    kept = exclude_sentences(sents, block)
    if long_block:
        kept = [s for s in kept if not any(b in s for b in long_block) and not (len(s) >= 15 and any(s in b for b in long_block))]
    n_blocked = before - len(kept)
    heldout, train = kept[:N_HELDOUT], kept[N_HELDOUT:]
    if MAX_TRAIN[lang] is not None:
        train = train[: MAX_TRAIN[lang]]
    lm = CharNgramLM(order=ORDER, smoothing="mkn")
    lm.meta.update(
        language=lang,
        source="Tatoeba per-language sentence export (downloads.tatoeba.org/exports/per_language)",
        licence="CC BY 2.0 FR (Tatoeba default; some sentences CC0). Attribution: Tatoeba contributors, https://tatoeba.org",
        downloaded="2026-11-08",
        seed=SEED,
        n_heldout=len(heldout),
        n_blocked=n_blocked,
        blocklist="SpanishBCBL targets + fidetype corpus.py sentences",
    )
    lm.train(train, normalize=False)
    t_train = time.time() - t0
    path = OUT / f"{lang}_tatoeba_{ORDER}gram_mkn.npz"
    lm.save(path)
    (OUT / f"{lang}_tatoeba_heldout.txt").write_text("\n".join(heldout) + "\n", encoding="utf-8")
    lm2 = CharNgramLM.load(path)
    r = {
        "n_sentences_unique": n_all,
        "n_blocked": n_blocked,
        "n_train": len(train),
        "n_train_chars": lm.meta["n_chars"],
        "n_heldout": len(heldout),
        "n_grams_per_order": lm.meta["n_grams_per_order"],
        "discounts": lm.discounts,
        "ppl_heldout": lm2.perplexity(heldout[:2000], normalize=False),
        "ppl_heldout_unigram_ref": CharNgramLM(1).train(train[:100000], normalize=False).perplexity(heldout[:2000], normalize=False),
        "file": str(path),
        "file_mb": path.stat().st_size / 1e6,
        "train_s": t_train,
    }
    if lang == "spa":
        r["ppl_spanishbcbl_targets"] = lm2.perplexity(blocklist, normalize=False) if blocklist else None
    if lang == "eng":
        r["ppl_corpus_py_sentences"] = lm2.perplexity(toy_sentences(500), normalize=True)
    for o in (3, 4, 5):
        small = CharNgramLM(order=o).train(train, normalize=False)
        r[f"ppl_heldout_order{o}"] = small.perplexity(heldout[:2000], normalize=False)
    report[lang] = r
    print(lang, json.dumps(r, indent=1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets, info = spanishbcbl_targets()
    (OUT / "spanishbcbl_blocklist.txt").write_text("\n".join(targets) + "\n", encoding="utf-8")
    print("SpanishBCBL targets:", json.dumps(info, indent=1))
    toy = [normalize_text(s) for s in toy_sentences(2000)]
    report: dict = {"spanishbcbl": info}
    build("eng", toy, report)
    build("spa", targets, report)
    (OUT / "build_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
