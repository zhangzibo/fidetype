"""Torch dataset over the preprocessed SpanishBCBL cache.

The dataset reads only the cache files (see :mod:`fidetype.decoders.synthetic`
for the format). Each item is one typing segment (one sentence).

Memory
------
The dataset does not load whole blocks into RAM. It memory-maps the
``data`` array of each block:

- If the ``.npz`` member is stored without compression, the dataset maps
  the bytes in the zip file directly.
- Otherwise it extracts ``data`` once to ``<mmap_dir>/<subject>/<stem>.npy``
  and maps that file.

Only the samples of one segment are read for each item.

Item
----
``x``           float32 tensor [306, T] (after augmentation)
``target``      int64 tensor of CTC ids from ``typed_text`` (no blanks)
``subject``     int index of the participant
``target_text`` and ``typed_text`` strings, plus ids for bookkeeping.

Trials with ``is_training=True`` (practice trials with visual feedback)
are always excluded.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import torch
from torch.utils.data import Dataset, Sampler

from fidetype.streams.vocab import encode


@dataclass
class AugmentConfig:
    """Training augmentations. Each one is off when its value is 0."""

    start_jitter_s: float = 0.3  # random shift of the segment start, +/- seconds
    end_jitter_s: float = 0.1  # random extension of the segment end, 0..seconds
    channel_offset_std: float = 0.3  # per-channel constant offset ~ N(0, std)
    time_mask_n: int = 2  # number of time masks
    time_mask_max_s: float = 0.3  # max length of one time mask
    channel_mask_n: int = 1  # number of channel masks
    channel_mask_max: int = 30  # max channels per mask
    stretch_min: float = 0.9  # time-stretch factor range; 1.0/1.0 = off
    stretch_max: float = 1.1

    @classmethod
    def off(cls) -> "AugmentConfig":
        return cls(0.0, 0.0, 0.0, 0, 0.0, 0, 0, 1.0, 1.0)


@dataclass
class Segment:
    subject: str
    participant: str
    session: str
    block: str
    npz: str
    trial_idx: int
    split: str
    start: int
    end: int
    target_text: str
    typed_text: str
    first_key: int
    last_key: int
    n_samples: int


def _block_meta(sidecar: Path) -> tuple[str, str]:
    stem = sidecar.stem  # "<session>_<block>"
    if "_" in stem:
        session, block = stem.split("_", 1)
    else:
        session, block = stem, ""
    return session, block


def scan_cache(root: str | Path, subjects: Sequence[str] | None = None) -> list[Segment]:
    """Return all non-practice segments in the cache.

    The function globs ``<root>/<subject>/*.json`` sidecars that have a
    matching ``.npz``. It does not depend on the ``_index.json`` schema.
    """
    root = Path(root)
    out: list[Segment] = []
    for sidecar in sorted(root.glob("*/*.json")):
        npz = sidecar.with_suffix(".npz")
        if not npz.exists():
            continue
        meta = json.loads(sidecar.read_text(encoding="utf-8"))
        subject = str(meta.get("subject", sidecar.parent.name))
        if subjects is not None and subject not in subjects:
            continue
        participant = str(meta.get("participant", meta.get("participant_id", subject)))
        session, block = _block_meta(sidecar)
        session = str(meta.get("session", session))
        block = str(meta.get("block", block))
        n_samples = int(meta.get("n_samples", -1))
        for seg in meta.get("segments", []):
            if seg.get("is_training", False):
                continue
            typed = seg.get("typed_text", "") or ""
            if not typed.strip():
                continue
            start, end = int(seg["start_sample"]), int(seg["end_sample"])
            keys = [int(k) for k in (seg.get("key_samples") or [])] or [start + 1, end - 1]
            if min(keys) < start:  # key_samples are relative to the segment start
                keys = [start + k for k in keys]
            out.append(
                Segment(
                    subject=subject,
                    participant=participant,
                    session=session,
                    block=block,
                    npz=str(npz.relative_to(root)).replace("\\", "/"),
                    trial_idx=int(seg["trial_idx"]),
                    split=str(seg.get("split", "train")),
                    start=start,
                    end=end,
                    target_text=seg.get("target_text", "") or "",
                    typed_text=typed,
                    first_key=int(min(keys)),
                    last_key=int(max(keys)),
                    n_samples=n_samples,
                )
            )
    return out


