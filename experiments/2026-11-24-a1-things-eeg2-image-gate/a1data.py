"""A1 data layer: safe loading, concept splits, 4-trial units, galleries, session reconstruction (plan.md).

Our own code, Apache-2.0. Inputs (never committed; see plan.md "Data and licence"):

* ``<raw>/hf/sub-XX/preprocessed_eeg_{training,test}.npy``: pickled dicts written by the ATM preprocessing code
  (keys ``preprocessed_eeg_data``, ``ch_names``, ``times``). Third-party files: we read them with the whitelist
  :class:`LazyUnpickler` (NumPy names only; the big payload is memory-mapped, not loaded) and store plain
  float32 ``.npy`` arrays.
* ``<raw>/hf/ViT-H-14_features_{train,test}.pt``: CLIP features, read with ``torch.load(weights_only=True)``.
* ``<raw>/osf/image_metadata.npy``: the official image and concept lists (an object ``.npy``, same safe reader).

Every reader here takes paths as arguments. Run any script that uses this module with ``python -I``.
"""

from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

SALT = "fidetype-a1-2026-11-24/"
N_VAL, N_CAL, N_ORDER = 200, 300, 100
UNIT_REPS = 4
TEST_REPS = 80
N_SESSIONS = 4
PREP_SEED = 20200220  # the seed in the ATM preprocessing code (EEG-preprocessing/preprocessing.py)
GALLERY = 200

TRAIN_SHAPE = (16540, 4, 63, 250)
TEST_SHAPE = (200, 80, 63, 250)


# --- safe reading --------------------------------------------------------------------------------------------------

class SafeUnpickler(pickle.Unpickler):
    """Unpickler that builds only NumPy arrays, dtypes and plain Python containers (no other globals)."""

    ALLOWED = {
        ("numpy.core.multiarray", "_reconstruct"), ("numpy._core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"), ("numpy._core.multiarray", "scalar"),
        ("numpy", "ndarray"), ("numpy", "dtype"),
    }

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) in self.ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"blocked global {module}.{name}")


def safe_load(path: str | Path) -> Any:
    """Load a pickle file or an object ``.npy`` file with :class:`SafeUnpickler`."""
    from numpy.lib import format as npf

    with open(path, "rb") as f:
        if f.read(6) == b"\x93NUMPY":
            f.seek(0)
            ver = npf.read_magic(f)
            reader = npf.read_array_header_1_0 if ver == (1, 0) else npf.read_array_header_2_0
            shape, _, dtype = reader(f)
            if dtype != np.dtype(object):
                f.seek(0)
                return np.load(f, allow_pickle=False)
            obj = SafeUnpickler(f).load()
            return obj.item() if isinstance(obj, np.ndarray) and obj.shape == () else obj
        f.seek(0)
        return SafeUnpickler(f).load()


@dataclass
class LazyArray:
    """An ndarray found in a pickle, not loaded: its raw bytes stay in the file at ``offset`` (or in ``data``)."""

    shape: tuple[int, ...] = ()
    dtype: Any = None
    fortran: bool = False
    offset: int | None = None
    data: bytes | None = None

    def __setstate__(self, state: tuple) -> None:
        if len(state) == 5:
            state = state[1:]
        shape, dtype, fortran, raw = state
        self.shape, self.dtype, self.fortran = tuple(int(n) for n in shape), np.dtype(dtype), bool(fortran)
        if isinstance(raw, _Skipped):
            self.offset = raw.offset
        else:
            self.data = bytes(raw)

    def array(self, path: str | Path) -> np.ndarray:
        """Read-only view: a memmap of the source file for a skipped payload, else a small in-memory array."""
        order = "F" if self.fortran else "C"
        if self.offset is not None:
            return np.memmap(path, dtype=self.dtype, mode="r", offset=self.offset, shape=self.shape, order=order)
        return np.frombuffer(self.data, dtype=self.dtype).reshape(self.shape, order=order)


@dataclass(frozen=True)
class _Skipped:
    offset: int
    n: int


