"""Generic CTC-logits adapter: the frame output of any CTC decoder -> NeuralTextStream.

Most public neural and EMG text decoders end in a CTC output layer: a
``(T, V)`` matrix of scores per output frame (Brain-to-Text '24 / '25
GRU baselines, emg2qwerty, wav2vec2-style models, our own ConvCTC and
lookahead GRU). This module turns that matrix into a valid
NeuralTextStream (spec ``nts-1.0-rc2`` sections 3, 4.2 and 5) with one
call, so a decoder author does not need to read the spec first.

What it adds to :func:`fidetype.writer.make_stream`:

- **Input kinds.** ``logits`` (any real numbers), ``log_probs`` (natural
  log, may be ``-inf``), ``probs`` (in [0, 1]) or ``auto`` (detected per
  matrix, see :func:`detect_input_kind`). FRM-3 normalisation is applied
  or checked.
- **Batch layouts.** ``(T, V)``, ``(B, T, V)`` and ``(T, B, V)`` (the
  PyTorch ``CTCLoss`` order), with per-item lengths, so padded frames
  never reach a stream. Torch tensors are accepted by duck typing
  (``.detach().cpu().numpy()``); torch is not imported.
- **Vocabulary files.** A JSON list, a JSON ``{token: id}`` map (the
  Hugging Face CTC tokenizer ``vocab.json`` form, blank = ``<pad>``,
  word delimiter ``|`` -> space) and ``tokens.txt`` (one token per line,
  or ``token id`` per line as in k2 / icefall / sherpa). These are file
  formats only. No third-party code is used or copied.
- **Timing.** ``frame_period`` and ``t0`` (the time of frame 0), or
  explicit frame times; ``latency`` is the decoder lookahead (spec 5.2)
  and is copied to ``meta["decoder.lookahead_s"]``. Spec MET-5: a
  bounded lookahead is causal with ``latency`` = the window; an offline
  (full-sequence) decoder is ``causal=False`` with no ``latency``.
- **Temperature.** An optional frame temperature ``T``:
  ``log_softmax(x / T)``. A temperature other than 1 is a calibration
  step, so the stream gets ``calibration.applied = true`` and
  ``decoder.calibration_method = "temperature"`` (TR-CALIB).
- **Provenance.** ``meta`` from :func:`fidetype.writer.stream_meta`, the
  adapter name and version, an opaque content-hash ``stream.id`` and an
  optional ``decoder.weights_sha256``.
- **Files and a command line.** ``.npy`` (one matrix) and ``.npz`` (one
  matrix per key) are read with ``allow_pickle=False``. Each output
  stream is checked with the conformance suite::

      python -m fidetype.adapters.ctc_logits logprobs.npz --vocab vocab.json \\
          --frame-period 0.08 --t0 0.28 --modality intracortical \\
          --decoder-name my-gru --decoder-version 1 --out streams/ --level trust-ready

Licence: our own code, Apache-2.0. See ``wiki/concepts/ctc-logits-adapter.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.streams.spec import NORM_TOL, VOCAB_TYPES, NeuralTextStream
from fidetype.writer import MODALITIES, stream_meta

__all__ = [
    "ADAPTER_NAME",
    "INPUT_KINDS",
    "CTCVocab",
    "detect_input_kind",
    "to_log_probs",
    "from_array",
    "from_batch",
    "iter_file",
    "vocab_from_list",
    "vocab_from_json_map",
    "vocab_from_tokens_txt",
    "load_vocab",
    "content_stream_id",
    "main",
]

#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = {
    "id": "ctc-logits", "kind": "decoder-output", "signal": "any", "status": "tested",
    "target": "Any CTC decoder: (T, V) logits, probabilities or log-probabilities (.npy / .npz, batches)",
    "licence": "Code Apache-2.0. No dependency beyond NumPy.",
    "tests": ["tests/test_adapter_ctc_logits.py", "tests/test_conformance.py", "tests/test_adapter_conformance.py"],
    "docs": "wiki/concepts/ctc-logits-adapter.md",
    "support": "replay-only", "transport": ["file", "in-process"],
    "real_data_evidence": ["experiments/2026-11-16-p11-01-emg-decoder/results.md"],
    "test_covers": "CI: synthetic logits, probabilities and padded batches. Real: the output of our "
                   "emg2qwerty decoder (P11-01: 2,445 streams, all trust-ready, local run); the "
                   "pretrained decoders call it on each decode.",
    "limits": "The input must be CTC scores (T, V) with a known vocabulary. It cannot check that the "
              "scores come from the decoder that the header names.",
}

ADAPTER_NAME = "fidetype.adapters.ctc_logits"
INPUT_KINDS = ("auto", "logits", "log_probs", "probs")
LAYOUTS = ("TV", "BTV", "TBV")
#: Blank token names that :func:`vocab_from_tokens_txt` and
#: :func:`vocab_from_list` look for when no blank is given.
BLANK_NAMES = ("<blank>", "<blk>", "<b>", "<eps>", "_", "-")


# --- vocabulary -------------------------------------------------------------------


@dataclass(frozen=True)
class CTCVocab:
    """The output columns of a CTC decoder.

    ``tokens[i]`` is the token of column ``i`` (spec HDR-3, HDR-4).
    ``blank_id`` is the CTC blank column, or ``None`` if the model has no
    blank (HDR-6, HDR-13).
    """

    tokens: tuple[str, ...]
    blank_id: int | None
    vocab_type: str = "char"
    vocab_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tokens:
            raise ValueError("a CTC vocabulary needs at least one token")
        if not all(isinstance(t, str) for t in self.tokens):
            raise ValueError("vocabulary tokens must be strings")
        if len(set(self.tokens)) != len(self.tokens):
            dup = sorted({t for t in self.tokens if self.tokens.count(t) > 1})
            raise ValueError(f"vocabulary tokens must be unique; duplicates: {dup[:5]}")
        if self.blank_id is not None and not 0 <= self.blank_id < len(self.tokens):
            raise ValueError(f"blank_id {self.blank_id} is out of range 0..{len(self.tokens) - 1}")
        if self.vocab_type not in VOCAB_TYPES:
            raise ValueError(f"vocab_type must be one of {VOCAB_TYPES}")

    def __len__(self) -> int:
        return len(self.tokens)


def _resolve_blank(tokens: Sequence[str], blank: int | str | None, guess: bool) -> int | None:
    if blank is None:
        if not guess:
            return None
        for name in BLANK_NAMES:
            if name in tokens:
                return list(tokens).index(name)
        raise ValueError(f"no blank token found (looked for {BLANK_NAMES}); give blank= an index, a token or 'none'")
    if isinstance(blank, str):
        if blank.lower() == "none":
            return None
        if blank in tokens:
            return list(tokens).index(blank)
        if blank.lstrip("-").isdigit():
            return int(blank)
        raise ValueError(f"blank token {blank!r} is not in the vocabulary")
    if isinstance(blank, bool):
        raise ValueError("blank must be an index, a token or None")
    return int(blank)


def vocab_from_list(
    tokens: Sequence[str],
    blank: int | str | None = 0,
    *,
    vocab_type: str = "char",
    vocab_id: str | None = None,
    word_delimiter: str | None = None,
) -> CTCVocab:
    """Build a vocabulary from a token list in column order.

    ``blank`` is a column index, a token string, ``"none"`` / ``None`` (no
    blank class). ``word_delimiter`` (for example ``"|"``) is written as a
    space, the word boundary of the NTS ``char`` convention.
    """
    toks = [str(t) for t in tokens]
    bid = _resolve_blank(toks, blank, guess=False)
    if word_delimiter is not None and word_delimiter in toks:
        if " " in toks:
            raise ValueError(f"vocabulary has both {word_delimiter!r} and ' '")
        toks = [" " if t == word_delimiter else t for t in toks]
    return CTCVocab(tuple(toks), bid, vocab_type, vocab_id)


def vocab_from_json_map(
    mapping: Mapping[str, int],
    blank: int | str | None = "<pad>",
    *,
    word_delimiter: str | None = "|",
    vocab_type: str = "char",
    vocab_id: str | None = None,
) -> CTCVocab:
    """Build a vocabulary from a ``{token: column}`` map.

    This is the ``vocab.json`` form of Hugging Face CTC tokenizers. There
    the CTC blank is the padding token (default ``"<pad>"``) and ``"|"``
    marks a word boundary (written as a space here). The ids must be
    exactly ``0 .. V-1``.
    """
    if not isinstance(mapping, Mapping) or not mapping:
        raise ValueError("the vocabulary map must be a non-empty object")
    ids = {}
    for tok, i in mapping.items():
        if isinstance(i, bool) or not isinstance(i, int):
            raise ValueError(f"id of {tok!r} must be an integer")
        if i in ids:
            raise ValueError(f"tokens {ids[i]!r} and {tok!r} share id {i}")
        ids[i] = str(tok)
    if sorted(ids) != list(range(len(ids))):
        raise ValueError("vocabulary ids must be exactly 0 .. V-1")
    toks = [ids[i] for i in range(len(ids))]
    if isinstance(blank, str) and blank not in toks and blank.lower() != "none" and not blank.lstrip("-").isdigit():
        raise ValueError(f"blank token {blank!r} is not in the vocabulary map")
    return vocab_from_list(toks, blank, vocab_type=vocab_type, vocab_id=vocab_id, word_delimiter=word_delimiter)


def vocab_from_tokens_txt(
    text: str,
    blank: int | str | None = None,
    *,
    vocab_type: str = "char",
    vocab_id: str | None = None,
    word_delimiter: str | None = None,
) -> CTCVocab:
    """Build a vocabulary from ``tokens.txt`` text.

    Two line forms: ``token`` (column = line number) or ``token id``
    (k2 / icefall / sherpa form; the last field is the id). A line that is
    only white space stands for the space token. Without ``blank`` the
    first of :data:`BLANK_NAMES` found is the blank.
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    lines = [ln.rstrip("\r") for ln in lines]
    pairs: list[tuple[str, int]] = []
    with_ids = all(len(ln.split()) >= 2 and ln.split()[-1].isdigit() for ln in lines if ln.strip())
    for n, ln in enumerate(lines):
        if with_ids and ln.strip():
            tok, _, num = ln.rpartition(" ")
            pairs.append((tok if tok.strip() else " ", int(num)))
        elif with_ids:
            raise ValueError(f"line {n + 1}: empty line in a 'token id' file")
        else:
            pairs.append((ln if ln.strip() else " ", n))
    mapping = {}
    for tok, i in pairs:
        if tok in mapping:
            raise ValueError(f"token {tok!r} appears twice")
        mapping[tok] = i
    if sorted(mapping.values()) != list(range(len(mapping))):
        raise ValueError("token ids must be exactly 0 .. V-1")
    toks = [t for t, _ in sorted(mapping.items(), key=lambda kv: kv[1])]
    bid = _resolve_blank(toks, blank, guess=blank is None)
    return vocab_from_list(toks, bid, vocab_type=vocab_type, vocab_id=vocab_id, word_delimiter=word_delimiter)


