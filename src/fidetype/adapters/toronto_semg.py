"""Toronto sEMG typing adapter: forearm EMG key presses -> NeuralTextStream.

Source: Achituve, Beutel, Eby, Fetaya, Koivisto, Zariffa, "Electromyographic
typing gesture classification dataset for neurotechnological human-machine
interfaces", Scientific Data 12:440 (2025), doi:10.1038/s41597-025-04763-w.
Data on Borealis (University of Toronto Dataverse), doi:10.5683/SP3/KV65VI,
**CC BY 4.0**. File ``EMG typing dataset.zip``, 2,766,730,294 bytes,
MD5 ``27d052ee1b5dcdf1e5eb0b875c698f6d`` (Borealis API).

This is our own code (Apache-2.0). The baseline code of the dataset
(``ANSLab-UHN/sEMG-TypingDatabase``) is CC BY-SA 4.0. We read it only to
learn the alignment convention (one line, see :func:`key_events`). Nothing
is copied from it. The RHD reader follows the published Intan RHD2000 data
file format description; it is not the Intan reader.

Data layout (``CleanData/P<n>/T<m>/``)
-------------------------------------
- 19 participants (P1-P19), 2 sessions (T1, T2) on different days.
- ``Data/<L>_<yymmdd>_<hhmmss>.rhd``: one Intan recording per trial. ``<L>``
  is the letter of the trial; the time is the recording start (local
  clock, 1 s resolution). 16 amplifier channels (8 bipolar pairs per
  forearm), 2 kHz. About 2 recordings per letter per session.
- One trial: 5 presses of the space bar, then 10 presses of the letter
  key, paced by a metronome. Isolated key presses, not text.
- ``Keylogs.txt``: the keylogger output of the whole session, one line per
  key press: ``YYYY-MM-DD hh:mm:ss,mmm - 'a'`` or ``... - Key.space``.
- ``LAG_TIMINGS.csv``: ``Filename,Lag,Error`` per recording. ``Lag`` (s)
  aligns the keylog with the EMG. ``Error`` is the residual of that
  alignment (s, as we read it; the dataset does not define the unit).

Alignment: key time in the recording = keylog time - file start time +
``Lag``. (Same convention as the dataset's own baseline code.)

Streams
-------
The decoder in ``experiments/2026-11-11-emg-toronto/`` classifies one EMG
window per key press (oracle key timing from the keylog). The adapter
gives two stream forms:

- :func:`keypress_stream`: the canonical stream. One frame per key press,
  ``vocab_type="key"``, vocabulary :data:`KEY_VOCAB` (W3C
  ``KeyboardEvent.code`` names ``KeyA`` ... ``KeyZ``, ``Space``),
  ``blank_id=None`` (not a CTC decoder). This is the "wrist-EMG keyboard
  decoder" row of spec section 8.2.
- :func:`to_ctc_char_stream`: the same probabilities in the 28-token CTC
  character vocabulary of :mod:`fidetype.streams.vocab` (blank, ``a``-``z``,
  space), with one blank frame between two key frames. The trust core and
  the CTC beam search need this form. The blank frames keep double
  letters ("ll") apart. :func:`from_ctc_char_stream` reverses it.

Both forms follow ``spec/neuraltextstream-v0.1.md`` without change.
"""

from __future__ import annotations

import csv
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.streams.spec import NeuralTextStream
from fidetype.streams.vocab import BLANK_ID as CHAR_BLANK_ID
from fidetype.streams.vocab import VOCAB as CHAR_VOCAB

# --- dataset constants ----------------------------------------------------------

BOREALIS_DOI = "10.5683/SP3/KV65VI"
BOREALIS_FILE_ID = 836662
ZIP_NAME = "EMG typing dataset.zip"
ZIP_SIZE = 2_766_730_294
ZIP_MD5 = "27d052ee1b5dcdf1e5eb0b875c698f6d"
ZIP_SHA256 = "73c4f925b81c627643373dc271878a6fda6c0b59c521ae856a5610c8e5de7ef3"  # computed by us
LICENCE = "CC-BY-4.0"
SAMPLE_RATE_HZ = 2000.0
N_CHANNELS = 16

