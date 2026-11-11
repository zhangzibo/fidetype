"""Brain-to-Text '25 adapter: phoneme CTC logits -> NeuralTextStream.

Source: Card et al., "An accurate and rapidly calibrating speech
neuroprosthesis", NEJM 2024. Data on Dryad (doi:10.5061/dryad.dncjsxm85,
CC0). This module reads ``t15_copyTask.pkl``: 1,718 copy-task evaluation
trials of participant T15 (intracortical, 256 electrodes, attempted
speech). For each trial the file has the cue sentence, its phonemes, the
online decoder output (phonemes and words) and the RNN logits.

This is our own code. The companion code repository of the dataset has no
licence, so nothing here is copied from it.

Vocabulary (41 classes)
-----------------------
Column order of ``decoded_logits``: 0 = CTC blank, 1 = ``SIL`` (the word
boundary), 2..40 = the 39 ARPAbet phonemes in alphabetical order
(:data:`PHONEMES`, no stress marks). We checked this order on the data:
the CTC greedy path of the logits equals the stored
``decoded_phonemes_raw`` for 1,709 of 1,718 trials, and differs by one
phoneme in the other 9.

Timing
------
The logits are unnormalised, so the adapter applies ``log_softmax``. The
neural features are 20 ms bins. The baseline RNN of the challenge uses
input patches of 14 bins with a stride of 4 bins (``rnn_args.yaml`` of
the challenge repository, read for the values only), so one output frame
is 80 ms. The data agrees: ``speech_duration_s / T`` is at most 0.076 s.
We put frame ``t`` at the end of its input patch,
``(4 t + 14) * 0.02`` s from the start of the trial, and set
``latency = 0`` (a unidirectional GRU uses no later input). These timing
values are **inferred**, not stated in the dataset file.

Safe loading
------------
A pickle can run code when it loads. :func:`safe_load` first scans the
opcodes without loading (:func:`scan_pickle`), then loads with an
Unpickler that allows only the numpy globals in :data:`ALLOWED_GLOBALS`.

Two stream forms
----------------
- :func:`trial_stream` gives the canonical stream: ``vocab`` is
  :data:`VOCAB` (``"<blank>"``, ``"SIL"``, ``"AA"``, ...).
- :func:`to_symbol_stream` gives the same probabilities with one
  character per token (:data:`SYMBOL_VOCAB`; ``SIL`` becomes a space).
  The trust core and the CTC beam join tokens into strings, so they need
  this form. :func:`from_symbol_stream` reverses it.
"""

from __future__ import annotations

import hashlib
import pickle
import pickletools
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from fidetype.streams.spec import NeuralTextStream

# --- vocabulary ---------------------------------------------------------------

#: The 39 ARPAbet phonemes (no stress), in the column order of the logits.
PHONEMES: tuple[str, ...] = tuple(
    "AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG "
    "OW OY P R S SH T TH UH UW V W Y Z ZH".split()
)
BLANK_TOKEN = "<blank>"
SIL_TOKEN = "SIL"
BLANK_ID = 0
SIL_ID = 1
#: The 41 tokens of the canonical stream, in column order.
VOCAB: tuple[str, ...] = (BLANK_TOKEN, SIL_TOKEN, *PHONEMES)
#: Our name for this vocabulary (spec section 3.4 namespace ``phoneme.*``).
VOCAB_ID = "phoneme.arpabet-39-sil"
SYMBOL_VOCAB_ID = "phoneme.arpabet-39-sil.sym1"

_SYMBOL_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLM"
assert len(_SYMBOL_CHARS) == len(PHONEMES)
#: One character per token: blank, space for SIL, then one letter per phoneme.
SYMBOL_VOCAB: tuple[str, ...] = (BLANK_TOKEN, " ", *_SYMBOL_CHARS)
_PH_TO_SYM = {SIL_TOKEN: " ", **{p: c for p, c in zip(PHONEMES, _SYMBOL_CHARS)}}
_SYM_TO_PH = {c: p for p, c in _PH_TO_SYM.items()}

# --- timing ---------------------------------------------------------------------

BIN_S = 0.02
PATCH_SIZE = 14
PATCH_STRIDE = 4
FRAME_PERIOD_S = PATCH_STRIDE * BIN_S  # 0.08 s