def _fake_reconstruct(subtype: Any, shape: Any, dtype: Any) -> LazyArray:
    return LazyArray()


class LazyUnpickler(pickle._Unpickler):  # the pure-Python unpickler, so that opcodes can be overridden
    """Restricted unpickler for the ATM EEG pickles that does not load big byte payloads into memory.

    Globals: only the NumPy names of :class:`SafeUnpickler`; ``_reconstruct`` builds a :class:`LazyArray` (no NumPy
    code runs on file data). A ``BINBYTES`` / ``BINBYTES8`` payload above ``big`` bytes that is outside a pickle
    frame is skipped with ``seek``; its file offset is kept. Peak memory stays small for an 8 GB file.
    """

    dispatch = dict(pickle._Unpickler.dispatch)

    def __init__(self, file, big: int = 1 << 24):
        super().__init__(file)
        self._f, self._big = file, big

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) not in SafeUnpickler.ALLOWED:
            raise pickle.UnpicklingError(f"blocked global {module}.{name}")
        if name == "_reconstruct":
            return _fake_reconstruct
        if name == "ndarray":
            return np.ndarray  # only passed to _fake_reconstruct as a tag
        return super().find_class(module, name)

    def _bytes(self, n: int) -> None:
        if n > self._big and self._unframer.current_frame is None:
            off = self._f.tell()
            self._f.seek(n, 1)
            self.append(_Skipped(off, n))
        else:
            self.append(self.read(n))

    def _binbytes(self) -> None:
        import struct

        self._bytes(struct.unpack("<I", self.read(4))[0])

    def _binbytes8(self) -> None:
        import struct

        self._bytes(struct.unpack("<Q", self.read(8))[0])

    dispatch[pickle.BINBYTES[0]] = _binbytes
    dispatch[pickle.BINBYTES8[0]] = _binbytes8


def lazy_load(path: str | Path, big: int = 1 << 24) -> Any:
    with open(path, "rb") as f:
        return LazyUnpickler(f, big).load()


