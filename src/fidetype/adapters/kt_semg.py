"""KT-sEMG adapter: forearm sEMG during natural typing -> NeuralTextStream.

Source: Crouch, Zheng, Eggleston, "Natural Typing Recognition via Surface
Electromyography", arXiv:2109.10743 (Nokia Bell Labs). Data: "KT-sEMG
(Keyboard Typing via Surface Electromyography)", Harvard Dataverse
doi:10.7910/DVN/AV6XIR, version 1.1, copyright 2021 Nokia, **CC BY 4.0**.
88 files: ``README.txt`` and 29 runs.

This is our own code (Apache-2.0). No code comes with the dataset.

Data layout (per run ``N``; README.txt and our checks)
------------------------------------------------------
- ``runN.csv``: tab-separated, one header line (``Time`` and 32 channel
  names: ``i1 1`` ... ``i2b 8``), then one row per sample at 2000 Hz
  (16 channels per forearm). The ``Time`` column is printed with 6
  significant digits, so it loses resolution after 100 s; the adapter
  uses ``row index / 2000`` instead (:func:`read_emg_csv`).
- ``runN_keys.txt``: one line per key press, ``<char> <unix time>``
  (seconds, microsecond digits). The char is the typed character: a
  space for the space bar, upper case for shifted letters, ``\\x08`` for
  Backspace and ``\\r`` (sometimes ``\\r\\n``) for Enter.
- ``runN_ts.txt``: the start of the EMG recording as a local wall-clock
  time without a zone, ``YYYY-MM-DD hh:mm:ss.mmm``.

Alignment (inferred, not stated in the dataset)
-----------------------------------------------
Key time in the recording = unix time - start. The start has no time
zone, so :func:`infer_utc_offset_hours` tries whole-hour UTC offsets and
keeps the one that puts the key presses inside the recording. On the
runs we checked this is UTC-4 (US daylight time) or UTC-5 (standard
time), and every key press then falls inside the recording.

Streams
-------
The dataset has no decoder output. A replay stream comes from a decoder
that classifies one EMG window per key press (oracle key timing from the
key log, as in the Toronto sEMG adapter). :func:`keypress_stream` makes
one frame per key press, ``vocab_type="key"``, vocabulary
:data:`KEY_VOCAB` (32 W3C ``KeyboardEvent.code`` names), ``blank_id=None``.
Key presses outside the vocabulary (digits, some punctuation; < 0.1 %)
still get a frame: the decoder runs at every key press.

:class:`LdaKeyDecoder` is a small reference decoder (shrinkage LDA on
log-RMS window features, numpy only). It exists so that real-data replay
streams can be made and validated without a GPU. It is a baseline, not a
result.

No text and no participant identifier go into ``meta``.
"""

from __future__ import annotations

import hashlib
import re
import warnings
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.streams.spec import NeuralTextStream

# --- dataset constants ----------------------------------------------------------

DATAVERSE_DOI = "10.7910/DVN/AV6XIR"
DATAVERSE_VERSION = "1.1"
LICENCE = "CC-BY-4.0"
ATTRIBUTION = "KT-sEMG dataset, copyright 2021 Nokia, CC BY 4.0"
DATASET_SLUG = "kt-semg"
#: Catalogue metadata (P14-42): read by fidetype.adapters.registry -> docs/adapters.md.
ADAPTER_INFO = {
    "id": "kt-semg", "kind": "dataset-replay", "signal": "emg", "status": "tested",
    "target": "KT-sEMG (Nokia, forearm sEMG during natural typing): key presses, LDA reference decoder",
    "licence": "Code Apache-2.0. Data CC BY 4.0 (copyright 2021 Nokia).",
    "tests": ["tests/test_adapter_kt_semg.py", "tests/test_conformance.py"], "docs": "wiki/entities/kt-semg-dataset.md",
}

ADAPTER_NAME = "fidetype.adapters.kt_semg"
SAMPLE_RATE_HZ = 2000.0
N_CHANNELS = 32

# --- vocabulary -----------------------------------------------------------------