# --- vocabulary -----------------------------------------------------------------

LETTERS = "abcdefghijklmnopqrstuvwxyz"
#: The 27 key classes in column order: letters a-z, then the space bar.
KEY_CHARS: tuple[str, ...] = (*LETTERS, " ")
#: W3C UI Events ``KeyboardEvent.code`` names of the keys, same order.
KEY_VOCAB: tuple[str, ...] = (*(f"Key{c.upper()}" for c in LETTERS), "Space")
KEY_VOCAB_ID = "key.w3c-code.az-space"
SPACE_INDEX = 26
assert CHAR_VOCAB == ("<blank>", *KEY_CHARS)
CTC_VOCAB_ID = "char.b2q-28"
ADAPTER_NAME = "fidetype.adapters.toronto_semg"

#: Default mass given to the blank token on a key frame and to the 27 keys
#: on a blank frame (CTC form). Same values as the MEG run M2-10.
KEY_FRAME_BLANK = 1e-3
GAP_FRAME_NONBLANK = 1e-4


def key_label(raw: str) -> str | None:
    """Map a keylog key (``'a'``, ``Key.space``) to a key char, else None."""
    raw = raw.strip()
    if raw == "Key.space":
        return " "
    m = re.fullmatch(r"'(.)'", raw)
    if m and m.group(1).lower() in LETTERS:
        return m.group(1).lower()
    return None


# --- Intan RHD reader -------------------------------------------------------------

RHD_MAGIC = 0xC6912702


class RhdFormatError(ValueError):
    """The file is not a valid RHD file, or uses a feature we do not read."""


def _read(f: BinaryIO, fmt: str) -> tuple:
    n = struct.calcsize(fmt)
    b = f.read(n)
    if len(b) != n:
        raise RhdFormatError("unexpected end of header")
    return struct.unpack(fmt, b)


def _qstring(f: BinaryIO, max_bytes: int = 1 << 16) -> str:
    (n,) = _read(f, "<I")
    if n == 0xFFFFFFFF:
        return ""
    if n > max_bytes or n % 2:
        raise RhdFormatError(f"bad QString length {n}")
    b = f.read(n)
    if len(b) != n:
        raise RhdFormatError("unexpected end of header")
    return b.decode("utf-16-le", errors="replace")


@dataclass
class RhdRecording:
    """Amplifier data of one RHD file."""

    sample_rate: float
    channel_names: list[str]
    amplifier_uv: np.ndarray  # (C, N) float32, microvolts
    timestamps: np.ndarray  # (N,) int64 sample counters
    version: tuple[int, int]
    notch_filter_hz: int
    bandwidth_hz: tuple[float, float]  # actual lower, upper bandwidth
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return int(self.amplifier_uv.shape[1])

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.sample_rate

    @property
    def t0_s(self) -> float:
        """Time of the first sample (s), from the sample counter."""
        return float(self.timestamps[0]) / self.sample_rate if self.n_samples else 0.0


