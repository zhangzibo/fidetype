"""M6-13 soak: the decision consumer (LSL ``trust_decision`` stream -> validation -> counts).

It is the "app" end of the live chain. It reads the JSON strings of the decisions outlet
(FEP-0002 section 8) and checks **every** event:

- format: ``fidetype.conformance.profiles.fep0001.td_format_errors`` (the conformance validator);
- order rules 5-7 of FEP-0001 online (seq increases, utterance never goes back, one final per utterance);
- loss: a seq step > 1 is a lost event; seq <= last is a duplicate or a reorder;
- transport: receive time - (LSL timestamp + time_correction), and the clock offset over time.

A restart of the trust process (seq back to 0) starts a new epoch; it is counted, not hidden.
All events go to ``--events-file`` (local, not committed). Every ``--window-s`` one metrics line goes
to ``metrics-consumer.jsonl``. Stop: create the ``--stop-file``.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import JsonlWriter, LogHist, log, now_iso, proc_stats, pstats  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--events-file", required=True)
    ap.add_argument("--stop-file", required=True)
    ap.add_argument("--outlet-name", default="soak.decisions")
    ap.add_argument("--window-s", type=float, default=120.0)
    ap.add_argument("--epoch", type=int, default=0)
    a = ap.parse_args()

    import pylsl

    from fidetype.conformance.profiles.fep0001 import td_format_errors

    out = JsonlWriter(Path(a.results_dir) / "metrics-consumer.jsonl")
    evf = open(a.events_file, "a", encoding="utf-8")
    stop = Path(a.stop_file)
    t_start = time.monotonic()

    log(f"consumer: resolving {a.outlet_name}")
    infos: list[Any] = []
    while not infos:
        if stop.exists():
            return 0
        infos = pylsl.resolve_byprop("name", a.outlet_name, 1, 5.0)
    inlet = pylsl.StreamInlet(infos[0], max_buflen=360, recover=True)
    inlet.open_stream(10.0)
    log(f"consumer: connected to {a.outlet_name} ({infos[0].source_id()})")

    C: dict[str, Any] = {"received": 0, "invalid": 0, "json_errors": 0, "lost": 0, "dup_or_reorder": 0,
                         "utt_back": 0, "double_final": 0, "epochs": 0, "finals": 0,
                         "actions": {"COMMIT": 0, "OFFER": 0, "ABSTAIN": 0}, "commit_texts": 0}
    examples: list[str] = []
    last_seq: int | None = None
    last_utt: int | None = None
    finals: set[int] = set()
    tc = 0.0
    tc_at = -1e9
    tc_vals: list[float] = []
    lat: list[float] = []
    H = LogHist()
    win = 0
    t_win = time.monotonic()
    n_win = 0
    last_stop_check = 0.0
    stopping_since: float | None = None
    last_rx = 0.0

    def bad(msg: str) -> None:
        if len(examples) < 20:
            examples.append(msg)

    def write(final: bool = False) -> None:
        nonlocal lat, tc_vals, t_win, win, n_win
        now = time.monotonic()
        rec = {"kind": "final" if final else "window", "epoch": a.epoch, "window": win, "t_iso": now_iso(),
               "t_s": now - t_start, "window_s": now - t_win, **proc_stats(), "received_window": n_win,
               "transport_ms": pstats(lat), "counts": dict(C, actions=dict(C["actions"])), "last_seq": last_seq,
               "time_correction_s": {"last": tc_vals[-1] if tc_vals else None,
                                     "min": min(tc_vals) if tc_vals else None,
                                     "max": max(tc_vals) if tc_vals else None, "n": len(tc_vals)}}
        if final:
            rec["whole_run_transport_ms"] = H.summary_ms()
            rec["examples"] = examples
        out.write(rec)
        lat, tc_vals = [], []
        t_win = now
        win += 1
        n_win = 0

    while True:
        now = time.monotonic()
        if now - last_stop_check >= 1.0:
            last_stop_check = now
            if stopping_since is None and stop.exists():
                stopping_since = now  # keep reading until the stream is quiet for 3 s
            if now - tc_at >= 5.0:
                try:
                    tc = float(inlet.time_correction(2.0))
                    tc_vals.append(tc)
                except Exception:  # noqa: BLE001 - keep the old offset
                    pass
                tc_at = now
        if now - t_win >= a.window_s:
            write()
        s, ts = inlet.pull_chunk(timeout=0.0, max_samples=4096)
        if not ts:
            if stopping_since is not None and now - max(stopping_since, last_rx) >= 3.0:
                break
            time.sleep(0.02)
            continue
        last_rx = now
        rt = pylsl.local_clock()
        for sample, t in zip(s, ts):
            raw = sample[0]
            evf.write(raw + "\n")
            C["received"] += 1
            n_win += 1
            d = rt - (t + tc)
            lat.append(d)
            H.add(max(d, 0.0))
            try:
                e = json.loads(raw)
            except ValueError:
                C["json_errors"] += 1
                C["invalid"] += 1
                bad(f"json error at received {C['received']}")
                continue
            errs = [] if e.get("type") == "trust_decision" else [f"type {e.get('type')!r}"]
            errs += td_format_errors(e)
            seq, utt = e.get("seq"), e.get("utterance")
            if isinstance(seq, int):
                if last_seq is not None and seq == 0 and last_seq > 0:
                    C["epochs"] += 1  # the trust process restarted
                    last_utt, finals = None, set()
                elif last_seq is not None and seq <= last_seq:
                    C["dup_or_reorder"] += 1
                    errs.append(f"seq {seq} after {last_seq}")
                elif last_seq is not None and seq > last_seq + 1:
                    C["lost"] += seq - last_seq - 1
                    bad(f"lost seq {last_seq + 1}..{seq - 1}")
                last_seq = seq if last_seq is None or seq > last_seq or seq == 0 else last_seq
            if isinstance(utt, int):
                if last_utt is not None and utt < last_utt:
                    C["utt_back"] += 1
                    errs.append(f"utterance {utt} after {last_utt}")
                if utt in finals:
                    C["double_final"] += 1
                    errs.append(f"decision after the final one for utterance {utt}")
                if e.get("is_final") is True:
                    finals.add(utt)
                    if len(finals) > 10000:
                        finals = {x for x in finals if x > utt - 100}
                last_utt = utt if last_utt is None else max(last_utt, utt)
            if e.get("is_final") is True:
                C["finals"] += 1
                act = e.get("action")
                C["actions"][act] = C["actions"].get(act, 0) + 1
                if act == "COMMIT" and e.get("shown"):
                    C["commit_texts"] += 1
            if errs:
                C["invalid"] += 1
                bad(f"seq {seq}: {errs}")
        evf.flush()
    write(final=True)
    evf.close()
    log(f"consumer: stop; received {C['received']}, invalid {C['invalid']}, lost {C['lost']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
