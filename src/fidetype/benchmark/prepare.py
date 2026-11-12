"""Build the local truth files of the benchmark tracks from downloaded data.

The repository holds no data and no ground-truth text. A user who has
downloaded a dataset (see :mod:`fidetype.benchmark.registry`) runs::

    python -m fidetype.benchmark prepare <track> --data <path> --out truth.jsonl

The command rebuilds every trial of the track with its split, its
normalised truth text and its cluster labels. Then it checks the result
against the committed split file (ids and text hashes). A mismatch means
that the local data or code differ from the benchmark version: the
command stops and does not write a truth file.

Each builder returns a list of :class:`TruthTrial`. The trial ids are
the ones of the split file.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Callable

import numpy as np


@dataclass
class TruthTrial:
    id: str
    split: str
    text: str
    clusters: dict[str, str] = field(default_factory=dict)
    #: Extra per-trial data that defines the trial but is not text (for
    #: composed sentences: the press ids). Hashed into the split file.
    detail: Any = None

    def to_dict(self) -> dict[str, Any]:
        d = {"id": self.id, "split": self.split, "text": self.text, "clusters": self.clusters}
        if self.detail is not None:
            d["detail"] = self.detail
        return d


# ---------------------------------------------------------------------------
# SpanishBCBL MEG (async): from the sidecars of our preprocessing cache
# ---------------------------------------------------------------------------


def spanishbcbl_trials(cache_root: str | PathLike[str]) -> list[TruthTrial]:
    """Trials of the SpanishBCBL cache (``tools/data/preprocess_spanishbcbl.py``).

    Rules (as in ``fidetype.decoders.dataset``): practice trials
    (``is_training``) and trials with no typed key are dropped. The split
    is :func:`fidetype.data.preprocess.assign_split` of the target text.
    The truth is the normalised target sentence.
    """
    from fidetype.data.preprocess import assign_split
    from fidetype.streams.vocab import normalize_text

    root = Path(cache_root)
    sidecars = sorted(root.glob("S*/*.json"))
    if not sidecars:
        raise FileNotFoundError(f"no cache sidecars (S*/*.json) under {root}")
    out = []
    for sc in sidecars:
        if not sc.with_suffix(".npz").exists():
            continue
        meta = json.loads(sc.read_text(encoding="utf-8"))
        subj, ses, blk = meta["subject"], meta["session"], meta["block"]
        part = str(meta.get("participant", subj))
        for seg in meta.get("segments", []):
            if seg.get("is_training", False) or not (seg.get("typed_text") or "").strip():
                continue
            target = seg.get("target_text", "") or ""
            text = normalize_text(target)
            out.append(TruthTrial(
                id=f"{subj}_{ses}_{blk}_{int(seg['trial_idx'])}",
                split=assign_split(target),
                text=text,
                clusters={"participant": part, "sentence": text_hash(text)[:12]},
            ))
    return out


# ---------------------------------------------------------------------------
# Brain-to-Text '25 (T15 copy task)
# ---------------------------------------------------------------------------

B2T_VOCAB_SIZE_MAIN = 125000


def b2t25_trials(pkl_path: str | PathLike[str]) -> list[TruthTrial]:
    """Trials of ``t15_copyTask.pkl`` (125k-vocabulary trials only).

    Per post-implant day, in file order: the first half is ``cal``, the
    second half is ``test`` (the split of experiments/2026-11-10-b2t25-trust).
    """
    from fidetype.adapters.b2t25 import load_copytask

    trials = load_copytask(pkl_path, verify=True)
    by_day: dict[int, list] = defaultdict(list)
    for t in trials:
        if t.vocab_size == B2T_VOCAB_SIZE_MAIN:
            by_day[t.post_implant_day].append(t)
    out = []
    for d in sorted(by_day):
        ts = by_day[d]
        h = len(ts) // 2
        for k, t in enumerate(ts):
            out.append(TruthTrial(
                id=f"t15-copytask-{t.index:04d}",
                split="cal" if k < h else "test",
                text=t.truth_words,
                clusters={"day": f"day{d:03d}"},
            ))
    return out


# ---------------------------------------------------------------------------
# Toronto sEMG, composed sentences
# ---------------------------------------------------------------------------

TORONTO_RECIPE = {
    "seed": 0,
    "sentence_chars": [12, 50],
    "sentences_per_participant": {"cal": 30, "test": 30},
    "min_words": 2,
    "pool_rule": "day-2 (session T2) presses; recording order 1 -> cal pool, order >= 2 -> test pool",
    "sentence_rule": "Tatoeba held-out list; keep typeable a-z/space sentences with 12-50 chars and >= 2 words; "
    "dedupe; permute with default_rng(seed); first half -> cal texts, second half -> test texts; "
    "participant k takes slice k of each half",
    "press_rule": "per character: a random unused press of that character from the pool (rng shared, "
    "participants in numeric order, cal then test)",
}


def toronto_trials(cache_root: str | PathLike[str], heldout_sentences: str | PathLike[str],
                   recipe: dict[str, Any] | None = None) -> list[TruthTrial]:
    """Composed sentences of the Toronto sEMG track.

    ``cache_root`` is the window cache of
    ``experiments/2026-11-11-emg-toronto/prep.py`` (``windows.npz`` and
    ``files.json``). ``heldout_sentences`` is the Tatoeba held-out list of
    the English char LM. This reproduces the plan of
    ``experiments/2026-11-11-emg-toronto/trust.py`` exactly (same seed,
    same order of random draws). ``detail`` holds the press ids
    (``<recording key>#<press index in recording>``) of each character.
    """
    from fidetype.adapters.toronto_semg import KEY_CHARS, is_typeable

    r = {**TORONTO_RECIPE, **(recipe or {})}
    root = Path(cache_root)
    with np.load(root / "windows.npz", allow_pickle=False) as d:
        y = d["label"].astype(np.int64)
        file_idx = d["file_idx"].astype(np.int64)
    files = json.loads((root / "files.json").read_text(encoding="utf-8"))

    lo, hi = r["sentence_chars"]
    texts, seen = [], set()
    for line in Path(heldout_sentences).read_text(encoding="utf-8").splitlines():
        s = " ".join(line.split())
        if lo <= len(s) <= hi and is_typeable(s) and len(s.split()) >= r["min_words"] and s not in seen:
            seen.add(s)
            texts.append(s)
    texts = [texts[i] for i in np.random.default_rng(r["seed"]).permutation(len(texts))]

    # Press ids: ordinal of the window inside its recording.
    ordinal = np.zeros(len(y), dtype=np.int64)
    counter: dict[int, int] = defaultdict(int)
    for i, fi in enumerate(file_idx):
        ordinal[i] = counter[int(fi)]
        counter[int(fi)] += 1

    pools: dict[str, dict[str, dict[str, list[int]]]] = defaultdict(lambda: {"fit": defaultdict(list), "test": defaultdict(list)})
    for i, (lab, fi) in enumerate(zip(y, file_idx)):
        f = files[int(fi)]
        if f["session"] != "T2":
            continue
        which = "fit" if f["order"] == 1 else "test"
        pools[f["participant"]][which][KEY_CHARS[int(lab)]].append(i)

    def compose(cands, pool, rng, n_want):
        got = []
        for t in cands:
            if len(got) >= n_want:
                break
            if any(len(pool.get(c, ())) == 0 for c in set(t)):
                continue
            used: dict[str, set] = defaultdict(set)
            idx = []
            for c in t:
                cand = [i for i in pool[c] if i not in used[c]] or pool[c]
                j = int(cand[rng.integers(len(cand))])
                used[c].add(j)
                idx.append(j)
            got.append((t, idx))
        return got

    pids = sorted(pools, key=lambda s: int(s[1:]))
    half = len(texts) // 2
    fit_texts, test_texts = texts[:half], texts[half:]
    per_p = len(fit_texts) // len(pids)
    rng = np.random.default_rng(r["seed"])
    n_cal, n_test = r["sentences_per_participant"]["cal"], r["sentences_per_participant"]["test"]
    out = []
    for k, p in enumerate(pids):
        plan = {"cal": compose(fit_texts[k * per_p:(k + 1) * per_p], pools[p]["fit"], rng, n_cal),
                "test": compose(test_texts[k * per_p:(k + 1) * per_p], pools[p]["test"], rng, n_test)}
        for split in ("cal", "test"):
            for j, (t, idx) in enumerate(plan[split]):
                presses = [f"{files[int(file_idx[i])]['key']}#{int(ordinal[i])}" for i in idx]
                out.append(TruthTrial(id=f"{p}-{split}-{j:02d}", split=split, text=t,
                                      clusters={"participant": p}, detail=presses))
    return out


# ---------------------------------------------------------------------------
# Common
# ---------------------------------------------------------------------------


def text_hash(text: str) -> str:
    """SHA-256 (hex) of the UTF-8 text. Used in split files instead of the text."""
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def detail_hash(detail: Any) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(detail, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


BUILDERS: dict[str, Callable[..., list[TruthTrial]]] = {
    "spanishbcbl-meg-async": spanishbcbl_trials,
    "b2t25-t15-copytask": b2t25_trials,
    "toronto-semg-composed": toronto_trials,
}


def build_trials(track: str, data: str | PathLike[str], extra: str | PathLike[str] | None = None) -> list[TruthTrial]:
    """Run the builder of ``track``. ``extra`` is the Tatoeba held-out file (Toronto only)."""
    if track not in BUILDERS:
        raise KeyError(f"no builder for track {track!r}")
    if track == "toronto-semg-composed":
        if extra is None:
            raise ValueError("toronto-semg-composed needs --sentences <eng_tatoeba_heldout.txt>")
        return toronto_trials(data, extra)
    return BUILDERS[track](data)


def write_truth(trials: list[TruthTrial], path: str | PathLike[str], splits: tuple[str, ...] | None = None) -> int:
    """Write the truth file (JSON Lines, one trial per line). Keep it local: never commit it."""
    rows = [t for t in trials if splits is None or t.split in splits]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for t in rows:
            f.write(json.dumps({"id": t.id, "split": t.split, "text": t.text, "clusters": t.clusters},
                               ensure_ascii=False) + "\n")
    return len(rows)


def read_truth(path: str | PathLike[str]) -> dict[str, dict[str, Any]]:
    """Read a truth file: {trial id: {"text", "split", "clusters"}}."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["id"]] = r
    return out