def _mmap_npz_member(npz_path: Path, member: str, mmap_dir: Path | None, rel: str) -> np.ndarray:
    """Memory-map array ``member`` of an ``.npz`` file (read only)."""
    name = member + ".npy"
    with zipfile.ZipFile(npz_path) as zf:
        info = zf.getinfo(name)
        stored = info.compress_type == zipfile.ZIP_STORED
    if stored:
        with open(npz_path, "rb") as f:
            # Local file header: 30 bytes + name + extra field.
            f.seek(info.header_offset)
            hdr = f.read(30)
            n_name = int.from_bytes(hdr[26:28], "little")
            n_extra = int.from_bytes(hdr[28:30], "little")
            npy_offset = info.header_offset + 30 + n_name + n_extra
            f.seek(npy_offset)
            version = np.lib.format.read_magic(f)
            if version == (1, 0):
                shape, fortran, dtype = np.lib.format.read_array_header_1_0(f)
            else:
                shape, fortran, dtype = np.lib.format.read_array_header_2_0(f)
            data_offset = f.tell()
        return np.memmap(npz_path, dtype=dtype, mode="r", offset=data_offset, shape=shape,
                         order="F" if fortran else "C")
    if mmap_dir is None:
        raise ValueError(f"{npz_path} is compressed; give mmap_dir to extract it")
    out = Path(mmap_dir) / (rel[: -len(".npz")] + f".{member}.npy")
    if not out.exists() or out.stat().st_mtime < npz_path.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        with np.load(npz_path, allow_pickle=False) as z:
            arr = z[member]
        tmp = out.with_suffix(".tmp.npy")
        np.save(tmp, arr)
        tmp.replace(out)
    return np.load(out, mmap_mode="r")


def time_stretch(x: np.ndarray, factor: float) -> np.ndarray:
    """Resample x [C, T] to round(T * factor) samples by linear interpolation."""
    T = x.shape[1]
    T_new = max(2, int(round(T * factor)))
    pos = np.linspace(0, T - 1, T_new, dtype=np.float32)
    i0 = np.floor(pos).astype(np.int64)
    i1 = np.minimum(i0 + 1, T - 1)
    w = (pos - i0)[None, :]
    return x[:, i0] * (1 - w) + x[:, i1] * w


class MEGSegments(Dataset):
    """Typing segments from the cache.

    Parameters
    ----------
    root : cache root (for example ``.../cache/spanishbcbl/v1``).
    splits : the splits to keep (for example ``("train",)``).
    subject_map : participant id -> index. Give the training map to val/test
        datasets so the indices agree. If None, the map is built from all
        participants in the cache (sorted).
    augment : an :class:`AugmentConfig`, or None for no augmentation.
    seed : base seed. The augmentation of item i in epoch e uses the RNG
        seed (seed, e, i). Thus the data is the same with any number of
        workers and after a resume.
    """

    def __init__(
        self,
        root: str | Path,
        splits: Sequence[str] = ("train",),
        subjects: Sequence[str] | None = None,
        subject_map: dict[str, int] | None = None,
        augment: AugmentConfig | None = None,
        seed: int = 0,
        mmap_dir: str | Path | None = None,
        pad_s: float = 0.0,
        max_segments: int | None = None,
    ) -> None:
        self.root = Path(root)
        all_segs = scan_cache(self.root, subjects)
        if subject_map is None:
            subject_map = {p: i for i, p in enumerate(sorted({s.participant for s in all_segs}))}
        self.subject_map = dict(subject_map)
        self.segments = [s for s in all_segs if s.split in splits and s.participant in self.subject_map]
        if max_segments is not None:
            self.segments = self.segments[:max_segments]
        self.augment = augment
        self.seed = int(seed)
        self.epoch = 0
        self.mmap_dir = Path(mmap_dir) if mmap_dir is not None else self.root.parent / (self.root.name + "-mmap")
        self.pad_s = pad_s
        self._arrays: dict[str, np.ndarray] = {}
        self._sfreq: dict[str, float] = {}

    def __getstate__(self) -> dict[str, Any]:
        st = self.__dict__.copy()
        st["_arrays"] = {}  # Workers open their own maps.
        return st

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def __len__(self) -> int:
        return len(self.segments)

    def lengths(self) -> list[int]:
        return [s.end - s.start for s in self.segments]

    def _array(self, rel: str) -> np.ndarray:
        arr = self._arrays.get(rel)
        if arr is None:
            path = self.root / rel
            arr = _mmap_npz_member(path, "data", self.mmap_dir, rel)
            with np.load(path, allow_pickle=False) as z:
                self._sfreq[rel] = float(z["sfreq"])
            self._arrays[rel] = arr
        return arr

    def sfreq(self, i: int) -> float:
        rel = self.segments[i].npz
        self._array(rel)
        return self._sfreq[rel]

    def __getitem__(self, i: int) -> dict[str, Any]:
        seg = self.segments[i]
        arr = self._array(seg.npz)
        sf = self._sfreq[seg.npz]
        T_block = arr.shape[1]
        start, end = seg.start, seg.end
        a = self.augment
        rng = np.random.default_rng([self.seed, self.epoch, i])
        if a is not None and a.start_jitter_s > 0:
            j = int(round(a.start_jitter_s * sf))
            # Do not cut away the first key press (keep >= 0.1 s before it).
            hi = min(j, max(0, seg.first_key - int(0.1 * sf) - start))
            start = start + int(rng.integers(-j, hi + 1))
        if a is not None and a.end_jitter_s > 0:
            end = end + int(rng.integers(0, int(round(a.end_jitter_s * sf)) + 1))
        start, end = max(0, start), min(T_block, end)
        x = np.asarray(arr[:, start:end], dtype=np.float32)
        if a is not None:
            C, T = x.shape
            if a.stretch_max > a.stretch_min or a.stretch_min != 1.0:
                f = float(rng.uniform(a.stretch_min, a.stretch_max))
                if abs(f - 1.0) > 1e-3:
                    x = time_stretch(x, f)
                    T = x.shape[1]
            if a.channel_offset_std > 0:
                x = x + rng.normal(0, a.channel_offset_std, size=(C, 1)).astype(np.float32)
            for _ in range(a.time_mask_n):
                w = int(rng.integers(0, int(a.time_mask_max_s * sf) + 1))
                if 0 < w < T:
                    t0 = int(rng.integers(0, T - w))
                    x[:, t0 : t0 + w] = 0.0
            for _ in range(a.channel_mask_n):
                w = int(rng.integers(0, a.channel_mask_max + 1))
                if 0 < w < C:
                    idx = rng.choice(C, size=w, replace=False)
                    x[idx] = 0.0
        return {
            "x": torch.from_numpy(np.ascontiguousarray(x)),
            "target": torch.tensor(encode(seg.typed_text), dtype=torch.long),
            "subject": self.subject_map[seg.participant],
            "target_text": seg.target_text,
            "typed_text": seg.typed_text,
            "index": i,
            "start_sample": start,
            "sfreq": sf,
        }


