"""B1 data layer: EDF reading, events, subsequent-memory labels, list split, A0 timing check.

Our own code (Apache-2.0). No MNE, no PTSA. Input files are untrusted data: the EDF reader
parses only the fixed-width header fields it needs and never keeps the "patient" and
"recording" fields; the events reader is the csv module.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------------------------- EDF


@dataclass
class EdfHeader:
    n_records: int
    record_s: float
    labels: list[str]
    spr: list[int]
    gain: np.ndarray          # physical = dig * gain + offset (per signal)
    offset: np.ndarray
    header_bytes: int
    data_idx: list[int] = field(default_factory=list)   # signals that are not "EDF Annotations"

    @property
    def rec_len(self) -> int:
        return int(sum(self.spr))

    @property
    def fs(self) -> float:
        s = {self.spr[i] for i in self.data_idx}
        if len(s) != 1:
            raise ValueError(f"data signals have different sample counts per record: {sorted(s)}")
        return s.pop() / self.record_s

    @property
    def n_samples(self) -> int:
        return self.n_records * self.spr[self.data_idx[0]]

    @property
    def data_labels(self) -> list[str]:
        return [self.labels[i] for i in self.data_idx]


def _num(b: bytes) -> float:
    return float(b.decode("ascii").strip())


def read_edf_header(path: Path) -> EdfHeader:
    """Parse the EDF / EDF+ header. Fields "patient" (8:88) and "recording" (88:168) are skipped."""
    with Path(path).open("rb") as fh:
        h = fh.read(256)
        if len(h) < 256:
            raise ValueError("EDF header too short")
        hdr_bytes = int(_num(h[184:192]))
        n_rec = int(_num(h[236:244]))
        rec_s = _num(h[244:252])
        ns = int(_num(h[252:256]))
        s = fh.read(256 * ns)
    if ns <= 0 or n_rec <= 0 or rec_s <= 0 or len(s) < 256 * ns or hdr_bytes != 256 * (ns + 1):
        raise ValueError("bad EDF header")

    def col(off: int, w: int) -> list[bytes]:
        base = off * ns
        return [s[base + w * i: base + w * (i + 1)] for i in range(ns)]

    labels = [b.decode("latin-1").strip() for b in col(0, 16)]
    pmin = np.array([_num(b) for b in col(104, 8)])
    pmax = np.array([_num(b) for b in col(112, 8)])
    dmin = np.array([_num(b) for b in col(120, 8)])
    dmax = np.array([_num(b) for b in col(128, 8)])
    spr = [int(_num(b)) for b in col(216, 8)]
    gain = (pmax - pmin) / (dmax - dmin)
    offset = pmin - dmin * gain
    data_idx = [i for i, lab in enumerate(labels) if lab != "EDF Annotations"]
    hd = EdfHeader(n_rec, rec_s, labels, spr, gain, offset, hdr_bytes, data_idx)
    expect = hdr_bytes + n_rec * 2 * hd.rec_len
    if Path(path).stat().st_size != expect:
        raise ValueError(f"EDF size {Path(path).stat().st_size} != header {expect}")
    return hd


class EdfReader:
    """Record-wise memory-mapped reader (int16). Only data signals are returned, in physical units."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.h = read_edf_header(self.path)
        self.mm = np.memmap(self.path, dtype="<i2", mode="r", offset=self.h.header_bytes,
                            shape=(self.h.n_records, self.h.rec_len))
        starts = np.cumsum([0] + self.h.spr[:-1])
        self._start = [int(starts[i]) for i in self.h.data_idx]
        self._spr = self.h.spr[self.h.data_idx[0]]
        self.fs = self.h.fs
        self.n_samples = self.h.n_samples
        self.labels = self.h.data_labels
        self.gain = self.h.gain[self.h.data_idx].astype(np.float64)
        self.offset = self.h.offset[self.h.data_idx].astype(np.float64)

    def segment(self, start: int, stop: int) -> np.ndarray:
        """All data channels, samples [start, stop) -> (n_channels, stop - start) float64."""
        if start < 0 or stop > self.n_samples or stop <= start:
            raise IndexError("segment out of range")
        spr = self._spr
        r0, r1 = start // spr, (stop - 1) // spr + 1
        rows = np.asarray(self.mm[r0:r1])
        out = np.empty((len(self._start), (r1 - r0) * spr), dtype=np.float64)
        for k, st in enumerate(self._start):
            out[k] = rows[:, st:st + spr].reshape(-1)
        a = start - r0 * spr
        out = out[:, a:a + (stop - start)]
        return out * self.gain[:, None] + self.offset[:, None]

    def to_channel_major(self, tmp: Path, chunk: int = 32) -> np.memmap:
        """Write the data channels channel-major (int16) to ``tmp`` and return a read-only memmap."""
        spr, nc = self._spr, len(self._start)
        out = np.memmap(tmp, dtype="<i2", mode="w+", shape=(nc, self.n_samples))
        for r0 in range(0, self.h.n_records, chunk):
            r1 = min(self.h.n_records, r0 + chunk)
            rows = np.asarray(self.mm[r0:r1])
            for k, st in enumerate(self._start):
                out[k, r0 * spr:r1 * spr] = rows[:, st:st + spr].reshape(-1)
        out.flush()
        out._mmap.close()
        del out
        return np.memmap(tmp, dtype="<i2", mode="r", shape=(nc, self.n_samples))

    def close(self) -> None:
        self.mm._mmap.close()
        del self.mm


# ------------------------------------------------------------------------------------------- events

_INT_NA = -999


def read_events(path: Path) -> list[dict]:
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def _int(x: str | None, default: int = _INT_NA) -> int:
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def _float(x: str | None) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return math.nan