def read_rhd(path: str | PathLike[str], max_bytes: int = 200_000_000) -> RhdRecording:
    """Read the amplifier channels of an Intan RHD2000 file (``.rhd``).

    Supports format versions 1.x to 3.x. Raises :class:`RhdFormatError` on
    a bad magic number, a header that does not parse, or a data size that
    is not a whole number of data blocks. ``max_bytes`` limits the file
    size (untrusted input).
    """
    p = Path(path)
    size = p.stat().st_size
    if size > max_bytes:
        raise RhdFormatError(f"file too large ({size} bytes)")
    with open(p, "rb") as f:
        (magic,) = _read(f, "<I")
        if magic != RHD_MAGIC:
            raise RhdFormatError(f"bad magic number {magic:#x}")
        major, minor = _read(f, "<hh")
        ver = (major, minor)
        (sample_rate,) = _read(f, "<f")
        if not (0 < sample_rate < 1e6):
            raise RhdFormatError(f"bad sample rate {sample_rate}")
        _dsp_enabled, = _read(f, "<h")
        _dsp, lower_bw, upper_bw, _ddsp, _dlo, _dhi = _read(f, "<ffffff")
        (notch_mode,) = _read(f, "<h")
        _read(f, "<ff")  # impedance test frequencies
        notes = [_qstring(f) for _ in range(3)]
        n_temp = _read(f, "<h")[0] if ver >= (1, 1) else 0
        _eval_mode = _read(f, "<h")[0] if ver >= (1, 3) else 0
        reference = _qstring(f) if major > 1 else ""
        (n_groups,) = _read(f, "<h")
        if not (0 <= n_groups <= 64):
            raise RhdFormatError(f"bad group count {n_groups}")
        counts = {k: 0 for k in range(6)}
        amp_names: list[tuple[int, str]] = []
        for _g in range(n_groups):
            _qstring(f)
            _qstring(f)
            enabled, n_ch, _n_amp = _read(f, "<hhh")
            if n_ch < 0 or n_ch > 1024:
                raise RhdFormatError(f"bad channel count {n_ch}")
            if n_ch > 0 and enabled > 0:
                for _c in range(n_ch):
                    native = _qstring(f)
                    custom = _qstring(f)
                    native_order, _custom_order, sig_type, ch_enabled = _read(f, "<hhhh")
                    _read(f, "<hhhhhh")  # chip channel, board stream, trigger settings
                    _read(f, "<ff")  # impedance magnitude, phase
                    if sig_type not in counts:
                        raise RhdFormatError(f"bad signal type {sig_type}")
                    if ch_enabled:
                        counts[sig_type] += 1
                        if sig_type == 0:
                            amp_names.append((len(amp_names), custom or native))
        header_end = f.tell()
    n_amp, n_aux, n_supply, n_adc, n_din, n_dout = (counts[k] for k in range(6))
    N = 128 if major >= 3 else 60
    block = (
        N * 4  # timestamps
        + N * 2 * n_amp
        + (N // 4) * 2 * n_aux
        + 2 * n_supply
        + 2 * n_temp
        + N * 2 * n_adc
        + (N * 2 if n_din > 0 else 0)
        + (N * 2 if n_dout > 0 else 0)
    )
    rest = size - header_end
    if rest % block:
        raise RhdFormatError(f"data size {rest} is not a whole number of {block}-byte blocks")
    n_blocks = rest // block
    raw = np.fromfile(p, dtype=np.uint8, offset=header_end)
    raw = raw.reshape(n_blocks, block)
    ts_dtype = "<i4" if ver >= (1, 2) else "<u4"
    ts = raw[:, : N * 4].copy().view(ts_dtype).reshape(n_blocks * N).astype(np.int64)
    a0 = N * 4
    amp = raw[:, a0 : a0 + N * 2 * n_amp].copy().view("<u2").reshape(n_blocks, n_amp, N)
    amp = amp.transpose(1, 0, 2).reshape(n_amp, n_blocks * N)
    uv = (0.195 * (amp.astype(np.float32) - 32768.0)).astype(np.float32)
    return RhdRecording(
        sample_rate=float(sample_rate),
        channel_names=[n for _, n in amp_names],
        amplifier_uv=uv,
        timestamps=ts,
        version=ver,
        notch_filter_hz={1: 50, 2: 60}.get(int(notch_mode), 0),
        bandwidth_hz=(float(lower_bw), float(upper_bw)),
        meta={"notes": notes, "reference": reference, "n_aux": n_aux, "n_supply": n_supply,
              "n_adc": n_adc, "n_temp": n_temp, "n_din": n_din, "n_dout": n_dout},
    )


# --- keylogs, lag timings, recordings ------------------------------------------------

_KEYLOG_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) - (.+?)\s*$")
_FILE_RE = re.compile(r"^([A-Za-z])_(\d{6})_(\d{6})$")