LETTERS = "abcdefghijklmnopqrstuvwxyz"
#: The 32 key classes: W3C UI Events ``KeyboardEvent.code`` names.
KEY_VOCAB: tuple[str, ...] = (
    *(f"Key{c.upper()}" for c in LETTERS), "Space", "Period", "Comma", "Quote", "Backspace", "Enter",
)
KEY_VOCAB_ID = "key.w3c-code.az-space-punct-edit-32"

_CHAR_CODE: dict[str, str] = {
    **{c: f"Key{c.upper()}" for c in LETTERS},
    **{c.upper(): f"Key{c.upper()}" for c in LETTERS},
    " ": "Space", ".": "Period", ",": "Comma", "'": "Quote",
    "\x08": "Backspace", "\r": "Enter", "\n": "Enter",
    ";": "Semicolon", "/": "Slash", "[": "BracketLeft", "^": "Digit6",
    **{str(d): f"Digit{d}" for d in range(10)},
}
_CODE_INDEX = {c: i for i, c in enumerate(KEY_VOCAB)}


def key_code(char: str) -> str | None:
    """W3C ``KeyboardEvent.code`` of a logged character, or None if unknown."""
    return _CHAR_CODE.get(char)


def key_class(char: str) -> int | None:
    """Index of a logged character in :data:`KEY_VOCAB`, or None (not a class)."""
    code = _CHAR_CODE.get(char)
    return _CODE_INDEX.get(code) if code is not None else None


# --- files ------------------------------------------------------------------------

