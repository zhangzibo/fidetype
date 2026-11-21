"""``fidetype live``: one-command live decode with the trust guard (P14-04).

::

    fidetype live --source synthetic                                   # no hardware, no data, no extra
    fidetype live --source synthetic --publish lsl                     # + LSL outlets ([lsl]; P14-16)
    fidetype live --publish ws://127.0.0.1:8765/nts                    # + send NTS to a WebSocket server ([ws])
    fidetype live --publish ws://127.0.0.1:8766/decisions              # + serve trust decisions ([ws])
    fidetype live --source brainflow --board-id -1 --out s.nts.jsonl   # BrainFlow Synthetic board ([brainflow])
    fidetype live --source brainflow --board-id 0 --serial-port COM3   # OpenBCI Cyton (untested: P4-06)
    fidetype live --source lsl --stream-name fidetype.replay.kt-semg \\
        --model kt.model.json --guard kt.guard.json                    # any raw-signal LSL stream ([lsl])
    fidetype live --source file --path rec.edf --speed 0               # a recording file (reader from the registry)
    fidetype live --source file --reader openbci-gui --path my.txt     # pick the file reader by id (P4-17)
    fidetype live make-synthetic --out DIR                             # rebuild builtin:synthetic-keys
    fidetype live train-kt --data ~/bci-data/raw/kt-semg --out DIR     # KT-sEMG demo model + guard (local)
    fidetype live replay-kt --data ~/bci-data/raw/kt-semg --run run28  # KT-sEMG recording -> LSL ([lsl])
    fidetype live replay-synthetic                                     # synthetic typist -> LSL ([lsl])

Defaults: ``--model builtin:synthetic-keys --guard builtin:synthetic-keys``.
Each decision prints one line (``--json``: one JSON object). ``--out``
writes an NTS JSON Lines input stream (header, frames, final hypotheses,
segment ends, end). The trust decisions go to a separate FEP-0001 decision
log, ``--decisions-out`` (default with ``--out``: ``S.decisions.jsonl``
next to ``S.jsonl``), never into the stream (TD-4; P14-17).
``--publish`` sends the same events over a binding in real time
(:mod:`fidetype.live.publish`). Read docs/live-decode.md first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

SOURCES = ("synthetic", "brainflow", "lsl", "file")


def _err(msg: str) -> None:
    sys.stderr.write(f"[fidetype.live] {msg}\n")
    sys.stderr.flush()


def decisions_path(out: str | None, decisions_out: str | None) -> str | None:
    """The decision log path: ``--decisions-out``, else derived from ``--out`` (P14-17); None = not written.

    ``s.nts.jsonl`` -> ``s.nts.decisions.jsonl``; a name without ``.jsonl`` gets ``.decisions.jsonl`` added.
    ``--decisions-out none`` turns the log off.
    """
    if decisions_out is not None:
        return None if decisions_out.lower() == "none" else decisions_out
    if not out:
        return None
    return (out[: -len(".jsonl")] if out.endswith(".jsonl") else out) + ".decisions.jsonl"


def _run_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="fidetype live",
        description="Live decode: signal source -> windows -> model -> trust guard (commit / offer / withhold) "
                    "-> NTS. Subcommands: make-synthetic, train-kt, replay-kt (see --help of each).")
    ap.add_argument("--source", choices=SOURCES, default="synthetic", help="signal source (default: synthetic)")
    ap.add_argument("--model", default="builtin:synthetic-keys", help="*.model.json path or builtin:<name>")
    ap.add_argument("--guard", default=None, help="trust guard JSON (fidetype.trust save); default: the model's "
                    "builtin guard when --model is builtin")
    ap.add_argument("--out", help="write the NTS JSON Lines input stream here (frames, hypotheses; no trust decisions)")
    ap.add_argument("--decisions-out", metavar="FILE",
                    help="write the trust decisions here as a FEP-0001 decision log (JSON Lines, no header). "
                         "Default with --out: OUT without .jsonl + .decisions.jsonl; 'none' = do not write them")
    ap.add_argument("--json", action="store_true", help="print one JSON object per decision")
    ap.add_argument("--no-text", action="store_true", help="do not print decoded text")
    ap.add_argument("--summary", help="write the run summary (counts, latency) as JSON here")
    ap.add_argument("--duration", type=float, help="stop after this many seconds")
    ap.add_argument("--max-decisions", type=int, help="stop after this many decisions")
    ap.add_argument("--timing", choices=("markers", "fixed", "detect"),
                    help="window timing (default: the model's); detect = find key onsets in the signal (P4-10)")
    ap.add_argument("--onset", help='detect timing: onset detector, "envelope" or a *.onset.json file '
                    "(default: the model card's onset file, else envelope)")
    ap.add_argument("--hop", type=float, help="fixed timing: seconds between windows (default: the model's)")
    ap.add_argument("--segment-s", type=float, help="end a segment every S seconds (instead of segment_end markers)")
    pg = ap.add_argument_group("publish over a binding (P14-16; docs/live-decode.md)")
    pg.add_argument("--publish", action="append", default=[], metavar="TARGET",
                    help="send the NTS events in real time: lsl or lsl:NAME (frames NAME, events NAME.events, "
                         "decisions NAME.decisions; [lsl]), ws://HOST:PORT/nts (send to a server; [ws]) or "
                         "ws://HOST:PORT/decisions (serve the trust decisions; port 0 = free port; [ws]). Repeat "
                         "for more targets")
    pg.add_argument("--publish-wait", type=float, default=0.0, metavar="S",
                    help="before the decode, wait up to S seconds for a consumer on each target (default 0)")
    pg.add_argument("--publish-linger", type=float, default=1.0, metavar="S",
                    help="keep the outlets open S seconds after the end (default 1)")
    g = ap.add_argument_group("synthetic source")
    g.add_argument("--utterances", type=int, default=10, help="number of synthetic utterances (default 10)")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--speed", type=float, default=1.0, help="synthetic and file sources: 1 = real time, "
                   "0 = as fast as possible")
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
    fg = ap.add_argument_group("file source (a recording file; reader from the adapter registry; P4-17)")
    fg.add_argument("--path", help="the recording file")
    fg.add_argument("--reader", metavar="ID", help="file reader id (default: the reader whose file-name pattern "
                    "matches --path; list: docs/adapters.md, section 'File readers')")
    fg.add_argument("--modality", help="NTS device.modality of the file signal (default: the reader's)")
    lg = ap.add_argument_group("lsl source")
    lg.add_argument("--stream-name")
    lg.add_argument("--stream-type")
    lg.add_argument("--source-id")
    lg.add_argument("--markers", default="auto", help='marker stream: "auto" (from the signal desc), "none", or a name')
    lg.add_argument("--resolve-timeout", type=float, default=10.0)
    lg.add_argument("--max-reconnects", type=int, default=5,
                    help="reconnects allowed in one run after a lost stream (default 5; 0 = end the run at a loss)")
    lg.add_argument("--reconnect-timeout", type=float, default=30.0,
                    help="seconds to find a lost stream again before the run ends (default 30)")
    lg.add_argument("--reconnect-backoff", type=float, default=2.0,
                    help="retry wait factor after each failed try (0.05 s, x2, at most 2 s; default 2)")
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
    if a.source == "file":
        from fidetype.adapters.registry import open_file_source

        entry, src = open_file_source(a.path, a.reader, modality=a.modality, speed=a.speed)
        src.info.setdefault("meta", {})["fidetype.file_reader"] = entry["id"]
        _err(f"file reader {entry['id']} ({entry['status']}; {entry['module']})")
        return src
    return S.LSLSource(a.stream_name, a.stream_type, a.source_id, a.markers, a.resolve_timeout,
                       max_reconnects=a.max_reconnects, reconnect_timeout=a.reconnect_timeout,
                       backoff=a.reconnect_backoff, log=_err)


def run_main(argv: Sequence[str]) -> int:
    a = _run_parser().parse_args(list(argv))
    import fidetype.trust as ft
    from fidetype.live.model import load_model, resolve_asset
    from fidetype.live.runner import LiveDecoder, make_writer, print_decision
    from fidetype.live.synthetic import KEYPRESS

    model = load_model(a.model)
    gspec = a.guard or (a.model if str(a.model).startswith("builtin:") else None)
    if gspec is None:
        _err("give --guard (a trust guard JSON calibrated for this model)")
        return 2
    guard = ft.load(resolve_asset(gspec, ".guard.json"), audit_text=not a.no_text)
    if guard.input_kind != "nbest":
        _err("the guard must be calibrated on n-best input (input_kind nbest)")
        return 2
    if a.source == "file":
        if not a.path:
            _err("--source file needs --path FILE")
            return 2
        if not Path(a.path).is_file():
            _err(f"no such file: {a.path}")
            return 2
        from fidetype.adapters.registry import pick_file_reader

        try:
            pick_file_reader(a.path, a.reader)
        except ValueError as e:
            _err(str(e))
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
    file_mk = getattr(src, "markers", None) or []
    if a.source == "file" and not a.timing and timing == "markers" and not any(m == KEYPRESS for _, m in file_mk):
        timing = "fixed"  # P4-16: real files carry other markers (EDF+ "T0", "start"), which open no window
        _err(f"note: the file has no '{KEYPRESS}' markers ({len(file_mk)} other markers); fixed timing "
             "(give --timing to change it)")
    _err(f"source {info['name']} ({info['channels']} ch, {info['sample_rate']:g} Hz); model {model.name} "
         f"({model.channels} ch, {model.sample_rate:g} Hz, timing {timing}); guard {guard.config_id} "
         f"(alpha {guard.alpha:g}, delta {guard.delta:g})")
    if model.card.get("warning"):
        _err(f"model note: {model.card['warning']}")
    if a.source == "brainflow" and "brainflow" not in json.dumps(model.card.get("training", {})).lower():
        _err("note: the model was not trained on this board; expect no commits (the correct output on a "
             "signal with no text information)")
    detector = None
    if timing == "detect":
        from fidetype.live.onset import load_onset

        ospec = a.onset or model.card.get("onset") or "envelope"
        if not a.onset and ospec != "envelope" and not Path(str(ospec)).is_absolute():
            ospec = str(Path(resolve_asset(a.model, ".model.json")).parent / str(ospec))  # next to the model
        try:
            detector = load_onset(ospec, model.sample_rate, model.channels)
        except (OSError, ValueError) as e:
            src.close()
            _err(f"cannot load the onset detector {ospec!r}: {e}")
            return 2
        _err(f"onset detector: {detector.kind} {json.dumps(detector.params)}")
    tee = None
    if a.publish:
        from fidetype.live.publish import EventTee, make_publisher

        try:
            pubs = [make_publisher(t, same_clock=a.source == "lsl", log=_err) for t in a.publish]
        except (ValueError, ImportError) as e:
            src.close()
            _err(str(e))
            return 2
    else:
        from fidetype.live.publish import EventTee

        pubs = []
    dec_out = decisions_path(a.out, a.decisions_out)
    if pubs or a.out or dec_out:
        tee = EventTee(pubs, open(a.out, "w", encoding="utf-8", newline="\n") if a.out else None, log=_err,
                       decisions_file=open(dec_out, "w", encoding="utf-8", newline="\n") if dec_out else None)
    try:
        writer = make_writer(tee, model, info, guard, a.source, timing) if tee is not None else None
    except Exception as e:  # noqa: BLE001 - e.g. a WebSocket server that does not answer
        src.close()
        if tee is not None:
            tee.finish()
        _err(f"cannot open the output: {e}")
        return 3
    if tee is not None:
        for p in tee.publishers:
            _err(f"publish: {p.describe()}")
        if a.publish_wait > 0:
            for t, ok in tee.wait(a.publish_wait).items():
                if not ok:
                    _err(f"publish: no consumer on {t} after {a.publish_wait:g} s; sending anyway")
    try:
        dec = LiveDecoder(model, guard, src, timing=timing, hop_s=a.hop, segment_s=a.segment_s, writer=writer,
                          detector=detector,
                          on_decision=lambda d: print_decision(d, as_json=a.json, include_text=not a.no_text))
    except ValueError as e:
        src.close()
        if writer is not None:
            writer.close()
        if tee is not None:
            tee.finish()
        _err(str(e))
        return 2
    published = None
    try:
        st = dec.run(duration_s=a.duration, max_decisions=a.max_decisions)
    finally:
        if writer is not None:
            writer.close()
        if tee is not None:
            published = tee.finish(a.publish_linger)
    s = st.as_dict()
    if st.losses or st.gaps:
        _err(f"stream losses {st.losses}, gap records {st.gaps}, segments dropped at a gap {st.dropped_segments} "
             f"({st.dropped_frames} frames; no decision on a cut input)")
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
        _err(f"NTS written: {a.out} (check: nts-conform check {a.out})")
    if dec_out:
        _err(f"decision log written: {dec_out} ({tee.decisions if tee is not None else 0} decisions; "
             f"check: nts-conform check {dec_out})")
        s["decisions_out"] = dec_out
    if published is not None and a.publish:
        s["published"] = published
        _err(f"published: {json.dumps(published)}")
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
    ap.add_argument("--fit-run", action="append", help="train the model on this run id (repeat; overrides the split)")
    ap.add_argument("--guard-run", action="append", help="calibrate the guard on this run id (repeat)")
    ap.add_argument("--guard-chunk-keys", type=int, help="cut guard segments into chunks of N keys")
    a = ap.parse_args(list(argv))
    from fidetype.live.build import train_kt

    print(json.dumps(train_kt(a.data, a.out, a.model_runs, a.guard_runs, a.max_csv_mb, log=_err, fit_ids=a.fit_run,
                              guard_ids=a.guard_run, guard_chunk_keys=a.guard_chunk_keys), indent=2))
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