def convert_eeg(src: str | Path, dst_dir: str | Path, name: str, expect_shape: tuple[int, ...] | None,
                big: int = 1 << 24) -> dict:
    """Pickled EEG dict -> ``<dst>/<name>.npy`` (float32, no pickle) + ``<name>_meta.json``. Returns the meta.

    Streams the data from the source file in chunks (:class:`LazyUnpickler`); never holds the whole array.
    """
    import json

    d = lazy_load(src, big)
    if set(d) != {"preprocessed_eeg_data", "ch_names", "times"}:
        raise ValueError(f"{src}: unexpected keys {sorted(d)}")
    la = d["preprocessed_eeg_data"]
    if not isinstance(la, LazyArray):
        raise ValueError(f"{src}: EEG is not an array")
    if expect_shape is not None and tuple(la.shape) != tuple(expect_shape):
        raise ValueError(f"{src}: shape {la.shape}, expected {expect_shape}")
    if la.offset is not None and la.offset + int(np.prod(la.shape)) * la.dtype.itemsize > Path(src).stat().st_size:
        raise ValueError(f"{src}: payload past the end of the file")
    x = la.array(src)
    times = d["times"].array(src) if isinstance(d["times"], LazyArray) else np.asarray(d["times"])
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    tmp = dst_dir / f"{name}.npy.tmp"
    out = np.lib.format.open_memmap(tmp, mode="w+", dtype=np.float32, shape=la.shape)
    for i in range(0, la.shape[0], 256):
        blk = np.asarray(x[i:i + 256], dtype=np.float32)
        if not np.all(np.isfinite(blk)):
            raise ValueError(f"{src}: non-finite values near row {i}")
        out[i:i + 256] = blk
    out.flush()
    del out, x
    tmp.replace(dst_dir / f"{name}.npy")
    times = np.asarray(times, dtype=np.float64).ravel()
    n_t = la.shape[-1]
    # The ATM files keep all 300 epoch times (-0.2 .. 0.996 s) but the data start at sample 50 (0 s).
    t_data = times[len(times) - n_t:] if len(times) >= n_t else times
    meta = {"shape": list(la.shape), "src_dtype": str(la.dtype), "ch_names": [str(c) for c in d["ch_names"]],
            "times": [float(t) for t in t_data], "n_times_in_file": int(len(times))}
    (dst_dir / f"{name}_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def load_features(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """(image features, text features), float32, from a ViT-H-14 ``.pt`` file (tensors only)."""
    import torch

    d = torch.load(str(path), weights_only=True, map_location="cpu")
    return d["img_features"].float().numpy(), d["text_features"].float().numpy()


# --- splits --------------------------------------------------------------------------------------------------------

def concept_rank(concepts: Sequence[str], salt: str = SALT) -> list[str]:
    """Unique concepts ordered by sha256(salt + concept)."""
    uniq = sorted(set(concepts))
    return sorted(uniq, key=lambda c: hashlib.sha256((salt + c).encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class Split:
    val: tuple[str, ...]
    cal: tuple[str, ...]
    fit: tuple[str, ...]

    @property
    def order(self) -> tuple[str, ...]:
        return self.cal[:N_ORDER]

    @property
    def certify(self) -> tuple[str, ...]:
        return self.cal[N_ORDER:]


def make_split(train_concepts: Sequence[str], test_concepts: Sequence[str] = (), n_val: int = N_VAL,
               n_cal: int = N_CAL, salt: str = SALT) -> Split:
    """The plan's concept split. Asserts that test concepts are disjoint from training concepts."""
    if set(train_concepts) & set(test_concepts):
        raise ValueError("test concepts overlap training concepts")
    r = concept_rank(train_concepts, salt)
    if len(r) <= n_val + n_cal:
        raise ValueError("too few concepts")
    return Split(tuple(r[:n_val]), tuple(r[n_val:n_val + n_cal]), tuple(r[n_val + n_cal:]))


def image_indices(img_concepts: Sequence[str], concepts: Sequence[str]) -> np.ndarray:
    """Indices of the images whose concept is in ``concepts`` (ascending)."""
    s = set(concepts)
    return np.array([i for i, c in enumerate(img_concepts) if c in s], dtype=np.int64)


def concept_ids(img_concepts: Sequence[str]) -> np.ndarray:
    """Concept index (0..K-1, sorted names) of every image."""
    names = sorted(set(img_concepts))
    pos = {c: i for i, c in enumerate(names)}
    return np.array([pos[c] for c in img_concepts], dtype=np.int64)


# --- units ---------------------------------------------------------------------------------------------------------

def train_units(eeg: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """One unit per training image: the mean of its 4 repetitions. ``eeg`` [N, 4, C, T] -> [len(idx), C, T]."""
    out = np.empty((len(idx),) + eeg.shape[2:], dtype=np.float32)
    for k in range(0, len(idx), 256):
        out[k:k + 256] = np.asarray(eeg[idx[k:k + 256]], dtype=np.float32).mean(axis=1)
    return out


def test_units(eeg: np.ndarray, reps_per_unit: int = UNIT_REPS) -> tuple[np.ndarray, np.ndarray]:
    """20 units per test image: unit g = mean of file repetitions g*4 .. g*4+3. Returns (units [I*G, C, T], image)."""
    n_img, n_rep = eeg.shape[:2]
    g = n_rep // reps_per_unit
    x = np.asarray(eeg[:, : g * reps_per_unit], dtype=np.float32)
    u = x.reshape(n_img, g, reps_per_unit, *eeg.shape[2:]).mean(axis=2)
    return u.reshape(n_img * g, *eeg.shape[2:]), np.repeat(np.arange(n_img), g)


def session_of_file_rep(n_rep: int = TEST_REPS, n_ses: int = N_SESSIONS, seed: int = PREP_SEED) -> np.ndarray:
    """Reconstructed session (0..3) of each file repetition position of the test array (plan.md R1).

    ATM ``save_prepr`` concatenates sessions along the repetition axis (20 each) and applies
    ``sklearn.utils.shuffle(arange(80), random_state=seed)``, i.e. ``RandomState(seed).permutation(80)``.
    """
    perm = np.random.RandomState(seed).permutation(n_rep)
    return perm // (n_rep // n_ses)


def session_units(eeg: np.ndarray, sessions: Sequence[int], reps_per_unit: int = UNIT_REPS,
                  ses_of_rep: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Units built only from repetitions of the given (reconstructed) sessions. Returns (units, image)."""
    ses = session_of_file_rep(eeg.shape[1]) if ses_of_rep is None else np.asarray(ses_of_rep)
    reps = np.nonzero(np.isin(ses, list(sessions)))[0]
    g = len(reps) // reps_per_unit
    reps = reps[: g * reps_per_unit]
    x = np.asarray(eeg[:, reps], dtype=np.float32)
    u = x.reshape(eeg.shape[0], g, reps_per_unit, *eeg.shape[2:]).mean(axis=2)
    return u.reshape(eeg.shape[0] * g, *eeg.shape[2:]), np.repeat(np.arange(eeg.shape[0]), g)


def s0_session_check(eeg: np.ndarray, ses_of_rep: np.ndarray | None = None, max_images: int | None = None) -> dict:
    """S0 (plan.md): same-session repetition pairs correlate more than cross-session pairs (per image, Wilcoxon).

    Uses the EEG only (no decoder, no labels). Returns the statistic per image and the one-sided p-value.
    """
    from scipy.stats import wilcoxon

    ses = session_of_file_rep(eeg.shape[1]) if ses_of_rep is None else np.asarray(ses_of_rep)
    same = ses[:, None] == ses[None, :]
    off = ~np.eye(len(ses), dtype=bool)
    n = eeg.shape[0] if max_images is None else min(max_images, eeg.shape[0])
    diffs = np.empty(n)
    for i in range(n):
        x = np.asarray(eeg[i], dtype=np.float64).reshape(eeg.shape[1], -1)
        x = x - x.mean(axis=1, keepdims=True)
        x /= np.linalg.norm(x, axis=1, keepdims=True) + 1e-12
        r = x @ x.T
        diffs[i] = r[same & off].mean() - r[~same].mean()
    p = float(wilcoxon(diffs, alternative="greater").pvalue) if n >= 10 else float("nan")
    return {"n_images": int(n), "mean_diff": float(diffs.mean()), "p_one_sided": p, "pass": bool(p < 0.01)}


# --- galleries -----------------------------------------------------------------------------------------------------

def make_galleries(unit_img: np.ndarray, img_concept: np.ndarray, pool_imgs: np.ndarray, subject: int,
                   size: int = GALLERY) -> np.ndarray:
    """200-way gallery per val / cal unit: column 0 = its own image, then 199 images of other concepts in the pool.

    ``unit_img``: image index of each unit. ``img_concept``: concept id of every image. ``pool_imgs``: the images of
    the split. Seed ``[subject, 2026, unit index]``. Returns [n_units, size] image indices.
    """
    pool_imgs = np.asarray(pool_imgs)
    by_concept: dict[int, np.ndarray] = {}
    for c in np.unique(img_concept[pool_imgs]):
        by_concept[int(c)] = pool_imgs[img_concept[pool_imgs] == c]
    concepts = np.array(sorted(by_concept))
    if len(concepts) < size:
        raise ValueError("pool has fewer concepts than the gallery size")
    out = np.empty((len(unit_img), size), dtype=np.int64)
    for u, im in enumerate(unit_img):
        rng = np.random.default_rng([subject, 2026, u])
        own = int(img_concept[im])
        others = rng.choice(concepts[concepts != own], size - 1, replace=False)
        out[u, 0] = im
        for j, c in enumerate(others, start=1):
            imgs = by_concept[int(c)]
            out[u, j] = imgs[rng.integers(len(imgs))]
    return out