_KEY_RE = re.compile(rb"(.?) (\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class KeyPress:
    """One logged key press. ``char`` is ground truth: it never goes into a stream."""

    unix_s: float
    char: str

    @property
    def code(self) -> str | None:
        return key_code(self.char)


def parse_keys(data: bytes) -> list[KeyPress]:
    """Parse the bytes of ``runN_keys.txt``.

    Each record is ``<char> <unix time>`` and ends with ``\\n``. An Enter
    key logged as ``\\r\\n`` splits its record over two lines; such a
    line pair is joined back into one Enter press. Other lines are
    skipped.
    """
    out: list[KeyPress] = []
    lines = data.split(b"\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.endswith(b"\r") and len(line) > 1:
            line = line[:-1]  # CRLF line end
        m = _KEY_RE.fullmatch(line)
        if m is None and line == b"\r" and i + 1 < len(lines):
            m2 = re.fullmatch(rb" (\d+(?:\.\d+)?)\r?", lines[i + 1])
            if m2:
                out.append(KeyPress(float(m2.group(1)), "\r"))
                i += 2
                continue
        if m is not None:
            ch = m.group(1).decode("latin-1")
            if ch:
                out.append(KeyPress(float(m.group(2)), ch))
        i += 1
    out.sort(key=lambda k: k.unix_s)
    return out


def read_keys(path: str | PathLike[str], max_bytes: int = 50_000_000) -> list[KeyPress]:
    p = Path(path)
    if p.stat().st_size > max_bytes:
        raise ValueError(f"key file too large ({p.stat().st_size} bytes)")
    return parse_keys(p.read_bytes())


def parse_start_time(text: str) -> datetime:
    """``runN_ts.txt`` content -> naive local datetime."""
    s = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"not a start time: {s[:40]!r}")


def read_start_time(path: str | PathLike[str]) -> datetime:
    p = Path(path)
    if p.stat().st_size > 1000:
        raise ValueError("start-time file too large")
    return parse_start_time(p.read_text(encoding="ascii", errors="replace"))


def infer_utc_offset_hours(
    start_local: datetime,
    key_unix: Sequence[float],
    duration_s: float,
    candidates: Sequence[int] = tuple(range(-12, 15)),
    min_inside: float = 0.95,
) -> int:
    """The whole-hour UTC offset that puts the most key presses inside the recording.

    Raises ``ValueError`` if no offset puts at least ``min_inside`` of the
    key presses into ``[0, duration_s]``, or if two offsets tie.
    """
    k = np.asarray(key_unix, dtype=np.float64)
    if k.size == 0:
        raise ValueError("no key presses")
    scores = []
    for h in candidates:
        start = start_local.replace(tzinfo=timezone(timedelta(hours=h))).timestamp()
        rel = k - start
        scores.append((float(np.mean((rel >= 0) & (rel <= duration_s))), h))
    scores.sort(reverse=True)
    best, h = scores[0]
    if best < min_inside:
        raise ValueError(f"no UTC offset puts {min_inside:.0%} of the key presses in the recording (best {best:.1%})")
    if len(scores) > 1 and scores[1][0] == best:
        raise ValueError("two UTC offsets fit equally well")
    return h


def start_unix(start_local: datetime, utc_offset_hours: int) -> float:
    return start_local.replace(tzinfo=timezone(timedelta(hours=utc_offset_hours))).timestamp()


@dataclass
class EmgRecording:
    emg: np.ndarray  # (N, 32) float32, units as in the file
    channel_names: list[str]
    sample_rate: float = SAMPLE_RATE_HZ

    @property
    def n_samples(self) -> int:
        return int(self.emg.shape[0])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate


def read_emg_csv(
    path: str | PathLike[str],
    max_bytes: int = 2_000_000_000,
    chunk_bytes: int = 64 << 20,
) -> EmgRecording:
    """Read ``runN.csv`` (header + tab-separated numbers) in chunks.

    Drops the ``Time`` column (see the module doc). Raises ``ValueError``
    on a bad header, a row with the wrong number of fields, or a file
    larger than ``max_bytes`` (untrusted input).
    """
    p = Path(path)
    if p.stat().st_size > max_bytes:
        raise ValueError(f"file too large ({p.stat().st_size} bytes)")
    parts: list[np.ndarray] = []
    with open(p, "rb") as f:
        header = f.readline().rstrip(b"\r\n").split(b"\t")
        names = [h.decode("ascii", errors="replace").strip() for h in header]
        if len(names) != N_CHANNELS + 1 or names[0] != "Time":
            raise ValueError(f"unexpected header ({len(names)} fields)")
        ncol = len(names)
        rest = b""
        while True:
            block = f.read(chunk_bytes)
            if not block:
                break
            block = rest + block
            cut = block.rfind(b"\n")
            if cut < 0:
                rest = block
                continue
            rest = block[cut + 1:]
            parts.append(_parse_rows(block[: cut + 1], ncol))
        if rest.strip():
            parts.append(_parse_rows(rest, ncol))
    a = np.concatenate(parts) if parts else np.zeros((0, ncol), np.float32)
    return EmgRecording(emg=np.ascontiguousarray(a[:, 1:]), channel_names=names[1:])


def _parse_rows(block: bytes, ncol: int) -> np.ndarray:
    n_rows = sum(1 for line in block.split(b"\n") if line.strip())
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # numpy warns (does not raise) on a non-numeric field
        try:
            vals = np.fromstring(block, dtype=np.float32, sep=" ")  # any whitespace separates (tab, newline)
        except (DeprecationWarning, ValueError) as e:
            raise ValueError(f"non-numeric field in the EMG data: {e}") from None
    if vals.size != n_rows * ncol:
        raise ValueError(f"rows do not have {ncol} numeric fields")
    return vals.reshape(n_rows, ncol)


@dataclass(frozen=True)
class RunFiles:
    run: int
    csv: Path
    keys: Path
    ts: Path


def list_runs(root: str | PathLike[str]) -> list[RunFiles]:
    """All complete runs (csv, keys, ts) under ``root``, sorted by run number."""
    r = Path(root)
    out = []
    for c in r.glob("run*.csv"):
        m = re.fullmatch(r"run(\d+)", c.stem)
        if not m:
            continue
        k, t = r / f"{c.stem}_keys.txt", r / f"{c.stem}_ts.txt"
        if k.is_file() and t.is_file():
            out.append(RunFiles(int(m.group(1)), c, k, t))
    return sorted(out, key=lambda x: x.run)


@dataclass(frozen=True)
class KeyEvent:
    """A key press inside the recording: ``t`` in seconds from the first sample."""

    t: float
    char: str


def key_events(keys: Sequence[KeyPress], start_s: float, duration_s: float, margin_s: float = 0.0) -> list[KeyEvent]:
    """Key presses with ``margin_s <= t <= duration_s - margin_s``; ``t = unix - start_s``.

    Two presses with the same time keep only the first (frame times must
    increase strictly).
    """
    out: list[KeyEvent] = []
    for k in keys:
        t = k.unix_s - start_s
        if t < margin_s or t > duration_s - margin_s:
            continue
        if out and t <= out[-1].t:
            continue
        out.append(KeyEvent(t, k.char))
    return out


def segment_events(times: Sequence[float], max_gap_s: float = 2.0, min_len: int = 1) -> list[tuple[int, int]]:
    """Split key presses at pauses longer than ``max_gap_s``: list of (start, stop) indices."""
    t = np.asarray(times, dtype=np.float64)
    if t.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(t) > max_gap_s) + 1
    bounds = [0, *cuts.tolist(), int(t.size)]
    return [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if b - a >= min_len]


