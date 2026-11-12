"""Provenance ledger v0 (M2-09): an append-only, hash-chained audit trail.

For each decision of the trust layer, the ledger records where the text
came from: the device and adapter, the decoder (id, version, weights
hash), the calibration (temperatures, conformal and risk-control
thresholds, alpha, delta, calibration set id), the LM, the policy
version, the input stream segment (frame range), the action and its
scores. A later user correction links to the decision that it corrects.
So a wrong commit can be traced back to the exact models and settings
that produced it.

File format
-----------
JSON Lines, UTF-8, one entry per line. Every entry has these keys::

    {"schema": "fidetype.provenance/0.1", "seq": 3, "ts": "2026-11-11T20:30:00.123456Z",
     "kind": "decision", "prev_hash": "<64 hex>", "body": {...}, "hash": "<64 hex>"}

- ``seq`` starts at 0 and increases by 1.
- ``prev_hash`` is the ``hash`` of the previous entry (:data:`GENESIS_PREV`
  for entry 0).
- ``hash`` = SHA-256 (hex) of the canonical JSON (:func:`canonical_json`)
  of the entry without ``hash``. Because the entry holds ``prev_hash``,
  each hash covers the full history before it.

Entry kinds (``kind``)
----------------------
``genesis``
    Always entry 0: ledger id, schema, text mode, id mode, hash algorithm.
``context``
    A provenance context: device, adapter, decoder, calibration, LM,
    policy. Its id is the SHA-256 of its canonical JSON (content
    addressed), so the same context is written once.
``decision``
    One decision of the policy: context id, input reference (stream id,
    frame range), action, reason, scores, the text shown.
``correction``
    A later correction by the user (or an oracle in a replay). It names
    the corrected decision (``decision_id`` and that entry's ``hash``).
``note``
    Free, structured operational data (for example a session start).

Privacy by design
-----------------
- The ledger never stores raw signals or frame arrays. A decision holds
  only the SHA-256 of the NeuralTextStream (a derived product) and the
  frame range. :func:`check_no_raw` rejects numeric arrays longer than
  :data:`MAX_NUMERIC_LIST` in any body.
- Text (decoded or corrected) follows ``text_mode``: ``"store"`` (plain
  text), ``"hash"`` (keyed hash plus lengths, the default) or ``"omit"``.
  With a secret ``hash_key`` the hash is HMAC-SHA256, so short sentences
  cannot be found by a dictionary attack; keep the key outside the
  ledger. Without a key it is plain SHA-256 (``text_hash_alg`` says so).
- Subject and session ids follow ``id_mode`` (same three values, default
  ``"hash"``).

Limits
------
The chain detects an edit, a deletion inside the file and a reorder. It
cannot detect a cut of the last entries by itself. For that, store the
head (:meth:`ProvenanceLedger.anchor`) in a second place and pass it to
:func:`verify` as ``expected_head``. The ledger is tamper-evident, not
tamper-proof: a person who can rewrite the whole file can recompute the
chain. A signed or external anchor closes that gap.

Command line::

    python -m fidetype.trust.provenance verify ledger.jsonl [--head <hash>]
    python -m fidetype.trust.provenance report ledger.jsonl [--max-items 20]
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import os
import sys
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Literal, Sequence

import numpy as np

SCHEMA = "fidetype.provenance/0.1"
SCHEMA_VERSION = "0.1"
GENESIS_PREV = "0" * 64
KINDS = ("genesis", "context", "decision", "correction", "note")
TEXT_MODES = ("store", "hash", "omit")
#: A body must not hold a numeric list longer than this (no raw arrays).
MAX_NUMERIC_LIST = 64
#: Stream ``meta`` keys copied into a context (spec section 4.2 namespaces).
META_PREFIXES = ("device.", "decoder.", "lm.", "calibration.", "adapter.", "fidetype.vocab_id")
META_KEYS = ("data.derived", "consent.ref", "language", "user.personalized")
ID_KEYS = ("subject.id", "session.id")

TextMode = Literal["store", "hash", "omit"]


# ---------------------------------------------------------------------------
# Canonical JSON and hashing
# ---------------------------------------------------------------------------


def _plain(o: Any) -> Any:
    """Convert ``o`` to plain JSON types. Non-finite floats become strings."""
    if isinstance(o, Enum):
        return _plain(o.value)
    if is_dataclass(o) and not isinstance(o, type):
        return _plain(asdict(o))
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        o = o.item()
    if isinstance(o, bool) or o is None or isinstance(o, (int, str)):
        return o
    if isinstance(o, float):
        if math.isfinite(o):
            return o
        return "nan" if math.isnan(o) else ("inf" if o > 0 else "-inf")
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    if isinstance(o, np.ndarray):
        return _plain(o.tolist())
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"value of type {type(o).__name__} is not JSON-serialisable")


def canonical_json(obj: Any) -> str:
    """Canonical JSON: sorted keys, no spaces, UTF-8 text, no NaN/inf."""
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def entry_hash(entry: dict) -> str:
    """SHA-256 of the canonical JSON of ``entry`` without its ``hash`` key."""
    return sha256_hex(canonical_json({k: v for k, v in entry.items() if k != "hash"}))


def content_id(obj: Any) -> str:
    """Content address of a JSON object: SHA-256 of its canonical JSON."""
    return sha256_hex(canonical_json(obj))


def file_sha256(path: str | os.PathLike, chunk: int = 1 << 20) -> str:
    """SHA-256 of a file (for example a weights checkpoint)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stream_fingerprint(stream: Any) -> str:
    """SHA-256 of a NeuralTextStream: header (canonical JSON) + array bytes.

    The ledger stores only this id, never the arrays. Two byte-identical
    streams give the same id.
    """
    header = {
        "spec_version": getattr(stream, "version", None),
        "vocab": list(stream.vocab),
        "vocab_type": getattr(stream, "vocab_type", None),
        "blank_id": stream.blank_id,
        "source": getattr(stream, "source", None),
        "frame_period": getattr(stream, "frame_period", None),
        "latency": getattr(stream, "latency", None),
        "meta": getattr(stream, "meta", {}),
    }
    h = hashlib.sha256()
    h.update(canonical_json(header).encode("utf-8"))
    h.update(np.ascontiguousarray(stream.log_probs, dtype=np.float32).tobytes())
    h.update(np.ascontiguousarray(stream.frame_times, dtype=np.float64).tobytes())
    return h.hexdigest()


def check_no_raw(obj: Any, path: str = "body") -> None:
    """Raise ``ValueError`` if ``obj`` holds a numeric array or a long numeric list."""
    if isinstance(obj, np.ndarray) and obj.size > MAX_NUMERIC_LIST:
        raise ValueError(f"{path}: numeric array of size {obj.size} (raw data is not allowed in the ledger)")
    if isinstance(obj, (list, tuple)):
        if len(obj) > MAX_NUMERIC_LIST and all(isinstance(v, (int, float, np.number)) for v in obj):
            raise ValueError(f"{path}: numeric list of length {len(obj)} (raw data is not allowed in the ledger)")
        for i, v in enumerate(obj):
            check_no_raw(v, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            check_no_raw(v, f"{path}.{k}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def meta_subset(meta: dict | None) -> dict:
    """The stream ``meta`` keys that describe provenance (no ids, no free text)."""
    meta = meta or {}
    return {
        k: v for k, v in meta.items()
        if k in META_KEYS or any(k == p or k.startswith(p) for p in META_PREFIXES)
    }


def policy_version(policy: Any) -> str:
    """A short version id of a policy: class name + config, content hashed."""
    cfg = getattr(policy, "config", None)
    obj = {"class": type(policy).__name__, "config": cfg, "use_guard": getattr(policy, "use_guard", None)}
    return "pol-" + content_id(obj)[:16]


def pipeline_context(
    pipe: Any,
    *,
    adapter: dict | None = None,
    decoder: dict | None = None,
    lm: dict | None = None,
    calibration_set_id: str | None = None,
    stream_meta: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """Build a provenance context from a fitted ``TrustPipeline``.

    ``adapter``, ``decoder`` and ``lm`` are free dicts (for example
    ``{"name": ..., "version": ..., "weights_sha256": ...}``).
    ``stream_meta``: the ``meta`` of a typical input stream; only
    :func:`meta_subset` keys are kept. The calibration block holds the
    fitted temperatures, the conformal thresholds, the risk-control
    result (method, alpha, delta, n, threshold, bound) and an id that is
    the content hash of these values plus ``calibration_set_id``.
    """
    from fidetype import __version__

    fr = dict(getattr(pipe, "fit_report", {}) or {})
    cfg = pipe.config
    calib = {
        "temperature_frame": fr.get("temperature_frame", getattr(pipe.frame_scaler, "temperature", 1.0)),
        "temperature_sentence": fr.get("temperature_sentence"),
        "temperature_char": fr.get("temperature_char"),
        "conformal_alpha": cfg.alpha,
        "conformal_score": cfg.conformal_score,
        "conformal_mode": cfg.conformal_mode,
        "conformal_q": fr.get("conformal_q"),
        "word_conformal_q": fr.get("word_conformal_q"),
        "max_wrong_commit": cfg.max_wrong_commit,
        "risk_control": {
            "method": fr.get("risk_control_method", "none"),
            "alpha": fr.get("risk_control_alpha"),
            "delta": fr.get("risk_control_delta") if fr.get("risk_control_method") == "ltt" else None,
            "threshold": fr.get("risk_control_threshold"),
            "feasible": fr.get("risk_control_feasible"),
            "n": fr.get("risk_control_n"),
            "bound": fr.get("risk_control_bound"),
        },
        "calibration_set_id": calibration_set_id,
    }
    calib["id"] = "cal-" + content_id(calib)[:16]
    pol = pipe.policy
    policy = {
        "class": type(pol).__name__,
        "config": getattr(pol, "config", None),
        "use_guard": getattr(pol, "use_guard", None),
        "guard_config": cfg.guard_config,
        "fit_feasible": fr.get("policy_fit_feasible"),
        "version": policy_version(pol),
    }
    ctx = {
        "software": {"package": "fidetype", "version": __version__},
        "adapter": adapter or {},
        "decoder": decoder or {},
        "lm": lm or {},
        "stream_meta": meta_subset(stream_meta),
        "calibration": calib,
        "policy": policy,
    }
    if extra:
        ctx["extra"] = extra
    return ctx


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------


@dataclass
class VerifyResult:
    ok: bool
    n_entries: int
    errors: list[str] = field(default_factory=list)
    head_hash: str | None = None
    head_seq: int | None = None

    def __bool__(self) -> bool:
        return self.ok


class ProvenanceLedger:
    """Append-only, hash-chained provenance ledger.

    ``path=None`` keeps the ledger in memory only (``entries``). With a
    path, each entry is appended to the file at once (one JSON line,
    flushed; ``fsync=True`` also forces it to disk). An existing file is
    verified and continued; its genesis settings win.
    """

    def __init__(
        self,
        path: str | os.PathLike | None = None,
        *,
        text_mode: TextMode = "hash",
        id_mode: TextMode = "hash",
        hash_key: bytes | None = None,
        key_id: str | None = None,
        ledger_id: str | None = None,
        clock: Callable[[], str] | None = None,
        fsync: bool = False,
    ) -> None:
        if text_mode not in TEXT_MODES or id_mode not in TEXT_MODES:
            raise ValueError(f"text_mode and id_mode must be one of {TEXT_MODES}")
        self.path = None if path is None else Path(path)
        self.hash_key = hash_key
        self.clock = clock or _utc_now
        self.fsync = fsync
        self.entries: list[dict] = []
        self._contexts: set[str] = set()
        self._decisions: dict[str, dict] = {}
        #: In memory only (never written): the first shown text of each
        #: decision of this session, so a correction can compute its
        #: edit distance in every text mode.
        self._shown_text: dict[str, str] = {}
        if self.path is not None and self.path.exists() and self.path.stat().st_size > 0:
            entries = read_entries(self.path)
            res = verify(entries)
            if not res.ok:
                raise ValueError(f"cannot continue a ledger that fails verification: {res.errors[:3]}")
            self.entries = entries
            g = entries[0]["body"]
            self.text_mode, self.id_mode = g["text_mode"], g["id_mode"]
            self.ledger_id = g["ledger_id"]
            if g.get("text_hash_alg") == "hmac-sha256" and hash_key is None:
                raise ValueError("this ledger uses keyed text hashes: pass hash_key")
            for e in entries:
                self._index(e)
        else:
            self.text_mode, self.id_mode = text_mode, id_mode
            self.ledger_id = ledger_id or str(uuid.uuid4())
            self.append("genesis", {
                "ledger_id": self.ledger_id,
                "schema": SCHEMA,
                "text_mode": text_mode,
                "id_mode": id_mode,
                "text_hash_alg": "hmac-sha256" if hash_key is not None else "sha256",
                "key_id": key_id,
            })

    # --- low level --------------------------------------------------------

    @property
    def head(self) -> dict:
        return self.entries[-1]

    def anchor(self) -> dict:
        """The head of the chain, to store in a second place (detects truncation)."""
        return {"ledger_id": self.ledger_id, "seq": self.head["seq"], "hash": self.head["hash"]}

    def append(self, kind: str, body: dict) -> dict:
        if kind not in KINDS:
            raise ValueError(f"unknown entry kind {kind!r}")
        check_no_raw(body)
        body = _plain(body)
        prev = self.entries[-1] if self.entries else None
        if prev is None and kind != "genesis":
            raise ValueError("the first entry must be the genesis entry")
        entry = {
            "schema": SCHEMA,
            "seq": 0 if prev is None else prev["seq"] + 1,
            "ts": self.clock(),
            "kind": kind,
            "prev_hash": GENESIS_PREV if prev is None else prev["hash"],
            "body": body,
        }
        entry["hash"] = entry_hash(entry)
        self.entries.append(entry)
        self._index(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(canonical_json(entry) + "\n")
                f.flush()
                if self.fsync:
                    os.fsync(f.fileno())
        return entry

    def _index(self, e: dict) -> None:
        if e["kind"] == "context":
            self._contexts.add(e["body"]["context_id"])
        elif e["kind"] == "decision":
            self._decisions[e["body"]["decision_id"]] = e

    # --- privacy-aware values -----------------------------------------------

    def _hash_value(self, s: str) -> str:
        if self.hash_key is not None:
            return hmac.new(self.hash_key, s.encode("utf-8"), hashlib.sha256).hexdigest()
        return sha256_hex(s)

    def text_record(self, text: str | None) -> dict | None:
        """A text value under ``text_mode``. ``None`` stays ``None``."""
        if text is None:
            return None
        if self.text_mode == "store":
            return {"text": text, "n_chars": len(text), "n_words": len(text.split())}
        if self.text_mode == "hash":
            return {"hash": self._hash_value(text), "n_chars": len(text), "n_words": len(text.split())}
        return {"omitted": True}

    def id_value(self, value: Any) -> Any:
        if value is None:
            return None
        if self.id_mode == "store":
            return value
        if self.id_mode == "hash":
            return "h:" + self._hash_value(str(value))[:16]
        return "omitted"

    def same_text(self, record: dict | None, text: str | None) -> bool | None:
        """``True``/``False`` if ``record`` can be compared with ``text``, else ``None``."""
        if record is None or text is None:
            return None if (record is None) != (text is None) else True
        if "text" in record:
            return record["text"] == text
        if "hash" in record:
            return hmac.compare_digest(record["hash"], self._hash_value(text))
        return None

    # --- high level ---------------------------------------------------------

    def record_context(self, context: dict) -> str:
        """Write ``context`` once (content addressed). Return its id."""
        ctx = dict(_plain(context))
        if "stream_meta" in ctx:
            ctx["stream_meta"] = meta_subset(ctx["stream_meta"])
        cid = "ctx-" + content_id(ctx)[:24]
        if cid not in self._contexts:
            self.append("context", {"context_id": cid, "context": ctx})
        return cid

    def record_decision(
        self,
        *,
        context_id: str,
        decision: Any,
        inputs: Any = None,
        stream: Any = None,
        stream_id: str | None = None,
        frame_range: tuple[int, int] | None = None,
        attempt: int = 0,
        final_attempt: bool = False,
        item_ref: str | None = None,
        scores: dict | None = None,
        decision_id: str | None = None,
    ) -> dict:
        """Write one decision. ``decision`` is a :class:`~fidetype.trust.policy.Decision`.

        ``inputs`` (the :class:`PolicyInputs`) gives the scores and the
        top-1 text. ``stream`` gives the stream id, frame count, time
        range, source, the producer's ``stream.id`` (as ``stream_ref``)
        and the pseudonymous ids (under ``id_mode``). ``stream_id`` is the
        content hash (:func:`stream_fingerprint`). The stream arrays are
        not stored. Returns the entry.
        """
        if context_id not in self._contexts:
            raise ValueError(f"unknown context {context_id!r}: call record_context first")
        did = decision_id or f"dec-{len(self._decisions):06d}-{uuid.uuid4().hex[:8]}"
        if did in self._decisions:
            raise ValueError(f"duplicate decision id {did!r}")
        inp: dict[str, Any] = {"attempt": attempt, "final_attempt": final_attempt, "item_ref": item_ref}
        if stream is not None:
            n = int(stream.log_probs.shape[0])
            ft = np.asarray(stream.frame_times)
            lo, hi = frame_range if frame_range is not None else (0, n)
            meta = getattr(stream, "meta", {}) or {}
            inp.update({
                "stream_id": stream_id or stream_fingerprint(stream),
                "stream_ref": meta.get("stream.id"),
                "source": getattr(stream, "source", None),
                "n_frames": n,
                "frame_range": [int(lo), int(hi)],
                "t_range": [float(ft[lo]), float(ft[hi - 1])] if hi > lo else None,
                "subject": self.id_value(meta.get("subject.id", meta.get("subject"))),
                "session": self.id_value(meta.get("session.id", meta.get("session"))),
            })
        elif stream_id is not None:
            inp.update({"stream_id": stream_id, "frame_range": list(frame_range) if frame_range else None})
        sc: dict[str, Any] = {}
        top1 = None
        n_cand = None
        if inputs is not None:
            sc = {
                "p_top1": inputs.p_top1,
                "set_size": inputs.set_size,
                "includes_other": inputs.includes_other,
                "guard_risk": inputs.guard_risk,
            }
            wc = inputs.word_confidence
            if wc == wc:  # not nan
                sc["word_confidence"] = wc
            top1 = inputs.texts[0] if inputs.texts else None
            n_cand = len(inputs.texts)
        if scores:
            sc.update(scores)
        action = getattr(decision.action, "value", decision.action)
        body = {
            "decision_id": did,
            "context_id": context_id,
            "input": inp,
            "action": action,
            "reason": getattr(decision, "reason", ""),
            "scores": sc,
            "n_candidates": n_cand,
            "top1": self.text_record(top1),
            "shown": [self.text_record(t) for t in getattr(decision, "shown_candidates", ())],
            "word_choices": [
                {"index": w.index, "confidence": w.confidence, "n_alternatives": len(w.alternatives)}
                for w in getattr(decision, "word_choices", ())
            ],
        }
        entry = self.append("decision", body)
        shown = tuple(getattr(decision, "shown_candidates", ()))
        if shown:
            self._shown_text[did] = shown[0]
        return entry

    def record_correction(
        self,
        decision_id: str,
        corrected_text: str | None,
        *,
        source: str = "user",
        relation: Literal["correction", "confirmation", "rejection"] | None = None,
        note: dict | None = None,
        original_text: str | None = None,
    ) -> dict:
        """Write a correction that links to an earlier decision.

        ``corrected_text`` is what the user meant (``None`` = the user
        rejected the output without giving text). The entry stores
        ``changed`` (does it differ from the first shown text) and the
        character edit distance to it, computed now, so a report works
        also in ``hash`` or ``omit`` mode. The first shown text comes from
        ``original_text``, else from the stored record (``store`` mode),
        else from this session's memory. If ``original_text`` is given and
        the stored record can be checked, it must match. ``relation``
        defaults to ``"correction"`` if the text changed, else
        ``"confirmation"``.
        """
        dec = self._decisions.get(decision_id)
        if dec is None:
            raise ValueError(f"unknown decision {decision_id!r}")
        b = dec["body"]
        shown0 = b["shown"][0] if b["shown"] else None
        body: dict[str, Any] = {
            "decision_id": decision_id,
            "decision_hash": dec["hash"],
            "decision_action": b["action"],
            "source": source,
            "corrected": self.text_record(corrected_text),
        }
        if original_text is not None and shown0 is not None and self.same_text(shown0, original_text) is False:
            raise ValueError("original_text does not match the text recorded for this decision")
        orig = original_text
        if orig is None and shown0 is not None:
            orig = shown0.get("text", self._shown_text.get(decision_id))
        if corrected_text is None:
            changed = True
        elif orig is not None:
            changed = orig != corrected_text
        else:
            same = self.same_text(shown0, corrected_text)
            changed = (not same) if same is not None else None
        body["changed"] = changed
        if orig is not None and corrected_text is not None:
            from fidetype.eval.metrics import edit_distance

            body["char_edits"] = edit_distance(orig, corrected_text)
            body["word_edits"] = edit_distance(orig.split(), corrected_text.split())
        body["relation"] = relation or ("rejection" if corrected_text is None else "correction" if changed else "confirmation")
        if note:
            body["note"] = note
        return self.append("correction", body)

    def note(self, body: dict) -> dict:
        return self.append("note", body)


class LedgeredPolicy:
    """Wrap a policy so that each ``decide`` call writes a decision entry.

    Use it outside the harness (for example in a live loop)::

        pol = LedgeredPolicy(DecisionPolicy(cfg), ledger, ledger.record_context(ctx))
        d = pol.decide(inputs, stream=stream)
        pol.last_entry["body"]["decision_id"]
    """

    def __init__(self, policy: Any, ledger: ProvenanceLedger, context_id: str) -> None:
        self.policy = policy
        self.ledger = ledger
        self.context_id = context_id
        self.last_entry: dict | None = None

    @property
    def config(self) -> Any:
        return getattr(self.policy, "config", None)

    def decide(self, x: Any, final_attempt: bool = False, **record_kw: Any) -> Any:
        d = self.policy.decide(x, final_attempt=final_attempt)
        self.last_entry = self.ledger.record_decision(
            context_id=self.context_id, decision=d, inputs=x, final_attempt=final_attempt, **record_kw
        )
        return d


# ---------------------------------------------------------------------------
# Reading and verification
# ---------------------------------------------------------------------------


def read_entries(path: str | os.PathLike) -> list[dict]:
    """Read a ledger file (``.gz`` too). Raise ``ValueError`` on a line that is not JSON."""
    import gzip

    out = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"line {i + 1}: not valid JSON ({e})") from e
    return out


def verify(
    source: str | os.PathLike | Sequence[dict],
    expected_head: str | dict | None = None,
) -> VerifyResult:
    """Check a ledger: schema, sequence, hash chain and references.

    Detects an edited entry (hash mismatch), a deleted entry (seq gap and
    ``prev_hash`` mismatch), a reordered entry, a correction or decision
    that points to an unknown or later entry, and a bad genesis. Pass
    ``expected_head`` (a hash, or the dict from
    :meth:`ProvenanceLedger.anchor`) to detect a cut at the end.
    """
    errors: list[str] = []
    try:
        entries = list(source) if not isinstance(source, (str, os.PathLike)) else read_entries(source)
    except ValueError as e:
        return VerifyResult(False, 0, [str(e)])
    if not entries:
        return VerifyResult(False, 0, ["empty ledger"])
    contexts: set[str] = set()
    decisions: dict[str, str] = {}
    prev = GENESIS_PREV
    for i, e in enumerate(entries):
        tag = f"entry {i}"
        missing = {"schema", "seq", "ts", "kind", "prev_hash", "body", "hash"} - set(e)
        if missing:
            errors.append(f"{tag}: missing keys {sorted(missing)}")
            prev = e.get("hash", prev)
            continue
        if e["schema"] != SCHEMA:
            errors.append(f"{tag}: unknown schema {e['schema']!r}")
        if e["seq"] != i:
            errors.append(f"{tag}: seq {e['seq']} != {i} (entry deleted, inserted or reordered)")
        if e["prev_hash"] != prev:
            errors.append(f"{tag}: prev_hash does not match the previous entry (chain broken)")
        try:
            h = entry_hash(e)
        except (TypeError, ValueError) as ex:
            errors.append(f"{tag}: cannot hash ({ex})")
            h = None
        if h != e["hash"]:
            errors.append(f"{tag}: hash mismatch (entry edited)")
        if e["kind"] not in KINDS:
            errors.append(f"{tag}: unknown kind {e['kind']!r}")
        if (i == 0) != (e["kind"] == "genesis"):
            errors.append(f"{tag}: genesis must be entry 0 and only entry 0")
        b = e["body"] if isinstance(e["body"], dict) else {}
        if e["kind"] == "context":
            cid = b.get("context_id")
            if cid != "ctx-" + content_id(b.get("context", {}))[:24]:
                errors.append(f"{tag}: context_id does not match the context content")
            contexts.add(cid)
        elif e["kind"] == "decision":
            did = b.get("decision_id")
            if did in decisions:
                errors.append(f"{tag}: duplicate decision id {did!r}")
            if b.get("context_id") not in contexts:
                errors.append(f"{tag}: decision refers to an unknown or later context")
            decisions[did] = e["hash"]
        elif e["kind"] == "correction":
            did = b.get("decision_id")
            if did not in decisions:
                errors.append(f"{tag}: correction refers to an unknown or later decision {did!r}")
            elif b.get("decision_hash") != decisions[did]:
                errors.append(f"{tag}: decision_hash does not match decision {did!r}")
        prev = e["hash"]
    last = entries[-1]
    if expected_head is not None:
        want = expected_head["hash"] if isinstance(expected_head, dict) else expected_head
        if last.get("hash") != want:
            errors.append("head hash != expected head (entries cut or added at the end)")
    return VerifyResult(not errors, len(entries), errors, last.get("hash"), last.get("seq"))


# ---------------------------------------------------------------------------
# Queries and reports
# ---------------------------------------------------------------------------


class LedgerView:
    """Indexes over the entries of a ledger, for queries."""

    def __init__(self, source: str | os.PathLike | Sequence[dict] | ProvenanceLedger) -> None:
        if isinstance(source, ProvenanceLedger):
            entries = source.entries
        elif isinstance(source, (str, os.PathLike)):
            entries = read_entries(source)
        else:
            entries = list(source)
        self.entries = entries
        self.genesis = entries[0]["body"] if entries else {}
        self.contexts = {e["body"]["context_id"]: e["body"]["context"] for e in entries if e["kind"] == "context"}
        self.decisions = {e["body"]["decision_id"]: e for e in entries if e["kind"] == "decision"}
        self.corrections: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            if e["kind"] == "correction":
                self.corrections[e["body"]["decision_id"]].append(e)

    def latest_correction(self, decision_id: str) -> dict | None:
        cs = self.corrections.get(decision_id)
        return cs[-1] if cs else None

    def is_wrong_commit(self, decision_id: str) -> bool:
        d = self.decisions[decision_id]["body"]
        c = self.latest_correction(decision_id)
        return d["action"] == "COMMIT" and c is not None and bool(c["body"].get("changed"))

    def wrong_commits(self) -> list[dict]:
        """Every COMMIT whose latest correction changed the text, with its full provenance."""
        out = []
        for did, e in self.decisions.items():
            if self.is_wrong_commit(did):
                out.append({
                    "decision": e,
                    "context": self.contexts.get(e["body"]["context_id"]),
                    "corrections": self.corrections[did],
                })
        return out

    def group_key(self, decision: dict, keys: Sequence[str]) -> tuple:
        ctx = self.contexts.get(decision["body"]["context_id"], {})
        return tuple(_dig(ctx, k) for k in keys)

    def summary(self, keys: Sequence[str] = ("decoder.name", "decoder.version", "calibration.id", "policy.version")) -> list[dict]:
        """Per group (default: decoder, calibration, policy version): counts and rates.

        ``wrong_commit_rate`` = wrong commits / decisions (the harness
        metric); ``commit_precision`` = 1 - wrong commits / commits. A
        commit without any correction counts as right: in live use that
        is an assumption (see the docs).
        """
        groups: dict[tuple, dict] = {}
        for did, e in self.decisions.items():
            g = groups.setdefault(self.group_key(e, keys), {"n": 0, "actions": Counter(), "wrong_commits": 0, "corrected": 0})
            g["n"] += 1
            g["actions"][e["body"]["action"]] += 1
            g["wrong_commits"] += self.is_wrong_commit(did)
            g["corrected"] += self.latest_correction(did) is not None
        rows = []
        for k, g in groups.items():
            nc = g["actions"].get("COMMIT", 0)
            rows.append({
                **dict(zip(keys, k)),
                "n_decisions": g["n"],
                "actions": dict(g["actions"]),
                "n_commits": nc,
                "n_wrong_commits": g["wrong_commits"],
                "n_with_correction": g["corrected"],
                "wrong_commit_rate": g["wrong_commits"] / g["n"] if g["n"] else math.nan,
                "commit_precision": 1 - g["wrong_commits"] / nc if nc else math.nan,
            })
        return rows


def _dig(obj: Any, dotted: str) -> Any:
    """``_dig(ctx, "decoder.name")`` -> ``ctx["decoder"]["name"]`` (None if absent)."""
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4f}" if math.isfinite(v) else str(v)
    if isinstance(v, str) and v in ("nan", "inf", "-inf"):
        return v
    return str(v)


def _text(rec: dict | None) -> str:
    if rec is None:
        return "—"
    if "text" in rec:
        return f"\"{rec['text']}\""
    if "hash" in rec:
        return f"hash {rec['hash'][:12]}… ({rec['n_chars']} chars)"
    return "(omitted)"


def audit_report(
    source: str | os.PathLike | Sequence[dict] | ProvenanceLedger,
    max_items: int | None = 20,
    keys: Sequence[str] = ("decoder.name", "decoder.version", "calibration.id", "policy.version"),
    expected_head: str | dict | None = None,
) -> str:
    """A Markdown audit report: verification, summary per version, wrong commits."""
    view = LedgerView(source)
    res = verify(view.entries, expected_head)
    lines = ["# Provenance audit report", ""]
    lines.append(f"- Ledger id: `{view.genesis.get('ledger_id')}`; schema `{view.genesis.get('schema')}`; "
                 f"text mode `{view.genesis.get('text_mode')}`; id mode `{view.genesis.get('id_mode')}`.")
    lines.append(f"- Entries: {res.n_entries}; head seq {res.head_seq}; head hash `{res.head_hash}`.")
    lines.append(f"- Chain verification: **{'PASS' if res.ok else 'FAIL'}**.")
    for err in res.errors[:20]:
        lines.append(f"  - {err}")
    lines += ["", "## Summary per decoder / calibration / policy version", ""]
    rows = view.summary(keys)
    head = list(keys) + ["decisions", "commits", "wrong commits", "wrong-commit rate", "commit precision", "actions"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "---|" * len(head))
    for r in rows:
        acts = ", ".join(f"{a} {n}" for a, n in sorted(r["actions"].items()))
        vals = [r[k] for k in keys] + [r["n_decisions"], r["n_commits"], r["n_wrong_commits"],
                                        r["wrong_commit_rate"], r["commit_precision"], acts]
        lines.append("| " + " | ".join(_fmt(v) for v in vals) + " |")
    wcs = view.wrong_commits()
    lines += ["", f"## Wrong commits ({len(wcs)})", ""]
    if wcs and max_items is not None and len(wcs) > max_items:
        lines.append(f"The first {max_items} of {len(wcs)} are shown.")
        lines.append("")
    for w in wcs[: max_items if max_items is not None else None]:
        d = w["decision"]
        b = d["body"]
        c = w["corrections"][-1]["body"]
        ctx = w["context"] or {}
        inp = b["input"]
        s = b["scores"]
        lines.append(f"### `{b['decision_id']}` (entry {d['seq']}, hash `{d['hash'][:16]}…`)")
        lines.append(f"- Committed: {_text(b['shown'][0] if b['shown'] else None)}")
        lines.append(f"- Correction ({c['source']}, entry hash-linked): {_text(c['corrected'])}; "
                     f"char edits {c.get('char_edits', '—')}, word edits {c.get('word_edits', '—')}")
        lines.append(f"- Scores: p_top1 {_fmt(s.get('p_top1'))}, set size {s.get('set_size')}, "
                     f"guard risk {_fmt(s.get('guard_risk'))}; reason: {b['reason']}")
        lines.append(f"- Input: stream `{str(inp.get('stream_id'))[:16]}…`, source {inp.get('source')}, "
                     f"frames {inp.get('frame_range')}, t {inp.get('t_range')}, attempt {inp.get('attempt')}, "
                     f"item {inp.get('item_ref')}")
        dec, cal, pol = ctx.get("decoder", {}), ctx.get("calibration", {}), ctx.get("policy", {})
        rc = cal.get("risk_control", {}) or {}
        lines.append(f"- Decoder: {dec.get('name')} {dec.get('version')}; weights `{dec.get('weights_sha256')}`; "
                     f"LM {ctx.get('lm', {}).get('name')}; adapter {ctx.get('adapter', {}).get('name')}")
        lines.append(f"- Calibration `{cal.get('id')}`: T_frame {_fmt(cal.get('temperature_frame'))}, "
                     f"T_sentence {_fmt(cal.get('temperature_sentence'))}, risk control {rc.get('method')} "
                     f"(α {rc.get('alpha')}, δ {rc.get('delta')}, threshold {_fmt(rc.get('threshold'))}), "
                     f"set {cal.get('calibration_set_id')}")
        cfg = pol.get("config") or {}
        lines.append(f"- Policy `{pol.get('version')}`: commit_p {cfg.get('commit_p')}, "
                     f"commit_max_risk {cfg.get('commit_max_risk')}, offer_max_k {cfg.get('offer_max_k')}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.trust.provenance")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify the hash chain of a ledger")
    v.add_argument("path")
    v.add_argument("--head", default=None, help="expected head hash (detects a cut at the end)")
    r = sub.add_parser("report", help="print a Markdown audit report")
    r.add_argument("path")
    r.add_argument("--max-items", type=int, default=20)
    r.add_argument("--head", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        res = verify(a.path, a.head)
        print(f"{'PASS' if res.ok else 'FAIL'}: {res.n_entries} entries, head seq {res.head_seq}, head {res.head_hash}")
        for e in res.errors:
            print("  " + e)
        return 0 if res.ok else 1
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(audit_report(a.path, a.max_items, expected_head=a.head))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
