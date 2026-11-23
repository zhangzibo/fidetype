"""Willett 2021 handwriting BCI adapter: real-time RNN character output -> NeuralTextStream.

Source: Willett, Avansino, Hochberg, Henderson, Shenoy, "High-performance
brain-to-text communication via handwriting", Nature 593:249 (2021).
Data: "Data from: High-performance brain-to-text communication via
handwriting", Dryad doi:10.5061/dryad.wh70rxwmv (version 5), **CC0 1.0**.
We use the identical deposit on Zenodo record 4695519
(``handwritingBCIData.tar.gz``, see :data:`ARCHIVE_SHA256`).

This is our own code (Apache-2.0). The example code of the dataset
(``fwillett/handwritingBCI``) has no licence; nothing is copied from it.
We read only the dataset ``readme.pdf`` and the ``.mat`` files.

Safe loading
------------
Only ``Datasets/<session>/sentences.mat`` is read, with
:func:`scipy.io.loadmat` (MATLAB 5 format: plain arrays, no code). The
archive also holds ``.sh`` scripts and ``.p`` pickles. This module never
runs or unpickles them. scipy is the optional ``[data]`` extra; the
stream functions take plain arrays and need only numpy.

What the file holds (readme.pdf, "Sentences")
---------------------------------------------
- Ten sessions of one participant. Neural data: 192 electrodes (two
  96-channel Utah arrays, hand knob of precentral gyrus), threshold
  crossing counts in 10 ms bins (:data:`BIN_S`).
- One trial = one sentence: a 5 s delay, a go cue
  (``goCueOnsetTimeBin``), writing, then ``sentenceEndTimeBin``.
- Closed-loop trials (condition ``CL ...``) ran the real-time RNN
  decoder. ``rnn_charProbTimeSeries`` (bins x 31) holds its character
  probabilities, ``rnn_newCharTimeSeries`` its "new character" signal
  (threshold 0.3), ``rnn_decodedCharTimes`` the (time bin, char index)
  of each character that the system put on the screen.
  ``rnn_charMapASCII`` maps the 31 columns to characters; ``>`` is the
  space and ``~`` the period.
- Bins and char indices are MATLAB 1-based.

What we checked on the data (2026-11-14, 9 sessions with RNN output)
-------------------------------------------------------------------
- The RNN output changes every 10 bins (100 ms, :data:`RNN_STEP_BINS`).
- Each decoded time bin ``t`` (1-based) is the 0-based row ``t`` of
  ``rnn_charProbTimeSeries``, the first row of a new RNN output; the
  argmax of that row is the decoded character for 100 % of decoded
  characters. So the probabilities of a decoded character are in row
  ``t`` (0-based), at time ``t * BIN_S`` from the first bin.
- All decoded characters fall inside ``[goCue, sentenceEnd]`` of a trial.
- The rows sum to 1 (softmax output, |sum - 1| < 1e-6).

Streams
-------
- :func:`trial_stream`: the canonical stream of one closed-loop trial.
  One frame per character that the real-time system emitted, at the time
  of the RNN output that carried it (seconds from the go cue). ``vocab``
  is :data:`VOCAB` (31 characters; ``>`` -> ``" "``, ``~`` -> ``"."``),
  ``vocab_type="char"``, ``blank_id=None``. The RNN ran causally in real
  time, so ``decoder.causal = true`` and ``latency = 0`` (spec MET-5:
  frame t uses no signal after its time). The RNN was trained to output
  characters about 1 s after the pen movement; that is user delay, not
  lookahead, and the stream does not declare it.
- :func:`to_ctc_stream`: the same frames in a 32-token CTC form (blank
  first) with one blank frame between two characters, for the trust core
  and the CTC beam. :func:`from_ctc_stream` reverses it.

No text and no participant identifier go into ``meta``. The trial is
named by a session ordinal and a trial index only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.streams.spec import NeuralTextStream

# --- dataset constants ----------------------------------------------------------

DRYAD_DOI = "10.5061/dryad.wh70rxwmv"
ZENODO_RECORD = 4695519
LICENCE = "CC0-1.0"
ARCHIVE_NAME = "handwritingBCIData.tar.gz"
ARCHIVE_SIZE = 1_408_201_020
ARCHIVE_SHA256 = "f41ff3577f8e8d0e76c24f61b46b1bc5a36ab329cd027947960c5e29ab7223ac"
DATASET_SLUG = "willett-handwriting-2021"
#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = {
    "id": "willett-handwriting", "kind": "dataset-replay", "signal": "intracortical", "status": "tested",
    "target": "Willett et al. 2021 handwriting BCI: real-time RNN character output", "extra": "data",
    "licence": "Code Apache-2.0. Data CC0. Reads sentences.mat with SciPy (BSD-3-Clause).",
    "tests": ["tests/test_adapter_willett_handwriting.py", "tests/test_conformance.py"],
    "docs": "wiki/entities/willett-handwriting-2021.md",
    "support": "replay-only", "transport": ["dataset"],
    "real_data_evidence": ["experiments/2026-11-16-p6-02-scorer/results.md"],
    "test_covers": "CI: synthetic sessions. Real: sentences.mat of the public archive (SHA-256 "
                   "pinned) in the benchmark baselines (local).",
    "limits": "Replays recorded real-time RNN output of one participant (T5). The RNN weights have no"
              " hash (PV-WEIGHTS fails).",
}

ADAPTER_NAME = "fidetype.adapters.willett_handwriting"

BIN_S = 0.01
RNN_STEP_BINS = 10
N_CHANNELS = 192
NEW_CHAR_THRESHOLD = 0.3

#: Column order of ``rnn_charProbTimeSeries`` (``rnn_charMapASCII``).
CHAR_MAP_ASCII = "abcdefghijklmnopqrstuvwxyz>,'~?"
_TOKEN_OF = {">": " ", "~": "."}
#: The 31 tokens of the canonical stream, in column order.
VOCAB: tuple[str, ...] = tuple(_TOKEN_OF.get(c, c) for c in CHAR_MAP_ASCII)
VOCAB_ID = "char.willett2021-31"
CTC_BLANK = "<blank>"
CTC_VOCAB: tuple[str, ...] = (CTC_BLANK, *VOCAB)
CTC_VOCAB_ID = "char.willett2021-31.ctc"

#: Default mass of the blank on a character frame and of the 31 characters
#: on a gap frame (CTC form). Same values as the Toronto sEMG adapter.
CHAR_FRAME_BLANK = 1e-3
GAP_FRAME_NONBLANK = 1e-4

#: Variables of ``sentences.mat`` that the adapter reads (never the neural cube).
SENTENCE_VARS = (
    "sentenceCondition",
    "excludedSentences",
    "goCueOnsetTimeBin",
    "sentenceEndTimeBin",
    "sentenceBlockNums",
    "intendedText",
    "rnn_charProbTimeSeries",
    "rnn_newCharTimeSeries",
    "rnn_decodedCharTimes",
    "rnn_decodedText",
    "rnn_charMapASCII",
)


def ascii_to_text(s: str) -> str:
    """Dataset string (``>`` = space, ``~`` = period) -> plain text."""
    return "".join(_TOKEN_OF.get(c, c) for c in s)


# --- session data -----------------------------------------------------------------


@dataclass
class SentenceSession:
    """The decoder-output part of one ``sentences.mat``. Bins are 1-based."""

    conditions: list[str]
    excluded: np.ndarray  # (S,) bool
    go_bin: np.ndarray  # (S,) int64, 1-based
    end_bin: np.ndarray  # (S,) int64, 1-based
    block: np.ndarray  # (S,) int64
    char_probs: np.ndarray  # (N, 31) float32; zero rows where no decoder ran
    new_char: np.ndarray  # (N,) float32
    decoded_times: np.ndarray  # (K,) int64, 1-based bins
    decoded_ids: np.ndarray  # (K,) int64, 1-based column indices
    intended_text: list[str]  # ground truth: never goes into a stream
    decoded_text: list[str]  # online output text: never goes into meta

    @property
    def n_trials(self) -> int:
        return len(self.conditions)

    @property
    def has_rnn(self) -> bool:
        return self.char_probs.size > 0

    def is_closed_loop(self, i: int) -> bool:
        return self.conditions[i].startswith("CL")

    def closed_loop_trials(self, include_excluded: bool = False) -> list[int]:
        if not self.has_rnn:
            return []
        return [i for i in range(self.n_trials)
                if self.is_closed_loop(i) and (include_excluded or not self.excluded[i])]


def _cellstr(a: Any) -> list[str]:
    out = []
    for c in np.asarray(a, dtype=object).reshape(-1):
        c = np.asarray(c)
        out.append(str(c.reshape(-1)[0]) if c.size else "")
    return out


def _ivec(a: Any) -> np.ndarray:
    return np.asarray(a).reshape(-1).astype(np.int64)


def session_from_dict(d: Mapping[str, Any]) -> SentenceSession:
    """Build a :class:`SentenceSession` from the arrays of ``sentences.mat``.

    ``d`` maps the names of :data:`SENTENCE_VARS` to arrays (as
    :func:`scipy.io.loadmat` returns them, or plain lists). Checks the
    shapes and the character map.
    """
    conds = _cellstr(d["sentenceCondition"])
    S = len(conds)
    cp = np.asarray(d["rnn_charProbTimeSeries"], dtype=np.float32)
    if cp.size == 0:
        cp = np.zeros((0, len(VOCAB)), np.float32)
    if cp.ndim != 2 or cp.shape[1] != len(VOCAB):
        raise ValueError(f"rnn_charProbTimeSeries must be (N, {len(VOCAB)}), got {cp.shape}")
    cmap = d.get("rnn_charMapASCII")
    if cmap is not None and np.asarray(cmap).size:
        got = "".join(str(x) for x in np.asarray(cmap).reshape(-1))
        if got != CHAR_MAP_ASCII:
            raise ValueError(f"unexpected rnn_charMapASCII {got!r}")
    nc = np.asarray(d.get("rnn_newCharTimeSeries", np.zeros(0)), dtype=np.float32).reshape(-1)
    dct = np.asarray(d.get("rnn_decodedCharTimes", np.zeros((0, 2))))
    dct = dct.reshape(-1, 2).astype(np.int64) if dct.size else np.zeros((0, 2), np.int64)
    if len(dct) and (dct[:, 1].min() < 1 or dct[:, 1].max() > len(VOCAB)):
        raise ValueError("rnn_decodedCharTimes has a char index out of 1..31")
    if len(dct) and cp.shape[0] and (dct[:, 0].min() < 1 or dct[:, 0].max() >= cp.shape[0]):
        raise ValueError("rnn_decodedCharTimes has a time bin out of range")
    dec_txt = _cellstr(d["rnn_decodedText"]) if np.asarray(d.get("rnn_decodedText", [])).size else [""] * S
    sess = SentenceSession(
        conditions=conds,
        excluded=_ivec(d["excludedSentences"]).astype(bool),
        go_bin=_ivec(d["goCueOnsetTimeBin"]),
        end_bin=_ivec(d["sentenceEndTimeBin"]),
        block=_ivec(d["sentenceBlockNums"]),
        char_probs=cp,
        new_char=nc,
        decoded_times=dct[:, 0].copy(),
        decoded_ids=dct[:, 1].copy(),
        intended_text=[ascii_to_text(s) for s in _cellstr(d["intendedText"])],
        decoded_text=[ascii_to_text(s) for s in dec_txt],
    )
    for name in ("excluded", "go_bin", "end_bin", "block"):
        if len(getattr(sess, name)) != S:
            raise ValueError(f"{name} has {len(getattr(sess, name))} values for {S} sentences")
    if len(sess.decoded_text) != S:
        raise ValueError("rnn_decodedText does not have one entry per sentence")
    if np.any(sess.end_bin < sess.go_bin):
        raise ValueError("a sentence ends before its go cue")
    return sess


def load_sentences(path: str | PathLike[str], max_bytes: int = 400_000_000) -> SentenceSession:
    """Read ``sentences.mat`` with :func:`scipy.io.loadmat` (MATLAB 5 only).

    Reads only :data:`SENTENCE_VARS` (not the neural cube). ``max_bytes``
    limits the file size (untrusted input). Needs scipy (``[data]`` extra).
    """
    from scipy.io import loadmat  # optional dependency

    p = Path(path)
    if p.suffix.lower() != ".mat":
        raise ValueError(f"not a .mat file: {p.name}")
    if p.stat().st_size > max_bytes:
        raise ValueError(f"file too large ({p.stat().st_size} bytes)")
    d = loadmat(p, variable_names=list(SENTENCE_VARS))
    missing = [k for k in ("sentenceCondition", "excludedSentences", "goCueOnsetTimeBin", "sentenceEndTimeBin",
                           "sentenceBlockNums", "intendedText", "rnn_charProbTimeSeries") if k not in d]
    if missing:
        raise ValueError(f"{p.name}: missing variables {missing}")
    d.setdefault("rnn_decodedText", np.zeros((0, 0)))
    return session_from_dict(d)


def list_session_files(root: str | PathLike[str]) -> list[Path]:
    """``Datasets/*/sentences.mat`` under ``root``, sorted by folder name."""
    r = Path(root)
    if (r / "Datasets").is_dir():
        r = r / "Datasets"
    return sorted(r.glob("*/sentences.mat"), key=lambda p: p.parent.name)