#: SHA-256 of ``t15_copyTask.pkl`` as Dryad lists it (version of 2025-07-03).
DRYAD_SHA256 = "7313b9a1102794cfd31455a85d3d16a1aca962aa730a7134d9346fb8f5e165e3"
DRYAD_SIZE = 57_786_348

#: The keys of the copy-task dictionary (each holds one value per trial).
COPYTASK_KEYS = (
    "post_implant_day",
    "vocab_size",
    "cue_sentence",
    "cue_sentence_phonemes",
    "decoded_logits",
    "decoded_phonemes_raw",
    "decoded_sentence",
    "decoded_sentence_phonemes",
    "speech_duration_s",
)


def phonemes_to_symbols(phonemes: Iterable[str]) -> str:
    """Return the symbol string of a phoneme list. ``SIL`` becomes a space.

    Runs of spaces are joined and spaces at the ends are removed, so the
    result has one space between words (the trust core convention).
    """
    out = []
    for p in phonemes:
        if p not in _PH_TO_SYM:
            raise ValueError(f"unknown phoneme {p!r}")
        out.append(_PH_TO_SYM[p])
    return " ".join("".join(out).split())


def symbols_to_phonemes(symbols: str) -> list[str]:
    """Return the phoneme list of a symbol string (a space becomes ``SIL``)."""
    out = []
    for c in symbols:
        if c not in _SYM_TO_PH:
            raise ValueError(f"unknown symbol {c!r}")
        out.append(_SYM_TO_PH[c])
    return out


def normalize_words(text: str) -> str:
    """Lower-case ``text``; keep ``a``-``z``, the apostrophe and single spaces.

    The cue sentences use only these characters (plus upper case), so this
    keeps words such as ``that's`` intact.
    """
    t = "".join(c if ("a" <= c <= "z" or c == "'") else " " for c in text.lower())
    return " ".join(t.split())


# --- safe pickle loading --------------------------------------------------------

#: The only globals the copy-task pickle may reference (module, name).
ALLOWED_GLOBALS: frozenset[tuple[str, str]] = frozenset(
    {
        ("numpy.core.multiarray", "_reconstruct"),
        ("numpy._core.multiarray", "_reconstruct"),
        ("numpy", "ndarray"),
        ("numpy", "dtype"),
        ("numpy.core.multiarray", "scalar"),
        ("numpy._core.multiarray", "scalar"),
    }
)
_RISKY_OPS = {"INST", "OBJ", "NEWOBJ", "NEWOBJ_EX", "EXT1", "EXT2", "EXT4", "PERSID", "BINPERSID"}
_STR_OPS = {"SHORT_BINUNICODE", "BINUNICODE", "UNICODE", "BINUNICODE8", "STRING", "BINSTRING", "SHORT_BINSTRING"}
_GET_OPS = {"GET", "BINGET", "LONG_BINGET"}
_PUT_OPS = {"PUT", "BINPUT", "LONG_BINPUT"}
_NO_PUSH = {"FRAME", "PROTO", "STOP", "POP", "POP_MARK", "MEMOIZE"} | _PUT_OPS


class UnsafePickleError(pickle.UnpicklingError):
    """The pickle references a global or opcode outside the whitelist."""


