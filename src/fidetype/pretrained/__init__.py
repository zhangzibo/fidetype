"""Pretrained decoders: one line to load, one line to decode into NeuralTextStream (P14-01).

::

    import fidetype.pretrained as ftp

    m = ftp.load("t15-m4-13")                      # checks SHA-256 and size of the weights
    path = "t15.2023.08.13/data_val.hdf5"
    print(m.n_items(path))                         # number of trials (no decoding)
    streams = m.decode_file(path, limit=5)         # a list: one NTS stream per trial
    print(m.text(streams[0]))                      # greedy readout (phonemes, characters or keys)
    print(m.decide(streams[0]).action)             # the committed trust guard, right input per model

    toy = ftp.toy_model()                          # a tiny random model to try the API (no download)

``fidetype.decoders.load`` is the same function. Command line: ``fidetype decoders list|info|path|
verify|decode``.

Models: :func:`list_models` (packaged manifests, :mod:`fidetype.pretrained.manifest`). The weights
are **not** in the package or the git repository. :func:`load` finds them, in this order:

1. ``weights=`` (a folder with the release files, or the path of the weights file);
2. ``cache_dir=`` / the environment variable ``FIDETYPE_PRETRAINED_DIR``;
3. ``~/.cache/fidetype/pretrained`` (``$FIDETYPE_CACHE/pretrained`` if that variable is set).

Inside a cache folder, the files of model ``<name>`` are in ``<cache>/<name>/``. Each file must
match the SHA-256 and the size in the manifest, or :class:`WeightsMismatch` is raised.
``download=True`` fetches a missing file from its ``url``; no model has a URL yet (hosting is the
user step P14-02), so today the files come from ``tools/pretrained/export_weights.py`` on a machine
with our training outputs.

Licence gate (FEP-0010): a model whose manifest has ``data.research_only = true`` (emg2qwerty,
CC BY-NC-SA 4.0) refuses to load or download (:class:`ResearchOnlyRefused`) unless the caller passes
``accept_research_only=True``. Every stream carries ``data.licence``, ``data.research_only`` and
``decoder.weights_sha256``, so the collector's ``refuse_research_only`` gate drops it downstream.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
import warnings
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from fidetype import __version__ as _FIDETYPE_VERSION
from fidetype.pretrained.manifest import FileEntry, Manifest, ManifestError, all_manifests, load_manifest

__all__ = ["PretrainedError", "ModelNotAvailable", "WeightsNotFound", "WeightsMismatch", "ResearchOnlyRefused",
           "NoTrustConfig", "Manifest", "ManifestError", "PretrainedDecoder", "default_cache_dir", "list_models",
           "info", "load", "resolve_files", "download", "sha256_file", "toy_model", "make_toy_manifest"]

ENV_DIR = "FIDETYPE_PRETRAINED_DIR"
ENV_CACHE = "FIDETYPE_CACHE"
ADAPTER_NAME = "fidetype.pretrained"


class PretrainedError(RuntimeError):
    """Base class of the errors of this module."""


class ModelNotAvailable(PretrainedError):
    """The model is registered but has no weights yet (status ``planned``)."""


class WeightsNotFound(PretrainedError, FileNotFoundError):
    """A release file is not in the weights folder or the cache, and cannot be downloaded."""


class WeightsMismatch(PretrainedError):
    """A release file does not match the SHA-256 or the size in the manifest."""


class ResearchOnlyRefused(PretrainedError, PermissionError):
    """The model is research only (non-commercial data licence) and the caller did not opt in."""


class NoTrustConfig(PretrainedError):
    """The model has no committed trust config (or its text decoder is not packaged)."""


def default_cache_dir() -> Path:
    """The cache folder: ``$FIDETYPE_PRETRAINED_DIR``, else ``$FIDETYPE_CACHE/pretrained``, else ``~/.cache/...``."""
    if os.environ.get(ENV_DIR):
        return Path(os.environ[ENV_DIR])
    if os.environ.get(ENV_CACHE):
        return Path(os.environ[ENV_CACHE]) / "pretrained"
    return Path.home() / ".cache" / "fidetype" / "pretrained"


def sha256_file(path: str | PathLike[str]) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def list_models(status: str | None = None) -> list[Manifest]:
    """All packaged model manifests (``status``: only ``available`` or ``planned``)."""
    return [m for m in all_manifests() if status is None or m.status == status]


def info(name: str) -> Manifest:
    """The manifest of one model."""
    return load_manifest(name)


def _gate(m: Manifest, accept_research_only: bool) -> None:
    if m.research_only and not accept_research_only:
        raise ResearchOnlyRefused(
            f"{m.name} is research only: its training data licence is {m.data_licence} (data.research_only = true). "
            f"Its weights keep these terms ({m.licence.get('weights') or 'see the manifest'}). Pass "
            f"accept_research_only=True (CLI: --accept-research-only) only if your use is non-commercial research "
            f"and you accept the licence. Streams from it carry data.research_only = true.")


def _candidates(m: Manifest, f: FileEntry, weights: str | PathLike[str] | None, cache: Path) -> list[Path]:
    out: list[Path] = []
    if weights is not None:
        w = Path(weights)
        if w.is_dir():
            out += [w / f.name, w / m.name / f.name]
            if f.role == "text":
                out.append(w / "text" / f.name)
        else:
            out.append(w if f.role == "weights" else w.parent / f.name)
    out.append(cache / m.name / f.name)
    if f.role == "text":
        out.append(cache / "text" / f.name)
    return out


def _check(p: Path, f: FileEntry, verify: bool) -> None:
    size = p.stat().st_size
    if size != f.size:
        raise WeightsMismatch(f"{p}: size {size} bytes, the manifest says {f.size}")
    if verify:
        sha = sha256_file(p)
        if sha != f.sha256:
            raise WeightsMismatch(f"{p}: SHA-256 {sha} does not match the manifest ({f.sha256}); the file is "
                                  f"damaged, changed or of another release")


def download(name: str, *, cache_dir: str | PathLike[str] | None = None, roles: Sequence[str] | None = None,
             accept_research_only: bool = False) -> dict[str, Path]:
    """Download the release files of a model into the cache (needs a ``url`` in the manifest).

    No model has a URL yet: hosting is the user step P14-02. Each file is checked (SHA-256, size)
    before it moves into the cache.
    """
    m = load_manifest(name)
    _gate(m, accept_research_only)
    cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    out: dict[str, Path] = {}
    for f in m.files:
        if roles is not None and f.role not in roles:
            continue
        dst = cache / m.name / f.name
        if dst.is_file():
            _check(dst, f, True)
            out[f.name] = dst
            continue
        if not f.url:
            raise WeightsNotFound(_not_found_msg(m, f, [dst]))
        dst.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dst.parent, prefix=f".{f.name}.", suffix=".part", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            with urllib.request.urlopen(f.url, timeout=60) as r:  # noqa: S310 (https only, checked in the manifest)
                shutil.copyfileobj(r, tmp, 1 << 20)
        try:
            _check(tmp_path, f, True)
        except WeightsMismatch:
            tmp_path.unlink(missing_ok=True)
            raise
        os.replace(tmp_path, dst)
        out[f.name] = dst
    return out


def _not_found_msg(m: Manifest, f: FileEntry, tried: Sequence[Path]) -> str:
    host = (m.raw.get("hosting") or {}).get("notes") or "no download URL yet (hosting: roadmap P14-02)"
    return (f"{m.name}: release file {f.name} ({f.role}, {f.size} bytes) not found. Looked in: "
            f"{', '.join(str(p) for p in tried)}. Put the file there, pass weights=<folder>, or set "
            f"{ENV_DIR}. Download: {host}.")


def resolve_files(name: str | Manifest, *, weights: str | PathLike[str] | None = None,
                  cache_dir: str | PathLike[str] | None = None, roles: Sequence[str] = ("weights", "card", "guard"),
                  download_missing: bool = False, verify: bool = True,
                  accept_research_only: bool = False) -> dict[str, Path]:
    """Find and check the release files of a model: file name -> path."""
    m = name if isinstance(name, Manifest) else load_manifest(name)
    _gate(m, accept_research_only)
    if m.status != "available":
        raise ModelNotAvailable(f"{m.name} is registered but not available yet: {m.raw.get('status_note') or m.status}")
    cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    out: dict[str, Path] = {}
    for f in m.files:
        if f.role not in roles:
            continue
        tried = _candidates(m, f, weights, cache)
        hit = next((p for p in tried if p.is_file()), None)
        if hit is None:
            if download_missing and f.url:
                hit = download(m.name, cache_dir=cache, roles=[f.role], accept_research_only=accept_research_only)[f.name]
            else:
                raise WeightsNotFound(_not_found_msg(m, f, tried))
        _check(hit, f, verify)
        out[f.name] = hit
    return out


def _npz(path: Path, keys: Sequence[str]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as z:
        missing = [k for k in keys if k not in z.files]
        if missing:
            raise WeightsMismatch(f"{path.name}: missing arrays {missing[:5]}")
        return {k: np.asarray(z[k], dtype=np.float32) for k in z.files}


# ---------------------------------------------------------------------------------------------------
# decoders
# ---------------------------------------------------------------------------------------------------


class PretrainedDecoder:
    """A loaded pretrained decoder. Use :func:`load`; do not build it directly.

    - :meth:`decode` (= :meth:`decode_array`): one input array -> one
      :class:`~fidetype.streams.spec.NeuralTextStream`.
    - :meth:`decode_file`: a data file -> a list of streams (one per trial, prompt or typing
      burst), with the items (keys, and the ground truth for evaluation) when ``with_items=True``.
    - :meth:`n_items`: the number of items of a data file (no decoding).
    - :meth:`text`: a greedy readout of a stream (no LM).
    - :meth:`guard`: the committed trust config as a :class:`~fidetype.trust.dropin.TrustGuard`.
    - :meth:`guard_input` / :meth:`decide`: the guard input of a stream for this model, and the
      guard decision on a stream (one call for every model).
    - :meth:`save`: write streams as NTS JSON Lines files.
    """

    def __init__(self, manifest: Manifest, files: Mapping[str, Path], *, cache_dir: Path,
                 weights: str | PathLike[str] | None) -> None:
        self.manifest = manifest
        self.files = dict(files)
        self._cache_dir = cache_dir
        self._weights_arg = weights

    # --- identity ---------------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def weights_sha256(self) -> str:
        return str(self.manifest.weights_sha256)

    @property
    def research_only(self) -> bool:
        return self.manifest.research_only

    @property
    def sessions(self) -> tuple[str, ...]:
        """The recording sessions that the day layer of this model knows (empty if it has none)."""
        return tuple(str(s) for s in (self.manifest.architecture.get("sessions") or []))

    def card(self) -> str:
        return self.manifest.card()

    def __repr__(self) -> str:
        return f"<PretrainedDecoder {self.name} v{self.manifest.version} ({self.manifest.runtime})>"

    def _path(self, role: str) -> Path:
        return self.files[self.manifest.file(role).name]

    def _decoder_extra(self) -> dict[str, Any]:
        return {**self.manifest.licence_meta(), "fidetype.pretrained": f"{self.name}@{self.manifest.version}"}

    # --- decoding -----------------------------------------------------------------------------------

    def decode(self, x: Any, **kwargs: Any) -> Any:
        """One input array -> one stream (the same as :meth:`decode_array`).

        Deprecated (P14-44): a path (str or PathLike) still gives a list of streams, with a
        ``DeprecationWarning``. Use :meth:`decode_file` for files: it always returns a list.
        """
        if isinstance(x, (str, PathLike)):
            warnings.warn("decode(path) is deprecated: use decode_file(path) for a data file (it returns a list); "
                          "decode(array) returns one stream", DeprecationWarning, stacklevel=2)
            return self.decode_file(x, **kwargs)
        return self.decode_array(x, **kwargs)

    def n_items(self, path: str | PathLike[str], **kwargs: Any) -> int:
        """The number of items (trials, prompts, typing bursts) of a data file, without decoding.

        Valid ``decode_file(indices=...)`` values are ``0 .. n_items(path) - 1``. ``kwargs``: the
        reader options that change the count (``blocks=`` for ``willett-hw``).
        """
        from fidetype.pretrained import readers as R

        return R.count_items(str(self.manifest.input.get("file_format")), path, **kwargs)

    def decode_array(self, x: Any, **kwargs: Any) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def decode_file(self, path: str | PathLike[str], *, limit: int | None = None, with_items: bool = False,
                    **kwargs: Any) -> Any:  # pragma: no cover - overridden
        raise NotImplementedError

    def text(self, stream: Any) -> str:
        """Greedy CTC readout of a stream (no LM)."""
        from fidetype.eval.metrics import ctc_greedy_decode

        return ctc_greedy_decode(stream)

    # --- trust ----------------------------------------------------------------------------------------

    def guard_path(self) -> Path:
        """The trust config file of this model (packaged, or a release file with role ``guard``)."""
        t = self.manifest.trust
        if not t:
            raise NoTrustConfig(f"{self.name}: no committed trust config. "
                                f"{(self.manifest.raw.get('trust_note') or '')}".strip())
        cfg = str(t["config"])
        if cfg.startswith("file:"):
            return self.files[cfg.removeprefix("file:")]
        from importlib import resources

        p = Path(str(resources.files("fidetype.pretrained").joinpath(cfg)))
        if not p.is_file():
            raise NoTrustConfig(f"{self.name}: packaged trust config {cfg} is missing")
        return p

    def guard(self, decode_fn: Callable[..., Any] | None = None, *, offer_gate: Any = None,
              **kwargs: Any) -> Any:
        """The committed trust config of this model as a TrustGuard (``fidetype.trust.load``).

        ``offer_gate`` (P5-33): None (default) uses the manifest gate ``trust.offer_gate`` if there is one
        (it withholds offers on no-evidence input; commits do not change); ``False`` switches it off; an
        :class:`~fidetype.trust.OfferGate` replaces it.
        """
        import fidetype.trust as ft

        if offer_gate is None:
            og = (self.manifest.trust or {}).get("offer_gate")
            if og:
                from fidetype.trust.offer_gate import OfferGate

                offer_gate = OfferGate.from_dict(og)
        return ft.load(self.guard_path(), decode_fn=decode_fn, offer_gate=offer_gate, **kwargs)

    def guard_input(self, stream: Any) -> Any:
        """The input of this model's guard for one stream: ``guard.decide(model.guard_input(stream))``.

        The default is the score matrix ``stream.log_probs``. A model whose guard reads an n-best
        list (``kt-semg-lda``) overrides it (P14-44).
        """
        return stream.log_probs

    def decide(self, stream: Any, *, guard: Any = None, utterance_id: str | None = None) -> Any:
        """The guard decision (a ``TrustResult``) on one stream of this model: the same call for every model.

        ``guard``: a TrustGuard; default: :meth:`guard` (built at the first call, then kept).
        Raises :class:`NoTrustConfig` if the model has no committed trust config.
        """
        if guard is None:
            guard = getattr(self, "_default_guard", None)
            if guard is None:
                guard = self._default_guard = self.guard()
        return guard.decide(self.guard_input(stream), utterance_id=utterance_id)

    # --- output -------------------------------------------------------------------------------------

    def save(self, streams: Any, out_dir: str | PathLike[str], prefix: str | None = None) -> list[Path]:
        """Write streams as ``<prefix>-NNNN.nts.jsonl`` files in ``out_dir``; return the paths."""
        from fidetype.writer import write_stream

        if not isinstance(streams, (list, tuple)):
            streams = [streams]
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        pre = prefix or self.name
        return [write_stream(s, d / f"{pre}-{i:04d}.nts.jsonl") for i, s in enumerate(streams)]


def _session_index(m: Manifest, session: Any) -> int:
    sessions = list(m.architecture.get("sessions") or [])
    if isinstance(session, (int, np.integer)) and not isinstance(session, bool):
        if not 0 <= int(session) < len(sessions):
            raise ValueError(f"{m.name}: session index {session} out of range 0..{len(sessions) - 1}")
        return int(session)
    if isinstance(session, str):
        if session not in sessions:
            raise ValueError(f"{m.name}: unknown session {session!r}. The day layer of this model exists only for "
                             f"its {len(sessions)} recording sessions ({sessions[0]} .. {sessions[-1]}); a new "
                             f"session needs calibration (not in this model).")
        return sessions.index(session)
    raise ValueError(f"{m.name}: pass session= (a session name such as {sessions[0]!r}, or its index)")


class GruCtcDecoder(PretrainedDecoder):
    """Runtime ``gru-ctc``: our causal GRU-CTC phoneme decoders on 20 ms binned implant features."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        from fidetype.pretrained import _gru

        arch = self.manifest.architecture
        self._la = arch.get("lookahead")
        self._p = _npz(self._path("weights"), _gru.required_keys(int(arch["layers"]), bool(self._la)))
        n_s = self._p["day_W"].shape[0]
        if n_s != len(arch.get("sessions") or []):
            raise WeightsMismatch(f"{self.name}: weights have {n_s} sessions, the manifest lists "
                                  f"{len(arch.get('sessions') or [])}")

    def logits(self, x: Any, session: Any) -> np.ndarray:
        from fidetype.pretrained import _gru

        a = self.manifest.architecture
        x = np.asarray(x, dtype=np.float32)
        if a.get("input_round") == "float16":
            x = x.astype(np.float16).astype(np.float32)  # the training data were stored as float16
        la_bins = None if not self._la else int(self._la["bins"])
        return _gru.gru_ctc_logits(self._p, x, _session_index(self.manifest, session), patch=int(a["patch"]),
                                   stride=int(a["stride"]), layers=int(a["layers"]), hidden=int(a["hidden"]),
                                   smooth_sd=float(a["smooth_sd"]), la_bins=la_bins,
                                   la_max=int(self._la["max"]) if self._la else 0)

    def _stream(self, logits: np.ndarray, id_part: str) -> Any:
        from fidetype.adapters import b2t25 as B
        from fidetype.adapters.ctc_logits import DecoderInfo, from_array, vocab_from_list

        a = self.manifest.architecture
        o = self.manifest.output
        v = vocab_from_list(list(B.VOCAB), blank=0, vocab_type="phoneme", vocab_id=B.VOCAB_ID)
        bin_s = float(self.manifest.input.get("bin_s", 0.02))
        extra = {**self._decoder_extra(), "device.invasive": True, "implant.bin_s": bin_s,
                 "fidetype.timing": f"frame k = end of input patch: ({a['stride']} k + {a['patch']}) x {bin_s} s"}
        dec = DecoderInfo(modality="intracortical", name=f"fidetype-{self.name}", version=self.manifest.version,
                          causal=True, language=self.manifest.language, weights_sha256=self.weights_sha256, extra=extra)
        return from_array(logits, v, dec, frame_period=float(o["frame_period_s"]), t0=int(a["patch"]) * bin_s,
                          latency=float(o.get("latency_s", 0.0)), input_kind="logits", source=f"fidetype-{self.name}",
                          id_parts=(id_part,))

    def decode_array(self, x: Any, session: Any = None, **_: Any) -> Any:
        """``x`` (T, 512) binned features of one trial (as in the public files) -> one phoneme stream."""
        return self._stream(self.logits(x, session), "array")

    def decode_file(self, path: str | PathLike[str], *, limit: int | None = None, with_items: bool = False,
                    indices: list[int] | None = None, **_: Any) -> Any:
        from fidetype.pretrained import readers as R

        fmt = self.manifest.input.get("file_format")
        if fmt == "b2t25-hdf5":
            items = R.read_b2t25_hdf5(path, limit=limit, indices=indices)
        elif fmt == "b2t24-mat":
            n = self.manifest.input.get("normalisation") or {}
            items = R.read_b2t24_session(path, window=int(n.get("window_trials", 20)),
                                         clip=float(n.get("clip_abs_z", 10.0)), limit=limit)
            if indices is not None:
                R.check_indices(indices, len(items), Path(path).name)
                items = [items[i] for i in indices]
        else:
            raise ValueError(f"{self.name}: unknown input file format {fmt!r}")
        streams = [self._stream(self.logits(it.x, it.session), it.key) for it in items]
        return list(zip(items, streams)) if with_items else streams

    def text(self, stream: Any) -> str:
        """Greedy phonemes, ARPAbet separated by spaces; ``|`` marks a word boundary (SIL)."""
        from fidetype.eval.metrics import ctc_greedy_ids

        toks = [stream.vocab[i] for i in ctc_greedy_ids(stream)]
        return " ".join("|" if t == "SIL" else t for t in toks)

    def guard(self, decode_fn: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
        """The committed trust config. Without ``decode_fn`` the packaged text decoder is built.

        The text decoder needs its text resources (manifest files with role ``text``) in the model
        folder or in ``<cache>/text/``.
        """
        if decode_fn is None:
            decode_fn = self.text_decoder()
        return super().guard(decode_fn=decode_fn, **kwargs)

    def text_decoder(self) -> Callable[[np.ndarray], list[dict[str, Any]]]:
        """The phoneme -> word n-best decoder that the committed guard was calibrated with."""
        from fidetype.pretrained.textdec import DECODER_ID, make_phoneme_words_decode_fn

        t = self.manifest.trust
        if not t:
            raise NoTrustConfig(f"{self.name}: no committed trust config. "
                                f"{(self.manifest.raw.get('trust_note') or '')}".strip())
        if t.get("decode") != DECODER_ID:
            raise NoTrustConfig(f"{self.name}: the text decoder {t.get('decode')!r} is not packaged. "
                                f"{(self.manifest.raw.get('trust_note') or '')}".strip())
        files = resolve_files(self.manifest, weights=self._weights_arg, cache_dir=self._cache_dir, roles=("text",),
                              accept_research_only=True)
        by_name = {p.name: p for p in files.values()}
        role_files = {k: by_name[v] for k, v in t["text_files"].items()}
        return make_phoneme_words_decode_fn(role_files, t["decoder_settings"])


class CrtCtcDecoder(PretrainedDecoder):
    """Runtime ``crt-ctc``: the P11-01 causal ring-TCN on 2 kHz wristband EMG (emg2qwerty layout)."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        from fidetype.pretrained import _crt

        arch = self.manifest.architecture
        self._p = _npz(self._path("weights"), _crt.required_keys(len(arch["dilations"])))

    def log_probs_of_features(self, feat: np.ndarray) -> np.ndarray:
        from fidetype.pretrained import _crt

        a = self.manifest.architecture
        return _crt.crt_log_probs(self._p, feat, ring_k=int(a["ring_k"]), kernel=int(a["kernel"]),
                                  dilations=list(a["dilations"]))

    def _stream(self, lp: np.ndarray, t0: float, id_part: str) -> Any:
        from fidetype.adapters.ctc_logits import DecoderInfo, from_array, vocab_from_list
        from fidetype.pretrained import _crt

        v = vocab_from_list(list(_crt.VOCAB), blank=0, vocab_type="char", vocab_id=self.manifest.output["vocab_id"])
        extra = {**self._decoder_extra(), "device.invasive": False, "emg.placement": "wrist",
                 "fidetype.timing": "frame k = end of the 32 ms window: (20 k + 64) / 2000 s"}
        dec = DecoderInfo(modality="emg", name=f"fidetype-{self.name}", version=self.manifest.version, causal=True,
                          language=self.manifest.language, weights_sha256=self.weights_sha256, extra=extra)
        return from_array(lp, v, dec, frame_period=float(self.manifest.output["frame_period_s"]), t0=t0, latency=0.0,
                          input_kind="log_probs", source=f"fidetype-{self.name}", id_parts=(id_part,))

    def decode_array(self, x: Any, **_: Any) -> Any:
        """``x`` (n, 32) raw EMG at 2 kHz (left band channels 0-15, right 16-31) -> one character stream."""
        from fidetype.pretrained import _crt

        x = np.asarray(x, dtype=np.float32)
        if x.ndim != 2 or x.shape[1] != _crt.N_CH:
            raise ValueError(f"EMG must be (n, {_crt.N_CH}), got {x.shape}")
        feat = _crt.frames_from_block(x)
        if len(feat) < 2:
            raise ValueError("EMG too short (needs at least 84 samples)")
        return self._stream(self.log_probs_of_features(feat), _crt.WIN / _crt.FS, "array")

    def decode_file(self, path: str | PathLike[str], *, limit: int | None = None, with_items: bool = False,
                    **_: Any) -> Any:
        """One emg2qwerty session file -> one stream per text prompt (causal, with left context)."""
        from fidetype.pretrained import _crt
        from fidetype.pretrained import readers as R

        sess, items = R.read_emg2qwerty_session(path)
        rf = _crt.receptive_field(int(self.manifest.architecture["kernel"]), self.manifest.architecture["dilations"])
        out = []
        try:
            nf = _crt.n_frames(sess.n_samples)
            for it in items[:limit] if limit is not None else items:
                lo, hi = it.extra["lo"], it.extra["hi"]
                klo = max(0, -((_crt.WIN - lo) // _crt.HOP))  # first frame whose window ends at or after lo
                khi = min(nf, max(0, -((_crt.WIN - hi) // _crt.HOP)) + 1)
                if khi - klo < 2:
                    continue
                c = max(0, klo - rf)
                emg = sess.read_emg(c * _crt.HOP, (khi - 1) * _crt.HOP + _crt.WIN)
                lp = self.log_probs_of_features(_crt.frames_from_block(emg))[klo - c:khi - c]
                st = self._stream(lp, (klo * _crt.HOP + _crt.WIN) / _crt.FS, it.key)
                out.append((it, st))
        finally:
            sess.close()
        return out if with_items else [s for _, s in out]

    def text(self, stream: Any) -> str:
        """Greedy CTC characters (Backspace and Enter as the symbols U+232B and U+23CE)."""
        return super().text(stream)


class XBodyCtcDecoder(PretrainedDecoder):
    """Runtime ``xbody-ctc``: the P15-08 Willett handwriting decoder (linear stem + P11-01 causal trunk)."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        from fidetype.pretrained import _xbody

        arch = self.manifest.architecture
        self._p = _npz(self._path("weights"), _xbody.required_keys(len(arch["dilations"])))
        n_s = self._p["mean"].shape[0]
        if n_s != len(arch.get("sessions") or []):
            raise WeightsMismatch(f"{self.name}: weights have {n_s} sessions, the manifest lists "
                                  f"{len(arch.get('sessions') or [])}")

    def log_probs(self, x: Any, session: Any) -> np.ndarray:
        """``x`` (T, 192) threshold crossings of one sentence (10 ms bins) -> (T, 98) log-probs."""
        from fidetype.pretrained import _xbody

        a = self.manifest.architecture
        return _xbody.xbody_log_probs(self._p, np.asarray(x, np.float32), _session_index(self.manifest, session),
                                      kernel=int(a["kernel"]), dilations=list(a["dilations"]))

    def _stream(self, lp: np.ndarray, id_part: str) -> Any:
        from fidetype.adapters.ctc_logits import DecoderInfo, from_array, vocab_from_list
        from fidetype.pretrained import _xbody

        v = vocab_from_list(list(_xbody.VOCAB), blank=0, vocab_type="char", vocab_id=self.manifest.output["vocab_id"])
        extra = {**self._decoder_extra(), "device.invasive": True, "implant.bin_s": _xbody.BIN_S,
                 "fidetype.timing": "frame k = end of 10 ms bin k after the go cue: (k + 1) x 0.01 s"}
        dec = DecoderInfo(modality="intracortical", name=f"fidetype-{self.name}", version=self.manifest.version,
                          causal=True, language=self.manifest.language, weights_sha256=self.weights_sha256, extra=extra)
        return from_array(lp, v, dec, frame_period=float(self.manifest.output["frame_period_s"]), t0=_xbody.BIN_S,
                          latency=float(self.manifest.output.get("latency_s", 0.0)), input_kind="log_probs",
                          source=f"fidetype-{self.name}", id_parts=(id_part,))

    def decode_array(self, x: Any, session: Any = None, **_: Any) -> Any:
        """``x`` (T, 192) threshold crossings of one sentence plus ``session=`` -> one character stream."""
        return self._stream(self.log_probs(x, session), "array")

    def decode_file(self, path: str | PathLike[str], *, limit: int | None = None, with_items: bool = False,
                    blocks: list[int] | None = None, **_: Any) -> Any:
        """One Willett session (``t5.YYYY.MM.DD`` folder or its ``sentences.mat``) -> one stream per sentence."""
        from fidetype.pretrained import readers as R

        items = R.read_willett_session(path, blocks=blocks, limit=limit)
        streams = [self._stream(self.log_probs(it.x, it.session), it.key) for it in items]
        return list(zip(items, streams)) if with_items else streams

    def text(self, stream: Any, readout: str = "greedy") -> str:
        """The text of a stream. ``readout="greedy"`` (default): greedy CTC characters, no LM.

        ``readout="lm"`` (opt-in, P14-48): the gated LM readout of :meth:`lm_readout` (the empty text
        when the no-signal gate stops the stream).
        """
        if readout == "greedy":
            return super().text(stream)
        if readout == "lm":
            r = getattr(self, "_lm_readout", None)
            if r is None:
                r = self._lm_readout = self.lm_readout()
            return r.text(np.asarray(stream.log_probs))
        raise ValueError(f"{self.name}: readout must be 'greedy' or 'lm', got {readout!r}")

    def lm_readout(self, gate: Any = None) -> Any:
        """The opt-in LM readout (P14-48): no-signal gate + CTC beam with the character LM of the manifest.

        Returns a :class:`fidetype.pretrained.lmreadout.LmReadout` (``text``, ``nbest``, ``decode_fn``).
        The LM file (manifest role ``text``) is local: model folder or ``<cache>/text/``.
        """
        from fidetype.pretrained.lmreadout import readout_for

        return readout_for(self, gate)

    def guard(self, decode_fn: Callable[..., Any] | None = None, readout: str = "greedy", **kwargs: Any) -> Any:
        """The committed trust config. ``readout="lm"``: the guard calibrated on the LM readout (P14-48)."""
        if readout == "greedy":
            return super().guard(decode_fn=decode_fn, **kwargs)
        if readout != "lm":
            raise ValueError(f"{self.name}: readout must be 'greedy' or 'lm', got {readout!r}")
        import fidetype.trust as ft

        t = ((self.manifest.raw.get("readouts") or {}).get("lm") or {}).get("trust")
        if not t:
            raise NoTrustConfig(f"{self.name}: no trust config for the LM readout")
        return ft.load(self.files[str(t["config"]).removeprefix("file:")],
                       decode_fn=decode_fn or self.lm_readout().decode_fn(), **kwargs)


class KeyLdaDecoder(PretrainedDecoder):
    """Runtime ``key-lda``: the ``fidetype live`` KT-sEMG key-window model (one frame per key press)."""

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, **k)
        from fidetype.live.model import load_model

        self.model = load_model(self._path("card"))
        if self.model.weights_sha256 != self.weights_sha256:
            raise WeightsMismatch(f"{self.name}: the card points to other weights than the manifest")

    def _stream(self, lp: np.ndarray, times: Sequence[float], run: int | None, seg: int | None, key: str) -> Any:
        from fidetype.adapters import kt_semg as K

        sid = K.opaque_stream_id("fidetype.pretrained", self.name, self.weights_sha256, key)
        meta = K.stream_meta(run_index=run, segment_index=seg, decoder_name=f"fidetype-{self.name}",
                             decoder_version=self.manifest.version, weights_sha256=self.weights_sha256,
                             stream_id=sid, extra={**self._decoder_extra(), "adapter.name": ADAPTER_NAME,
                                                   "adapter.version": _FIDETYPE_VERSION})
        return K.keypress_stream(lp, list(times), meta=meta, latency=self.model.post_s, source=f"fidetype-{self.name}")

    def decode_array(self, x: Any, times: Sequence[float] | None = None, **_: Any) -> Any:
        """``x`` (n, 32) EMG at 2 kHz and ``times`` (key-press onsets, s from the first sample) -> one key stream."""
        if times is None or len(times) == 0:
            raise ValueError(f"{self.name} decodes one window per key press: pass times= (key onsets in seconds)")
        f = self.model.features(np.asarray(x), list(times))
        lp = self.model.log_proba(self.model.new_scaler().update_transform(f))
        return self._stream(lp, times, None, None, "array")

    def decode_file(self, path: str | PathLike[str], *, limit: int | None = None, with_items: bool = False,
                    **_: Any) -> Any:
        """One KT-sEMG run (``runN.csv`` + key log) -> one stream per typing burst (live recipe, causal z-score)."""
        from fidetype.pretrained import readers as R

        emg, items = R.read_kt_run(path)
        scaler = self.model.new_scaler()  # one running z-score over the run, as `fidetype live`
        out = []
        for it in items:
            t = it.extra["times"]
            lp = self.model.log_proba(scaler.update_transform(self.model.features(emg, t)))
            out.append((it, self._stream(lp, t, it.extra["run"], it.extra["segment"], it.key)))
            if limit is not None and len(out) >= limit:
                break
        return out if with_items else [s for _, s in out]

    def text(self, stream: Any) -> str:
        """Greedy key readout: the screen text of the per-frame argmax keys."""
        from fidetype.adapters.kt_semg import greedy_codes
        from fidetype.demo.live.keys import render_keys

        return render_keys(greedy_codes(stream))[0]

    def nbest(self, stream: Any) -> list[dict[str, Any]]:
        """The key n-best list of a stream (screen text): the input of this model's guard (n-best kind)."""
        from fidetype.live.runner import nbest_of_frames

        return nbest_of_frames(stream.log_probs, np.asarray(stream.frame_times))

    def guard_input(self, stream: Any) -> Any:
        """The guard of this model reads the screen-text n-best list: :meth:`nbest`."""
        return self.nbest(stream)

    def track_nbest(self, stream: Any, n_best: int = 8) -> list[dict[str, Any]]:
        """The n-best list in the text space of the ``kt-semg`` benchmark track (P14-46).

        Each text is the space-separated W3C ``KeyboardEvent.code`` names, one per key press
        (``Backspace`` included), as in the track truth. Feed it to ``scorecard.unit_row``. The
        :meth:`nbest` list is screen text (the guard input), not track text.
        """
        from fidetype.adapters.kt_semg import code_nbest

        return code_nbest(stream, n_best=n_best)

    def guard(self, decode_fn: Callable[..., Any] | None = None, **kwargs: Any) -> Any:
        """The guard of the model release (n-best input: ``guard.decide(model.nbest(stream))``)."""
        return super().guard(decode_fn=decode_fn, **kwargs)