# --- reference decoder ----------------------------------------------------------------

#: Window of the reference decoder, seconds relative to the key press.
WINDOW_PRE_S = 0.15
WINDOW_POST_S = 0.05


def window_features(
    emg: np.ndarray,
    times: Sequence[float],
    fs: float = SAMPLE_RATE_HZ,
    pre_s: float = WINDOW_PRE_S,
    post_s: float = WINDOW_POST_S,
    n_sub: int = 2,
) -> np.ndarray:
    """Log-RMS features per channel in ``n_sub`` sub-windows of ``[t - pre_s, t + post_s]``.

    Each sub-window has its channel mean removed first. Returns
    ``(K, n_sub * C)`` float64. Windows that leave the recording are
    clipped to it.
    """
    x = np.asarray(emg)
    N, C = x.shape
    a_off, b_off = int(round(pre_s * fs)), int(round(post_s * fs))
    edges = np.linspace(0, a_off + b_off, n_sub + 1).round().astype(int)
    out = np.zeros((len(times), n_sub * C), dtype=np.float64)
    for k, t in enumerate(times):
        c0 = int(round(t * fs)) - a_off
        for j in range(n_sub):
            lo, hi = min(max(c0 + edges[j], 0), N), min(max(c0 + edges[j + 1], 0), N)
            if hi - lo < 2:
                continue  # window outside the recording: features stay 0
            seg = x[lo:hi].astype(np.float64)
            seg -= seg.mean(axis=0, keepdims=True)
            out[k, j * C:(j + 1) * C] = 0.5 * np.log(np.mean(seg * seg, axis=0) + 1e-12)
    return out


def standardize_run(X: np.ndarray) -> np.ndarray:
    """Z-score each feature within one run (unsupervised; uses no labels).

    Electrode placement and gain change from run to run, so the reference
    decoder sees features standardised per run. A live decoder does the
    same with the statistics of its first minutes.
    """
    X = np.asarray(X, dtype=np.float64)
    if len(X) == 0:
        return X
    return (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)