def collate(batch: list[dict[str, Any]], pad_multiple: int = 1) -> dict[str, Any]:
    """Pad a list of items into a batch.

    ``pad_multiple`` rounds the padded length up to a multiple of this many
    samples. On ROCm, MIOpen searches conv kernels for every new input
    shape, so few distinct shapes make training much faster. The model
    masks the padding, so the outputs do not change.

    Returns ``x`` [B, C, T_pad] (zero padded), ``lengths`` [B],
    ``targets`` [B, L_max] (zero padded), ``target_lengths`` [B],
    ``subjects`` [B] and the text lists.
    """
    B = len(batch)
    C = batch[0]["x"].shape[0]
    lengths = torch.tensor([b["x"].shape[1] for b in batch], dtype=torch.long)
    tlen = torch.tensor([len(b["target"]) for b in batch], dtype=torch.long)
    T_pad = int(lengths.max())
    if pad_multiple > 1:
        T_pad = -(-T_pad // pad_multiple) * pad_multiple
    x = torch.zeros(B, C, T_pad)
    tg = torch.zeros(B, max(1, int(tlen.max())), dtype=torch.long)
    for k, b in enumerate(batch):
        x[k, :, : b["x"].shape[1]] = b["x"]
        tg[k, : len(b["target"])] = b["target"]
    return {
        "x": x,
        "lengths": lengths,
        "targets": tg,
        "target_lengths": tlen,
        "subjects": torch.tensor([b["subject"] for b in batch], dtype=torch.long),
        "target_text": [b["target_text"] for b in batch],
        "typed_text": [b["typed_text"] for b in batch],
        "index": [b["index"] for b in batch],
        "start_sample": [b["start_sample"] for b in batch],
    }


class BucketBatchSampler(Sampler[list[int]]):
    """Batches of items with similar length, in a seeded random order.

    The order depends only on (seed, epoch). ``skip`` drops the first
    batches; resume uses it to continue in the middle of an epoch.
    """

    def __init__(self, lengths: Sequence[int], batch_size: int, seed: int = 0,
                 shuffle: bool = True, bucket_factor: int = 20) -> None:
        self.lengths = np.asarray(lengths)
        self.batch_size = batch_size
        self.seed = seed
        self.shuffle = shuffle
        self.bucket_factor = bucket_factor
        self.epoch = 0
        self.skip = 0

    def set_epoch(self, epoch: int, skip: int = 0) -> None:
        self.epoch, self.skip = int(epoch), int(skip)

    def batches(self) -> list[list[int]]:
        n = len(self.lengths)
        if not self.shuffle:
            order = np.argsort(self.lengths, kind="stable")
            return [order[i : i + self.batch_size].tolist() for i in range(0, n, self.batch_size)]
        rng = np.random.default_rng([self.seed, self.epoch, 7])
        perm = rng.permutation(n)
        chunk = self.batch_size * self.bucket_factor
        out: list[list[int]] = []
        for c in range(0, n, chunk):
            idx = perm[c : c + chunk]
            idx = idx[np.argsort(self.lengths[idx], kind="stable")]
            out += [idx[i : i + self.batch_size].tolist() for i in range(0, len(idx), self.batch_size)]
        order = rng.permutation(len(out))
        return [out[k] for k in order]

    def __iter__(self) -> Iterator[list[int]]:
        yield from self.batches()[self.skip :]

    def __len__(self) -> int:
        return max(0, -(-len(self.lengths) // self.batch_size) - self.skip)


def augment_from_dict(d: dict[str, Any] | None) -> AugmentConfig | None:
    if d is None or d is False:
        return None
    base = asdict(AugmentConfig())
    base.update(d)
    return AugmentConfig(**base)


__all__ = [
    "AugmentConfig",
    "BucketBatchSampler",
    "MEGSegments",
    "Segment",
    "augment_from_dict",
    "collate",
    "scan_cache",
    "time_stretch",
]
