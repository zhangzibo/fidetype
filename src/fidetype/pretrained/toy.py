"""Toy pretrained models: try the pretrained API without a download (P14-44, P14-51).

::

    import fidetype.pretrained as ftp

    toy = ftp.toy_model()                                  # tiny random gru-ctc model in a temporary folder
    st = toy.decode(np.zeros((200, 16), np.float32), session=toy.sessions[0])
    hw = ftp.toy_model("xbody-ctc")                        # the runtime of willett-hw
    path = ftp.make_toy_manifest("toy-folder")             # or: write the files, then ftp.load(str(path), weights=...)

A toy model has **random weights**. It has learned nothing, so its text is noise. It uses the
same runtime, the same loader checks (SHA-256 and size of each file) and the same NTS output
as a real model. Its manifest has ``task = "tutorial"`` and no trust config.

Toy runtimes (:data:`TOY_RUNTIMES`) and the real models that use them:

==============  ==========================  =============================================
runtime         real model(s)               toy input of ``decode``
==============  ==========================  =============================================
``gru-ctc``     ``t15-m4-13``, ``t12-v2``   (T, ``n_in``) binned features + ``session=``
``xbody-ctc``   ``willett-hw``              (T, ``n_in``) threshold crossings + ``session=``
``crt-ctc``     ``emg2qwerty-p11-01``       (n >= 84, 32) raw EMG at 2 kHz
``key-lda``     ``kt-semg-lda``             (n, ``n_in``) raw EMG at 2 kHz + ``times=``
==============  ==========================  =============================================

Our own code (Apache-2.0).
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from os import PathLike
from pathlib import Path
from typing import Any, Sequence

import numpy as np

__all__ = ["TOY_RUNTIMES", "TOY_SESSIONS", "TOY_NAMES", "make_toy_manifest", "toy_model"]

#: The runtimes that have a toy model.
TOY_RUNTIMES = ("gru-ctc", "xbody-ctc", "crt-ctc", "key-lda")
#: The default model name of each toy runtime.
TOY_NAMES = {"gru-ctc": "toy-gru", "xbody-ctc": "toy-xbody", "crt-ctc": "toy-crt", "key-lda": "toy-lda"}
#: The default session names of a toy model with a per-session layer (``gru-ctc``, ``xbody-ctc``).
TOY_SESSIONS = ("toy.2026.01.01", "toy.2026.01.02")

_DEFAULT_N_IN = {"gru-ctc": 16, "xbody-ctc": 192, "crt-ctc": 32, "key-lda": 32}
_LICENCE = {"data.licence": "CC0-1.0", "data.research_only": False, "weights": "CC0-1.0",
            "weights_status": "toy model, random numbers"}
_LIMITS = ["Random weights: the output is noise. Use it to learn the API only."]
_TRUST_NOTE = "toy model: no trust config (calibrate one with fidetype.trust.calibrate)"


def _file(role: str, p: Path) -> dict[str, Any]:
    return {"role": role, "name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "size": p.stat().st_size, "url": None}


def _manifest(name: str, runtime: str, title: str, modality: str, input_: dict[str, Any], output: dict[str, Any],
              architecture: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema": "fidetype.pretrained-manifest/0.1", "name": name, "version": "1", "title": title,
            "status": "available", "task": "tutorial", "modality": modality, "runtime": runtime, "input": input_,
            "output": output, "architecture": architecture, "files": files, "licence": dict(_LICENCE),
            "limits": list(_LIMITS), "trust": None, "trust_note": _TRUST_NOTE}


def _dilations(layers: int) -> list[int]:
    return [2 ** (i % 4) for i in range(layers)]


def _trunk(rng: np.random.Generator, d: int, n_blocks: int, kernel: int, ff_mult: int,
           vocab: int) -> dict[str, np.ndarray]:
    """Random arrays of the P11-01 causal trunk + head (:func:`fidetype.pretrained._crt.trunk_keys`)."""
    def r(*shape: int, s: float = 0.1) -> np.ndarray:
        return (rng.standard_normal(shape) * s).astype(np.float32)

    p = {"out_norm.weight": np.ones(d, np.float32), "out_norm.bias": np.zeros(d, np.float32),
         "head.weight": r(vocab, d, s=d ** -0.5), "head.bias": np.zeros(vocab, np.float32)}
    for i in range(n_blocks):
        q = f"blocks.{i}."
        p.update({q + "norm.weight": np.ones(d, np.float32), q + "norm.bias": np.zeros(d, np.float32),
                  q + "dw.weight": r(d, 1, kernel), q + "dw.bias": np.zeros(d, np.float32),
                  q + "ff.0.weight": r(ff_mult * d, d, s=d ** -0.5),
                  q + "ff.0.bias": np.zeros(ff_mult * d, np.float32),
                  q + "ff.3.weight": r(d, ff_mult * d, s=(ff_mult * d) ** -0.5),
                  q + "ff.3.bias": np.zeros(d, np.float32)})
    return p


def _gru(d: Path, name: str, n_in: int, hidden: int, layers: int, sessions: list[str], seed: int) -> dict[str, Any]:
    from fidetype.adapters import b2t25 as B
    from fidetype.decoders.lookahead_gru import LookaheadGRUConfig, NumpyLookaheadGRU

    patch, stride = 4, 2
    cfg = LookaheadGRUConfig(n_in=n_in, n_out=len(B.VOCAB), n_sessions=len(sessions), hidden=hidden,
                             layers=layers, patch=patch, stride=stride, smooth_sd=1.0, la_max=3, la_proj=4)
    params = {k: v for k, v in NumpyLookaheadGRU.random(cfg, seed=seed).params.items() if not k.startswith("la_")}
    weights = d / f"{name}.weights.npz"
    np.savez(weights, **params)
    return _manifest(
        name, "gru-ctc", "Toy model: random GRU-CTC phoneme decoder (learned nothing)", "intracortical",
        {"bin_s": 0.02, "channels": n_in, "file_format": "b2t25-hdf5"},
        {"vocab_type": "phoneme", "vocab_id": B.VOCAB_ID, "frame_period_s": 0.02 * stride, "latency_s": 0.0},
        {"patch": patch, "stride": stride, "layers": layers, "hidden": hidden, "smooth_sd": 1.0, "lookahead": None,
         "input_round": "float16", "sessions": sessions},
        [_file("weights", weights)])


def _xbody(d: Path, name: str, n_in: int, hidden: int, layers: int, sessions: list[str],
           seed: int) -> dict[str, Any]:
    from fidetype.pretrained import _xbody as X

    rng = np.random.default_rng(seed)
    kernel, ff_mult = 3, 2
    p = {"mean": np.zeros((len(sessions), n_in), np.float32), "std": np.ones((len(sessions), n_in), np.float32),
         "stem.weight": (rng.standard_normal((hidden, n_in)) * n_in ** -0.5).astype(np.float32),
         "stem.bias": np.zeros(hidden, np.float32), **_trunk(rng, hidden, layers, kernel, ff_mult, len(X.VOCAB))}
    weights = d / f"{name}.weights.npz"
    np.savez(weights, **p)
    return _manifest(
        name, "xbody-ctc", "Toy model: random causal TCN CTC handwriting decoder (learned nothing)", "intracortical",
        {"channels": n_in, "bin_s": X.BIN_S, "file_format": "willett-hw-mat"},
        {"vocab_type": "char", "vocab_id": "fidetype-p11-01-keys-v1", "frame_period_s": X.BIN_S, "latency_s": 0.0},
        {"d": hidden, "kernel": kernel, "dilations": _dilations(layers), "ff_mult": ff_mult, "vocab": len(X.VOCAB),
         "sessions": sessions},
        [_file("weights", weights)])


def _crt(d: Path, name: str, n_in: int, hidden: int, layers: int, sessions: list[str], seed: int) -> dict[str, Any]:
    from fidetype.pretrained import _crt as C

    if n_in != C.N_CH:
        raise ValueError(f"the crt-ctc runtime has a fixed input of {C.N_CH} EMG channels (two 16-electrode bands); "
                         f"got n_in={n_in}")
    if hidden % 2:
        raise ValueError(f"crt-ctc: hidden must be even (half per wristband), got {hidden}")
    rng = np.random.default_rng(seed)
    kernel, ff_mult, ring_c, ring_k = 3, 2, 4, 3
    p = {"mean": np.zeros((C.N_CH, C.N_BANDS), np.float32), "std": np.ones((C.N_CH, C.N_BANDS), np.float32)}
    for side in ("left", "right"):
        p[f"{side}.conv.weight"] = (rng.standard_normal((ring_c, C.N_BANDS, ring_k)) * 0.1).astype(np.float32)
        p[f"{side}.conv.bias"] = np.zeros(ring_c, np.float32)
        p[f"{side}.proj.weight"] = (rng.standard_normal((hidden // 2, ring_c * C.N_EL)) * 0.1).astype(np.float32)
        p[f"{side}.proj.bias"] = np.zeros(hidden // 2, np.float32)
    p.update(_trunk(rng, hidden, layers, kernel, ff_mult, len(C.VOCAB)))
    weights = d / f"{name}.weights.npz"
    np.savez(weights, **p)
    return _manifest(
        name, "crt-ctc", "Toy model: random ring-TCN CTC EMG typing decoder (learned nothing)", "emg",
        {"channels": C.N_CH, "sample_rate_hz": float(C.FS), "file_format": "emg2qwerty-hdf5"},
        {"vocab_type": "char", "vocab_id": "fidetype-p11-01-keys-v1", "frame_period_s": C.HOP / C.FS,
         "latency_s": 0.0},
        {"d": hidden, "ring_c": ring_c, "ring_k": ring_k, "kernel": kernel, "dilations": _dilations(layers),
         "ff_mult": ff_mult, "vocab": len(C.VOCAB)},
        [_file("weights", weights)])


def _key_lda(d: Path, name: str, n_in: int, hidden: int, layers: int, sessions: list[str],
             seed: int) -> dict[str, Any]:
    from fidetype.adapters.kt_semg import KEY_VOCAB, LdaKeyDecoder
    from fidetype.live.model import KeyWindowModel

    rng = np.random.default_rng(seed)
    n_sub, fs = 2, 2000.0
    dim = n_sub * n_in
    v = len(KEY_VOCAB)
    lda = LdaKeyDecoder(rng.standard_normal((v, dim)) * 0.5, np.eye(dim), np.full(v, -np.log(v)), np.zeros(dim),
                        np.ones(dim))
    card = {"name": name, "version": "1", "sample_rate": fs, "channels": n_in, "modality": "emg",
            "timing": "markers", "scaler_n0": 20.0, "window": {"pre_s": 0.15, "post_s": 0.05, "n_sub": n_sub},
            "training": {"data": "none: random numbers (fidetype.pretrained.toy)", "licence": "CC0-1.0"},
            "warning": "Toy model: random weights, the output is noise."}
    weights, js = KeyWindowModel(lda, card, "", (np.zeros(dim), np.ones(dim))).save(d / name)
    return _manifest(
        name, "key-lda", "Toy model: random key-window LDA (learned nothing)", "emg",
        {"channels": n_in, "sample_rate_hz": fs, "file_format": "kt-semg-run"},
        {"vocab_type": "key", "vocab_id": "key.w3c-code.az-space-punct-edit-32", "frame_period_s": None,
         "latency_s": 0.05},
        {"code": "fidetype.live.model (KeyWindowModel)", "card": js.name},
        [_file("card", js), _file("weights", weights)])


_BUILDERS = {"gru-ctc": _gru, "xbody-ctc": _xbody, "crt-ctc": _crt, "key-lda": _key_lda}


def make_toy_manifest(folder: str | PathLike[str], *, runtime: str = "gru-ctc", name: str | None = None,
                      n_in: int | None = None, hidden: int = 32, layers: int = 2,
                      sessions: Sequence[str] = TOY_SESSIONS, seed: int = 0) -> Path:
    """Write random weights and a manifest that lists their SHA-256 and size. Return the manifest path.

    ``folder`` gets the release files and ``<name>.json``. Load the model with
    ``fidetype.pretrained.load(str(path), weights=folder)``.

    - ``runtime``: one of :data:`TOY_RUNTIMES`. ``name``: default ``TOY_NAMES[runtime]``.
    - ``n_in``: input channels (default 16 for ``gru-ctc``, 192 for ``xbody-ctc``, 32 for ``crt-ctc``
      and ``key-lda``; ``crt-ctc`` accepts only 32).
    - ``hidden``, ``layers``: model width and depth (``key-lda`` does not use them).
    - ``sessions``: the session names of the per-session layer (``gru-ctc`` and ``xbody-ctc`` only).
    """
    if runtime not in TOY_RUNTIMES:
        raise ValueError(f"no toy model for runtime {runtime!r}; toy runtimes: {list(TOY_RUNTIMES)}")
    name = name or TOY_NAMES[runtime]
    n_in = int(n_in) if n_in is not None else _DEFAULT_N_IN[runtime]
    if n_in < 1 or int(hidden) < 1 or int(layers) < 1:
        raise ValueError("n_in, hidden and layers must be >= 1")
    sessions = [str(s) for s in sessions]
    if runtime in ("gru-ctc", "xbody-ctc") and not sessions:
        raise ValueError("a toy model needs at least one session name")
    if runtime in ("crt-ctc", "key-lda"):
        sessions = []
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    manifest = _BUILDERS[runtime](d, name, n_in, int(hidden), int(layers), sessions, int(seed))
    path = d / f"{name}.json"
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return path


def toy_model(runtime: str = "gru-ctc", folder: str | PathLike[str] | None = None, **kwargs: Any) -> Any:
    """Make and load a toy model (a :class:`~fidetype.pretrained.PretrainedDecoder`).

    ``runtime``: one of :data:`TOY_RUNTIMES` (default ``gru-ctc``). ``folder``: where the files go
    (default: a new temporary folder, which stays after the call). ``kwargs``: as
    :func:`make_toy_manifest`. ``model.sessions`` lists the session names (empty for ``crt-ctc``
    and ``key-lda``).
    """
    from fidetype.pretrained import load

    if not isinstance(runtime, str) or runtime not in TOY_RUNTIMES:
        raise ValueError(f"no toy model for runtime {runtime!r}; toy runtimes: {list(TOY_RUNTIMES)}. "
                         f"The first argument is the runtime (P14-51); pass the folder as folder=")
    d = Path(folder) if folder is not None else Path(tempfile.mkdtemp(prefix="fidetype-toy-"))
    return load(str(make_toy_manifest(d, runtime=runtime, **kwargs)), weights=d)