def load_vocab(
    path: str | PathLike[str],
    blank: int | str | None = None,
    *,
    vocab_type: str = "char",
    vocab_id: str | None = None,
    word_delimiter: str | None = None,
) -> CTCVocab:
    """Load a vocabulary file: ``.json`` (list or map) or text (``tokens.txt``).

    Blank default: index 0 for a JSON list, ``"<pad>"`` for a JSON map,
    a known blank name for ``tokens.txt``. ``word_delimiter`` default:
    ``"|"`` for a JSON map, none otherwise.
    """
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        obj = json.loads(raw)
        if isinstance(obj, list):
            return vocab_from_list(obj, 0 if blank is None else blank, vocab_type=vocab_type, vocab_id=vocab_id,
                                   word_delimiter=word_delimiter)
        if isinstance(obj, dict):
            return vocab_from_json_map(obj, "<pad>" if blank is None else blank, vocab_type=vocab_type,
                                       vocab_id=vocab_id, word_delimiter="|" if word_delimiter is None else word_delimiter)
        raise ValueError("a JSON vocabulary must be a list or an object")
    return vocab_from_tokens_txt(raw, blank, vocab_type=vocab_type, vocab_id=vocab_id, word_delimiter=word_delimiter)


# --- scores -> log-probabilities ------------------------------------------------------


