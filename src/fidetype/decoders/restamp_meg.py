"""Re-write the header of cached MEG streams to the current adapter meta (CPU, no inference).

Streams written by :mod:`fidetype.decoders.infer` before 2026-11-11 carry
flat meta keys (``subject``, ``split``, ...) and no provenance keys
(``stream.id``, ``decoder.name``, ``decoder.weights_sha256``, ...). They
reach conformance level core only. This script keeps the ``log_probs``
unchanged and builds the header again with
:func:`fidetype.adapters.spanishbcbl_meg.segment_stream`, exactly as
``infer.py`` does now. So the output equals a fresh ``infer.py`` run
except for float noise of the GPU forward pass.

Usage (repo root)::

    python -m fidetype.decoders.restamp_meg --run-dir C:/Users/zhang/bci-data/runs/<run_name>

Input: ``<streams_root>/<run_name>/<split>/*.npz``. Output:
``<streams_root>/<run_name><suffix>/<split>/*.npz`` (default suffix
``_provenance``) plus a copy of ``labels.jsonl`` and a ``restamp.json``
report. The input folder is not changed, because older experiments read
its flat keys.

The checkpoint is only hashed (SHA-256), not loaded. The script refuses a
checkpoint that is newer than the cached streams (its hash would not
describe the weights that made them), unless ``--allow-newer-checkpoint``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from fidetype.adapters.spanishbcbl_meg import opaque_stream_id, segment_stream
from fidetype.streams.spec import NeuralTextStream
from fidetype.trust.provenance import file_sha256

DEFAULT_STREAMS_ROOT = "C:/Users/zhang/bci-data/streams"


def restamp_stream(old: NeuralTextStream, *, run_name: str, checkpoint: str, split: str, name: str,
                   weights_sha256: str, conformer_layers: int, lookahead_frames: int | None,
                   frame_period_s: float) -> NeuralTextStream:
    """Build the current-format stream from an old cached stream. ``log_probs`` stay the same."""
    m = old.meta or {}
    for k in ("subject", "session"):
        if k not in m and f"spanishbcbl.{k}" not in m:
            raise ValueError(f"{name}: old meta has no {k!r}")
    get = lambda k: m.get(k, m.get(f"spanishbcbl.{k}"))  # noqa: E731
    return segment_stream(
        np.asarray(old.log_probs), frame_period_s,
        subject=str(get("subject")), session=str(get("session")),
        participant=get("participant"), block=get("block"), trial_idx=get("trial_idx"),
        split=split, run_name=run_name, checkpoint=checkpoint, segment_start_s=get("segment_start_s"),
        conformer_layers=conformer_layers, lookahead_frames=lookahead_frames,
        weights_sha256=weights_sha256, stream_id=opaque_stream_id(run_name, checkpoint, split, name),
        model=str(m.get("model", m.get("spanishbcbl.model", "conv_ctc"))),
    )


def restamp_run(run_dir: str | Path, *, checkpoint: str = "best.pt", splits: tuple[str, ...] = ("val", "test"),
                streams_root: str | Path = DEFAULT_STREAMS_ROOT, suffix: str = "_provenance",
                allow_newer_checkpoint: bool = False) -> dict[str, Any]:
    run_dir = Path(run_dir)
    run_name = run_dir.name
    ck_path = run_dir / checkpoint
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    model_cfg = cfg.get("model", {})
    conformer_layers = int(model_cfg.get("conformer_layers", 4))
    lookahead_frames = model_cfg.get("lookahead_frames")
    in_dir = Path(streams_root) / run_name
    out_dir = Path(streams_root) / f"{run_name}{suffix}"
    weights_sha256 = file_sha256(ck_path)
    report: dict[str, Any] = {"run_name": run_name, "checkpoint": checkpoint, "weights_sha256": weights_sha256,
                              "input": str(in_dir), "output": str(out_dir), "splits": {}}
    for split in splits:
        sdir = in_dir / split
        files = sorted(sdir.glob("*.npz"))
        if not files:
            raise FileNotFoundError(f"no streams in {sdir}")
        newest = max(f.stat().st_mtime for f in files)
        oldest = min(f.stat().st_mtime for f in files)
        if ck_path.stat().st_mtime > oldest and not allow_newer_checkpoint:
            raise RuntimeError(f"{ck_path} is newer than the cached streams in {sdir}; rerun infer.py instead")
        odir = out_dir / split
        odir.mkdir(parents=True, exist_ok=True)
        n = 0
        for f in files:
            old = NeuralTextStream.from_npz(f)
            period = float(old.frame_period or (old.meta or {}).get("frame_period_s")
                           or (old.meta or {}).get("spanishbcbl.frame_period_s") or 0.04)
            new = restamp_stream(old, run_name=run_name, checkpoint=checkpoint, split=split, name=f.stem,
                                 weights_sha256=weights_sha256, conformer_layers=conformer_layers,
                                 lookahead_frames=lookahead_frames, frame_period_s=period)
            assert np.array_equal(new.log_probs, old.log_probs)
            new.to_npz(odir / f.name)
            n += 1
        if (sdir / "labels.jsonl").exists():
            shutil.copy2(sdir / "labels.jsonl", odir / "labels.jsonl")
        report["splits"][split] = {"streams": n, "input_mtime_range": [oldest, newest]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "restamp.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-dir", required=True, action="append", help="run folder (repeatable)")
    p.add_argument("--checkpoint", default="best.pt")
    p.add_argument("--splits", default="val,test")
    p.add_argument("--streams-root", default=DEFAULT_STREAMS_ROOT)
    p.add_argument("--suffix", default="_provenance")
    p.add_argument("--allow-newer-checkpoint", action="store_true")
    a = p.parse_args(argv)
    for rd in a.run_dir:
        r = restamp_run(rd, checkpoint=a.checkpoint, splits=tuple(a.splits.split(",")),
                        streams_root=a.streams_root, suffix=a.suffix,
                        allow_newer_checkpoint=a.allow_newer_checkpoint)
        print(json.dumps({"run": r["run_name"], "output": r["output"],
                          "streams": {k: v["streams"] for k, v in r["splits"].items()}}))


if __name__ == "__main__":
    main()
