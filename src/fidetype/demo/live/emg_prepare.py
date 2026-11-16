"""Prepare the emg2qwerty track of the live demo (P14-06). Research use only (CC BY-NC-SA 4.0).

Inputs (read only):

- the P4-01 baseline streams: one NTS key-press stream per text prompt
  (``s<k>-p<j>.jsonl``, the held-out half of each session, LDA decoder);
- the raw emg2qwerty HDF5 files: only the ``keystrokes`` and ``prompts``
  attributes and the first and last sample time. The EMG is not read.

Outputs (all in the local output folder, never in the repository):

- ``truth.json``: for each stream file, the key sequence the typist
  pressed (the keylogger) and its screen text. This is ground truth for
  the wrong-commit count only. It never goes into a stream or a decision.
- ``trust-config-emg2qwerty-lda.json``: a frozen trust configuration
  fitted with :func:`fidetype.api.calibrate` on the **first half of the
  prompts of each session** (decoder :func:`~fidetype.demo.live.keys.key_nbest`).
- ``split.json``: which stream files are calibration and which are replay.
- ``eval.json``: aggregate numbers on the replay half (no ids, no text).

Our own code (Apache-2.0).
"""

from __future__ import annotations

import json

import re
import time
from pathlib import Path
from typing import Any

import numpy as np

STREAM_RE = re.compile(r"^s(\d{3})-p(\d{3})\.jsonl$")
TRUTH_FILE = "truth.json"
CONFIG_FILE = "trust-config-emg2qwerty-lda.json"
SPLIT_FILE = "split.json"
EVAL_FILE = "eval.json"


def _session_names(raw_root: Path, n_users: int, sessions_per_user: int) -> list[str]:
    from fidetype.adapters import emg2qwerty as E

    subset = E.select_subset(E.read_metadata(raw_root / "metadata.csv"), n_users, sessions_per_user)
    return [name for group in subset for name in group]


def _session_truth(path: Path) -> list[tuple[float, str | None]]:
    """(t, key code) of the key presses that the P4-01 baseline used, from the HDF5 attributes.

    Same rules as :func:`fidetype.adapters.emg2qwerty.key_events` with
    ``margin_s = WINDOW_PRE_S``, but the sample times are not read (only
    the first and last one).
    """
    from fidetype.adapters import emg2qwerty as E

    with E.Session(path) as s:
        ds = s._ds
        n = int(ds.shape[0])
        if n == 0:
            return []
        t0 = float(np.asarray(ds.fields("time")[0:1])[0])
        t1 = float(np.asarray(ds.fields("time")[n - 1:n])[0])
        dur = t1 - t0
        out: list[tuple[float, str | None]] = []
        m = E.WINDOW_PRE_S
        for k in s.keystrokes:
            r = float(np.float64(k.start) - np.float64(t0))
            if r < m or r > dur - m:
                continue
            if out and r <= out[-1][0]:
                continue
            out.append((r, E.key_code(k.key)))
        return out


def build_truth(streams_dir: Path, raw_root: Path, n_users: int = 8, sessions_per_user: int = 2,
                log: Any = print) -> dict[str, Any]:
    """Match each stream frame to its key press (by time). Return ``{file: {"keys": [...], "text": str}}``."""
    from fidetype.api import read_stream
    from fidetype.demo.live.keys import normalize, render_keys

    names = _session_names(raw_root, n_users, sessions_per_user)
    files = sorted(p for p in streams_dir.glob("s*-p*.jsonl") if STREAM_RE.match(p.name))
    by_session: dict[int, list[Path]] = {}
    for p in files:
        by_session.setdefault(int(STREAM_RE.match(p.name).group(1)), []).append(p)
    truth: dict[str, Any] = {}
    unmatched = 0
    for k, paths in sorted(by_session.items()):
        if k >= len(names):
            raise ValueError(f"stream session {k} is outside the documented subset ({len(names)} sessions)")
        ev = _session_truth(raw_root / f"{names[k]}.hdf5")
        times = np.array([t for t, _ in ev])
        for p in paths:
            st = read_stream(p)
            codes: list[str | None] = []
            for t in st.frame_times:
                i = int(np.searchsorted(times, t - 1e-6))
                if i < len(times) and abs(times[i] - t) < 1e-5:
                    codes.append(ev[i][1])
                else:
                    codes.append(None)
                    unmatched += 1
            truth[p.name] = {"keys": codes, "text": normalize(render_keys(codes)[0])}
        log(f"session {k}: {len(paths)} streams")
    if unmatched:
        raise ValueError(f"{unmatched} stream frames have no key press at the same time; the data do not match")
    return truth