@dataclass(frozen=True)
class KeylogEntry:
    time: datetime
    raw: str

    @property
    def char(self) -> str | None:
        return key_label(self.raw)


def parse_keylog(path: str | PathLike[str]) -> list[KeylogEntry]:
    """Parse ``Keylogs.txt``. Lines that are not key lines are skipped."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _KEYLOG_RE.match(line)
            if not m:
                continue
            t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(microsecond=int(m.group(2)) * 1000)
            out.append(KeylogEntry(t, m.group(3)))
    out.sort(key=lambda e: e.time)
    return out


def load_lag_timings(path: str | PathLike[str]) -> dict[str, tuple[float, float]]:
    """``LAG_TIMINGS.csv`` -> {file stem: (lag_s, error)}."""
    out = {}
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        for row in csv.DictReader(f):
            try:
                out[row["Filename"].strip()] = (float(row["Lag"]), float(row["Error"]))
            except (KeyError, ValueError):
                continue
    return out


@dataclass(frozen=True)
class RecordingInfo:
    participant: str  # "P1"
    session: str  # "T1"
    stem: str  # "A_220901_104337"
    letter: str  # "a"
    start: datetime
    path: Path

    @property
    def key(self) -> str:
        return f"{self.participant}/{self.session}/{self.stem}"


def parse_recording_name(stem: str) -> tuple[str, datetime]:
    m = _FILE_RE.match(stem)
    if not m:
        raise ValueError(f"not a recording name: {stem!r}")
    return m.group(1).lower(), datetime.strptime(m.group(2) + m.group(3), "%y%m%d%H%M%S")


def list_recordings(root: str | PathLike[str]) -> list[RecordingInfo]:
    """All recordings under ``root`` (the ``CleanData`` folder), sorted."""
    out = []
    for pdir in sorted(Path(root).glob("P*")):
        if not re.fullmatch(r"P\d+", pdir.name):
            continue
        for sdir in sorted(pdir.glob("T*")):
            for f in sorted((sdir / "Data").glob("*.rhd")):
                try:
                    letter, start = parse_recording_name(f.stem)
                except ValueError:
                    continue
                out.append(RecordingInfo(pdir.name, sdir.name, f.stem, letter, start, f))
    out.sort(key=lambda r: (int(r.participant[1:]), r.session, r.start, r.stem))
    return out


@dataclass(frozen=True)
class KeyEvent:
    """One key press inside a recording. ``t`` is in seconds from the
    first sample of the recording. ``char`` is ground truth: it never goes
    into a stream."""

    t: float
    char: str
    keylog_time: datetime


def key_events(
    rec: RecordingInfo,
    keylog: Sequence[KeylogEntry],
    lag_s: float,
    duration_s: float,
    margin_s: float = 0.0,
) -> list[KeyEvent]:
    """The key presses of one recording, with times in the recording.

    Takes the keylog entries from the file start time to the end of the
    recording; keeps the space bar and the letter of the trial; maps each
    to ``keylog time - file start + lag_s``; keeps events with
    ``margin_s <= t <= duration_s - margin_s``.
    """
    out = []
    t_end = duration_s - margin_s
    for e in keylog:
        rel = (e.time - rec.start).total_seconds()
        if rel < 0:
            continue
        t = rel + lag_s
        if t > t_end:
            if rel > duration_s + 5.0:
                break
            continue
        c = e.char
        if c is None or (c != " " and c != rec.letter) or t < margin_s:
            continue
        out.append(KeyEvent(t, c, e.time))
    return out


# --- streams ------------------------------------------------------------------------


def log_softmax(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    m = x.max(axis=-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(axis=-1, keepdims=True))


def stream_meta(
    subject: str | None = None,
    session: str | None = None,
    decoder_name: str = "fidetype-emg-keypress",
    decoder_version: str = "0",
    personalized: bool = False,
    composed: bool = False,
    extra: dict[str, Any] | None = None,
    weights_sha256: str | None = None,
    stream_id: str | None = None,
) -> dict[str, Any]:
    """The ``meta`` of a key-press stream (spec section 4 keys). No text, no labels.

    ``weights_sha256`` (SHA-256 of the decoder weights file) and
    ``stream_id`` (an opaque id) are the optional provenance keys of spec
    4.2 / 4.3. Give them to reach the conformance level "provenance".
    """
    m: dict[str, Any] = {
        "device.modality": "emg",
        "device.vendor": "Intan Technologies",
        "device.model": "RHD2000 (16 bipolar forearm channels)",
        "device.channel_count": N_CHANNELS,
        "device.invasive": False,
        "device.regulatory_status": "research",
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
        "fidetype.vocab_id": KEY_VOCAB_ID,
        "fidetype.timing": "oracle-keystroke: one frame per key press; key times from the keylogger",
        "fidetype.composed": bool(composed),
    }
    if weights_sha256 is not None:
        m["decoder.weights_sha256"] = weights_sha256
    if stream_id is not None:
        m["stream.id"] = stream_id
    if subject is not None:
        m["subject.id"] = subject
    if session is not None:
        m["session.id"] = session
    if extra:
        m.update(extra)
    return m


def keypress_stream(
    log_probs: np.ndarray,
    key_times: Sequence[float],
    meta: dict[str, Any] | None = None,
    latency: float | None = None,
    source: str = "toronto-semg",
) -> NeuralTextStream:
    """The canonical stream: one frame per key press over :data:`KEY_VOCAB`.

    ``log_probs`` is (K, 27) in the order of :data:`KEY_VOCAB` (logits are
    fine: the function applies ``log_softmax``). ``key_times`` must
    increase strictly. ``latency`` is the window time after the key press
    that the decoder used. The default leaves it out and ``meta`` says
    ``decoder.causal = false``. If ``latency`` is given, the decoder uses
    no signal after ``key_time + latency``, which is the spec 4.2
    definition of a causal decoder: the stream then sets
    ``decoder.causal = true`` and ``decoder.lookahead_s = latency``
    (conformance finding M5-10: before, a stream could carry a latency
    and ``decoder.causal = false`` at the same time).
    """
    lp = np.asarray(log_probs, dtype=np.float64)
    if lp.ndim != 2 or lp.shape[1] != len(KEY_VOCAB):
        raise ValueError(f"log_probs must be (K, {len(KEY_VOCAB)}), got {lp.shape}")
    meta = dict(meta) if meta is not None else stream_meta()
    if latency is not None:
        meta["decoder.causal"] = True
        meta["decoder.lookahead_s"] = float(latency)
    return NeuralTextStream(
        log_probs=log_softmax(lp).astype(np.float32),
        frame_times=np.asarray(key_times, dtype=np.float64),
        vocab=list(KEY_VOCAB),
        blank_id=None,
        source=source,
        meta=meta,
        vocab_type="key",
        latency=latency,
    )


def to_ctc_char_stream(
    stream: NeuralTextStream,
    key_blank: float = KEY_FRAME_BLANK,
    gap_nonblank: float = GAP_FRAME_NONBLANK,
) -> NeuralTextStream:
    """Return the 28-token CTC character form of a key-press stream.

    Frame 2k is key press k: the 27 key probabilities times
    ``1 - key_blank``, blank = ``key_blank``. Frame 2k+1 (between press k
    and k+1; none after the last press) is a blank frame: blank =
    ``1 - gap_nonblank``, the rest spread uniformly. Its time is the
    midpoint between the two presses. CTC greedy decoding of this stream
    equals the per-press argmax.
    """
    if tuple(stream.vocab) != KEY_VOCAB:
        raise ValueError("to_ctc_char_stream needs a stream with KEY_VOCAB")
    if not (0 < key_blank < 1 and 0 < gap_nonblank < 1):
        raise ValueError("key_blank and gap_nonblank must be in (0, 1)")
    K = stream.n_frames
    V = len(CHAR_VOCAB)
    T = max(0, 2 * K - 1)
    lp = np.empty((T, V), dtype=np.float64)
    times = np.empty(T, dtype=np.float64)
    key_lp = stream.log_probs.astype(np.float64)
    lp[0::2, CHAR_BLANK_ID] = np.log(key_blank)
    lp[0::2, 1:] = key_lp + np.log1p(-key_blank)
    if K > 1:
        lp[1::2, CHAR_BLANK_ID] = np.log1p(-gap_nonblank)
        lp[1::2, 1:] = np.log(gap_nonblank / (V - 1))
        ft = stream.frame_times
        times[1::2] = 0.5 * (ft[:-1] + ft[1:])
    times[0::2] = stream.frame_times
    meta = dict(stream.meta)
    meta["fidetype.vocab_id"] = CTC_VOCAB_ID
    meta["fidetype.ctc_form"] = {"from": KEY_VOCAB_ID, "key_blank": key_blank, "gap_nonblank": gap_nonblank}
    return NeuralTextStream(
        log_probs=lp.astype(np.float32), frame_times=times, vocab=list(CHAR_VOCAB), blank_id=CHAR_BLANK_ID,
        source=stream.source, meta=meta, vocab_type="char", latency=stream.latency,
    )


def from_ctc_char_stream(stream: NeuralTextStream) -> NeuralTextStream:
    """Reverse :func:`to_ctc_char_stream` (renormalises the key frames)."""
    if tuple(stream.vocab) != CHAR_VOCAB or stream.blank_id != CHAR_BLANK_ID:
        raise ValueError("from_ctc_char_stream needs a 28-token CTC char stream")
    if stream.n_frames % 2 != 1 and stream.n_frames != 0:
        raise ValueError("a CTC key stream has an odd number of frames")
    key = stream.log_probs[0::2, 1:].astype(np.float64)
    meta = dict(stream.meta)
    meta.pop("fidetype.ctc_form", None)
    meta["fidetype.vocab_id"] = KEY_VOCAB_ID
    return keypress_stream(key, stream.frame_times[0::2], meta, stream.latency, stream.source)


def greedy_keys(stream: NeuralTextStream) -> str:
    """Per-frame argmax of a key-press stream, as a string (``" "`` = space)."""
    if tuple(stream.vocab) != KEY_VOCAB:
        raise ValueError("greedy_keys needs a stream with KEY_VOCAB")
    return "".join(KEY_CHARS[i] for i in np.argmax(stream.log_probs, axis=1))


def chars_to_ids(text: str) -> np.ndarray:
    """Key class ids of a text in ``a``-``z`` and space."""
    idx = {c: i for i, c in enumerate(KEY_CHARS)}
    try:
        return np.array([idx[c] for c in text], dtype=np.int64)
    except KeyError as e:
        raise ValueError(f"character {e.args[0]!r} is not a key class") from None


def is_typeable(text: str) -> bool:
    """True if ``text`` uses only ``a``-``z`` and single inner spaces."""
    return bool(text) and text == " ".join(text.split()) and all(c in KEY_CHARS for c in text)


def compose_times(n: int, period_s: float, t0: float = 0.0) -> np.ndarray:
    """Frame times of a composed sentence: ``t0 + period_s * (1 .. n)``."""
    if period_s <= 0:
        raise ValueError("period_s must be > 0")
    return t0 + period_s * np.arange(1, n + 1, dtype=np.float64)


def iter_chars(texts: Iterable[str]) -> Iterable[str]:
    for t in texts:
        yield from t