def scan_pickle(data: bytes) -> dict[str, Any]:
    """Scan pickle bytes without loading them.

    Returns ``{"imports": {"module.name": count}, "opcodes": {...}}``.
    Raises :class:`UnsafePickleError` if an import is not in
    :data:`ALLOWED_GLOBALS`, if a ``STACK_GLOBAL`` cannot be resolved, or
    if a risky opcode (``INST``, ``OBJ``, ``NEWOBJ``, extension or
    persistent-id opcodes) is present.
    """
    ops: dict[str, int] = {}
    imports: dict[str, int] = {}
    memo: dict[int, Any] = {}
    recent: list[Any] = []
    for op, arg, _pos in pickletools.genops(data):
        n = op.name
        ops[n] = ops.get(n, 0) + 1
        key = None
        if n in _STR_OPS:
            recent.append(arg)
        elif n in _GET_OPS:
            recent.append(memo.get(arg))
        elif n == "MEMOIZE":
            memo[len(memo)] = recent[-1] if recent else None
        elif n in _PUT_OPS:
            memo[arg] = recent[-1] if recent else None
        elif n == "GLOBAL":
            mod, _, name = str(arg).partition(" ")
            key = (mod, name)
            recent.append(None)
        elif n == "STACK_GLOBAL":
            a, b = (recent[-2], recent[-1]) if len(recent) >= 2 else (None, None)
            if not (isinstance(a, str) and isinstance(b, str)):
                raise UnsafePickleError("STACK_GLOBAL with operands that the scan cannot resolve")
            key = (a, b)
            recent.append(None)
        elif n not in _NO_PUSH:
            recent.append(None)
        recent = recent[-4:]
        if key is not None:
            if key not in ALLOWED_GLOBALS:
                raise UnsafePickleError(f"pickle imports {key[0]}.{key[1]}, which is not allowed")
            imports[f"{key[0]}.{key[1]}"] = imports.get(f"{key[0]}.{key[1]}", 0) + 1
    risky = sorted(_RISKY_OPS & set(ops))
    if risky:
        raise UnsafePickleError(f"pickle uses risky opcodes {risky}")
    return {"imports": imports, "opcodes": ops}


class RestrictedUnpickler(pickle.Unpickler):
    """An Unpickler that resolves only :data:`ALLOWED_GLOBALS`."""

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) not in ALLOWED_GLOBALS:
            raise UnsafePickleError(f"blocked global {module}.{name}")
        if module.startswith("numpy.core"):
            module = "numpy._core" + module[len("numpy.core") :]
        return super().find_class(module, name)


def safe_load(path: str | PathLike[str], expected_sha256: str | None = None) -> Any:
    """Scan, then load a pickle with :class:`RestrictedUnpickler`.

    If ``expected_sha256`` is given, the file must have that digest.
    """
    data = Path(path).read_bytes()
    if expected_sha256 is not None:
        got = hashlib.sha256(data).hexdigest()
        if got != expected_sha256:
            raise ValueError(f"SHA-256 mismatch: expected {expected_sha256}, got {got}")
    scan_pickle(data)
    import io

    return RestrictedUnpickler(io.BytesIO(data)).load()


# --- trials and streams -----------------------------------------------------------


@dataclass
class CopyTaskTrial:
    """One copy-task evaluation trial. Text fields are ground truth or the
    published decoder output; they never go into a stream."""

    index: int
    post_implant_day: int
    vocab_size: int
    cue_sentence: str
    cue_phonemes: list[str]
    logits: np.ndarray  # (T, 41) float32, unnormalised
    decoded_phonemes_raw: list[str]
    decoded_sentence: str
    decoded_sentence_phonemes: list[str]
    speech_duration_s: float

    @property
    def n_frames(self) -> int:
        return int(self.logits.shape[0])

    @property
    def truth_words(self) -> str:
        """The cue sentence, normalised with :func:`normalize_words`."""
        return normalize_words(self.cue_sentence)

    @property
    def truth_symbols(self) -> str:
        """The cue phonemes as a symbol string (see :func:`phonemes_to_symbols`)."""
        return phonemes_to_symbols(self.cue_phonemes)


def trials_from_dict(d: dict[str, Sequence[Any]]) -> list[CopyTaskTrial]:
    """Build trials from the loaded copy-task dictionary. Checks the keys and shapes."""
    missing = [k for k in COPYTASK_KEYS if k not in d]
    if missing:
        raise ValueError(f"copy-task dict lacks keys {missing}")
    n = len(d["cue_sentence"])
    if any(len(d[k]) != n for k in COPYTASK_KEYS):
        raise ValueError("copy-task lists have different lengths")
    out = []
    for i in range(n):
        lg = np.asarray(d["decoded_logits"][i], dtype=np.float32)
        if lg.ndim != 2 or lg.shape[1] != len(VOCAB):
            raise ValueError(f"trial {i}: logits shape {lg.shape}, expected (T, {len(VOCAB)})")
        out.append(
            CopyTaskTrial(
                index=i,
                post_implant_day=int(d["post_implant_day"][i]),
                vocab_size=int(d["vocab_size"][i]),
                cue_sentence=str(d["cue_sentence"][i]),
                cue_phonemes=[str(p) for p in d["cue_sentence_phonemes"][i]],
                logits=lg,
                decoded_phonemes_raw=[str(p) for p in d["decoded_phonemes_raw"][i]],
                decoded_sentence=str(d["decoded_sentence"][i]),
                decoded_sentence_phonemes=[str(p) for p in d["decoded_sentence_phonemes"][i]],
                speech_duration_s=float(d["speech_duration_s"][i]),
            )
        )
    return out


