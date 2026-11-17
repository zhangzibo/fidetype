"""Build the model and trust guard files of ``fidetype live`` (P14-04).

Two builders. Both go through the same live loop as ``fidetype live``
(:class:`~fidetype.live.runner.LiveDecoder` in collect mode), so the
calibration n-best lists are made exactly as the live ones.

``make_synthetic(out)``
    Train ``synthetic-keys`` on the synthetic typist (no real data) and
    calibrate its guard. Deterministic. The packaged
    ``builtin:synthetic-keys`` files come from this function
    (``fidetype live make-synthetic --out src/fidetype/live/assets``).
``train_kt(data, out)``
    Train ``kt-semg-lda`` on KT-sEMG (CC BY 4.0, Nokia) and calibrate its
    guard. The run split is the benchmark split of track ``kt-semg``
    (:mod:`fidetype.benchmark.tracks`): the model trains on the first
    train runs, the guard calibrates on the last ``guard_train_runs``
    train runs plus the ``cal`` runs, and the ``test`` runs stay for the
    replay. The files go to a local folder; they are not committed.
    ``fit_ids`` / ``guard_ids`` pick runs by id instead (any split), and
    ``guard_chunk_keys`` cuts the guard segments into chunks of that many
    keys (more calibration items from a short recording). The CI job
    ``live-kt`` (P14-11) uses ``fit_ids = guard_ids = ["run3"]``: an
    in-sample plumbing model, marked so in its card.

Null input for the guard (required for n-best input). Synthetic: the same
key timing with no key bursts in the signal (no signal). KT-sEMG: the
key windows of each segment replaced by windows of other segments
(shuffled), so the text cannot match.

Our own code (Apache-2.0).
"""

from __future__ import annotations

import gc
import json
from os import PathLike
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from fidetype.demo.live.keys import normalize, render_keys
from fidetype.live.model import KeyWindowModel, fit_model
from fidetype.live.runner import LiveDecoder
from fidetype.live.sources import ArraySource, SyntheticSource
from fidetype.live.synthetic import KEYPRESS, SEGMENT_END, SyntheticTypist

__all__ = ["collect_nbests", "make_synthetic", "train_kt"]

SYNTHETIC_NAME = "synthetic-keys"
KT_NAME = "kt-semg-lda"


def collect_nbests(model: KeyWindowModel, source: Any, timing: str | None = None) -> list[list[dict[str, Any]]]:
    """Run the live loop with no guard; return the n-best list of each segment."""
    dec = LiveDecoder(model, None, source, timing=timing)
    dec.run()
    return [nb for nb, _, _ in dec.collected]


def _calibrate(nbests: Sequence[Any], texts: Sequence[str], nulls: Sequence[Any], alpha: float, delta: float,
               name: str, modality: str, model: KeyWindowModel) -> Any:
    import fidetype.trust as ft

    return ft.calibrate(list(nbests), list(texts), input_kind="nbest", null_inputs=list(nulls), alpha=alpha,
                        delta=delta, decoder_name=model.name, decoder_version=model.version, modality=modality,
                        name=name, seed=0)


