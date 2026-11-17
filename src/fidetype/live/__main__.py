"""``fidetype live``: one-command live decode with the trust guard (P14-04).

::

    fidetype live --source synthetic                                   # no hardware, no data, no extra
    fidetype live --source brainflow --board-id -1 --out s.nts.jsonl   # BrainFlow Synthetic board ([brainflow])
    fidetype live --source brainflow --board-id 0 --serial-port COM3   # OpenBCI Cyton (untested: P4-06)
    fidetype live --source lsl --stream-name fidetype.replay.kt-semg \\
        --model kt.model.json --guard kt.guard.json                    # any raw-signal LSL stream ([lsl])
    fidetype live make-synthetic --out DIR                             # rebuild builtin:synthetic-keys
    fidetype live train-kt --data ~/bci-data/raw/kt-semg --out DIR     # KT-sEMG demo model + guard (local)
    fidetype live replay-kt --data ~/bci-data/raw/kt-semg --run run28  # KT-sEMG recording -> LSL ([lsl])
    fidetype live replay-synthetic                                     # synthetic typist -> LSL ([lsl])

Defaults: ``--model builtin:synthetic-keys --guard builtin:synthetic-keys``.
Each decision prints one line (``--json``: one JSON object). ``--out``
writes an NTS JSON Lines file (frames, final hypotheses, trust decisions).
Read docs/live-decode.md first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

SOURCES = ("synthetic", "brainflow", "lsl")


def _err(msg: str) -> None:
    sys.stderr.write(f"[fidetype.live] {msg}\n")
    sys.stderr.flush()


def _run_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="fidetype live",
        description="Live decode: signal source -> windows -> model -> trust guard (commit / offer / withhold) "
                    "-> NTS. Subcommands: make-synthetic, train-kt, replay-kt (see --help of each).")
    ap.add_argument("--source", choices=SOURCES, default="synthetic", help="signal source (default: synthetic)")
    ap.add_argument("--model", default="builtin:synthetic-keys", help="*.model.json path or builtin:<name>")
    ap.add_argument("--guard", default=None, help="trust guard JSON (fidetype.trust save); default: the model's "
                    "builtin guard when --model is builtin")
    ap.add_argument("--out", help="write NTS JSON Lines here (frames, hypotheses, trust decisions)")
    ap.add_argument("--json", action="store_true", help="print one JSON object per decision")
    ap.add_argument("--no-text", action="store_true", help="do not print decoded text")
    ap.add_argument("--summary", help="write the run summary (counts, latency) as JSON here")
    ap.add_argument("--duration", type=float, help="stop after this many seconds")
    ap.add_argument("--max-decisions", type=int, help="stop after this many decisions")
    ap.add_argument("--timing", choices=("markers", "fixed"), help="window timing (default: the model's)")
    ap.add_argument("--hop", type=float, help="fixed timing: seconds between windows (default: the model's)")
    ap.add_argument("--segment-s", type=float, help="end a segment every S seconds (instead of segment_end markers)")
    g = ap.add_argument_group("synthetic source")
    g.add_argument("--utterances", type=int, default=10, help="number of synthetic utterances (default 10)")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--speed", type=float, default=1.0, help="1 = real time, 0 = as fast as possible")
    g.add_argument("--null", action="store_true", help="no key bursts in the signal (no-signal control)")
    b = ap.add_argument_group("brainflow source (OpenBCI boards use their BrainFlow board id)")
    b.add_argument("--board-id", type=int, default=-1, help="BrainFlow board id (-1 Synthetic, 0 Cyton, 1 Ganglion)")
    b.add_argument("--board", help="board name instead of an id (synthetic, cyton, ganglion, ...)")
    b.add_argument("--kind", choices=("eeg", "emg", "exg"), default="eeg", help="board channels to read")
    b.add_argument("--trial-s", type=float, default=2.0, help="seconds per segment (bridge trial clock; default 2)")
    b.add_argument("--serial-port", default="")
    b.add_argument("--ip-address", default="")
    b.add_argument("--ip-port", type=int, default=0)
    b.add_argument("--mac-address", default="")
    b.add_argument("--serial-number", default="")
    b.add_argument("--other-info", default="")
    lg = ap.add_argument_group("lsl source")
    lg.add_argument("--stream-name")
    lg.add_argument("--stream-type")
    lg.add_argument("--source-id")
    lg.add_argument("--markers", default="auto", help='marker stream: "auto" (from the signal desc), "none", or a name')
    lg.add_argument("--resolve-timeout", type=float, default=10.0)
    return ap


def _open_source(a: Any) -> Any:
    from fidetype.live import sources as S

    if a.source == "synthetic":
        return S.SyntheticSource(a.utterances, seed=a.seed, speed=a.speed, null=a.null)
    if a.source == "brainflow":
        from fidetype.adapters import brainflow_bridge as B

        bid = B.board_id_from_name(a.board) if a.board else a.board_id
        return S.BrainFlowSource(bid, a.kind, a.trial_s, serial_port=a.serial_port, ip_address=a.ip_address,
                                 ip_port=a.ip_port, mac_address=a.mac_address, serial_number=a.serial_number,
                                 other=a.other_info)
    return S.LSLSource(a.stream_name, a.stream_type, a.source_id, a.markers, a.resolve_timeout)


def run_main(argv: Sequence[str]) -> int:
    a = _run_parser().parse_args(list(argv))
    import fidetype.trust as ft
    from fidetype.live.model import load_model, resolve_asset
    from fidetype.live.runner import LiveDecoder, make_writer, print_decision

    model = load_model(a.model)
    gspec = a.guard or (a.model if str(a.model).startswith("builtin:") else None)
    if gspec is None:
        _err("give --guard (a trust guard JSON calibrated for this model)")
        return 2
    guard = ft.load(resolve_asset(gspec, ".guard.json"), audit_text=not a.no_text)
    if guard.input_kind != "nbest":
        _err("the guard must be calibrated on n-best input (input_kind nbest)")
        return 2
    try:
        src = _open_source(a)
    except ImportError as e:  # LSLUnavailableError / BrainFlowUnavailableError
        _err(str(e))
        return 2
    except Exception as e:  # noqa: BLE001 - resolve / board open errors: report and exit
        _err(f"cannot open the {a.source} source: {e}")
        return 3
    info = src.info
    timing = a.timing or ("fixed" if a.source == "brainflow" else model.timing)
    _err(f"source {info['name']} ({info['channels']} ch, {info['sample_rate']:g} Hz); model {model.name} "
         f"({model.channels} ch, {model.sample_rate:g} Hz, timing {timing}); guard {guard.config_id} "
         f"(alpha {guard.alpha:g}, delta {guard.delta:g})")
    if model.card.get("warning"):
        _err(f"model note: {model.card['warning']}")
    if a.source == "brainflow" and "brainflow" not in json.dumps(model.card.get("training", {})).lower():
        _err("note: the model was not trained on this board; expect no commits (the correct output on a "
             "signal with no text information)")
    writer = make_writer(a.out, model, info, guard, a.source) if a.out else None
    try:
        dec = LiveDecoder(model, guard, src, timing=timing, hop_s=a.hop, segment_s=a.segment_s, writer=writer,
                          on_decision=lambda d: print_decision(d, as_json=a.json, include_text=not a.no_text))
    except ValueError as e:
        src.close()
        if writer is not None:
            writer.close()
        _err(str(e))
        return 2
    try:
        st = dec.run(duration_s=a.duration, max_decisions=a.max_decisions)
    finally:
        if writer is not None:
            writer.close()
    s = st.as_dict()
    _err(f"stop ({st.stop_reason}): {st.decisions} decisions ({st.commits} commit, {st.offers} offer, "
         f"{st.withholds} withhold), {st.frames} windows, {st.samples} samples in {st.wall_s:.1f} s")
    fm, dm = s["frame_ms"], s["decision_ms"]
    if fm.get("n"):
        _err(f"latency per window: compute p50 {fm['p50']} ms, p95 {fm['p95']} ms; added p50 "
             f"{s['frame_added_ms']['p50']} ms, p95 {s['frame_added_ms']['p95']} ms")
    if dm.get("n"):
        _err(f"latency per decision: compute p50 {dm['p50']} ms, p95 {dm['p95']} ms; added p50 "
             f"{s['decision_added_ms']['p50']} ms, p95 {s['decision_added_ms']['p95']} ms")
    if a.out:
        _err(f"NTS written: {a.out} (check: fidetype validate {a.out})")
    if a.summary:
        s.update(source=a.source, model=model.name, config_id=guard.config_id, timing=timing)
        Path(a.summary).write_text(json.dumps(s, indent=2) + "\n", encoding="utf-8")
    return 0


def _make_synthetic(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(prog="fidetype live make-synthetic",
                                 description="Train builtin:synthetic-keys on the synthetic typist and calibrate "
                                             "its guard (deterministic; no real data).")
    ap.add_argument("--out", required=True, help="output folder")
    a = ap.parse_args(list(argv))
    from fidetype.live.build import make_synthetic

    print(json.dumps(make_synthetic(a.out, log=_err), indent=2))
    return 0


def _train_kt(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(prog="fidetype live train-kt",
                                 description="Train the KT-sEMG demo model (LDA) and calibrate its guard. Data: "
                                             "KT-sEMG, copyright 2021 Nokia, CC BY 4.0. Output stays local.")
    ap.add_argument("--data", required=True, help="KT-sEMG folder (run*.csv, run*_keys.txt, run*_ts.txt)")
    ap.add_argument("--out", required=True, help="output folder (outside the repository)")
    ap.add_argument("--model-runs", type=int, default=12, help="train runs for the model (default 12)")
    ap.add_argument("--guard-runs", type=int, default=4, help="extra train runs for the guard (plus the cal runs)")
    ap.add_argument("--max-csv-mb", type=float, default=1000.0, help="skip larger runs (RAM; default 1000)")
    a = ap.parse_args(list(argv))
    from fidetype.live.build import train_kt

    print(json.dumps(train_kt(a.data, a.out, a.model_runs, a.guard_runs, a.max_csv_mb, log=_err), indent=2))
    return 0


def _replay_kt(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(prog="fidetype live replay-kt",
                                 description="Publish one KT-sEMG run on LSL in real time: the EMG (32 ch, 2000 Hz) "
                                             "and a marker stream (keypress onsets, segment_end). Needs [lsl].")
    ap.add_argument("--data", required=True, help="KT-sEMG folder")
    ap.add_argument("--run", default="run28", help="run id (default run28, a test run of track kt-semg)")
    ap.add_argument("--start-s", type=float, default=0.0, help="start this many seconds into the run")
    ap.add_argument("--duration", type=float, default=None, help="send this many seconds (default: all)")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--name", default="fidetype.replay.kt-semg")
    ap.add_argument("--wait-consumers", type=float, default=30.0)
    ap.add_argument("--truth", help="write the truth of the sent segments (local scoring only) to this JSON file")
    a = ap.parse_args(list(argv))
    from fidetype.live.replay import replay_kt

    try:
        st = replay_kt(a.data, a.run, a.start_s, a.duration, a.speed, a.name, a.wait_consumers, a.truth, log=_err)
    except ImportError as e:
        _err(str(e))
        return 2
    _err(json.dumps(st))
    return 0


def _replay_synthetic(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(prog="fidetype live replay-synthetic",
                                 description="Publish the synthetic typist on LSL in real time (16 ch, 250 Hz, plus a "
                                             "marker stream). For an LSL test with no data. Needs [lsl].")
    ap.add_argument("--utterances", type=int, default=10)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--name", default="fidetype.replay.synthetic")
    ap.add_argument("--wait-consumers", type=float, default=30.0)
    a = ap.parse_args(list(argv))
    from fidetype.live.replay import publish_signal
    from fidetype.live.sources import SyntheticSource

    src = SyntheticSource(a.utterances, seed=a.seed)
    mk = [tuple(m) for m in src.markers]
    try:
        st = publish_signal(src.x, src.fs, mk, a.name, modality="other", speed=a.speed,
                            wait_consumers=a.wait_consumers, extra={"fidetype.replay": "fidetype synthetic typist"},
                            log=_err)
    except ImportError as e:
        _err(str(e))
        return 2
    _err(json.dumps(st))
    return 0


SUBCOMMANDS = {"make-synthetic": _make_synthetic, "train-kt": _train_kt, "replay-kt": _replay_kt,
               "replay-synthetic": _replay_synthetic}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in SUBCOMMANDS:
        return SUBCOMMANDS[args[0]](args[1:])
    if args and args[0] == "run":
        args = args[1:]
    return run_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
