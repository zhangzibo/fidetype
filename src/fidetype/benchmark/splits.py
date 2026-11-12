"""Fixed split files of the benchmark tracks.

A split file is committed JSON. It holds **no data and no text**: only
trial ids, cluster labels (participant, sentence group, day) and the
SHA-256 of each normalised truth text. A user rebuilds the truth from the
downloaded data (:mod:`fidetype.benchmark.prepare`) and checks it against
the file with :func:`verify`.

Schema ``fidetype.benchmark.split/0.1``::

    {
      "schema": "fidetype.benchmark.split/0.1",
      "track": "...", "benchmark_version": "0.1", "dataset": "...",
      "rule": "how the split was made",
      "counts": {"train": n, "val": n, "test": n},
      "scored": [{"id", "split", "text_sha256", "clusters", ["detail_sha256"]}, ...],
      "open": {"<split>": {"n": n, "ids_sha256": "...", "ids": [...]}}
    }

``scored`` lists the scored split and the calibration split with hashes.
``open`` lists the training splits by id only (or by rule, when a track
trains on recordings rather than trials).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from importlib import resources
from os import PathLike
from pathlib import Path
from typing import Any, Iterable

from fidetype.benchmark.prepare import TruthTrial, detail_hash, text_hash
from fidetype.benchmark.registry import BENCHMARK_VERSION, TRACKS, get_track

SPLIT_SCHEMA = "fidetype.benchmark.split/0.1"


def ids_digest(ids: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


@dataclass
class SplitFile:
    track: str
    rule: str
    scored: list[dict[str, Any]]
    open: dict[str, dict[str, Any]] = field(default_factory=dict)
    dataset: str = ""
    benchmark_version: str = BENCHMARK_VERSION
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def counts(self) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in self.scored:
            c[r["split"]] = c.get(r["split"], 0) + 1
        for k, v in self.open.items():
            if "n" in v:
                c[k] = int(v["n"])
        return c

    def trials(self, split: str) -> list[dict[str, Any]]:
        return [r for r in self.scored if r["split"] == split]

    def ids(self, split: str) -> list[str]:
        return [r["id"] for r in self.trials(split)]

    def clusters(self, split: str) -> dict[str, dict[str, str]]:
        return {r["id"]: r["clusters"] for r in self.trials(split)}

    def to_dict(self) -> dict[str, Any]:
        return {"schema": SPLIT_SCHEMA, "track": self.track, "benchmark_version": self.benchmark_version,
                "dataset": self.dataset, "rule": self.rule, "counts": self.counts, **self.extra,
                "scored": self.scored, "open": self.open}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SplitFile":
        if d.get("schema") != SPLIT_SCHEMA:
            raise ValueError(f"not a split file (schema {d.get('schema')!r})")
        known = {"schema", "track", "benchmark_version", "dataset", "rule", "counts", "scored", "open"}
        return cls(track=d["track"], rule=d["rule"], scored=list(d["scored"]), open=dict(d.get("open", {})),
                   dataset=d.get("dataset", ""), benchmark_version=d.get("benchmark_version", BENCHMARK_VERSION),
                   extra={k: v for k, v in d.items() if k not in known})

    def save(self, path: str | PathLike[str]) -> None:
        """Write the file with one trial per line (small and diff-friendly)."""
        d = self.to_dict()
        rows, open_ = d.pop("scored"), d.pop("open")
        head = json.dumps(d, indent=1, ensure_ascii=False)
        lines = [head[: head.rstrip().rfind("}")].rstrip() + ",", ' "scored": [']
        lines += ["  " + json.dumps(r, ensure_ascii=False, separators=(",", ":")) + ("," if i < len(rows) - 1 else "")
                  for i, r in enumerate(rows)]
        lines += [" ],", ' "open": ' + json.dumps(open_, ensure_ascii=False, separators=(",", ":")), "}"]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_split(track: str, trials: list[TruthTrial], scored_splits: tuple[str, ...], rule: str,
               open_rules: dict[str, str] | None = None, extra: dict[str, Any] | None = None) -> SplitFile:
    """Build a split file from rebuilt trials (maintainers only; needs the data)."""
    t = get_track(track)
    scored = []
    for tr in trials:
        if tr.split not in scored_splits:
            continue
        row = {"id": tr.id, "split": tr.split, "text_sha256": text_hash(tr.text), "clusters": tr.clusters}
        if tr.detail is not None:
            row["detail_sha256"] = detail_hash(tr.detail)
        scored.append(row)
    ids = [r["id"] for r in scored]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate trial ids")
    open_: dict[str, dict[str, Any]] = {}
    for split in sorted({tr.split for tr in trials} - set(scored_splits)):
        sids = sorted(tr.id for tr in trials if tr.split == split)
        open_[split] = {"n": len(sids), "ids_sha256": ids_digest(sids), "ids": sids}
    for name, text in (open_rules or {}).items():
        open_[name] = {"rule": text}
    return SplitFile(track=track, rule=rule, scored=scored, open=open_, dataset=t.dataset, extra=dict(extra or {}))


def split_path(track: str) -> Path:
    t = get_track(track)
    return Path(str(resources.files("fidetype.benchmark").joinpath("splits", f"v{BENCHMARK_VERSION}", t.split_file)))


def load_split(track: str) -> SplitFile:
    """Load the committed split file of a track."""
    return SplitFile.from_dict(json.loads(split_path(track).read_text(encoding="utf-8")))


@dataclass
class VerifyReport:
    track: str
    n_expected: int
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    text_mismatch: list[str] = field(default_factory=list)
    detail_mismatch: list[str] = field(default_factory=list)
    split_mismatch: list[str] = field(default_factory=list)
    open_mismatch: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.text_mismatch or self.detail_mismatch or self.split_mismatch
                    or self.open_mismatch)

    def summary(self) -> str:
        if self.ok:
            return f"{self.track}: OK ({self.n_expected} scored trials match the split file)"
        parts = [f"{k} {len(v)} (e.g. {v[:3]})" for k, v in (
            ("missing", self.missing), ("text hash mismatch", self.text_mismatch),
            ("detail mismatch", self.detail_mismatch), ("split mismatch", self.split_mismatch),
            ("open-split mismatch", self.open_mismatch)) if v]
        return f"{self.track}: MISMATCH: " + "; ".join(parts)


def verify(split: SplitFile, trials: list[TruthTrial]) -> VerifyReport:
    """Check rebuilt trials against a split file. Extra local trials are allowed."""
    by_id = {t.id: t for t in trials}
    rep = VerifyReport(split.track, len(split.scored))
    for r in split.scored:
        t = by_id.get(r["id"])
        if t is None:
            rep.missing.append(r["id"])
            continue
        if t.split != r["split"]:
            rep.split_mismatch.append(r["id"])
        if text_hash(t.text) != r["text_sha256"]:
            rep.text_mismatch.append(r["id"])
        if "detail_sha256" in r and (t.detail is None or detail_hash(t.detail) != r["detail_sha256"]):
            rep.detail_mismatch.append(r["id"])
    known = {r["id"] for r in split.scored}
    rep.extra = sorted(i for i in by_id if i not in known and by_id[i].split in {r["split"] for r in split.scored})
    for name, o in split.open.items():
        if "ids_sha256" in o:
            local = [t.id for t in trials if t.split == name]
            if ids_digest(local) != o["ids_sha256"]:
                rep.open_mismatch.append(name)
    return rep


def available_tracks() -> list[str]:
    return sorted(TRACKS)