def make_synthetic(out: str | PathLike[str], n_train: int = 400, n_cal: int = 600, alpha: float = 0.05,
                   delta: float = 0.1, log: Callable[[str], None] = print) -> dict[str, Any]:
    """Train and calibrate ``synthetic-keys`` (module docstring). Return a summary dict."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    fs, C = 250.0, 16
    card = {"name": SYNTHETIC_NAME, "version": "1", "sample_rate": fs, "channels": C, "modality": "other",
            "window": {"pre_s": 0.15, "post_s": 0.05, "n_sub": 2}, "timing": "markers", "hop_s": 0.25,
            "training": {"data": "fidetype synthetic typist (fidetype.live.synthetic), seed 1, no real data",
                         "licence": "Apache-2.0 (our own synthetic signal)"},
            "warning": "Decodes only the fidetype synthetic typist signal. It is a plumbing and trust test."}
    typ = SyntheticTypist(sample_rate=fs, channels=C, seed=1)  # default noise: about 0.97 key accuracy
    utts = list(typ.utterances(n_train))
    sig = typ.render(utts)
    times = [t for u in utts for t in u.key_times]
    labels = np.asarray([c for u in utts for c in u.key_classes])
    tmp = KeyWindowModel(None, card)  # type: ignore[arg-type]
    feats = tmp.features(sig, times)
    model = fit_model([feats], [labels], card)
    acc_train = float(np.mean(np.argmax(model.log_proba(model.new_scaler().update_transform(feats)), 1) == labels))
    log(f"synthetic model: {len(labels)} training keys, train key accuracy {acc_train:.3f}")
    model.save(out / SYNTHETIC_NAME)
    cal = SyntheticSource(n_cal, seed=2, speed=0)
    nbs = collect_nbests(model, cal)
    texts = [u.text for u in cal.utterances]
    null = SyntheticSource(300, seed=3, speed=0, null=True)
    nulls = collect_nbests(model, null)
    exact = float(np.mean([normalize(nb[0]["text"]) == normalize(t) for nb, t in zip(nbs, texts)]))
    log(f"calibration: {len(nbs)} utterances (top-1 exact {exact:.3f}), {len(nulls)} null inputs")
    guard = _calibrate(nbs, texts, nulls, alpha, delta, SYNTHETIC_NAME, "other", model)
    guard.save(out / f"{SYNTHETIC_NAME}.guard.json")
    summary = {"model": SYNTHETIC_NAME, "train_keys": int(len(labels)), "train_key_accuracy": round(acc_train, 4),
               "cal_utterances": len(nbs), "cal_top1_exact": round(exact, 4), "null_inputs": len(nulls),
               "config_id": guard.config_id, "alpha": alpha, "delta": delta}
    log(str(guard.sheet))
    return summary


# --- KT-sEMG ---------------------------------------------------------------------------------




def kt_run_events(csv: str, keys_path: str, ts_path: str, n_samples: int) -> list[Any]:
    """Key events (t from the first sample, char) of one run, with the inferred UTC offset."""
    from fidetype.adapters import kt_semg as K

    keys = K.read_keys(keys_path)
    start_local = K.read_start_time(ts_path)
    dur = n_samples / K.SAMPLE_RATE_HZ
    off = K.infer_utc_offset_hours(start_local, [k.unix_s for k in keys], dur)
    start = K.start_unix(start_local, off)
    return K.key_events(keys, start, dur, margin_s=K.WINDOW_PRE_S)


def kt_segments(events: Sequence[Any], max_gap_s: float = 2.0, min_keys: int = 5) -> list[tuple[int, int]]:
    """Typing bursts (same rule as the ``kt-semg`` benchmark track: pause > 2 s, >= 5 keys)."""
    from fidetype.adapters import kt_semg as K

    return [(a, b) for a, b in K.segment_events([e.t for e in events], max_gap_s=max_gap_s) if b - a >= min_keys]


def kt_markers(events: Sequence[Any], segments: Sequence[tuple[int, int]],
               end_pad_s: float = 0.5) -> list[tuple[float, str]]:
    """Markers of the kept segments: ``keypress`` at each key time, ``segment_end`` after the last key.

    The ``segment_end`` comes ``end_pad_s`` after the last key, or half way to the next key if that is
    sooner (chunks of one burst, :func:`kt_chunks`).
    """
    mk: list[tuple[float, str]] = []
    for a, b in segments:
        mk += [(float(e.t), KEYPRESS) for e in events[a:b]]
        pad = end_pad_s
        if b < len(events):
            pad = min(pad, (float(events[b].t) - float(events[b - 1].t)) / 2)
        mk.append((float(events[b - 1].t) + pad, SEGMENT_END))
    return mk


def kt_chunks(segments: Sequence[tuple[int, int]], keys: int) -> list[tuple[int, int]]:
    """Cut each segment into chunks of ``keys`` keys (a short last chunk joins the one before it)."""
    out: list[tuple[int, int]] = []
    for a, b in segments:
        cuts = list(range(a, b, keys))
        parts = [(c, min(b, c + keys)) for c in cuts]
        if len(parts) > 1 and parts[-1][1] - parts[-1][0] < keys:
            last = parts.pop()
            parts[-1] = (parts[-1][0], last[1])
        out += parts
    return out


def kt_text(events: Sequence[Any]) -> str:
    """The screen text of a key sequence (truth; never written to a stream)."""
    from fidetype.adapters import kt_semg as K

    return normalize(render_keys([K.key_code(e.char) for e in events])[0])


def _kt_runs(data: str | PathLike[str]) -> dict[str, list[dict[str, Any]]]:
    from fidetype.benchmark import tracks as TR

    out: dict[str, list[dict[str, Any]]] = {"train": [], "cal": [], "test": []}
    for u in TR.local_units("kt-semg", data):
        if u.set == "run":
            out[u.split].append({"id": u.id, **u.ref})
    return out


def train_kt(data: str | PathLike[str], out: str | PathLike[str], model_train_runs: int = 12,
             guard_train_runs: int = 4, max_csv_mb: float = 1000.0, alpha: float = 0.05, delta: float = 0.1,
             log: Callable[[str], None] = print, fit_ids: Sequence[str] | None = None,
             guard_ids: Sequence[str] | None = None, guard_chunk_keys: int | None = None) -> dict[str, Any]:
    """Train ``kt-semg-lda`` and calibrate its guard on KT-sEMG (module docstring). Return a summary dict.

    ``max_csv_mb``: skip runs whose CSV is larger (RAM limit: one run is read at a time).
    """
    from fidetype.adapters import kt_semg as K

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    runs = _kt_runs(data)
    small = [r for r in runs["train"] if Path(r["csv"]).stat().st_size <= max_csv_mb * 1e6]
    fit_runs = small[:model_train_runs]
    guard_runs = small[model_train_runs:model_train_runs + guard_train_runs] + runs["cal"]
    guard_runs = [r for r in guard_runs if Path(r["csv"]).stat().st_size <= max_csv_mb * 1e6]
    if fit_ids or guard_ids:
        by_id = {r["id"]: r for rs in runs.values() for r in rs}
        missing = [i for i in list(fit_ids or []) + list(guard_ids or []) if i not in by_id]
        if missing:
            raise ValueError(f"unknown runs {missing} (have {sorted(by_id)})")
        if fit_ids:
            fit_runs = [by_id[i] for i in fit_ids]
        if guard_ids:
            guard_runs = [by_id[i] for i in guard_ids]
    in_sample = sorted({r["id"] for r in fit_runs} & {r["id"] for r in guard_runs})
    card = {"name": KT_NAME, "version": "1", "sample_rate": K.SAMPLE_RATE_HZ, "channels": K.N_CHANNELS,
            "modality": "emg", "window": {"pre_s": K.WINDOW_PRE_S, "post_s": K.WINDOW_POST_S, "n_sub": 2},
            "timing": "markers",
            "training": {"data": f"KT-sEMG v{K.DATAVERSE_VERSION} doi:{K.DATAVERSE_DOI}", "licence": K.LICENCE,
                         "attribution": K.ATTRIBUTION, "split": "benchmark track kt-semg (tracks v0.2)",
                         "model_runs": [r["id"] for r in fit_runs], "guard_runs": [r["id"] for r in guard_runs]},
            "warning": "One typist. Session-to-session transfer only; no transfer to other people or devices."}
    if in_sample:
        card["warning"] = (f"IN-SAMPLE plumbing model: runs {in_sample} train the model and calibrate the guard. "
                           "Its decisions and its guard sheet say nothing about accuracy or risk. " + card["warning"])
    if guard_chunk_keys:
        card["training"]["guard_chunk_keys"] = int(guard_chunk_keys)
    tmp = KeyWindowModel(None, card)  # type: ignore[arg-type]
    feats, labels = [], []
    for r in fit_runs:
        rec = K.read_emg_csv(r["csv"])
        ev = kt_run_events(r["csv"], r["keys"], r["ts"], rec.n_samples)
        keep = [(e.t, K.key_class(e.char)) for e in ev]
        keep = [(t, c) for t, c in keep if c is not None]
        f = tmp.features(rec.emg, [t for t, _ in keep])
        feats.append(f)
        labels.append(np.asarray([c for _, c in keep]))
        log(f"train {r['id']}: {len(keep)} keys")
        del rec
        gc.collect()
    model = fit_model(feats, labels, card)
    model.save(out / KT_NAME)
    nbs, texts, pools = [], [], []
    for r in guard_runs:
        rec = K.read_emg_csv(r["csv"])
        ev = kt_run_events(r["csv"], r["keys"], r["ts"], rec.n_samples)
        segs = kt_segments(ev)
        if guard_chunk_keys:
            segs = kt_chunks(segs, int(guard_chunk_keys))
        src = ArraySource(rec.emg, K.SAMPLE_RATE_HZ, kt_markers(ev, segs), speed=0, chunk_s=0.5)
        got = collect_nbests(model, src)
        nbs += got
        texts += [kt_text(ev[a:b]) for a, b in segs]
        # per-key frames for the shuffled null: windows of this run, decoded in order
        times = [ev[i].t for a, b in segs for i in range(a, b)]
        sc = model.new_scaler()
        pools.append(model.log_proba(sc.update_transform(model.features(rec.emg, times))))
        log(f"guard {r['id']}: {len(segs)} segments")
        del rec, src
        gc.collect()
    if len(nbs) != len(texts):
        raise RuntimeError(f"segment count mismatch: {len(nbs)} n-best lists, {len(texts)} texts")
    pool = np.concatenate(pools)
    rng = np.random.default_rng(0)
    from fidetype.live.runner import nbest_of_frames

    nulls = []
    for nb, t in zip(nbs, texts):
        k = max(1, len(t))
        idx = rng.integers(0, len(pool), size=k)
        nulls.append(nbest_of_frames(pool[idx], np.arange(k) * 0.25))
    exact = float(np.mean([normalize(nb[0]["text"]) == t for nb, t in zip(nbs, texts)]))
    log(f"calibration: {len(nbs)} segments (top-1 exact {exact:.3f}), {len(nulls)} shuffled null inputs")
    guard = _calibrate(nbs, texts, nulls, alpha, delta, KT_NAME, "emg", model)
    guard.save(out / f"{KT_NAME}.guard.json")
    log(str(guard.sheet))
    summary = {"model": KT_NAME, "model_runs": card["training"]["model_runs"],
               "guard_runs": card["training"]["guard_runs"], "train_keys": int(sum(len(x) for x in labels)),
               "cal_segments": len(nbs), "cal_top1_exact": round(exact, 4), "config_id": guard.config_id,
               "alpha": alpha, "delta": delta, "weights_sha256": model.weights_sha256}
    (out / f"{KT_NAME}.summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary
