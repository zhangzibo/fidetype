"""Text n-best adapter: the text output of any decoder -> NeuralTextStream hypotheses.

Many public decoders give only text: a final sentence per trial, or an
n-best list with scores (a Kaggle-style ``id,text`` submission file, the
``decoded_sentence`` field of the Brain-to-Text '25 copy-task file, the
output of an LM rescoring step). They have no frame matrix, so the frame
adapters cannot carry them. This module writes them as a
**hypothesis-only** stream (spec ``nts-1.0-rc2`` 4.7 and HDR-12):

- one header with ``vocab = []``, ``blank_id = null`` and the decoder
  ``meta`` (no text in it);
- per utterance, one ``hypothesis`` event (``nbest`` best first,
  ``is_final``, ``score_semantics``), then one ``segment_end``
  (``unit = "utterance"``);
- one ``end`` event.

The events go through :class:`fidetype.StreamWriter` (``vocab = []``), so
the writer checks them; with an empty vocab it refuses every frame
(HDR-12).

Inputs (:func:`read_nbest`):

- **CSV** with a header row. Default columns ``id`` and ``text``; an
  optional score column. Rows with the same id form one n-best list in
  row order (best first).
- **JSON Lines**, one utterance per line: ``{"id", "nbest": [{"text",
  "score", ...}]}`` or ``{"id", "text", "score"}``.
- In Python: :func:`utterances_from_texts` for a plain list of strings.

Scores: a missing score is written as 0.0 with ``score_semantics =
"none"`` (EVD-3 asks for a finite number). Give
``score_semantics="uncalibrated_prob"`` only if the scores are
probabilities (DEC-2 range check). Optional FEP-0001 evidence keys
(``char_confidences``, ``logp_acoustic``, ``logp_lm``) pass through and
are checked.

Licence: our own code, Apache-2.0. See ``wiki/concepts/text-nbest-adapter.md``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.writer import MODALITIES, SCORE_SEMANTICS, StreamWriter, stream_meta

__all__ = [
    "ADAPTER_NAME",
    "Utterance",
    "TextDecoderInfo",
    "normalise_item",
    "utterances_from_texts",
    "read_csv",
    "read_jsonl",
    "read_nbest",
    "stream_events",
    "write_events",
    "write_stream",
    "check_stream_file",
    "main",
]

#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = {
    "id": "text-nbest", "kind": "decoder-output", "signal": "any", "status": "tested",
    "target": "Any text-only decoder: CSV id,text or JSON Lines n-best lists -> hypothesis stream",
    "licence": "Code Apache-2.0. No dependency beyond the standard library and NumPy.",
    "tests": ["tests/test_adapter_text_nbest.py"], "docs": "wiki/concepts/text-nbest-adapter.md",
    "support": "replay-only", "transport": ["file", "in-process"],
    "real_data_evidence": ["experiments/2026-11-21-p5-33-withhold/results.md"],
    "test_covers": "CI: synthetic CSV and JSON Lines n-best files. Real: the item check "
                   "(normalise_item) on the KT-sEMG LDA n-best lists through the trust drop-in "
                   "(P5-33, local).",
    "limits": "The CSV and JSON Lines file readers ran on synthetic files only.",
}

ADAPTER_NAME = "fidetype.adapters.text_nbest"
_EVIDENCE_KEYS = ("char_confidences", "logp_acoustic", "logp_lm")


def _finite(x: Any, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        try:
            import numpy as np

            if isinstance(x, (np.integer, np.floating)):
                x = float(x)
            else:
                raise TypeError
        except TypeError:
            raise ValueError(f"{name} must be a number") from None
    v = float(x)
    if not math.isfinite(v):
        raise ValueError(f"{name} must be finite")
    return v


def normalise_item(item: str | tuple[str, Any] | Mapping[str, Any]) -> dict[str, Any]:
    """Return one n-best item as a dict with ``text`` and a finite ``score``.

    A string gets score 0.0. A ``(text, score)`` pair keeps its score. A
    dict keeps ``text``, ``score`` (default 0.0), ``spans`` and the
    FEP-0001 evidence keys; they are checked (EVD-1, EVD-4).
    """
    if isinstance(item, str):
        return {"text": item, "score": 0.0}
    if isinstance(item, tuple):
        if len(item) != 2 or not isinstance(item[0], str):
            raise ValueError("a tuple item must be (text, score)")
        return {"text": item[0], "score": 0.0 if item[1] is None else _finite(item[1], "score")}
    if not isinstance(item, Mapping) or not isinstance(item.get("text"), str):
        raise ValueError("each n-best item needs a string 'text'")
    d: dict[str, Any] = {"text": item["text"]}
    sc = item.get("score")
    d["score"] = 0.0 if sc is None else _finite(sc, "score")
    cc = item.get("char_confidences")
    if cc is not None:
        vals = [_finite(c, "char_confidences") for c in cc]
        if len(vals) != len(d["text"]) or any(not 0.0 <= c <= 1.0 for c in vals):
            raise ValueError("char_confidences needs one value in [0, 1] per character (EVD-1)")
        d["char_confidences"] = vals
    for k in ("logp_acoustic", "logp_lm"):
        if item.get(k) is not None:
            v = _finite(item[k], k)
            if v > 0:
                raise ValueError(f"{k} must be <= 0 (EVD-4)")
            d[k] = v
    if item.get("spans") is not None:
        d["spans"] = list(item["spans"])
    return d


@dataclass
class Utterance:
    """One decoded utterance: an n-best list (best first) and optional times."""

    nbest: list[dict[str, Any]]
    id: str | None = None
    t_start: float | None = None
    t_end: float | None = None
    is_final: bool = True

    def __post_init__(self) -> None:
        self.nbest = [normalise_item(it) for it in self.nbest]
        if not self.nbest:
            raise ValueError("an utterance needs at least one n-best item")
        if self.id is not None and (not isinstance(self.id, str) or not self.id):
            raise ValueError("an utterance id must be a non-empty string")
        for name in ("t_start", "t_end"):
            v = getattr(self, name)
            if v is not None:
                setattr(self, name, _finite(v, name))
        if self.t_start is not None and self.t_end is not None and self.t_end < self.t_start:
            raise ValueError("t_end must not be before t_start")


def utterances_from_texts(texts: Iterable[str], ids: Sequence[str] | None = None) -> list[Utterance]:
    """One utterance per string (a 1-best list, score 0.0)."""
    texts = list(texts)
    if ids is not None and len(ids) != len(texts):
        raise ValueError("ids and texts must have the same length")
    return [Utterance([t], id=None if ids is None else str(ids[i])) for i, t in enumerate(texts)]


def read_csv(
    path: str | PathLike[str],
    *,
    id_col: str = "id",
    text_col: str = "text",
    score_col: str | None = None,
) -> list[Utterance]:
    """Read a CSV file with a header row. Rows with the same id form one n-best list.

    The order of utterances is the order of first appearance. A text cell
    may be empty (the decoder gave no output); it is kept as ``""``.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        for c in (id_col, text_col) + ((score_col,) if score_col else ()):
            if c not in cols:
                raise ValueError(f"CSV has no column {c!r} (columns: {cols})")
        for row in reader:
            item: dict[str, Any] = {"text": row[text_col] or ""}
            if score_col:
                cell = (row[score_col] or "").strip()
                item["score"] = float(cell) if cell else None
            groups.setdefault(str(row[id_col]), []).append(item)
    return [Utterance(items, id=k) for k, items in groups.items()]


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON (spec GEN-2)")


def read_jsonl(path: str | PathLike[str]) -> list[Utterance]:
    """Read JSON Lines: ``{"id", "nbest": [...]}`` or ``{"id", "text", "score"}`` per line."""
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            obj = json.loads(line, parse_constant=_reject_constant)
            if not isinstance(obj, dict):
                raise ValueError(f"line {n}: each line must be a JSON object")
            if "nbest" in obj:
                items = obj["nbest"]
            elif "text" in obj:
                items = [{k: obj[k] for k in ("text", "score", *_EVIDENCE_KEYS) if k in obj}]
            else:
                raise ValueError(f"line {n}: needs 'nbest' or 'text'")
            uid = obj.get("id")
            out.append(Utterance(list(items), id=None if uid is None else str(uid),
                                 t_start=obj.get("t_start"), t_end=obj.get("t_end"),
                                 is_final=bool(obj.get("is_final", True))))
    return out


def read_nbest(path: str | PathLike[str], **csv_kwargs: Any) -> list[Utterance]:
    """Read ``.csv`` with :func:`read_csv`, else JSON Lines with :func:`read_jsonl`."""
    suf = Path(path).suffix.lower()
    if suf == ".csv":
        return read_csv(path, **csv_kwargs)
    return read_jsonl(path)


@dataclass
class TextDecoderInfo:
    """What the stream says about the text decoder (``meta`` keys of spec 3.4)."""

    modality: str
    name: str
    version: str
    causal: bool = True
    language: str = "en"
    lm_name: str = "none"
    weights_sha256: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.modality not in MODALITIES:
            raise ValueError(f"modality must be one of {MODALITIES}")


def _stream_id(decoder: TextDecoderInfo, utterances: Sequence[Utterance]) -> str:
    """An opaque ``stream.id``: 32 hex characters of a SHA-256 over the content."""
    h = hashlib.sha256(f"text_nbest\x1f{decoder.name}\x1f{decoder.version}".encode("utf-8"))
    for u in utterances:
        h.update(json.dumps(u.nbest, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return h.hexdigest()[:32]


def _render(
    utterances: Sequence[Utterance],
    decoder: TextDecoderInfo,
    *,
    score_semantics: str = "none",
    decode_declaration: Mapping[str, Any] | None = None,
    source: str | None = None,
    stream_id: str | None = "auto",
    latency: float | None = None,
) -> str:
    """Write one hypothesis-only stream with :class:`StreamWriter` into a string (JSON Lines)."""
    if score_semantics not in SCORE_SEMANTICS:
        raise ValueError(f"score_semantics must be one of {SCORE_SEMANTICS}")
    if score_semantics in ("power", "strength"):
        raise ValueError("hypothesis scores with 'power' or 'strength' need a score_range; not supported here")
    if not decoder.causal and latency is not None:
        raise ValueError("an offline (non-causal) decoder omits latency (spec MET-5)")
    sid = _stream_id(decoder, utterances) if stream_id == "auto" else stream_id
    meta = stream_meta(
        modality=decoder.modality, decoder_name=decoder.name, decoder_version=decoder.version,
        causal=decoder.causal, lookahead_s=latency, language=decoder.language, lm_name=decoder.lm_name,
        weights_sha256=decoder.weights_sha256, stream_id=sid, adapter_name=ADAPTER_NAME,
        adapter_version=_FIDETYPE_VERSION, extra=dict(decoder.extra),
    )
    extra: dict[str, Any] = {}
    if decode_declaration is not None:
        dd = dict(decode_declaration)
        if not isinstance(dd.get("decoder"), str) or not dd["decoder"]:
            raise ValueError("decode_declaration needs a non-empty 'decoder' (DCL-1)")
        if "frame_temperature" in dd and not (_finite(dd["frame_temperature"], "frame_temperature") > 0):
            raise ValueError("frame_temperature must be > 0")
        if "params" in dd and not isinstance(dd["params"], Mapping):
            raise ValueError("decode_declaration params must be an object")
        extra["decode_declaration"] = dd
    # Check every utterance before the first line is written.
    used: set[str] = set()
    ids: list[str] = []
    for n, u in enumerate(utterances, 1):
        hid = u.id if u.id is not None else f"h{n}"
        if hid in used:
            raise ValueError(f"hypothesis id {hid!r} is used twice (HYP-1)")
        used.add(hid)
        ids.append(hid)
        if score_semantics in ("calibrated_prob", "uncalibrated_prob"):
            for it in u.nbest:
                if not 0.0 <= it["score"] <= 1.0:
                    raise ValueError(f"utterance {hid!r}: score {it['score']} is not a probability (DEC-2)")
    buf = io.StringIO()
    w = StreamWriter(buf, vocab=[], vocab_type="char", blank_id=None, source=source or decoder.name,
                     latency=None if latency is None else _finite(latency, "latency"), meta=meta,
                     extra_header=extra, flush=False)
    for hid, u in zip(ids, utterances):
        w.hypothesis(u.nbest, is_final=bool(u.is_final), id=hid, score_semantics=score_semantics,
                     t_start=u.t_start, t_end=u.t_end)
        w.segment_end(u.t_end, unit="utterance")
    w.close()
    return buf.getvalue()


def stream_events(
    utterances: Sequence[Utterance],
    decoder: TextDecoderInfo,
    *,
    score_semantics: str = "none",
    decode_declaration: Mapping[str, Any] | None = None,
    source: str | None = None,
    stream_id: str | None = "auto",
    latency: float | None = None,
) -> list[dict[str, Any]]:
    """Return the events of one hypothesis-only stream (header first, ``end`` last).

    Each utterance gives one ``hypothesis`` and one ``segment_end``. An
    utterance without an id gets ``h<n>``. Ids must be unique (HYP-1).
    ``decode_declaration`` (spec 4.7.3) goes into the header; it must name
    a ``decoder`` and must not hold user text (DCL-7). The events are the
    lines that :class:`StreamWriter` writes.
    """
    text = _render(utterances, decoder, score_semantics=score_semantics, decode_declaration=decode_declaration,
                   source=source, stream_id=stream_id, latency=latency)
    return [json.loads(line) for line in text.splitlines()]


def write_events(events: Sequence[Mapping[str, Any]], path: str | PathLike[str]) -> Path:
    """Write events as JSON Lines (UTF-8, ``\\n``, no NaN or Infinity)."""
    p = Path(path)
    p.write_text("".join(json.dumps(dict(e), ensure_ascii=False, allow_nan=False) + "\n" for e in events),
                 encoding="utf-8", newline="\n")
    return p


def write_stream(
    utterances: Sequence[Utterance],
    decoder: TextDecoderInfo,
    path: str | PathLike[str],
    **kwargs: Any,
) -> Path:
    """Write the stream with :class:`StreamWriter` (all checks run before the file is written)."""
    p = Path(path)
    p.write_text(_render(utterances, decoder, **kwargs), encoding="utf-8", newline="\n")
    return p


def check_stream_file(path: str | PathLike[str], level: str = "core") -> list[str]:
    """Run the conformance suite on a written stream. Return the failures (empty = pass).

    Two checks: the v0.1 suite at ``level`` (header, meta, hypothesis
    events) and the ``fep-0001`` profile (segments, evidence, scores,
    declarations).
    """
    from fidetype.conformance import check_file
    from fidetype.conformance.profiles import get_profile

    errs = [f"{r.check_id}: {r.message}" for r in check_file(path).failures(level)]
    rep = get_profile("fep-0001").check_file(path)
    errs += [f"{r.check_id}: {r.message}" for r in rep.failures("core")]
    return errs


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m fidetype.adapters.text_nbest",
                                description="Convert decoder text output (.csv / .jsonl) to a NeuralTextStream "
                                            "hypothesis-only stream.")
    p.add_argument("input", help=".csv (header row; id and text columns) or .jsonl (one utterance per line)")
    p.add_argument("--id-col", default="id")
    p.add_argument("--text-col", default="text")
    p.add_argument("--score-col", default=None)
    p.add_argument("--score-semantics", default="none", choices=("none", "uncalibrated_prob", "calibrated_prob"))
    p.add_argument("--modality", required=True, choices=MODALITIES)
    p.add_argument("--decoder-name", required=True)
    p.add_argument("--decoder-version", required=True)
    p.add_argument("--lm-name", default="none")
    p.add_argument("--language", default="en")
    p.add_argument("--non-causal", action="store_true")
    p.add_argument("--latency", type=float, default=None)
    p.add_argument("--out", required=True, help="output .jsonl")
    p.add_argument("--level", default="core", choices=("core", "trust-ready", "provenance"))
    a = p.parse_args(argv)
    utts = read_nbest(a.input, id_col=a.id_col, text_col=a.text_col, score_col=a.score_col) \
        if Path(a.input).suffix.lower() == ".csv" else read_nbest(a.input)
    dec = TextDecoderInfo(modality=a.modality, name=a.decoder_name, version=a.decoder_version,
                          causal=not a.non_causal, language=a.language, lm_name=a.lm_name)
    out = write_stream(utts, dec, a.out, score_semantics=a.score_semantics, latency=a.latency)
    errs = check_stream_file(out, a.level)
    for e in errs:
        print(f"FAIL {out}: {e}", file=sys.stderr)
    print(f"{len(utts)} utterance(s) written to {out}; level {a.level}: {'FAIL' if errs else 'OK'}")
    return 1 if errs else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
