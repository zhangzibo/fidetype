"""Train / test overlap check of benchmark entries (roadmap P6-10, open gap 33).

An entry must not be scored on units that its decoder, its tuning or its
calibration saw. The v0.2 submission manifest declares the data it used in
the field ``training_data``. The scorer compares that declaration with the
scored test units in three ways:

- **id**: unit hashes and named partitions resolve to scored unit hashes;
- **possible id**: a trial of another file of the same recording matches a
  scored unit, but the match has more than one candidate (committed map);
- **text**: the same normalised sentence (salted text hash), because the
  same sentence can sit under another trial id.

Declaration (``submission.json`` key ``training_data``)::

    "training_data": "none"            # no data of this dataset (train, tune or calibration)

    "training_data": {
      "sources": [
        {"dataset": "b2t25-hdf5", "partitions": ["train"], "use": "train",
         "exclude": "track-test-matches"},
        {"dataset": "b2t25-t15", "partitions": ["cal"], "use": "calibration"},
        {"dataset": "tatoeba-en", "use": "train", "note": "char LM"}
      ],
      "unit_ids":    {"tune": ["<16-hex unit hash>", ...]},
      "text_hashes": {"train": ["<16-hex text hash>", ...]},
      "file": "training_data.json"     # optional: more unit_ids / text_hashes, next to submission.json
    }

``use`` is ``train``, ``tune`` or ``calibration``. A source resolves when
its dataset is the track (slug or dataset id; partitions = split names of the
split file) or has a committed overlap map for the track (``MAPS``). Other
sources are *external*: the check lists them and cannot test them, unless the
entry also gives their ``text_hashes``. Make hashes with
``python -m fidetype.benchmark overlap-hashes``.

Result block (score card key ``overlap_check``): ``status`` is ``pass``,
``overlap`` or ``not checked``; ``passed`` is True, False or None. No
declaration gives ``not checked``, never ``pass``.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from os import PathLike
from pathlib import Path
from typing import Any, Iterable, Sequence

from fidetype.benchmark import tracks as TR
from fidetype.benchmark.submission import SubmissionError

OVERLAP_VERSION = "overlap-check/1"
MAP_SCHEMA = "fidetype.benchmark.overlap-map/1"
USES = ("train", "tune", "calibration")
DECL_KEYS = {"sources", "unit_ids", "text_hashes", "file", "note"}
SOURCE_KEYS = {"dataset", "partitions", "use", "exclude", "note"}
EXCLUDE_ALL = "track-test-matches"
MAPS_DIR = Path(__file__).resolve().parent / "splits" / "overlap-maps"
#: Committed hash-only maps: {(track, source dataset): file name in ``MAPS_DIR``}.
MAPS: dict[tuple[str, str], str] = {("b2t25-t15", "b2t25-hdf5"): "b2t25-t15__b2t25-hdf5.json"}
RULE = ("An entry overlaps when a scored test unit is in its declared train, tune or calibration data: by unit id, "
        "by a possible trial match in a committed map, or by the same normalised sentence (text hash).")


def _h(s: str, n: int = 16) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:n]


def _is_hex16(x: Any) -> bool:
    return isinstance(x, str) and len(x) == 16 and all(c in "0123456789abcdef" for c in x)


def text_hash(track: str, text: str) -> str:
    """Salted hash of the normalised text (track normalizer). Equal sentences give equal hashes."""
    from fidetype.benchmark.registry import normalize
    from fidetype.benchmark.scorecard import SCORE_SPECS

    return _h(f"{TR.salt(track)}|text|{normalize(text, SCORE_SPECS[track].normalizer)}")


def unit_hash(track: str, local_id: str) -> str:
    """The unit hash of a local unit id (same as the split file ``h``)."""
    return TR.id_hash(track, local_id)


def hdf5_trial_hash(session: str, block: int, trial: int) -> str:
    """Salted hash of one B2T '25 HDF5 trial: ``session`` like ``t15.2023.08.11``, the HDF5 attributes
    ``block_num`` and ``trial_num``."""
    return _h(f"{TR.salt('b2t25-t15')}|b2t25-hdf5|{session}|{int(block)}|{int(trial)}")


# ---------------------------------------------------------------------------
# Committed maps
# ---------------------------------------------------------------------------


def make_map_doc(rows: Sequence[dict[str, Any]], text: dict[str, list[str]], counts: dict[str, Any], *,
                 split_digest: str) -> dict[str, Any]:
    """The JSON document of the b2t25-t15 <- b2t25-hdf5 map (built by the P6-10 experiment script)."""
    return {
        "schema": MAP_SCHEMA, "track": "b2t25-t15", "source": "b2t25-hdf5", "split_digest": split_digest,
        "hash_rule": "t = sha256('fidetype/tracks/0.2/b2t25-t15|b2t25-hdf5|<session>|<block_num>|<trial_num>')[:16]; "
                     "u = the b2t25-t15 unit hash h of the split file",
        "partitions": {"train": "HDF5 data_train.hdf5", "val": "HDF5 data_val.hdf5",
                       "test": "HDF5 data_test.hdf5 (no sentence labels)",
                       "val_select": "Fidetype M4 split: val trials with an even index in sorted key order per session",
                       "val_eval": "Fidetype M4 split: val trials with an odd index in sorted key order per session"},
        "match_rule": "experiments/2026-11-17-t15-split-audit/match.py: session date, normalised sentence, frame "
                      "count; 'strict' = one candidate, 'possible' = one of several candidates",
        "fields": {"trials": "t: HDF5 trial hash, p: HDF5 file partition, sub: p or the M4 val half, u: test unit, "
                             "q: strict | possible",
                   "text": "u -> partitions that hold the same normalised sentence (any day)"},
        "counts": counts, "trials": list(rows), "text": dict(sorted(text.items())),
    }


@lru_cache(maxsize=None)
def _load_map_file(path: str) -> dict[str, Any]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") != MAP_SCHEMA:
        raise ValueError(f"{path}: schema must be {MAP_SCHEMA!r}")
    return d


def load_map(track: str, source: str) -> dict[str, Any] | None:
    name = MAPS.get((track, source))
    if name is None or not (MAPS_DIR / name).is_file():
        return None
    return _load_map_file(str(MAPS_DIR / name))


def map_partitions(track: str, source: str) -> set[str]:
    m = load_map(track, source)
    return set(m["partitions"]) if m else set()


def leave_out(track: str = "b2t25-t15", source: str = "b2t25-hdf5", *, possible: bool = True) -> set[str]:
    """Hashes of the source trials that match a scored test unit (strict, and possible if asked)."""
    m = load_map(track, source)
    if m is None:
        return set()
    return {r["t"] for r in m["trials"] if r["q"] == "strict" or possible}


# ---------------------------------------------------------------------------
# Declaration
# ---------------------------------------------------------------------------


def _hash_lists(d: Any, where: str) -> dict[str, list[str]]:
    if d is None:
        return {}
    if not isinstance(d, dict) or any(k not in USES for k in d):
        raise SubmissionError(f"{where} must be a dict with keys from {USES}")
    out = {}
    for use, xs in d.items():
        if not isinstance(xs, list) or not all(_is_hex16(x.split("#", 1)[0]) if isinstance(x, str) else False
                                               for x in xs):
            raise SubmissionError(f"{where}.{use} must be a list of 16-hex hashes")
        out[use] = list(xs)
    return out


def parse_declaration(raw: Any, folder: str | PathLike[str] | None = None) -> dict[str, Any] | None:
    """Validate ``training_data``. Returns None (missing), {"none": True} or a normalised dict."""
    if raw is None:
        return None
    if isinstance(raw, str):
        if raw.strip().lower() != "none":
            raise SubmissionError("submission.json: training_data is 'none' or a dict (see docs/benchmark-submission.md)")
        return {"none": True}
    if not isinstance(raw, dict):
        raise SubmissionError("submission.json: training_data is 'none' or a dict")
    bad = [k for k in raw if k not in DECL_KEYS]
    if bad:
        raise SubmissionError(f"training_data: unknown keys {bad} (allowed: {sorted(DECL_KEYS)})")
    srcs = raw.get("sources", [])
    if not isinstance(srcs, list):
        raise SubmissionError("training_data.sources must be a list")
    sources = []
    for i, s in enumerate(srcs):
        w = f"training_data.sources[{i}]"
        if not isinstance(s, dict) or not isinstance(s.get("dataset"), str) or not s["dataset"].strip():
            raise SubmissionError(f"{w}: 'dataset' is required")
        if any(k not in SOURCE_KEYS for k in s):
            raise SubmissionError(f"{w}: keys must be from {sorted(SOURCE_KEYS)}")
        if s.get("use") not in USES:
            raise SubmissionError(f"{w}: 'use' must be one of {USES}")
        parts = s.get("partitions")
        if parts is not None and (not isinstance(parts, list) or not all(isinstance(p, str) for p in parts)):
            raise SubmissionError(f"{w}: 'partitions' must be a list of names")
        ex = s.get("exclude")
        if ex is not None and ex != EXCLUDE_ALL and not (isinstance(ex, list) and all(_is_hex16(x) for x in ex)):
            raise SubmissionError(f"{w}: 'exclude' is {EXCLUDE_ALL!r} or a list of 16-hex trial hashes")
        sources.append(dict(s))
    ids = _hash_lists(raw.get("unit_ids"), "training_data.unit_ids")
    txt = _hash_lists(raw.get("text_hashes"), "training_data.text_hashes")
    if raw.get("file") and folder is not None:  # without a folder (manifest-only check) the file is read later
        p = Path(folder) / str(raw["file"])
        if not p.is_file() or Path(folder).resolve() not in p.resolve().parents:
            raise SubmissionError(f"training_data.file {raw['file']!r} is not a file in the submission folder")
        extra = json.loads(p.read_text(encoding="utf-8"))
        for key, into in (("unit_ids", ids), ("text_hashes", txt)):
            for use, xs in _hash_lists(extra.get(key), f"{raw['file']}:{key}").items():
                into.setdefault(use, []).extend(xs)
    if not sources and not ids and not txt and not raw.get("file"):
        raise SubmissionError("training_data: give sources, unit_ids or text_hashes (or the string 'none')")
    return {"none": False, "sources": sources, "unit_ids": ids, "text_hashes": txt, "note": raw.get("note", "")}


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def _parent(key: str) -> str:
    return key.split("#", 1)[0]


def check_overlap(track: str, decl: dict[str, Any] | None, scored_keys: Iterable[str],
                  unit_text: dict[str, str] | None = None, *, split: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compare a declaration with the scored unit keys. ``unit_text``: {unit key: text hash} (from the truth);
    None means the text check is not possible (no truth). Returns the ``overlap_check`` block."""
    keys = list(scored_keys)
    parents = {_parent(k) for k in keys}
    out: dict[str, Any] = {"version": OVERLAP_VERSION, "rule": RULE, "n_scored_units": len(keys)}
    if decl is None:
        return {**out, "status": "not checked", "passed": None, "declared": "missing", "n_overlapping_units": None,
                "findings": [], "unchecked": [], "text_checked": False,
                "message": "No training_data declaration: the overlap of training and test data is not checked."}
    if decl.get("none"):
        return {**out, "status": "pass", "passed": True, "declared": "none", "n_overlapping_units": 0,
                "findings": [], "unchecked": [], "text_checked": unit_text is not None,
                "message": "Declared: no data of this dataset was used for training, tuning or calibration."}
    split = split or TR.load_split(track)
    tdef = TR.get_track(track)
    by_split: dict[str, set[str]] = {}
    for e in split["entries"]:
        by_split.setdefault(e["s"], set()).add(e["h"])
    findings: list[dict[str, Any]] = []
    unchecked: list[str] = []
    hit: set[str] = set()  # overlapping unit keys

    def add(use: str, source: str, partition: str | None, kind: str, units: set[str]) -> None:
        ks = sorted(k for k in keys if k in units or _parent(k) in units)
        findings.append({"use": use, "source": source, "partition": partition, "kind": kind, "n_units": len(ks),
                         "_keys": set(ks)})
        hit.update(ks)

    for s in decl["sources"]:
        ds, use, parts = s["dataset"], s["use"], s.get("partitions")
        if ds in (track, tdef.dataset):
            if not parts:
                unchecked.append(f"{ds} ({use}): no partitions named")
                continue
            for p in parts:
                if p not in by_split:
                    unchecked.append(f"{ds}:{p} ({use}): not a split of {track} "
                                     f"(splits: {sorted(by_split)}; other files of the dataset need their own name)")
                    continue
                add(use, track, p, "id", by_split[p] & parents)
        elif (m := load_map(track, ds)) is not None:
            if not parts:
                unchecked.append(f"{ds} ({use}): no partitions named")
                continue
            ex = s.get("exclude")
            drop = {r["t"] for r in m["trials"]} if ex == EXCLUDE_ALL else set(ex or [])
            for p in parts:
                if p not in m["partitions"]:
                    unchecked.append(f"{ds}:{p} ({use}): not a partition of the map (partitions: {sorted(m['partitions'])})")
                    continue
                rows = [r for r in m["trials"] if p in (r["p"], r["sub"]) and r["t"] not in drop]
                add(use, ds, p, "id", {r["u"] for r in rows if r["q"] == "strict"})
                add(use, ds, p, "possible id", {r["u"] for r in rows if r["q"] == "possible"})
                add(use, ds, p, "text", {u for u, ps in m["text"].items() if p in ps})
        else:
            unchecked.append(f"external: {ds} ({use}); not data of {track}, so no id check"
                             + ("" if decl["text_hashes"].get(use) else "; give text_hashes to check its sentences"))
    for use, xs in decl["unit_ids"].items():
        add(use, "unit_ids", None, "id", {x for x in xs})
    text_checked = unit_text is not None
    for use, xs in decl["text_hashes"].items():
        if unit_text is None:
            unchecked.append(f"text_hashes ({use}): no truth, text not compared")
            continue
        want = set(xs)
        add(use, "text_hashes", None, "text", {k for k, th in unit_text.items() if th in want})
    own = [u for u in unchecked if not u.startswith("external:") and not u.startswith("text_hashes")]
    if hit:
        status, passed = "overlap", False
    elif own:
        status, passed = "not checked", None
    else:
        status, passed = "pass", True
    by_kind: dict[str, set[str]] = {}
    by_use: dict[str, set[str]] = {}
    for f in findings:
        ks = f.pop("_keys")
        by_kind.setdefault(f["kind"], set()).update(ks)
        by_use.setdefault(f["use"], set()).update(ks)
    kinds = sorted(k for k, v in by_kind.items() if v)
    msg = {"overlap": f"{len(hit)} of {len(keys)} scored units are in the declared training data ({', '.join(kinds)}).",
           "not checked": "Part of the declared training data does not resolve to this track; see 'unchecked'.",
           "pass": "No scored unit is in the declared training data."}[status]
    return {**out, "status": status, "passed": passed, "declared": "listed", "n_overlapping_units": len(hit),
            "by_kind": {k: len(v) for k, v in sorted(by_kind.items())},
            "by_use": {u: len(v) for u, v in sorted(by_use.items())},
            "findings": findings, "unchecked": unchecked, "text_checked": text_checked,
            "message": msg}


def overlap_text(block: dict[str, Any] | None) -> str:
    """One line for the score card text and the board."""
    if not block:
        return "overlap: not checked (scored before P6-10)"
    s = block["status"]
    if s == "overlap":
        worst = [f for f in block["findings"] if f["n_units"]]
        where = "; ".join(f"{f['use']} {f['source']}" + (f":{f['partition']}" if f["partition"] else "")
                          + f" {f['kind']} {f['n_units']}" for f in worst)
        return f"overlap: FAIL, {block['n_overlapping_units']}/{block['n_scored_units']} units ({where})"
    if s == "pass":
        return "overlap: pass" + ("" if block.get("text_checked") else " (ids only, text not compared)")
    why = ("no training_data declaration" if block.get("declared") == "missing"
           else "part of the declared data does not resolve")
    return f"overlap: not checked ({why})"


__all__ = ["OVERLAP_VERSION", "MAP_SCHEMA", "USES", "MAPS", "EXCLUDE_ALL", "text_hash", "unit_hash",
           "hdf5_trial_hash", "make_map_doc", "load_map", "map_partitions", "leave_out", "parse_declaration",
           "check_overlap", "overlap_text"]