RUNTIMES: dict[str, type[PretrainedDecoder]] = {
    "gru-ctc": GruCtcDecoder,
    "crt-ctc": CrtCtcDecoder,
    "key-lda": KeyLdaDecoder,
    "xbody-ctc": XBodyCtcDecoder,
}


def load(name: str, *, weights: str | PathLike[str] | None = None, cache_dir: str | PathLike[str] | None = None,
         download: bool = False, accept_research_only: bool = False, verify: bool = True) -> PretrainedDecoder:
    """Load a pretrained decoder by name (see :func:`list_models`).

    - ``weights``: a folder with the release files, or the path of the weights file.
    - ``cache_dir``: the cache folder (default :func:`default_cache_dir`).
    - ``download``: fetch missing files from their URL (none is hosted yet: P14-02).
    - ``accept_research_only``: required for a research-only model (licence gate, FEP-0010).
    - ``verify``: check the SHA-256 of each file (the size is always checked).
    """
    m = load_manifest(name)
    _gate(m, accept_research_only)
    if m.status != "available":
        raise ModelNotAvailable(f"{m.name} is registered but not available yet: {m.raw.get('status_note') or m.status}")
    rt = RUNTIMES.get(m.runtime)
    if rt is None:
        raise ManifestError(f"{m.name}: unknown runtime {m.runtime!r}; known: {sorted(RUNTIMES)}")
    cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    files = resolve_files(m, weights=weights, cache_dir=cache, download_missing=download, verify=verify,
                          accept_research_only=accept_research_only)
    return rt(m, files, cache_dir=cache, weights=weights)


def toy_model(*args: Any, **kwargs: Any) -> PretrainedDecoder:
    """A tiny random decoder to try the API without weights (see :func:`fidetype.pretrained.toy.toy_model`)."""
    from fidetype.pretrained.toy import toy_model as _toy

    return _toy(*args, **kwargs)


def make_toy_manifest(*args: Any, **kwargs: Any) -> Path:
    """Write the weights and the manifest of a toy model (see :func:`fidetype.pretrained.toy.make_toy_manifest`)."""
    from fidetype.pretrained.toy import make_toy_manifest as _make

    return _make(*args, **kwargs)


def _manifest_json(m: Manifest) -> str:
    return json.dumps(m.raw, indent=1, ensure_ascii=False)