@dataclass
class LdaKeyDecoder:
    """Shrinkage linear discriminant analysis over :data:`KEY_VOCAB` (numpy only).

    Classes with no training example get the prior floor and the global
    mean. ``predict_log_proba`` returns ``(K, 32)`` log posteriors.
    """

    means: np.ndarray  # (V, D)
    precision: np.ndarray  # (D, D)
    log_prior: np.ndarray  # (V,)
    mu: np.ndarray  # (D,) feature centre
    scale: np.ndarray  # (D,) feature scale

    @classmethod
    def fit(cls, X: np.ndarray, y: np.ndarray, shrinkage: float = 0.1, prior_floor: float = 1e-3) -> "LdaKeyDecoder":
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.int64)
        if X.ndim != 2 or len(X) != len(y) or len(X) == 0:
            raise ValueError("X must be (K, D) with one label per row")
        V = len(KEY_VOCAB)
        if y.min() < 0 or y.max() >= V:
            raise ValueError("labels must be key classes 0..31")
        mu, sd = X.mean(0), X.std(0) + 1e-9
        Z = (X - mu) / sd
        D = Z.shape[1]
        means = np.zeros((V, D))
        counts = np.bincount(y, minlength=V).astype(np.float64)
        for v in np.flatnonzero(counts):
            means[v] = Z[y == v].mean(0)
        R = Z - means[y]
        cov = R.T @ R / max(len(Z) - 1, 1)
        cov = (1 - shrinkage) * cov + shrinkage * np.eye(D) * np.trace(cov) / D
        prior = np.maximum(counts / counts.sum(), prior_floor)
        return cls(means, np.linalg.inv(cov), np.log(prior / prior.sum()), mu, sd)

    def predict_log_proba(self, X: np.ndarray) -> np.ndarray:
        Z = (np.asarray(X, dtype=np.float64) - self.mu) / self.scale
        W = self.means @ self.precision  # (V, D)
        b = -0.5 * np.einsum("vd,vd->v", W, self.means) + self.log_prior
        s = Z @ W.T + b
        m = s.max(axis=1, keepdims=True)
        return s - m - np.log(np.exp(s - m).sum(axis=1, keepdims=True))

    def save(self, path: str | PathLike[str]) -> str:
        """Write the weights as ``.npz`` and return their SHA-256 (for ``decoder.weights_sha256``)."""
        p = Path(path)
        with open(p, "wb") as f:
            np.savez(f, means=self.means, precision=self.precision, log_prior=self.log_prior, mu=self.mu,
                     scale=self.scale)
        return hashlib.sha256(p.read_bytes()).hexdigest()

    @classmethod
    def load(cls, path: str | PathLike[str]) -> "LdaKeyDecoder":
        with np.load(path, allow_pickle=False) as z:
            return cls(z["means"], z["precision"], z["log_prior"], z["mu"], z["scale"])


# --- streams ------------------------------------------------------------------------


def opaque_stream_id(*parts: Any) -> str:
    """Deterministic opaque ``stream.id``: SHA-256 of the parts, 32 hex characters."""
    return hashlib.sha256("/".join(str(p) for p in parts).encode()).hexdigest()[:32]


def _licence_meta(licence: str) -> dict[str, Any]:
    """``data.licence`` and ``data.research_only`` of the dataset (FEP-0010, NTS 1.0 RC4 amendment 6)."""
    from fidetype.trust.licence import licence_meta

    return licence_meta(licence)