@dataclass
class Words:
    """The WORD events of one session (lists with a REC_START only), in file order."""

    sample: np.ndarray      # int64, the `sample` column
    onset: np.ndarray       # float64 seconds
    lst: np.ndarray         # int64 list number
    serialpos: np.ndarray   # int64
    recalled: np.ndarray    # int8, 0/1
    items: list[str]

    def __len__(self) -> int:
        return int(self.sample.shape[0])

    def subset(self, keep: np.ndarray) -> "Words":
        keep = np.asarray(keep, dtype=bool)
        return Words(self.sample[keep], self.onset[keep], self.lst[keep], self.serialpos[keep],
                     self.recalled[keep], [w for w, k in zip(self.items, keep) if k])


def norm_item(x: str | None) -> str:
    return (x or "").strip().upper()


def words_from_events(rows: list[dict]) -> tuple[Words, dict]:
    """WORD events + subsequent-memory label (the plan's rule) and simple counts for the log."""
    rec_lists = {_int(r.get("list")) for r in rows if r.get("trial_type") == "REC_START"}
    recalled_by_list: dict[int, set[str]] = {}
    for r in rows:
        if r.get("trial_type") == "REC_WORD":
            recalled_by_list.setdefault(_int(r.get("list")), set()).add(norm_item(r.get("item_name")))
    smp, ons, lst, sp, lab, items = [], [], [], [], [], []
    n_word = n_dropped_list = 0
    for r in rows:
        if r.get("trial_type") != "WORD":
            continue
        n_word += 1
        li = _int(r.get("list"))
        if li not in rec_lists:
            n_dropped_list += 1
            continue
        it = norm_item(r.get("item_name"))
        smp.append(_int(r.get("sample"), -1))
        ons.append(_float(r.get("onset")))
        lst.append(li)
        sp.append(_int(r.get("serialpos")))
        lab.append(1 if it in recalled_by_list.get(li, set()) else 0)
        items.append(it)
    w = Words(np.array(smp, dtype=np.int64), np.array(ons, dtype=np.float64), np.array(lst, dtype=np.int64),
              np.array(sp, dtype=np.int64), np.array(lab, dtype=np.int8), items)
    return w, {"n_word_events": n_word, "n_dropped_no_rec_start": n_dropped_list, "n_lists": len(set(lst))}


def event_index(words: Words, fs: float, mode: str) -> np.ndarray:
    """EDF sample index of each word: the `sample` column (primary) or round(onset * fs) (A0 fallback)."""
    if mode == "sample":
        return words.sample.copy()
    if mode == "onset":
        return np.round(words.onset * fs).astype(np.int64)
    raise ValueError(mode)


# ------------------------------------------------------------------------------------ hashing, split


def rank_key(salt: str, *parts: str) -> str:
    return hashlib.sha256((salt + "/".join(parts)).encode("utf-8")).hexdigest()


def cal_list_split(subject: str, session: int, lists: list[int]) -> tuple[list[int], list[int]]:
    """Order / certify lists of the cal session: hash order, the first floor(n/3) are order lists.

    Key: sha256("fidetype-b1/" + "sub-<code>" + "/" + "ses-<n>" + "/" + str(list)).
    """
    ls = sorted(set(int(x) for x in lists))
    ranked = sorted(ls, key=lambda li: rank_key("fidetype-b1/", subject, f"ses-{session}", str(li)))
    k = len(ranked) // 3
    return sorted(ranked[:k]), sorted(ranked[k:])


# ----------------------------------------------------------------------------------------------- A0


def a0_statistic(reader, idx: np.ndarray, fs: float) -> float:
    """Mean over channels of mean_{0..500 ms} |ERP|, ERP baseline-corrected on -200..0 ms.

    ``reader.segment(start, stop)`` returns (channels, samples). Events whose epoch is out of
    range are skipped. Returns nan if no event is usable.
    """
    pre, post = int(round(0.2 * fs)), int(round(0.5 * fs))
    acc = None
    n = 0
    for i in np.asarray(idx, dtype=np.int64):
        a, b = int(i) - pre, int(i) + post
        if a < 0 or b > reader.n_samples:
            continue
        seg = reader.segment(a, b)
        seg = seg - seg[:, :pre].mean(axis=1, keepdims=True)
        acc = seg if acc is None else acc + seg
        n += 1
    if n == 0:
        return math.nan
    erp = acc / n
    return float(np.mean(np.abs(erp[:, pre:]).mean(axis=1)))


def a0_random_times(idx_all: np.ndarray, fs: float, n: int, seed: list[int]) -> np.ndarray:
    """``n`` random sample indices, uniform between the first and the last WORD index of the session."""
    rng = np.random.default_rng(seed)
    lo, hi = int(np.min(idx_all)), int(np.max(idx_all))
    return rng.integers(lo, hi + 1, size=n)


# ------------------------------------------------------------------------------------------ dataset


def session_paths(root: Path, subject: str, session: int) -> dict[str, Path]:
    d = Path(root) / subject / f"ses-{session}" / "ieeg"
    base = f"{subject}_ses-{session}_task-FR1"
    return {"edf": d / f"{base}_acq-bipolar_ieeg.edf", "channels": d / f"{base}_acq-bipolar_channels.tsv",
            "events": d / f"{base}_events.tsv", "ok": d / f"{base}_acq-bipolar_ieeg.edf.ok"}


def load_selection(raw: Path) -> dict:
    return json.loads((Path(raw) / "selection.json").read_text(encoding="utf-8"))


def read_channels_tsv(path: Path) -> list[str]:
    with Path(path).open("r", encoding="utf-8", newline="") as fh:
        return [r["name"] for r in csv.DictReader(fh, delimiter="\t")]