def load_copytask(path: str | PathLike[str], verify: bool = True) -> list[CopyTaskTrial]:
    """Load ``t15_copyTask.pkl`` safely and return its trials.

    With ``verify``, the file must have the Dryad SHA-256 (:data:`DRYAD_SHA256`).
    """
    d = safe_load(path, DRYAD_SHA256 if verify else None)
    if not isinstance(d, dict):
        raise ValueError("t15_copyTask.pkl must hold a dict")
    return trials_from_dict(d)


def log_softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    m = x.max(axis=1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=1, keepdims=True))


def frame_times(n_frames: int) -> np.ndarray:
    """Time of each output frame: the end of its input patch, in seconds."""
    return (np.arange(n_frames) * PATCH_STRIDE + PATCH_SIZE) * BIN_S


def stream_meta(trial: CopyTaskTrial) -> dict[str, Any]:
    """The ``meta`` of a trial stream (spec section 4 keys). No text, no labels."""
    return {
        "device.modality": "intracortical",
        "device.channel_count": 256,
        "device.invasive": True,
        "device.regulatory_status": "investigational",
        "decoder.name": "card2024-online-rnn",
        "decoder.version": "t15-copytask-online",
        "decoder.causal": True,
        "decoder.lookahead_s": 0.0,
        "decoder.calibration_method": "none",
        "lm.name": "none",
        "user.personalized": True,
        "subject.id": "T15",
        "session.id": f"day{trial.post_implant_day:03d}",
        "language": "en-US",
        "data.derived": True,
        "fidetype.vocab_id": VOCAB_ID,
        "fidetype.trial_index": trial.index,
        "fidetype.timing": "inferred: 80 ms frames, frame time = end of a 14 x 20 ms patch",
        "b2t25.vocab_size": trial.vocab_size,
    }


def trial_stream(trial: CopyTaskTrial) -> NeuralTextStream:
    """Return the canonical NeuralTextStream of one trial (vocab :data:`VOCAB`)."""
    return NeuralTextStream(
        log_probs=log_softmax(trial.logits).astype(np.float32),
        frame_times=frame_times(trial.n_frames),
        vocab=list(VOCAB),
        blank_id=BLANK_ID,
        source="b2t25-copytask",
        meta=stream_meta(trial),
        vocab_type="phoneme",
        frame_period=FRAME_PERIOD_S,
        latency=0.0,
    )


def to_symbol_stream(stream: NeuralTextStream) -> NeuralTextStream:
    """Return ``stream`` with one character per token (:data:`SYMBOL_VOCAB`)."""
    if tuple(stream.vocab) != VOCAB:
        raise ValueError("to_symbol_stream needs a stream with the b2t25 VOCAB")
    meta = dict(stream.meta)
    meta["fidetype.vocab_id"] = SYMBOL_VOCAB_ID
    return NeuralTextStream(
        log_probs=stream.log_probs, frame_times=stream.frame_times, vocab=list(SYMBOL_VOCAB),
        blank_id=stream.blank_id, source=stream.source, meta=meta, vocab_type=stream.vocab_type,
        frame_period=stream.frame_period, latency=stream.latency,
    )


def from_symbol_stream(stream: NeuralTextStream) -> NeuralTextStream:
    """Reverse :func:`to_symbol_stream`."""
    if tuple(stream.vocab) != SYMBOL_VOCAB:
        raise ValueError("from_symbol_stream needs a stream with SYMBOL_VOCAB")
    meta = dict(stream.meta)
    meta["fidetype.vocab_id"] = VOCAB_ID
    return NeuralTextStream(
        log_probs=stream.log_probs, frame_times=stream.frame_times, vocab=list(VOCAB),
        blank_id=stream.blank_id, source=stream.source, meta=meta, vocab_type=stream.vocab_type,
        frame_period=stream.frame_period, latency=stream.latency,
    )