def stream_meta(
    run_index: int | None = None,
    segment_index: int | None = None,
    decoder_name: str = "fidetype-kt-lda-baseline",
    decoder_version: str = "0",
    weights_sha256: str | None = None,
    stream_id: str | None = None,
    personalized: bool = True,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``meta`` of a key-press stream (spec 3.4 keys). No text, no participant id."""
    replay: dict[str, Any] = {"dataset": DATASET_SLUG, "doi": DATAVERSE_DOI, "licence": LICENCE,
                              "attribution": ATTRIBUTION}
    if run_index is not None:
        replay["run_index"] = int(run_index)
    if segment_index is not None:
        replay["segment_index"] = int(segment_index)
    m: dict[str, Any] = {
        "device.modality": "emg",
        "device.model": "custom forearm sleeves, 16 sEMG channels per arm, 2000 Hz",
        "device.channel_count": N_CHANNELS,
        "device.invasive": False,
        "device.regulatory_status": "research",
        "emg.placement": "forearm",  # modality key: NTS 1.0 RC4 MET-11 (FEP-0009)
        "decoder.name": decoder_name,
        "decoder.version": decoder_version,
        "decoder.causal": False,
        "decoder.calibration_method": "none",
        "adapter.name": ADAPTER_NAME,
        "adapter.version": _FIDETYPE_VERSION,
        "lm.name": "none",
        "user.personalized": bool(personalized),
        "calibration.applied": False,
        "language": "en",
        "data.derived": True,
        **_licence_meta(LICENCE),  # data.licence, data.research_only: FEP-0010 (MET-12)
        "fidetype.vocab_id": KEY_VOCAB_ID,
        "fidetype.timing": "oracle-keystroke: one frame per key press; key times from the key log, seconds from "
                           "the first EMG sample (UTC offset of the start time inferred)",
        "fidetype.replay": replay,
    }
    if weights_sha256 is not None:
        m["decoder.weights_sha256"] = weights_sha256
    if stream_id is not None:
        m["stream.id"] = stream_id
    if extra:
        m.update(extra)
    return m


def keypress_stream(
    log_probs: np.ndarray,
    key_times: Sequence[float],
    meta: dict[str, Any] | None = None,
    latency: float | None = None,
    source: str = DATASET_SLUG,
) -> NeuralTextStream:
    """One frame per key press over :data:`KEY_VOCAB`.

    ``log_probs`` is (K, 32); logits are fine (``log_softmax`` is
    applied). ``latency`` is the window time after the key press that
    the decoder used: with it the stream is causal with
    ``decoder.lookahead_s = latency`` (spec MET-5); without it,
    ``decoder.causal = false``.
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    if lp.ndim != 2 or lp.shape[1] != len(KEY_VOCAB):
        raise ValueError(f"log_probs must be (K, {len(KEY_VOCAB)}), got {lp.shape}")
    if len(lp):
        m = lp.max(axis=1, keepdims=True)
        lp = lp - m - np.log(np.exp(lp - m).sum(axis=1, keepdims=True))
    meta = dict(meta) if meta is not None else stream_meta()
    if latency is not None:
        meta["decoder.causal"] = True
        meta["decoder.lookahead_s"] = float(latency)
    else:
        meta["decoder.causal"] = False
        meta.pop("decoder.lookahead_s", None)
    return NeuralTextStream(
        log_probs=lp.astype(np.float32), frame_times=np.asarray(key_times, dtype=np.float64),
        vocab=list(KEY_VOCAB), blank_id=None, source=source, meta=meta, vocab_type="key", latency=latency,
    )


def greedy_codes(stream: NeuralTextStream) -> list[str]:
    """Per-frame argmax key codes of a key-press stream."""
    if tuple(stream.vocab) != KEY_VOCAB:
        raise ValueError("greedy_codes needs a stream with the KT-sEMG KEY_VOCAB")
    return [KEY_VOCAB[i] for i in np.argmax(stream.log_probs, axis=1)]


def code_nbest(stream: NeuralTextStream, top_per_frame: int = 3, beam: int = 16,
               n_best: int = 8) -> list[dict[str, Any]]:
    """The n-best key-code sequences of a key-press stream, in the ``kt-semg`` track text space (P14-46).

    A beam search over the per-frame key posteriors (no language model). Each candidate is
    ``{"text": "KeyH KeyI Space ...", "score": <sum of log-probs>}``: one W3C code per key press,
    ``Backspace`` included, best first. The first candidate is :func:`greedy_codes`.
    """
    if tuple(stream.vocab) != KEY_VOCAB:
        raise ValueError("code_nbest needs a stream with the KT-sEMG KEY_VOCAB")
    lp = np.asarray(stream.log_probs, dtype=np.float64)
    beams: list[tuple[float, tuple[int, ...]]] = [(0.0, ())]
    for row in lp:
        top = np.argsort(-row, kind="stable")[:max(1, int(top_per_frame))]
        nxt = [(s + float(row[j]), seq + (int(j),)) for s, seq in beams for j in top]
        nxt.sort(key=lambda x: -x[0])
        beams = nxt[:max(1, int(beam))]
    return [{"text": " ".join(KEY_VOCAB[j] for j in seq), "score": float(s)} for s, seq in beams[:max(1, int(n_best))]]


def codes_from_text(text: str, unknown: str = "?") -> list[str]:
    """Screen text -> one W3C ``KeyboardEvent.code`` per character (P14-46).

    Lossy: screen text has no ``Backspace`` presses, so a burst with corrections maps to
    fewer keys than were typed. Use :func:`code_nbest` (or ``KeyLdaDecoder.track_nbest``) to
    keep every key press. Characters without a code give ``unknown`` (the track truth uses ``?``).
    """
    return [key_code(ch) or unknown for ch in str(text)]