def split_files(files: list[str]) -> tuple[list[str], list[str]]:
    """Calibration = the first half of the prompts of each session; replay = the second half."""
    by_s: dict[str, list[str]] = {}
    for f in sorted(files):
        by_s.setdefault(f.split("-")[0], []).append(f)
    cal, rep = [], []
    for s in sorted(by_s):
        fs = by_s[s]
        h = len(fs) // 2
        cal += fs[:h]
        rep += fs[h:]
    return cal, rep


def _cp(k: int, n: int) -> list[float | None]:
    """Clopper-Pearson 95 % interval (no scipy needed)."""
    from fidetype.demo.live.tracks import clopper_pearson

    return clopper_pearson(k, n)


def key_frame_temperature(streams: Any, key_truths: Any) -> Any:
    """Frame temperature for key-press streams: every frame is one key press, the target is the pressed key.

    The CTC peak rule of :func:`fidetype.trust.calibration.fit_frame_temperature`
    needs a blank class; key streams have none (``blank_id`` null), so
    the targets come straight from the keylogger codes.
    """
    from fidetype.trust.calibration import TemperatureScaler

    rows, ys = [], []
    for s, codes in zip(streams, key_truths):
        idx = {v: i for i, v in enumerate(s.vocab)}
        for t, c in enumerate(codes):
            if c in idx:
                rows.append(np.asarray(s.log_probs[t], dtype=np.float64))
                ys.append(idx[c])
    if not rows:
        return TemperatureScaler()
    return TemperatureScaler().fit(np.stack(rows), np.asarray(ys, dtype=np.int64))


def calibrate_keys(streams: Any, texts: Any, key_truths: Any, name: str, max_wrong_commit: float = 0.05,
                   policy_fraction: float = 0.5) -> Any:
    """:func:`fidetype.api.calibrate` (same Paper 1 recipe and split) for key-press streams.

    The only change: the frame temperature step uses
    :func:`key_frame_temperature` (the keylogger codes travel in
    ``Item.stream_text``).
    """
    from fidetype.demo.live.keys import key_nbest
    from fidetype.eval import harness as H
    from fidetype.trust.frozen import PAPER1_V4_RECIPE, FrozenTrustConfig, paper1_v4_harness_config

    items = [H.Item(s, t, stream_text=k) for s, t, k in zip(streams, texts, key_truths)]
    n_cal = len(items) - int(round(len(items) * policy_fraction))
    pipe = H.TrustPipeline(key_nbest, paper1_v4_harness_config(max_wrong_commit=max_wrong_commit), {})
    orig = H.fit_frame_temperature
    H.fit_frame_temperature = key_frame_temperature  # scoped swap; restored below
    try:
        pipe.fit(items[:n_cal], items[n_cal:])
    finally:
        H.fit_frame_temperature = orig
    recipe = dict(PAPER1_V4_RECIPE)
    recipe["risk_control"] = dict(recipe["risk_control"], alpha=max_wrong_commit)
    return FrozenTrustConfig.from_pipeline(pipe, name, recipe)


