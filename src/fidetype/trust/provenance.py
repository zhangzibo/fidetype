"""Provenance ledger (M2-09 v0; P5-03 lineage + licence flags; P5-04 redaction): a hash-chained audit trail.

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
- **Hash rule ``salted-body`` (P5-04, default for new ledgers).** Each
  entry also holds ``salt`` (16 random bytes, hex) and ``body_sha256`` =
  SHA-256 of ``salt + "\\n" + canonical_json(body)``. The entry ``hash``
  then covers ``body_sha256`` instead of ``body`` (the keys ``body``,
  ``salt`` and ``redacted`` are left out). So a ``body`` can be removed
  later (a tombstone, see ``redaction``) and the chain still verifies. The
  salt goes with the body, so nobody can confirm a guessed body from its
  digest. Ledgers written before P5-04 have no ``salt`` (genesis without
  ``hash_rule``): they keep the old rule (``v0``) and cannot be redacted.

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
``update``
    One step of a decoder / trust-configuration update (P15-02,
    :class:`~fidetype.trust.adaptive.GuardedUpdateLoop`). ``stage`` is
    ``"proposed"``, ``"accepted"`` or ``"rejected"``. Each update has an
    ``update_id`` and belongs to a ``chain`` (one loop or one guard). A
    decision entry (accepted / rejected) names its proposal
    (``update_id`` and the proposal entry's ``hash``). ``parent_config_id``
    and ``config_id`` give the configuration chain: an accepted update
    must start from the last accepted ``config_id`` of its chain and give
    a new one; a rejected update leaves it unchanged. :func:`verify`
    checks these rules. See :meth:`ProvenanceLedger.record_update`.
``source`` (P5-03)
    One data source: name, version, URL, content digest and **licence**
    (SPDX id), plus its licence flags (:mod:`fidetype.trust.licence`).
    Consented own data names its consent reference and scope (no personal
    data). Content addressed (``src-...``), written once.
``artifact`` (P5-03)
    One derived artifact (``weights``, ``lm``, ``calibration``, ``split``,
    ``config``, ``other``): name, version, SHA-256, ``derived_from`` (earlier
    source / artifact ids), ``purpose`` (``research`` or ``product``) and the
    combined licence flags of all inputs. An artifact for ``product`` use
    whose inputs the product policy does not allow (for example NC data) is
    refused when it is written, and :func:`verify` flags it. Content
    addressed (``art-...``), written once.
``redaction`` (P5-04)
    An erasure record: the ``seq`` and ``hash`` of each removed entry
    (decisions, corrections, notes), a reason code and an opaque request
    reference. After this entry the bodies of the targets are removed
    (tombstones: every key except ``body`` and ``salt`` stays). :func:`verify`
    accepts a tombstone only if a later ``redaction`` entry names it.

Lineage and licence flags (P5-03)
---------------------------------
A ``context`` may name ``lineage``: the artifact ids of the models and the
calibration that it uses (in the context dict, or for every context
through :meth:`ProvenanceLedger.set_lineage`). The context entry then
carries the combined licence flags (``licence``), and each ``decision`` of
that context carries the short flags (``research_only``,
``commercial_ok``, ``product_ok``). So an output that depends on NC data
is flagged. :meth:`LedgerView.lineage` gives the full chain of one
decision: corrections, context, artifacts, sources, licence flags (CLI
``lineage``). :func:`record_lineage_spec` writes sources and artifacts
from a JSON / TOML file.

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
chain. A signed anchor (:mod:`fidetype.trust.anchor`, P5-14) closes that
gap: the head is signed with an Ed25519 key kept outside the ledger.

Command line::

    python -m fidetype.trust.provenance verify ledger.jsonl [--head <hash> | --anchor anchor.json
        [--public-key pub.pem] [--allow-growth]]
    python -m fidetype.trust.provenance report ledger.jsonl [--max-items 20]
    python -m fidetype.trust.provenance anchor ledger.jsonl [--out anchor.json]
        [--sign-key-file key.pem | --sign-key-env VAR]
    python -m fidetype.trust.provenance keygen --private key.pem --public pub.pem
    python -m fidetype.trust.provenance lineage ledger.jsonl <decision_id> [--word N] [--json]
    python -m fidetype.trust.provenance redact ledger.jsonl --decision <id> [--decision <id> ...]
        --request-ref <opaque ref> [--reason erasure-request] [--key-env VAR]
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
from typing import Any, Callable, Literal, Mapping, Sequence

import numpy as np

SCHEMA = "fidetype.provenance/0.1"
SCHEMA_VERSION = "0.1"
GENESIS_PREV = "0" * 64
KINDS = ("genesis", "context", "decision", "correction", "note", "update", "source", "artifact", "redaction")
#: ``salted-body``: entries hold ``salt`` + ``body_sha256`` (redactable, P5-04); ``v0``: the M2-09 rule.
HASH_RULES = ("salted-body", "v0")
#: Keys left out of the entry hash under the ``salted-body`` rule.
_BODY_KEYS = ("hash", "body", "salt", "redacted")
#: Artifact kinds and purposes (P5-03).
ARTIFACT_KINDS = ("weights", "lm", "calibration", "split", "config", "other")
PURPOSES = ("research", "product")
#: Entry kinds that a ``redaction`` may remove (P5-04).
REDACTABLE_KINDS = ("decision", "correction", "note")
REDACTION_REASONS = ("erasure-request", "consent-withdrawn", "retention-expired", "other")
#: Stages of an ``update`` entry (P15-02).
UPDATE_STAGES = ("proposed", "accepted", "rejected")
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


def body_digest(salt: str, body: Any) -> str:
    """``body_sha256`` of the ``salted-body`` rule: SHA-256 of ``salt + "\\n" + canonical_json(body)``."""
    return sha256_hex(f"{salt}\n{canonical_json(body)}")


def entry_hash(entry: dict) -> str:
    """The ``hash`` of an entry.

    Rule ``v0`` (no ``salt`` / ``body_sha256`` key): SHA-256 of the canonical JSON of ``entry`` without
    ``hash``. Rule ``salted-body``: the same over the entry without ``body``, ``salt`` and ``redacted``, with
    ``body_sha256`` recomputed from ``salt`` and ``body`` when the body is present (the stored value for a
    tombstone).
    """
    if "body_sha256" not in entry and "salt" not in entry:
        return sha256_hex(canonical_json({k: v for k, v in entry.items() if k != "hash"}))
    head = {k: v for k, v in entry.items() if k not in _BODY_KEYS}
    if "body" in entry and "salt" in entry:
        head["body_sha256"] = body_digest(entry["salt"], entry["body"])
    return sha256_hex(canonical_json(head))


def is_tombstone(entry: dict) -> bool:
    """True if the body of ``entry`` was removed by a redaction (P5-04)."""
    return "body" not in entry and "body_sha256" in entry


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
    lineage: Sequence[str] | None = None,
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
    if lineage is not None:
        ctx["lineage"] = list(lineage)  # artifact ids (P5-03); the ledger checks them
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
        hash_rule: str = "salted-body",
    ) -> None:
        if text_mode not in TEXT_MODES or id_mode not in TEXT_MODES:
            raise ValueError(f"text_mode and id_mode must be one of {TEXT_MODES}")
        if hash_rule not in HASH_RULES:
            raise ValueError(f"hash_rule must be one of {HASH_RULES}")
        self.path = None if path is None else Path(path)
        self.hash_key = hash_key
        self.clock = clock or _utc_now
        self.fsync = fsync
        self.hash_rule = hash_rule
        self.entries: list[dict] = []
        self._contexts: set[str] = set()
        #: P5-03: context id -> combined licence flags (None: no lineage); source / artifact id -> licence flags.
        self._ctx_licence: dict[str, dict | None] = {}
        self._sources: dict[str, dict] = {}
        self._artifacts: dict[str, dict] = {}
        #: Artifact ids added to every new context without its own ``lineage`` (:meth:`set_lineage`).
        self.default_lineage: list[str] | None = None
        #: P5-04: seq -> redaction seq of each entry named by a redaction entry.
        self._redaction_targets: dict[int, int] = {}
        self._decisions: dict[str, dict] = {}
        #: In memory only (never written): the first shown text of each
        #: decision of this session, so a correction can compute its
        #: edit distance in every text mode.
        self._shown_text: dict[str, str] = {}
        #: update_id -> proposal entry, the decided ids, chain -> last accepted config_id (``update`` entries).
        self._proposals: dict[str, dict] = {}
        self._decided: set[str] = set()
        self._chain_head: dict[str, str | None] = {}
        if self.path is not None and self.path.exists() and self.path.stat().st_size > 0:
            entries = read_entries(self.path)
            res = verify(entries)
            if not res.ok:
                raise ValueError(f"cannot continue a ledger that fails verification: {res.errors[:3]}")
            self.entries = entries
            g = entries[0]["body"]
            self.text_mode, self.id_mode = g["text_mode"], g["id_mode"]
            self.ledger_id = g["ledger_id"]
            self.hash_rule = g.get("hash_rule", "v0")
            if g.get("text_hash_alg") == "hmac-sha256" and hash_key is None:
                raise ValueError("this ledger uses keyed text hashes: pass hash_key")
            for e in entries:
                self._index(e)
            if self.pending_redactions():
                self.apply_redactions()  # finish an erasure that stopped between the entry and the rewrite
        else:
            self.text_mode, self.id_mode = text_mode, id_mode
            self.ledger_id = ledger_id or str(uuid.uuid4())
            gen = {
                "ledger_id": self.ledger_id,
                "schema": SCHEMA,
                "text_mode": text_mode,
                "id_mode": id_mode,
                "text_hash_alg": "hmac-sha256" if hash_key is not None else "sha256",
                "key_id": key_id,
            }
            if hash_rule != "v0":
                gen["hash_rule"] = hash_rule
            self.append("genesis", gen)

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
        if self.hash_rule == "salted-body":
            entry["salt"] = os.urandom(16).hex()
            entry["body_sha256"] = body_digest(entry["salt"], body)
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
        if is_tombstone(e):
            return
        if e["kind"] == "context":
            self._contexts.add(e["body"]["context_id"])
            self._ctx_licence[e["body"]["context_id"]] = e["body"].get("licence")
        elif e["kind"] == "source":
            self._sources[e["body"]["source_id"]] = e["body"]["licence"]
        elif e["kind"] == "artifact":
            self._artifacts[e["body"]["artifact_id"]] = e["body"]["licence"]
        elif e["kind"] == "redaction":
            for t in e["body"].get("targets", ()):
                self._redaction_targets[int(t["seq"])] = e["seq"]
        elif e["kind"] == "decision":
            self._decisions[e["body"]["decision_id"]] = e
        elif e["kind"] == "update":
            b = e["body"]
            if b.get("stage") == "proposed":
                self._proposals[b["update_id"]] = e
            else:
                self._decided.add(b["update_id"])
                if b.get("stage") == "accepted":
                    self._chain_head[b.get("chain", "default")] = b.get("config_id")

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
        """Write ``context`` once (content addressed). Return its id.

        P5-03: ``context["lineage"]`` (or else :attr:`default_lineage`) lists the artifact ids that the
        context uses. They must be in this ledger. The context entry then holds their combined licence flags
        (``licence``), and each decision of the context gets the short flags.
        """
        ctx = dict(_plain(context))
        if "stream_meta" in ctx:
            ctx["stream_meta"] = meta_subset(ctx["stream_meta"])
        if ctx.get("lineage") is None and self.default_lineage is not None:
            ctx["lineage"] = list(self.default_lineage)
        lic = None
        if ctx.get("lineage") is not None:
            ids = sorted(set(str(a) for a in ctx["lineage"]))
            unknown = [a for a in ids if a not in self._artifacts]
            if unknown:
                raise ValueError(f"unknown artifact id(s) in lineage: {unknown} (call record_artifact first)")
            ctx["lineage"] = ids
            from fidetype.trust.licence import combine

            lic = combine(self._artifacts[a] for a in ids)
        cid = "ctx-" + content_id(ctx)[:24]
        if cid not in self._contexts:
            body: dict[str, Any] = {"context_id": cid, "context": ctx}
            if lic is not None:
                body["licence"] = lic
            self.append("context", body)
        return cid

    # --- lineage and licence flags (P5-03) -------------------------------------

    def record_source(
        self,
        name: str,
        licence: str,
        *,
        version: str | None = None,
        url: str | None = None,
        digest: str | None = None,
        attribution: str | None = None,
        consent: Mapping[str, Any] | None = None,
        track: str | None = None,
        details: dict | None = None,
    ) -> str:
        """Write one data source (content addressed, once). Return its id ``src-...``.

        ``licence``: an SPDX id or a common form (``"CC BY-NC 4.0"``); it is normalised
        (:func:`fidetype.trust.licence.normalise`), the given text stays in ``licence_text``.
        ``digest``: a content hash of the data or of the split file (no data). ``consent``: for own consented
        data (``LicenseRef-fidetype-consented``) a dict with ``ref`` (an opaque consent reference) and
        ``scope`` (purposes, :data:`fidetype.trust.privacy.PURPOSES`); required for that licence.
        """
        from fidetype.trust.licence import CONSENTED, normalise, source_summary

        spdx = normalise(licence)
        src: dict[str, Any] = {"name": str(name), "licence": spdx, "licence_text": str(licence)}
        for k, v in (("version", version), ("url", url), ("digest", digest), ("attribution", attribution),
                     ("track", track)):
            if v is not None:
                src[k] = str(v)
        scope: list[str] = []
        if consent is not None:
            from fidetype.trust.privacy import check_consent_ref, check_scope

            scope = check_scope(consent.get("scope") or ())
            src["consent"] = {"ref": check_consent_ref(consent.get("ref")), "scope": scope}
        elif spdx == CONSENTED:
            raise ValueError(f"a {CONSENTED} source needs consent={{'ref': ..., 'scope': [...]}}")
        if details:
            src["details"] = dict(details)
        sid = "src-" + content_id(src)[:24]
        if sid not in self._sources:
            self.append("source", {"source_id": sid, "source": src, "licence": source_summary(spdx, scope)})
        return sid

    def record_track_source(self, track: str, *, digest: str | None = None) -> str:
        """Write the dataset of a benchmark track (``fidetype.benchmark.tracks``) as a source.

        Licence, URL and attribution come from the track definition. ``digest`` defaults to the digest of the
        track's split file (if it is in the package).
        """
        from fidetype.benchmark.tracks import TRACKS_VERSION, get_track, load_split
        from fidetype.trust.licence import track_licence

        t = get_track(track)
        spdx, _, attribution = track_licence(track)
        if digest is None:
            try:
                sp = load_split(track)
                digest = sp.get("digest") or sp.get("entries_digest")
            except (OSError, ValueError, KeyError):
                digest = None
        return self.record_source(t.dataset_title, spdx, version=f"tracks-{TRACKS_VERSION}", url=t.url,
                                  digest=digest, attribution=attribution, track=track)

    def record_artifact(
        self,
        kind: str,
        name: str,
        *,
        derived_from: Sequence[str] = (),
        version: str | None = None,
        sha256: str | None = None,
        licence: str | None = None,
        purpose: str = "research",
        product_policy: str = "project",
        details: dict | None = None,
    ) -> str:
        """Write one derived artifact (content addressed, once). Return its id ``art-...``.

        ``derived_from``: earlier source / artifact ids (the training data of weights, the corpus of an LM,
        the calibration split of a calibration, the weights a calibration belongs to). ``licence``: the
        artifact's own licence, if it has one (for example third-party weights). The entry holds the
        combined flags of all inputs. ``purpose="product"`` raises
        :class:`~fidetype.trust.licence.LicenceError` if the inputs do not allow product use under
        ``product_policy`` (``"project"``: CC0 / own / consented with the product scope; ``"commercial"``).
        """
        from fidetype.trust.licence import PRODUCT_POLICIES, check_product, combine, source_summary

        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"artifact kind must be one of {ARTIFACT_KINDS}")
        if purpose not in PURPOSES:
            raise ValueError(f"purpose must be one of {PURPOSES}")
        if product_policy not in PRODUCT_POLICIES:
            raise ValueError(f"product_policy must be one of {PRODUCT_POLICIES}")
        inputs = sorted(set(str(x) for x in derived_from))
        unknown = [x for x in inputs if x not in self._sources and x not in self._artifacts]
        if unknown:
            raise ValueError(f"unknown input id(s) {unknown}: record the sources and artifacts first")
        parts = [self._sources.get(x) or self._artifacts[x] for x in inputs]
        if licence is not None:
            parts.append(source_summary(licence))
        lic = combine(parts)
        if not inputs and licence is None:
            from fidetype.trust.licence import UNKNOWN

            lic = source_summary(UNKNOWN)  # no recorded input: unknown lineage, research only
        art: dict[str, Any] = {"kind": kind, "name": str(name), "derived_from": inputs, "purpose": purpose,
                               "product_policy": product_policy}
        for k, v in (("version", version), ("sha256", sha256)):
            if v is not None:
                art[k] = str(v)
        if licence is not None:
            from fidetype.trust.licence import normalise

            art["licence"] = normalise(licence)
        if details:
            art["details"] = dict(details)
        if purpose == "product":
            check_product(lic, product_policy, what=f"artifact {name!r}")
        aid = "art-" + content_id(art)[:24]
        if aid not in self._artifacts:
            self.append("artifact", {"artifact_id": aid, "artifact": art, "licence": lic})
        return aid

    def set_lineage(self, artifact_ids: Sequence[str] | None) -> None:
        """Use ``artifact_ids`` as the lineage of every new context that has none (None: stop)."""
        if artifact_ids is not None:
            unknown = [a for a in artifact_ids if a not in self._artifacts]
            if unknown:
                raise ValueError(f"unknown artifact id(s): {unknown}")
            self.default_lineage = sorted(set(artifact_ids))
        else:
            self.default_lineage = None

    def licence_of(self, context_id: str) -> dict | None:
        """The combined licence flags of a context (None: the context has no lineage)."""
        return self._ctx_licence.get(context_id)

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
        lic = self._ctx_licence.get(context_id)
        if lic is not None:
            from fidetype.trust.licence import flag

            body["licence"] = flag(lic)
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

    def chain_head(self, chain: str = "default") -> str | None:
        """The last accepted ``config_id`` of an update chain (None: no accepted update yet)."""
        return self._chain_head.get(chain)

    def has_update(self, update_id: str) -> bool:
        """True if ``update_id`` was proposed in this ledger (open or decided)."""
        return update_id in self._proposals

    def is_open_update(self, update_id: str) -> bool:
        """True if ``update_id`` was proposed and is not decided yet."""
        return update_id in self._proposals and update_id not in self._decided

    def record_update(
        self,
        stage: str,
        update_id: str,
        *,
        chain: str = "default",
        parent_config_id: str | None = None,
        config_id: str | None = None,
        details: dict | None = None,
    ) -> dict:
        """Write one ``update`` entry (P15-02): a proposed, accepted or rejected update.

        ``stage="proposed"`` opens ``update_id`` (unique). ``"accepted"`` / ``"rejected"`` close it and
        link to the proposal by its hash. An accepted update needs ``parent_config_id`` equal to
        :meth:`chain_head` and a new ``config_id``; a rejected one keeps ``config_id`` equal to
        ``parent_config_id``. ``details`` holds the checks (null controls, champion / challenger test,
        threshold, reasons); it must not hold raw data (:func:`check_no_raw`) or plain text.
        """
        if stage not in UPDATE_STAGES:
            raise ValueError(f"stage must be one of {UPDATE_STAGES}")
        body: dict = {"update_id": str(update_id), "chain": str(chain), "stage": stage,
                      "parent_config_id": parent_config_id, "config_id": config_id}
        if stage == "proposed":
            if body["update_id"] in self._proposals:
                raise ValueError(f"update {update_id!r} was already proposed")
        else:
            prop = self._proposals.get(body["update_id"])
            if prop is None:
                raise ValueError(f"update {update_id!r} has no proposal entry")
            if body["update_id"] in self._decided:
                raise ValueError(f"update {update_id!r} is already decided")
            head = self._chain_head.get(body["chain"])
            if parent_config_id != head:
                raise ValueError(f"parent_config_id {parent_config_id!r} != chain head {head!r}")
            if stage == "accepted" and (config_id is None or config_id == parent_config_id):
                raise ValueError("an accepted update needs a new config_id")
            if stage == "rejected" and config_id != parent_config_id:
                raise ValueError("a rejected update must keep the config_id")
            body["proposal_hash"] = prop["hash"]
        body["details"] = dict(details or {})
        return self.append("update", body)

    # --- redaction (P5-04) -------------------------------------------------------

    def pending_redactions(self) -> list[int]:
        """The seqs named by a redaction entry whose body is still present."""
        return sorted(s for s in self._redaction_targets if not is_tombstone(self.entries[s]))

    def redact(self, seqs: Sequence[int], *, request_ref: str, reason: str = "erasure-request",
               subject: str | None = None) -> dict:
        """Remove the bodies of the entries ``seqs`` and keep the chain verifiable. Return the redaction entry.

        Only ``decision``, ``correction`` and ``note`` entries can be removed. A removed decision takes its
        corrections with it. Steps: (1) append a ``redaction`` entry that names each target by ``seq`` and
        ``hash``, with ``reason`` (:data:`REDACTION_REASONS`) and ``request_ref`` (an opaque reference to the
        erasure request: no personal data, checked like a consent reference); (2) replace each target by a
        tombstone (the entry without ``body`` and ``salt``); (3) rewrite the file (atomic replace). If the
        process stops between (1) and (3), the next open of the file finishes the job.
        ``subject``: the pseudonymous subject value as stored in the decisions (optional, for the record).
        """
        from fidetype.trust.privacy import check_opaque_ref

        if self.hash_rule != "salted-body":
            raise ValueError("this ledger uses the v0 hash rule (written before P5-04): a body cannot be removed "
                             "without breaking the chain; start a new ledger")
        if reason not in REDACTION_REASONS:
            raise ValueError(f"reason must be one of {REDACTION_REASONS}")
        targets = sorted(set(int(s) for s in seqs))
        # A removed decision takes its corrections with it.
        dids = {self.entries[s]["body"]["decision_id"] for s in targets
                if 0 <= s < len(self.entries) and self.entries[s]["kind"] == "decision" and not is_tombstone(self.entries[s])}
        for e in self.entries:
            if e["kind"] == "correction" and not is_tombstone(e) and e["body"].get("decision_id") in dids:
                targets.append(e["seq"])
        targets = sorted(set(targets))
        if not targets:
            raise ValueError("nothing to redact")
        for s in targets:
            if not 0 <= s < len(self.entries):
                raise ValueError(f"no entry with seq {s}")
            e = self.entries[s]
            if e["kind"] not in REDACTABLE_KINDS:
                raise ValueError(f"entry {s} is a {e['kind']!r} entry; only {REDACTABLE_KINDS} can be redacted")
            if is_tombstone(e) or s in self._redaction_targets:
                raise ValueError(f"entry {s} is already redacted")
        body = {
            "targets": [{"seq": s, "hash": self.entries[s]["hash"], "kind": self.entries[s]["kind"]} for s in targets],
            "n": len(targets),
            "reason": reason,
            "request_ref": check_opaque_ref(request_ref, "request_ref"),
        }
        if subject is not None:
            body["subject"] = str(subject)
        entry = self.append("redaction", body)
        self.apply_redactions()
        return entry

    def redact_decisions(self, decision_ids: Sequence[str], **kw: Any) -> dict:
        """:meth:`redact` the decisions ``decision_ids`` (and their corrections)."""
        seqs = []
        for did in decision_ids:
            e = self._decisions.get(did)
            if e is None:
                raise ValueError(f"unknown or already redacted decision {did!r}")
            seqs.append(e["seq"])
        return self.redact(seqs, **kw)

    def redact_subject(self, subject_id: str, **kw: Any) -> dict:
        """:meth:`redact` every decision whose input names ``subject_id`` (as the stream's ``subject.id``).

        The ledger finds them through :meth:`id_value` (same ``id_mode`` and key as at write time). With
        ``id_mode="omit"`` the decisions hold no subject, so this raises ``ValueError``.
        """
        if self.id_mode == "omit":
            raise ValueError("id_mode 'omit': the decisions name no subject; redact by decision id")
        v = self.id_value(subject_id)
        dids = [did for did, e in self._decisions.items() if (e["body"].get("input") or {}).get("subject") == v]
        if not dids:
            raise ValueError("no decision of this subject in the ledger")
        return self.redact_decisions(dids, subject=v if self.id_mode == "hash" else "stored-id", **kw)

    def apply_redactions(self) -> int:
        """Replace every target of a redaction entry by its tombstone; rewrite the file. Return the count."""
        n = 0
        for s, by in sorted(self._redaction_targets.items()):
            e = self.entries[s]
            if is_tombstone(e):
                continue
            if e["kind"] == "decision":
                did = e["body"].get("decision_id")
                self._decisions.pop(did, None)
                self._shown_text.pop(did, None)
            tomb = {k: v for k, v in e.items() if k not in ("body", "salt")}
            tomb["redacted"] = {"by_seq": by}
            self.entries[s] = tomb
            n += 1
        if n and self.path is not None:
            self._rewrite()
        return n

    def _rewrite(self) -> None:
        import tempfile

        p = self.path
        assert p is not None
        fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                for e in self.entries:
                    f.write(canonical_json(e) + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise


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
    """Check a ledger: schema, sequence, hash chain, references, lineage, licence flags and redactions.

    Detects an edited entry (hash mismatch), a deleted entry (seq gap and
    ``prev_hash`` mismatch), a reordered entry, a correction or decision
    that points to an unknown or later entry, and a bad genesis. Pass
    ``expected_head`` (a hash, or the dict from
    :meth:`ProvenanceLedger.anchor`) to detect a cut at the end.
    P5-03: a source / artifact / context whose licence flags differ from the
    recomputed ones, an artifact input that is unknown or later, a product
    artifact that the product policy does not allow, a decision whose
    licence flags differ from its context's. P5-04: a body digest that does
    not match (``salted-body`` rule), a tombstone that no later redaction
    entry names, a redaction target that is unknown, later or not redactable.
    """
    from fidetype.trust.licence import combine, flag, source_summary

    errors: list[str] = []
    try:
        entries = list(source) if not isinstance(source, (str, os.PathLike)) else read_entries(source)
    except ValueError as e:
        return VerifyResult(False, 0, [str(e)])
    if not entries:
        return VerifyResult(False, 0, ["empty ledger"])
    # Redaction targets named anywhere in the file (a redaction entry itself is never redacted).
    named: dict[int, tuple[int, str]] = {}
    for i, e in enumerate(entries):
        if e.get("kind") == "redaction" and isinstance(e.get("body"), dict):
            for t in e["body"].get("targets", ()):
                if isinstance(t, dict) and isinstance(t.get("seq"), int):
                    named[t["seq"]] = (i, str(t.get("hash")))
    contexts: set[str] = set()
    ctx_lic: dict[str, Any] = {}
    sources: dict[str, Any] = {}
    artifacts: dict[str, Any] = {}
    decisions: dict[str, str] = {}
    proposals: dict[str, str] = {}
    decided: set[str] = set()
    chain_head: dict[str, Any] = {}
    g0 = entries[0].get("body") if isinstance(entries[0].get("body"), dict) else {}
    salted = g0.get("hash_rule") == "salted-body"
    prev = GENESIS_PREV
    for i, e in enumerate(entries):
        tag = f"entry {i}"
        tomb = is_tombstone(e)
        need = {"schema", "seq", "ts", "kind", "prev_hash", "hash"} | (set() if tomb else {"body"})
        missing = need - set(e)
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
        if salted and not tomb and ("salt" not in e or "body_sha256" not in e):
            errors.append(f"{tag}: salt / body_sha256 missing (the ledger uses the salted-body rule)")
        try:
            h = entry_hash(e)
        except (TypeError, ValueError) as ex:
            errors.append(f"{tag}: cannot hash ({ex})")
            h = None
        if h != e["hash"]:
            errors.append(f"{tag}: hash mismatch (entry edited)")
        elif not tomb and "salt" in e and e.get("body_sha256") != body_digest(e["salt"], e["body"]):
            errors.append(f"{tag}: hash mismatch (body edited: body_sha256 differs)")
        if e["kind"] not in KINDS:
            errors.append(f"{tag}: unknown kind {e['kind']!r}")
        if (i == 0) != (e["kind"] == "genesis"):
            errors.append(f"{tag}: genesis must be entry 0 and only entry 0")
        if tomb:
            if i not in named:
                errors.append(f"{tag}: body removed, but no redaction entry names this entry")
            elif named[i][0] <= i or named[i][1] != e["hash"]:
                errors.append(f"{tag}: body removed, but the redaction entry is earlier or names another hash")
            if e["kind"] not in REDACTABLE_KINDS:
                errors.append(f"{tag}: a {e['kind']!r} entry must not be redacted")
            prev = e["hash"]
            continue
        b = e["body"] if isinstance(e["body"], dict) else {}
        k = e["kind"]
        if k == "context":
            cid = b.get("context_id")
            ctx = b.get("context", {}) or {}
            if cid != "ctx-" + content_id(ctx)[:24]:
                errors.append(f"{tag}: context_id does not match the context content")
            contexts.add(cid)
            lin = ctx.get("lineage") if isinstance(ctx, dict) else None
            if lin is not None:
                bad = [a for a in lin if a not in artifacts]
                if bad:
                    errors.append(f"{tag}: lineage names unknown or later artifacts {bad}")
                    ctx_lic[cid] = b.get("licence")
                else:
                    want = combine(artifacts[a] for a in lin)
                    if b.get("licence") != want:
                        errors.append(f"{tag}: context licence flags differ from the lineage")
                    ctx_lic[cid] = want
            else:
                if "licence" in b:
                    errors.append(f"{tag}: context has licence flags but no lineage")
                ctx_lic[cid] = None
        elif k == "source":
            sid, src = b.get("source_id"), b.get("source", {}) or {}
            if sid != "src-" + content_id(src)[:24]:
                errors.append(f"{tag}: source_id does not match the source content")
            want = source_summary(src.get("licence"), (src.get("consent") or {}).get("scope"))
            if b.get("licence") != want:
                errors.append(f"{tag}: source licence flags differ from its licence")
            sources[sid] = want
        elif k == "artifact":
            aid, art = b.get("artifact_id"), b.get("artifact", {}) or {}
            if aid != "art-" + content_id(art)[:24]:
                errors.append(f"{tag}: artifact_id does not match the artifact content")
            ins = list(art.get("derived_from") or [])
            bad = [x for x in ins if x not in sources and x not in artifacts]
            if bad:
                errors.append(f"{tag}: artifact input(s) unknown or later: {bad}")
            parts = [sources.get(x) or artifacts.get(x) for x in ins if x in sources or x in artifacts]
            if art.get("licence") is not None:
                parts.append(source_summary(art["licence"]))
            want = combine(parts) if (ins or art.get("licence") is not None) else source_summary(None)
            if not bad and b.get("licence") != want:
                errors.append(f"{tag}: artifact licence flags differ from its inputs")
            pol = art.get("product_policy", "project")
            if art.get("purpose") == "product" and not want["product_ok"].get(pol, False):
                errors.append(f"{tag}: product artifact {art.get('name')!r} has inputs that the {pol!r} policy "
                              "does not allow (licence rule)")
            artifacts[aid] = want
        elif k == "decision":
            did = b.get("decision_id")
            if did in decisions:
                errors.append(f"{tag}: duplicate decision id {did!r}")
            cid = b.get("context_id")
            if cid not in contexts:
                errors.append(f"{tag}: decision refers to an unknown or later context")
            elif ctx_lic.get(cid) is not None:
                if b.get("licence") != flag(ctx_lic[cid]):
                    errors.append(f"{tag}: decision licence flags differ from its context")
            elif "licence" in b:
                errors.append(f"{tag}: decision has licence flags but its context has no lineage")
            decisions[did] = e["hash"]
        elif k == "correction":
            did = b.get("decision_id")
            if did not in decisions:
                errors.append(f"{tag}: correction refers to an unknown, later or redacted decision {did!r}")
            elif b.get("decision_hash") != decisions[did]:
                errors.append(f"{tag}: decision_hash does not match decision {did!r}")
        elif k == "update":
            errors += _verify_update(tag, b, e["hash"], proposals, decided, chain_head)
        elif k == "redaction":
            for t in b.get("targets", ()):
                s = t.get("seq") if isinstance(t, dict) else None
                if not isinstance(s, int) or not 0 < s < i:
                    errors.append(f"{tag}: redaction target {s!r} is not an earlier entry")
                    continue
                if entries[s].get("hash") != t.get("hash"):
                    errors.append(f"{tag}: redaction target {s} has another hash")
                if entries[s].get("kind") not in REDACTABLE_KINDS:
                    errors.append(f"{tag}: redaction target {s} is a {entries[s].get('kind')!r} entry")
            if b.get("reason") not in REDACTION_REASONS:
                errors.append(f"{tag}: unknown redaction reason {b.get('reason')!r}")
        prev = e["hash"]
    last = entries[-1]
    if expected_head is not None:
        want_h = expected_head["hash"] if isinstance(expected_head, dict) else expected_head
        if last.get("hash") != want_h:
            errors.append("head hash != expected head (entries cut or added at the end)")
    return VerifyResult(not errors, len(entries), errors, last.get("hash"), last.get("seq"))


def _verify_update(tag: str, b: dict, h: str, proposals: dict[str, str], decided: set[str],
                   chain_head: dict[str, Any]) -> list[str]:
    """The rules of one ``update`` entry (P15-02). Updates the running state."""
    errs: list[str] = []
    uid, stage, chain = b.get("update_id"), b.get("stage"), b.get("chain", "default")
    if stage not in UPDATE_STAGES:
        return [f"{tag}: unknown update stage {stage!r}"]
    if stage == "proposed":
        if uid in proposals:
            errs.append(f"{tag}: duplicate update proposal {uid!r}")
        proposals[uid] = h
        return errs
    if uid not in proposals:
        errs.append(f"{tag}: update decision refers to an unknown or later proposal {uid!r}")
    elif b.get("proposal_hash") != proposals[uid]:
        errs.append(f"{tag}: proposal_hash does not match proposal {uid!r}")
    if uid in decided:
        errs.append(f"{tag}: update {uid!r} decided twice")
    decided.add(uid)
    parent, cid = b.get("parent_config_id"), b.get("config_id")
    if parent != chain_head.get(chain):
        errs.append(f"{tag}: parent_config_id does not match the last accepted config_id of chain {chain!r}")
    if stage == "accepted":
        if cid is None or cid == parent:
            errs.append(f"{tag}: an accepted update must give a new config_id")
        chain_head[chain] = cid
    elif cid != parent:
        errs.append(f"{tag}: a rejected update must keep the config_id")
    return errs


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
        live = [e for e in entries if not is_tombstone(e)]
        #: Entries whose body a redaction removed (P5-04).
        self.redacted = [e for e in entries if is_tombstone(e)]
        self.genesis = entries[0]["body"] if entries and "body" in entries[0] else {}
        self.context_entries = {e["body"]["context_id"]: e for e in live if e["kind"] == "context"}
        self.contexts = {cid: e["body"]["context"] for cid, e in self.context_entries.items()}
        self.decisions = {e["body"]["decision_id"]: e for e in live if e["kind"] == "decision"}
        self.sources = {e["body"]["source_id"]: e for e in live if e["kind"] == "source"}
        self.artifacts = {e["body"]["artifact_id"]: e for e in live if e["kind"] == "artifact"}
        self.corrections: dict[str, list[dict]] = defaultdict(list)
        for e in live:
            if e["kind"] == "correction":
                self.corrections[e["body"]["decision_id"]].append(e)

    def lineage(self, decision_id: str) -> dict:
        """The full lineage of one decision (P5-03).

        Returns ``decision`` (entry), ``corrections`` (entries), ``context`` (entry), ``artifacts`` (entries,
        inputs before the artifacts that use them), ``sources`` (entries), ``licence`` (the decision's flags,
        or None without lineage) and ``entries`` (seq, kind, hash of every entry in the lineage, by seq).
        Raises ``KeyError`` for an unknown or redacted decision.
        """
        if decision_id not in self.decisions:
            raise KeyError(f"unknown or redacted decision {decision_id!r}")
        d = self.decisions[decision_id]
        ctx = self.context_entries.get(d["body"]["context_id"])
        order: list[str] = []
        seen: set[str] = set()

        def visit(x: str) -> None:
            if x in seen:
                return
            seen.add(x)
            a = self.artifacts.get(x)
            if a is not None:
                for y in a["body"]["artifact"].get("derived_from", ()):
                    visit(y)
            order.append(x)

        for a in ((ctx or {}).get("body", {}).get("context", {}).get("lineage") or ()):
            visit(a)
        arts = [self.artifacts[x] for x in order if x in self.artifacts]
        srcs = [self.sources[x] for x in order if x in self.sources]
        corr = list(self.corrections.get(decision_id, ()))
        allents = [d, *corr, *([ctx] if ctx else []), *arts, *srcs]
        return {
            "decision": d, "corrections": corr, "context": ctx, "artifacts": arts, "sources": srcs,
            "licence": d["body"].get("licence"),
            "entries": [{"seq": e["seq"], "kind": e["kind"], "hash": e["hash"]}
                        for e in sorted(allents, key=lambda e: e["seq"])],
        }

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
    n_ro = sum(bool((e["body"].get("licence") or {}).get("research_only")) for e in view.decisions.values())
    n_lic = sum("licence" in e["body"] for e in view.decisions.values())
    lines.append(f"- Lineage: {len(view.sources)} sources, {len(view.artifacts)} artifacts; decisions with licence "
                 f"flags {n_lic} of {len(view.decisions)}, research-only {n_ro}.")
    if view.redacted:
        lines.append(f"- Redacted entries (body removed, P5-04): {len(view.redacted)}.")
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


def _short(h: Any) -> str:
    return "—" if not h else f"`{str(h)[:16]}…`"


def lineage_report(
    source: str | os.PathLike | Sequence[dict] | ProvenanceLedger,
    decision_id: str,
    *,
    word: int | None = None,
    expected_head: str | dict | None = None,
) -> str:
    """A Markdown report of the full lineage of one decision (P5-03), from the output back to the data.

    ``word``: a 0-based word index of the shown text; the report then names that word (``store`` mode) and
    its word choice, if any. The report first verifies the whole ledger: a lineage is only as good as the
    chain.
    """
    view = LedgerView(source)
    res = verify(view.entries, expected_head)
    lin = view.lineage(decision_id)
    d = lin["decision"]
    b = d["body"]
    lines = [f"# Lineage of decision `{decision_id}`", ""]
    lines.append(f"- Ledger `{view.genesis.get('ledger_id')}`: chain verification **{'PASS' if res.ok else 'FAIL'}** "
                 f"({res.n_entries} entries, head `{str(res.head_hash)[:16]}…`).")
    for err in res.errors[:10]:
        lines.append(f"  - {err}")
    lic = lin["licence"]
    if lic is None:
        lines.append("- Licence flags: **none** (the context has no recorded lineage).")
    else:
        lines.append(f"- Licence flags: research_only **{lic['research_only']}**, commercial_ok {lic['commercial_ok']}, "
                     f"product_ok project {lic['product_ok'].get('project')} / commercial "
                     f"{lic['product_ok'].get('commercial')}.")
    lines += ["", "## 1. Output", ""]
    shown = b["shown"][0] if b.get("shown") else None
    lines.append(f"- Entry {d['seq']} (`{d['hash'][:16]}…`): action **{b['action']}**, reason: {b.get('reason')}.")
    lines.append(f"- Shown text: {_text(shown)}.")
    if word is not None:
        w = None
        if shown is not None and "text" in shown:
            ws = shown["text"].split()
            w = ws[word] if 0 <= word < len(ws) else None
        wc = next((c for c in b.get("word_choices", ()) if c.get("index") == word), None)
        lines.append(f"- Word {word}: {repr(w) if w is not None else '(text not stored)'}; word choice: "
                     f"{wc if wc is not None else 'none (the word came with the whole text)'}.")
    s = b.get("scores", {})
    lines.append(f"- Scores: p_top1 {_fmt(s.get('p_top1'))}, set size {s.get('set_size')}, guard risk "
                 f"{_fmt(s.get('guard_risk'))}.")
    inp = b.get("input", {})
    lines.append(f"- Input: stream `{str(inp.get('stream_id'))[:16]}…`, frames {inp.get('frame_range')}, "
                 f"t {inp.get('t_range')}, item {inp.get('item_ref')}, subject {inp.get('subject')}.")
    lines += ["", "## 2. Corrections", ""]
    if not lin["corrections"]:
        lines.append("- None.")
    for c in lin["corrections"]:
        cb = c["body"]
        lines.append(f"- Entry {c['seq']}: {cb.get('relation')} by {cb.get('source')}: {_text(cb.get('corrected'))}; "
                     f"changed {cb.get('changed')}; linked to the decision hash "
                     f"{'yes' if cb.get('decision_hash') == d['hash'] else 'NO'}.")
    lines += ["", "## 3. Context (trust configuration)", ""]
    ctx_e = lin["context"]
    if ctx_e is not None:
        ctx = ctx_e["body"]["context"]
        cal, pol = ctx.get("calibration", {}) or {}, ctx.get("policy", {}) or {}
        lines.append(f"- Entry {ctx_e['seq']}: `{ctx_e['body']['context_id']}`; software "
                     f"{(ctx.get('software') or {}).get('package')} {(ctx.get('software') or {}).get('version')}.")
        lines.append(f"- Decoder: {(ctx.get('decoder') or {}).get('name')} {(ctx.get('decoder') or {}).get('version')}; "
                     f"LM {(ctx.get('lm') or {}).get('name')}; adapter {(ctx.get('adapter') or {}).get('name')}.")
        if cal:
            lines.append(f"- Calibration `{cal.get('id')}`: set {cal.get('calibration_set_id')}.")
        if pol:
            lines.append(f"- Policy `{pol.get('version')}`.")
        if ctx.get("trust_config"):
            lines.append(f"- Trust configuration `{ctx['trust_config'].get('id')}`.")
    lines += ["", "## 4. Artifacts (inputs first)", ""]
    if not lin["artifacts"]:
        lines.append("- None recorded.")
    for a in lin["artifacts"]:
        ab, la = a["body"]["artifact"], a["body"]["licence"]
        lines.append(f"- Entry {a['seq']}: **{ab['kind']}** {ab['name']}{' ' + ab['version'] if ab.get('version') else ''} "
                     f"(`{a['body']['artifact_id']}`); sha256 {_short(ab.get('sha256'))}; purpose {ab['purpose']}; "
                     f"from {ab.get('derived_from')}; licences {la['licences']}; research_only {la['research_only']}.")
    lines += ["", "## 5. Data sources", ""]
    if not lin["sources"]:
        lines.append("- None recorded.")
    for sr in lin["sources"]:
        sb, ls = sr["body"]["source"], sr["body"]["licence"]
        extra = f"; consent `{sb['consent']['ref']}` scope {sb['consent']['scope']}" if sb.get("consent") else ""
        lines.append(f"- Entry {sr['seq']}: {sb['name']} (`{sr['body']['source_id']}`); licence **{sb['licence']}**"
                     f"{'; track ' + sb['track'] if sb.get('track') else ''}; url {sb.get('url')}; "
                     f"digest {_short(sb.get('digest'))}; research_only {ls['research_only']}{extra}.")
    lines += ["", "## 6. Entries of this lineage", "", "| seq | kind | hash |", "|---|---|---|"]
    for e in lin["entries"]:
        lines.append(f"| {e['seq']} | {e['kind']} | `{e['hash'][:16]}…` |")
    return "\n".join(lines)


def record_lineage_spec(ledger: ProvenanceLedger, spec: str | os.PathLike | Mapping[str, Any],
                        *, set_default: bool = True) -> dict[str, str]:
    """Write the sources and artifacts of a lineage spec into ``ledger``; return {local name: id}.

    ``spec``: a dict or a JSON / TOML file (schema ``fidetype.lineage-spec/0.1``)::

        schema = "fidetype.lineage-spec/0.1"
        use = ["decoder", "calibration"]          # lineage of the contexts (set_default)

        [sources.t15]
        track = "b2t25-t15"                       # licence, URL, attribution from the track

        [sources.mydata]
        name = "Our sEMG pilot"
        licence = "LicenseRef-fidetype-consented"
        consent = {ref = "cr-2026-0001", scope = ["decode", "train-research"]}

        [artifacts.decoder]
        kind = "weights"
        name = "fidetype-emg-ctc"
        file = "ckpt/model.pt"                    # sha256 computed (relative to the spec file)
        derived_from = ["t15"]                    # local names, defined above
        purpose = "research"

    Artifacts may name earlier artifacts. With ``set_default`` the ``use`` list becomes
    :attr:`ProvenanceLedger.default_lineage`.
    """
    base = Path(".")
    if not isinstance(spec, Mapping):
        path = Path(spec)
        base = path.parent
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".toml":
            import tomllib

            spec = tomllib.loads(text)
        else:
            spec = json.loads(text)
    if spec.get("schema", "fidetype.lineage-spec/0.1") != "fidetype.lineage-spec/0.1":
        raise ValueError(f"unknown lineage spec schema {spec.get('schema')!r}")
    ids: dict[str, str] = {}
    for name, s in (spec.get("sources") or {}).items():
        s = dict(s)
        if "track" in s:
            ids[name] = ledger.record_track_source(s["track"], digest=s.get("digest"))
            continue
        ids[name] = ledger.record_source(
            s.get("name", name), s["licence"], version=s.get("version"), url=s.get("url"), digest=s.get("digest"),
            attribution=s.get("attribution"), consent=s.get("consent"), details=s.get("details"))
    for name, a in (spec.get("artifacts") or {}).items():
        a = dict(a)
        missing = [x for x in a.get("derived_from", ()) if x not in ids]
        if missing:
            raise ValueError(f"artifact {name!r}: unknown input(s) {missing} (define them above it)")
        sha = a.get("sha256")
        if sha is None and a.get("file"):
            sha = file_sha256(base / a["file"])
        ids[name] = ledger.record_artifact(
            a["kind"], a.get("name", name), derived_from=[ids[x] for x in a.get("derived_from", ())],
            version=a.get("version"), sha256=sha, licence=a.get("licence"), purpose=a.get("purpose", "research"),
            product_policy=a.get("product_policy", "project"), details=a.get("details"))
    use = spec.get("use")
    if set_default and use:
        bad = [u for u in use if u not in ids]
        if bad:
            raise ValueError(f"use: unknown name(s) {bad}")
        ledger.set_lineage([ids[u] for u in use])
    return ids


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def _anchor_arg(head: str | None, anchor: str | None) -> str | dict | None:
    if anchor:
        return json.loads(Path(anchor).read_text(encoding="utf-8"))
    return head


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fidetype.trust.provenance")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify", help="verify the hash chain of a ledger")
    v.add_argument("path")
    v.add_argument("--head", default=None, help="expected head hash (detects a cut at the end)")
    v.add_argument("--anchor", default=None, help="anchor JSON file from the 'anchor' command")
    v.add_argument("--public-key", default=None, help="Ed25519 public key (PEM) that checks a signed anchor")
    v.add_argument("--allow-growth", action="store_true",
                   help="accept entries after the anchored head (the anchored entry must still be in the chain)")
    r = sub.add_parser("report", help="print a Markdown audit report")
    r.add_argument("path")
    r.add_argument("--max-items", type=int, default=20)
    r.add_argument("--head", default=None)
    r.add_argument("--anchor", default=None)
    an = sub.add_parser("anchor", help="print (or write) the head of the chain, to keep in a second place")
    an.add_argument("path")
    an.add_argument("--out", default=None)
    an.add_argument("--sign-key-file", default=None, help="Ed25519 private key (PEM file) that signs the anchor")
    an.add_argument("--sign-key-env", default=None,
                    help="environment variable that holds the Ed25519 private key (PEM text)")
    kg = sub.add_parser("keygen", help="write a new Ed25519 key pair for signed anchors (never commit the private key)")
    kg.add_argument("--private", required=True)
    kg.add_argument("--public", required=True)
    li = sub.add_parser("lineage", help="print the full lineage of one decision (Markdown or JSON)")
    li.add_argument("path")
    li.add_argument("decision_id")
    li.add_argument("--word", type=int, default=None)
    li.add_argument("--json", action="store_true")
    li.add_argument("--head", default=None)
    li.add_argument("--anchor", default=None)
    rd = sub.add_parser("redact", help="remove the bodies of decisions (and their corrections); chain stays valid")
    rd.add_argument("path")
    rd.add_argument("--decision", action="append", default=[], help="decision id (repeat)")
    rd.add_argument("--subject-env", default=None,
                    help="environment variable that holds the subject.id to erase (not on the command line)")
    rd.add_argument("--request-ref", required=True, help="opaque reference to the erasure request")
    rd.add_argument("--reason", default="erasure-request", choices=REDACTION_REASONS)
    rd.add_argument("--key-env", default=None, help="environment variable with the ledger's hash key")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    if a.cmd == "keygen":
        from fidetype.trust.anchor import write_key_pair

        try:
            kid = write_key_pair(a.private, a.public)
        except (FileExistsError, RuntimeError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"key pair written; key id {kid}. Keep the private key out of any repository.")
        return 0
    if a.cmd == "verify" and a.anchor:
        from fidetype.trust.anchor import verify_anchored

        pub = Path(a.public_key).read_bytes() if a.public_key else None
        try:
            res = verify_anchored(a.path, _anchor_arg(None, a.anchor), pub, allow_growth=a.allow_growth)
        except (RuntimeError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"{'PASS' if res.ok else 'FAIL'}: {res.n_entries} entries, head seq {res.head_seq}, head {res.head_hash}"
              + ("; anchor signature checked" if pub is not None and res.ok else ""))
        for e in res.errors:
            print("  " + e)
        return 0 if res.ok else 1
    if a.cmd == "verify":
        if a.public_key or a.allow_growth:
            print("--public-key and --allow-growth need --anchor", file=sys.stderr)
            return 2
        res = verify(a.path, _anchor_arg(a.head, a.anchor))
        print(f"{'PASS' if res.ok else 'FAIL'}: {res.n_entries} entries, head seq {res.head_seq}, head {res.head_hash}")
        for e in res.errors:
            print("  " + e)
        return 0 if res.ok else 1
    if a.cmd == "anchor":
        ents = read_entries(a.path)
        res = verify(ents)
        if not res.ok:
            print(f"FAIL: the ledger does not verify ({res.errors[:3]}); no anchor written", file=sys.stderr)
            return 1
        from fidetype.trust.anchor import make_anchor, sign_anchor

        anc = make_anchor(ents)
        if a.sign_key_file or a.sign_key_env:
            pem = (Path(a.sign_key_file).read_bytes() if a.sign_key_file
                   else os.environ.get(a.sign_key_env, "").encode("utf-8"))
            if not pem:
                print(f"environment variable {a.sign_key_env} is empty", file=sys.stderr)
                return 2
            try:
                anc = sign_anchor(anc, pem)
            except (RuntimeError, ValueError) as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
        txt = json.dumps(anc, indent=1)
        if a.out:
            Path(a.out).write_text(txt + "\n", encoding="utf-8")
        print(txt)
        return 0
    if a.cmd == "lineage":
        view = LedgerView(a.path)
        if a.decision_id not in view.decisions:
            print(f"unknown or redacted decision {a.decision_id!r}", file=sys.stderr)
            return 1
        exp = _anchor_arg(a.head, a.anchor)
        if a.json:
            res = verify(view.entries, exp)
            print(json.dumps({"verify": {"ok": res.ok, "errors": res.errors}, **view.lineage(a.decision_id)},
                             indent=1, ensure_ascii=False))
            return 0 if res.ok else 1
        print(lineage_report(view.entries, a.decision_id, word=a.word, expected_head=exp))
        return 0
    if a.cmd == "redact":
        key = os.environ.get(a.key_env, "").encode("utf-8") if a.key_env else None
        ents = read_entries(a.path)
        g = ents[0]["body"]
        if g.get("text_hash_alg") == "hmac-sha256" and not key:
            print("this ledger uses keyed hashes: pass --key-env", file=sys.stderr)
            return 2
        led = ProvenanceLedger(a.path, hash_key=key or None)
        if a.subject_env:
            subj = os.environ.get(a.subject_env)
            if not subj:
                print(f"environment variable {a.subject_env} is empty", file=sys.stderr)
                return 2
            e = led.redact_subject(subj, request_ref=a.request_ref, reason=a.reason)
        elif a.decision:
            e = led.redact_decisions(a.decision, request_ref=a.request_ref, reason=a.reason)
        else:
            print("give --decision or --subject-env", file=sys.stderr)
            return 2
        res = verify(a.path)
        print(f"redacted {e['body']['n']} entries (redaction entry seq {e['seq']}); verify "
              f"{'PASS' if res.ok else 'FAIL'}; new head {res.head_hash}")
        return 0 if res.ok else 1
    print(audit_report(a.path, a.max_items, expected_head=_anchor_arg(a.head, a.anchor)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