def _as_numpy(x: Any) -> np.ndarray:
    """Return ``x`` as a float64 array. Accepts torch tensors without importing torch."""
    if hasattr(x, "detach") and hasattr(x, "cpu"):
        x = x.detach().cpu()
        if hasattr(x, "float"):
            x = x.float()
        x = x.numpy()
    a = np.asarray(x, dtype=np.float64)
    return a


def _lse_rows(x: np.ndarray) -> np.ndarray:
    m = np.max(x, axis=-1, keepdims=True)
    m = np.where(np.isfinite(m), m, 0.0)
    with np.errstate(divide="ignore"):
        return (m + np.log(np.sum(np.exp(x - m), axis=-1, keepdims=True)))[..., 0]


def _log_softmax(x: np.ndarray) -> np.ndarray:
    return x - _lse_rows(x)[..., None]


def detect_input_kind(x: Any) -> str:
    """Guess the kind of a score matrix: ``log_probs``, ``probs`` or ``logits``.

    - ``log_probs``: no value > 0 and every row log-sum-exps to 0 (FRM-3 tolerance);
    - ``probs``: every value in [0, 1] and every row sums to 1 (same tolerance);
    - ``logits``: anything else.

    An empty matrix gives ``log_probs``.
    """
    a = _as_numpy(x)
    if a.size == 0:
        return "log_probs"
    if np.isnan(a).any() or np.isposinf(a).any():
        raise ValueError("scores must not contain NaN or +inf")
    if np.all(a <= 0) and np.all(np.isfinite(_lse_rows(a))) and np.all(np.abs(_lse_rows(a)) <= NORM_TOL):
        return "log_probs"
    if np.isfinite(a).all() and np.all(a >= 0) and np.all(a <= 1) and np.all(np.abs(a.sum(axis=-1) - 1.0) <= NORM_TOL):
        return "probs"
    return "logits"


def to_log_probs(x: Any, input_kind: str = "auto", temperature: float = 1.0) -> np.ndarray:
    """Convert a ``(..., V)`` score array to normalised natural-log probabilities.

    ``logits`` get ``log_softmax``; ``probs`` get ``log`` (0 -> ``-inf``);
    ``log_probs`` are checked (FRM-3, FRM-4) and renormalised exactly.
    With ``temperature`` T != 1 the result is ``log_softmax(log_probs / T)``.
    """
    if input_kind not in INPUT_KINDS:
        raise ValueError(f"input_kind must be one of {INPUT_KINDS}")
    if isinstance(temperature, bool) or not (math.isfinite(float(temperature)) and float(temperature) > 0):
        raise ValueError("temperature must be a finite number > 0")
    a = _as_numpy(x)
    if a.ndim < 1:
        raise ValueError("scores need at least one dimension")
    if np.isnan(a).any() or np.isposinf(a).any():
        raise ValueError("scores must not contain NaN or +inf")
    kind = detect_input_kind(a) if input_kind == "auto" else input_kind
    if kind == "logits":
        if not np.isfinite(a).all():
            raise ValueError("logits must be finite")
        lp = _log_softmax(a)
    elif kind == "probs":
        if np.any(a < 0) or np.any(a > 1 + NORM_TOL):
            raise ValueError("probs must be in [0, 1]")
        with np.errstate(divide="ignore"):
            lp = np.log(np.clip(a, 0.0, None))
        lse = _lse_rows(lp)
        if a.size and np.any(np.abs(lse) > NORM_TOL):
            raise ValueError("each row of probs must sum to 1 (spec FRM-3); use input_kind='logits' for raw scores")
        lp = lp - lse[..., None]
    else:
        lse = _lse_rows(a)
        if a.size and (np.any(~np.isfinite(lse)) or np.any(np.abs(lse) > NORM_TOL)):
            raise ValueError("each row of log_probs must log-sum-exp to 0 (spec FRM-3); use input_kind='logits'")
        lp = a - lse[..., None]
    if float(temperature) != 1.0 and lp.size:
        with np.errstate(invalid="ignore"):
            lp = _log_softmax(lp / float(temperature))
        lp = np.where(np.isnan(lp), -np.inf, lp)
    return lp


# --- streams --------------------------------------------------------------------------


def content_stream_id(log_probs: np.ndarray, *parts: str) -> str:
    """An opaque, deterministic ``stream.id``: 32 hex characters of a SHA-256.

    It hashes ``parts`` (for example a file digest and a key) and the
    float32 bytes of the matrix. It contains no text from the input.
    """
    h = hashlib.sha256("\x1f".join(("ctc_logits", *parts)).encode("utf-8"))
    h.update(np.ascontiguousarray(log_probs, dtype=np.float32).tobytes())
    return h.hexdigest()[:32]


def sha256_file(path: str | PathLike[str]) -> str:
    """SHA-256 of a file, read in 1 MiB blocks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@dataclass
class DecoderInfo:
    """What the stream says about the decoder (``meta`` keys of spec 3.4)."""

    modality: str
    name: str
    version: str
    causal: bool = True
    language: str = "en"
    weights_sha256: str | None = None
    lm_name: str = "none"
    calibration_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.modality not in MODALITIES:
            raise ValueError(f"modality must be one of {MODALITIES}")


def from_array(
    scores: Any,
    vocab: CTCVocab,
    decoder: DecoderInfo,
    *,
    frame_period: float,
    t0: float | None = None,
    frame_times: Any = None,
    latency: float | None = None,
    input_kind: str = "auto",
    temperature: float = 1.0,
    length: int | None = None,
    source: str | None = None,
    stream_id: str | None = "auto",
    id_parts: Sequence[str] = (),
) -> NeuralTextStream:
    """Turn one ``(T, V)`` score matrix into a validated :class:`NeuralTextStream`.

    - ``frame_period``: seconds between output frames (> 0).
    - ``t0``: time of frame 0, seconds from the start of the input. Default
      ``frame_period`` (frame t is stamped at the end of its frame).
      Ignored if ``frame_times`` is given.
    - ``latency``: the decoder lookahead in seconds (spec 5.2, MET-5).
      A causal decoder gives 0; a decoder with a bounded lookahead window
      stays causal and gives the window. An offline (full-sequence)
      decoder sets ``causal=False`` and gives no latency.
    - ``length``: keep only the first ``length`` frames (drop padding).
    - ``stream_id``: ``"auto"`` (content hash, see :func:`content_stream_id`),
      a string, or ``None`` (no id).
    """
    a = _as_numpy(scores)
    if a.ndim != 2:
        raise ValueError(f"scores must be 2-D (T, V), got shape {a.shape}; use from_batch for 3-D input")
    if a.shape[1] != len(vocab):
        raise ValueError(f"scores have {a.shape[1]} columns but the vocabulary has {len(vocab)} tokens")
    if length is not None:
        if isinstance(length, bool) or not 0 <= int(length) <= a.shape[0]:
            raise ValueError(f"length {length} is out of range 0..{a.shape[0]}")
        a = a[: int(length)]
    if isinstance(frame_period, bool) or not (math.isfinite(float(frame_period)) and float(frame_period) > 0):
        raise ValueError("frame_period must be a finite number > 0")
    if latency is not None and not (math.isfinite(float(latency)) and float(latency) >= 0):
        raise ValueError("latency must be a finite number >= 0")
    if not decoder.causal and latency is not None:
        raise ValueError("an offline (non-causal) decoder omits latency (spec MET-5); a decoder with a bounded "
                         "lookahead window is causal with latency = the window")
    lp = to_log_probs(a, input_kind, temperature)
    T = lp.shape[0]
    if frame_times is not None:
        ft = np.asarray(frame_times, dtype=np.float64).reshape(-1)
        if ft.shape[0] < T:
            raise ValueError(f"frame_times must have at least {T} values, got {ft.shape[0]}")
        ft = ft[:T]
    else:
        start = float(frame_period) if t0 is None else float(t0)
        ft = start + float(frame_period) * np.arange(T)
    calibrated = float(temperature) != 1.0
    extra = dict(decoder.extra)
    extra["fidetype.frame_temperature"] = float(temperature)
    if vocab.vocab_id is not None:
        extra["fidetype.vocab_id"] = vocab.vocab_id
    if decoder.calibration_id is not None:
        extra["decoder.calibration_id"] = decoder.calibration_id
    sid = None
    if stream_id == "auto":
        sid = content_stream_id(lp, decoder.name, decoder.version, *id_parts)
    elif stream_id is not None:
        sid = str(stream_id)
    meta = stream_meta(
        modality=decoder.modality, decoder_name=decoder.name, decoder_version=decoder.version,
        causal=decoder.causal, lookahead_s=latency, language=decoder.language,
        calibration_applied=calibrated, calibration_method="temperature" if calibrated else "none",
        derived=True, lm_name=decoder.lm_name, weights_sha256=decoder.weights_sha256, stream_id=sid,
        adapter_name=ADAPTER_NAME, adapter_version=_FIDETYPE_VERSION, extra=extra,
    )
    return NeuralTextStream(
        log_probs=lp, frame_times=ft, vocab=list(vocab.tokens), blank_id=vocab.blank_id,
        source=source or decoder.name, meta=meta, vocab_type=vocab.vocab_type,
        frame_period=float(frame_period), latency=None if latency is None else float(latency),
    )


def from_batch(
    scores: Any,
    vocab: CTCVocab,
    decoder: DecoderInfo,
    *,
    lengths: Sequence[int] | Any | None = None,
    layout: str = "BTV",
    **kwargs: Any,
) -> list[NeuralTextStream]:
    """Split a padded batch into one stream per item.

    ``layout`` is ``"BTV"`` (batch first) or ``"TBV"`` (time first, the
    PyTorch ``CTCLoss`` order). ``lengths`` gives the valid frames of each
    item; without it every item keeps all frames. Other keyword arguments
    go to :func:`from_array`. Each item gets ``id_parts`` + its batch index.
    """
    if layout not in ("BTV", "TBV"):
        raise ValueError("layout must be 'BTV' or 'TBV'")
    a = _as_numpy(scores)
    if a.ndim != 3:
        raise ValueError(f"a batch must be 3-D, got shape {a.shape}")
    if layout == "TBV":
        a = np.transpose(a, (1, 0, 2))
    B = a.shape[0]
    if lengths is None:
        lens = [a.shape[1]] * B
    else:
        lens = [int(v) for v in np.asarray(_as_numpy(lengths)).reshape(-1)]
        if len(lens) != B:
            raise ValueError(f"lengths has {len(lens)} values for a batch of {B}")
    parts = tuple(kwargs.pop("id_parts", ()))
    return [from_array(a[b], vocab, decoder, length=lens[b], id_parts=(*parts, f"item{b}"), **kwargs)
            for b in range(B)]


def iter_file(
    path: str | PathLike[str],
    vocab: CTCVocab,
    decoder: DecoderInfo,
    **kwargs: Any,
) -> Iterator[tuple[str, NeuralTextStream]]:
    """Yield ``(key, stream)`` for each score matrix of a ``.npy`` or ``.npz`` file.

    The file is read with ``allow_pickle=False``. A ``.npy`` file holds one
    ``(T, V)`` matrix (key ``""``). A ``.npz`` file holds one matrix per
    key, in file order. The ``stream.id`` hashes the file digest and the
    key; the key itself does not go into ``meta`` (it may name a session).
    """
    p = Path(path)
    if p.suffix.lower() not in (".npy", ".npz"):
        raise ValueError(f"unknown score file type {p.suffix!r} (use .npy or .npz)")
    digest = sha256_file(p)
    parts = tuple(kwargs.pop("id_parts", ()))
    if p.suffix.lower() == ".npy":
        yield "", from_array(np.load(p, allow_pickle=False), vocab, decoder, id_parts=(*parts, digest), **kwargs)
        return
    with np.load(p, allow_pickle=False) as z:
        for key in z.files:
            yield key, from_array(z[key], vocab, decoder, id_parts=(*parts, digest, key), **kwargs)


# --- command line ---------------------------------------------------------------------


def _safe_name(key: str, index: int) -> str:
    keep = "".join(c if (c.isalnum() or c in "-_.") else "_" for c in key)[:80]
    return f"{index:05d}-{keep}" if keep else f"{index:05d}"


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m fidetype.adapters.ctc_logits",
                                description="Convert CTC decoder scores (.npy / .npz) to NeuralTextStream JSON Lines.")
    p.add_argument("scores", help=".npy (one (T, V) matrix) or .npz (one matrix per key)")
    p.add_argument("--vocab", required=True, help="vocabulary: .json list, .json {token: id} map, or tokens.txt")
    p.add_argument("--blank", default=None, help="blank column: index, token or 'none' (default: by file type)")
    p.add_argument("--word-delimiter", default=None, help="token to write as a space (default '|' for a JSON map)")
    p.add_argument("--vocab-type", default="char", choices=VOCAB_TYPES)
    p.add_argument("--vocab-id", default=None, help="vocabulary name for meta fidetype.vocab_id")
    p.add_argument("--input", dest="input_kind", default="auto", choices=INPUT_KINDS)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--frame-period", type=float, required=True, help="seconds between output frames")
    p.add_argument("--t0", type=float, default=None, help="time of frame 0 in seconds (default: one frame period)")
    p.add_argument("--latency", type=float, default=None, help="decoder lookahead in seconds (0 = causal, window = bounded lookahead)")
    p.add_argument("--non-causal", action="store_true", help="offline decoder: uses the whole sequence (no --latency, spec MET-5)")
    p.add_argument("--modality", required=True, choices=MODALITIES)
    p.add_argument("--decoder-name", required=True)
    p.add_argument("--decoder-version", required=True)
    p.add_argument("--weights", default=None, help="decoder weights file; its SHA-256 goes into meta")
    p.add_argument("--language", default="en")
    p.add_argument("--source", default=None)
    p.add_argument("--out", required=True, help="output .jsonl (one matrix) or a directory")
    p.add_argument("--level", default="core", choices=("core", "trust-ready", "provenance"),
                   help="conformance level that every stream must reach")
    a = p.parse_args(argv)

    from fidetype.conformance import check_file
    from fidetype.conformance.io import write_jsonl

    blank: int | str | None = a.blank
    vocab = load_vocab(a.vocab, blank, vocab_type=a.vocab_type, vocab_id=a.vocab_id, word_delimiter=a.word_delimiter)
    dec = DecoderInfo(modality=a.modality, name=a.decoder_name, version=a.decoder_version, causal=not a.non_causal,
                      language=a.language, weights_sha256=sha256_file(a.weights) if a.weights else None)
    streams = list(iter_file(a.scores, vocab, dec, frame_period=a.frame_period, t0=a.t0, latency=a.latency,
                             input_kind=a.input_kind, temperature=a.temperature, source=a.source))
    out = Path(a.out)
    single = out.suffix.lower() in (".jsonl", ".ndjson")
    if single and len(streams) != 1:
        p.error(f"--out is one file but the input has {len(streams)} matrices; give a directory")
    if not single:
        out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for i, (key, s) in enumerate(streams):
        target = out if single else out / f"{_safe_name(key, i)}.jsonl"
        write_jsonl(s, target)
        fails = check_file(target).failures(a.level)
        if fails:
            failed += 1
            print(f"FAIL {target}: " + "; ".join(f"{r.check_id}: {r.message}" for r in fails), file=sys.stderr)
    print(f"{len(streams)} stream(s) written to {out}; {len(streams) - failed} reach level {a.level}")
    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