def prepare(streams_dir: str | Path, raw_root: str | Path, out_dir: str | Path, log: Any = print,
            reuse_truth: bool = False) -> dict[str, Any]:
    """Write ``truth.json``, ``split.json``, the trust configuration and ``eval.json`` to ``out_dir``."""
    from fidetype.api import read_stream
    from fidetype.demo.live.keys import key_nbest, normalize
    from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer

    sd, rr, od = Path(streams_dir), Path(raw_root), Path(out_dir)
    for p, what in ((sd, "baseline streams"), (rr / "metadata.csv", "raw emg2qwerty metadata")):
        if not p.exists():
            raise FileNotFoundError(f"{what} not found: {p}")
    od.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    if reuse_truth and (od / TRUTH_FILE).is_file():
        truth = json.loads((od / TRUTH_FILE).read_text(encoding="utf-8"))
    else:
        truth = build_truth(sd, rr, log=log)
        (od / TRUTH_FILE).write_text(json.dumps(truth) + "\n", encoding="utf-8")
    cal, rep = split_files(list(truth))
    (od / SPLIT_FILE).write_text(json.dumps({"rule": "first half of the prompts of each session = calibration; "
                                             "second half = replay", "calibration": cal, "replay": rep}, indent=1)
                                 + "\n", encoding="utf-8")
    log(f"calibration {len(cal)} streams, replay {len(rep)} streams")
    # Mix the sessions (fixed seed) so that both calibrate() halves see every session.
    order = [cal[i] for i in np.random.default_rng(0).permutation(len(cal))]
    cfg = calibrate_keys([read_stream(sd / f) for f in order], [truth[f]["text"] for f in order],
                         [truth[f]["keys"] for f in order],
                         name="emg2qwerty LDA baseline (P14-06 demo; research use only)")
    cfg.recipe["data"] = ("emg2qwerty (CC BY-NC-SA 4.0, research only): P4-01 LDA baseline streams, 8 users x 2 "
                          "sessions, held-out half of each session; calibration = first half of the prompts")
    cfg.recipe["decoder"] = "fidetype.demo.live.keys.key_nbest (beam 16, top-3 keys per frame, no LM)"
    cfg.recipe["fitted_by"] = "fidetype.demo.live.emg_prepare"
    cfg.save(od / CONFIG_FILE)
    layer = StreamingTrustLayer(cfg, decode_fn=key_nbest, streaming=StreamingConfig(max_attempts=1))
    counts = {"COMMIT": 0, "OFFER": 0, "WITHHOLD": 0}
    wrong = always_wrong = hit = 0
    for i, f in enumerate(rep):
        from fidetype.trust.streaming import iter_events

        sid = f"e{i}"
        d = None
        for ev in iter_events(sd / f):
            r = layer.push(ev, sid)
            if r:
                d = r[-1]
        layer.close(sid)
        a = d.action.value
        t = truth[f]["text"]
        top = normalize(d.inputs.texts[0]) if d.inputs.texts else ""
        always_wrong += top != t
        if a == "COMMIT":
            counts["COMMIT"] += 1
            wrong += normalize(d.shown[0]) != t
        elif a in ("OFFER", "OFFER_WORDS"):
            counts["OFFER"] += 1
            hit += t in [normalize(x) for x in d.shown]
        else:
            counts["WITHHOLD"] += 1
    n = len(rep)
    ev_out = {
        "dataset": "emg2qwerty", "licence": "CC-BY-NC-SA-4.0", "research_only": True,
        "config_id": cfg.config_id, "n_calibration": len(cal), "n_replay": n, "actions": counts,
        "wrong_commits": wrong, "wrong_commit_rate": round(wrong / n, 4) if n else None,
        "wrong_commit_cp95": _cp(wrong, n), "offer_contains_truth": hit,
        "always_commit_wrong": always_wrong,
        "always_commit_wrong_rate": round(always_wrong / n, 4) if n else None,
        "alpha": cfg.risk_control.get("alpha"), "seconds": round(time.time() - t_start, 1),
    }
    (od / EVAL_FILE).write_text(json.dumps(ev_out, indent=1) + "\n", encoding="utf-8")
    log(json.dumps(ev_out))
    return ev_out


if __name__ == "__main__":  # pragma: no cover
    import argparse

    ap = argparse.ArgumentParser(description="Prepare the emg2qwerty track of the live demo (research use only).")
    ap.add_argument("--streams", required=True, type=Path)
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--reuse-truth", action="store_true")
    a = ap.parse_args()
    prepare(a.streams, a.raw, a.out, reuse_truth=a.reuse_truth)