# --- streams ------------------------------------------------------------------------


def _log_norm(p: np.ndarray, floor: float = 1e-30) -> np.ndarray:
    lp = np.log(np.maximum(np.asarray(p, dtype=np.float64), floor))
    m = lp.max(axis=1, keepdims=True)
    return lp - m - np.log(np.exp(lp - m).sum(axis=1, keepdims=True))


def opaque_stream_id(*parts: Any) -> str:
    """Deterministic opaque ``stream.id``: SHA-256 of the parts, 32 hex characters."""
    return hashlib.sha256("/".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _licence_meta(licence: str) -> dict[str, Any]:
    """``data.licence`` and ``data.research_only`` of the dataset (FEP-0010, NTS 1.0 RC4 amendment 6)."""
    from fidetype.trust.licence import licence_meta

    return licence_meta(licence)


def stream_meta(
    session_index: int | None = None,
    trial_index: int | None = None,
    condition: str | None = None,
    excluded: bool | None = None,
    stream_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``meta`` of a trial stream (spec 3.4 keys). No text, no participant id.

    ``fidetype.replay`` names the dataset and the trial by ordinals only.
    The real-time RNN weights are not in the deposit, so there is no
    ``decoder.weights_sha256`` (the stream reaches ``trust-ready``, not
    ``provenance``).
    """
    replay: dict[str, Any] = {"dataset": DATASET_SLUG, "doi": DRYAD_DOI, "licence": LICENCE}
    if session_index is not None:
        replay["session_index"] = int(session_index)
    if trial_index is not None:
        replay["trial_index"] = int(trial_index)
    if condition is not None:
        replay["condition"] = condition
    if excluded is not None:
        replay["excluded"] = bool(excluded)
    m: dict[str, Any] = {
        "device.modality": "intracortical",
        "device.model": "two 96-channel Utah arrays; threshold crossings in 10 ms bins",
        "device.channel_count": N_CHANNELS,
        "device.invasive": True,
        "device.regulatory_status": "investigational",
        "implant.array_type": "utah",  # modality keys: NTS 1.0 RC4 MET-11 (FEP-0009)
        "implant.array_count": 2,
        "implant.features": ["threshold_crossings"],
        "implant.bin_s": 0.01,
        "implant.areas": ["precentral gyrus (hand knob)"],
        "decoder.name": "willett2021-realtime-rnn",
        "decoder.version": "dryad-v5",
        "decoder.causal": True,
        "decoder.lookahead_s": 0.0,
        "decoder.calibration_method": "none",
        "adapter.name": ADAPTER_NAME,
        "adapter.version": _FIDETYPE_VERSION,
        "lm.name": "none",
        "user.personalized": True,
        "calibration.applied": False,
        "language": "en",
        "data.derived": True,
        **_licence_meta(LICENCE),  # data.licence, data.research_only: FEP-0010 (MET-12)
        "fidetype.vocab_id": VOCAB_ID,
        "fidetype.timing": "emitted-char: one frame per character the real-time system emitted; time = RNN output "
                           "row that carried it, seconds from the go cue (10 ms bins, RNN step 100 ms)",
        "fidetype.replay": replay,
    }
    if stream_id is not None:
        m["stream.id"] = stream_id
    if extra:
        m.update(extra)
    return m


def char_stream(
    char_probs: np.ndarray,
    frame_times: Sequence[float],
    meta: dict[str, Any] | None = None,
    source: str = DATASET_SLUG,
) -> NeuralTextStream:
    """One frame per emitted character over :data:`VOCAB` (probabilities in)."""
    p = np.asarray(char_probs, dtype=np.float64).reshape(-1, len(VOCAB))
    return NeuralTextStream(
        log_probs=_log_norm(p).astype(np.float32) if len(p) else np.zeros((0, len(VOCAB)), np.float32),
        frame_times=np.asarray(frame_times, dtype=np.float64),
        vocab=list(VOCAB),
        blank_id=None,
        source=source,
        meta=dict(meta) if meta is not None else stream_meta(),
        vocab_type="char",
        latency=0.0,
    )


def trial_frames(sess: SentenceSession, i: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The emitted characters of trial ``i``: (probability rows, times from go cue, char ids 0-based)."""
    if not sess.has_rnn:
        raise ValueError("this session has no real-time decoder output")
    g, e = int(sess.go_bin[i]), int(sess.end_bin[i])
    m = (sess.decoded_times >= g) & (sess.decoded_times <= e)
    t = sess.decoded_times[m]
    rows = sess.char_probs[t]  # 0-based row t = first row of the RNN output (see module doc)
    times = (t - (g - 1)) * BIN_S
    return rows, times.astype(np.float64), sess.decoded_ids[m] - 1


def trial_stream(sess: SentenceSession, i: int, session_index: int | None = None) -> NeuralTextStream:
    """The canonical stream of closed-loop trial ``i`` (see the module doc)."""
    if not sess.is_closed_loop(i):
        raise ValueError(f"trial {i} is open-loop ({sess.conditions[i]!r}): no decoder output")
    rows, times, _ = trial_frames(sess, i)
    sid = opaque_stream_id(DATASET_SLUG, session_index, i)
    meta = stream_meta(session_index, i, sess.conditions[i], bool(sess.excluded[i]), stream_id=sid)
    return char_stream(rows, times, meta)


def iter_streams(
    paths: Sequence[str | PathLike[str]],
    include_excluded: bool = False,
) -> Iterator[tuple[NeuralTextStream, list[str]]]:
    """Yield (stream, truth texts) for every closed-loop trial of the files.

    The session ordinal is the position of the file in ``paths``. The
    truth texts (intended and decoded text) are for leakage checks and
    scoring only.
    """
    for k, p in enumerate(paths):
        sess = load_sentences(p)
        for i in sess.closed_loop_trials(include_excluded):
            yield trial_stream(sess, i, k), [sess.intended_text[i], sess.decoded_text[i]]


def greedy_text(stream: NeuralTextStream) -> str:
    """Per-frame argmax of a canonical stream (= the text the system emitted)."""
    if tuple(stream.vocab) != VOCAB:
        raise ValueError("greedy_text needs a stream with the Willett VOCAB")
    return "".join(VOCAB[j] for j in np.argmax(stream.log_probs, axis=1))


def to_ctc_stream(
    stream: NeuralTextStream,
    char_blank: float = CHAR_FRAME_BLANK,
    gap_nonblank: float = GAP_FRAME_NONBLANK,
) -> NeuralTextStream:
    """The 32-token CTC form: blank first; a blank frame between two characters.

    Frame 2k is character k (31 probabilities times ``1 - char_blank``,
    blank = ``char_blank``). Frame 2k+1 is a blank frame at the midpoint
    of characters k and k+1 (blank = ``1 - gap_nonblank``). CTC greedy
    decoding of the result equals :func:`greedy_text`.
    """
    if tuple(stream.vocab) != VOCAB:
        raise ValueError("to_ctc_stream needs a stream with the Willett VOCAB")
    if not (0 < char_blank < 1 and 0 < gap_nonblank < 1):
        raise ValueError("char_blank and gap_nonblank must be in (0, 1)")
    K, V = stream.n_frames, len(CTC_VOCAB)
    T = max(0, 2 * K - 1)
    lp = np.empty((T, V), dtype=np.float64)
    times = np.empty(T, dtype=np.float64)
    lp[0::2, 0] = np.log(char_blank)
    lp[0::2, 1:] = stream.log_probs.astype(np.float64) + np.log1p(-char_blank)
    if K > 1:
        lp[1::2, 0] = np.log1p(-gap_nonblank)
        lp[1::2, 1:] = np.log(gap_nonblank / (V - 1))
        ft = stream.frame_times
        times[1::2] = 0.5 * (ft[:-1] + ft[1:])
    times[0::2] = stream.frame_times
    meta = dict(stream.meta)
    meta["fidetype.vocab_id"] = CTC_VOCAB_ID
    meta["fidetype.ctc_form"] = {"from": VOCAB_ID, "char_blank": char_blank, "gap_nonblank": gap_nonblank}
    return NeuralTextStream(
        log_probs=lp.astype(np.float32), frame_times=times, vocab=list(CTC_VOCAB), blank_id=0,
        source=stream.source, meta=meta, vocab_type="char", latency=stream.latency,
    )


def from_ctc_stream(stream: NeuralTextStream) -> NeuralTextStream:
    """Reverse :func:`to_ctc_stream` (renormalises the character frames)."""
    if tuple(stream.vocab) != CTC_VOCAB or stream.blank_id != 0:
        raise ValueError("from_ctc_stream needs a 32-token Willett CTC stream")
    if stream.n_frames % 2 != 1 and stream.n_frames != 0:
        raise ValueError("a Willett CTC stream has an odd number of frames")
    rows = np.exp(stream.log_probs[0::2, 1:].astype(np.float64))
    meta = dict(stream.meta)
    meta.pop("fidetype.ctc_form", None)
    meta["fidetype.vocab_id"] = VOCAB_ID
    return char_stream(rows, stream.frame_times[0::2], meta, stream.source)
