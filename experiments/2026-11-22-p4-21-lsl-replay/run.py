"""P4-21: the 816 Brain-to-Text '25 test trials of M4-06 over a real pylsl loopback (checks of plan.md).

Part A (hypothesis route, trust layer): one LSL events stream per session day (``NTSOutlet``, FEP-0002)
-> ``open_source`` -> ``LSLTrustRunner`` on one ``StreamingTrustLayer``. Compared with the in-process
streaming replay (as M4-06 / M6-11) and with the batch harness (``batch-ours.json``).
Part B (frames, transport only): one frames + events stream pair per day, ``double64``, frame timestamps
on one continuous axis per day; every received row is compared with the file row.

Inputs stay outside the repo (``<bci-data>/derived/m4-06-real-replay``). Nothing is written to
``bci-data`` except the run log in ``<bci-data>/derived/p4-21``. The repo gets aggregate counts only
(``results/results.json``): no texts, no per-trial values.

Run (repo root): .venv\\Scripts\\python.exe -I experiments/2026-11-22-p4-21-lsl-replay/run.py [A|B|AB]
"""

from __future__ import annotations

import json
import math
import sys
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pylsl  # noqa: E402

from fidetype.adapters import lsl as L  # noqa: E402
from fidetype.trust.frozen import FrozenTrustConfig  # noqa: E402
from fidetype.trust.streaming import StreamingConfig, StreamingTrustLayer, iter_events  # noqa: E402

DER = Path.home() / "bci-data" / "derived" / "m4-06-real-replay"
HYP = DER / "streams" / "hyp-ours"
FRAMES = DER / "streams" / "frames"
CONFIG = ROOT / "experiments" / "2026-11-13-m4-06-real-replay" / "configs" / "trust-config-b2t25-ours-splitA.json"
LOGDIR = Path.home() / "bci-data" / "derived" / "p4-21"
OUT = HERE / "results"
RUN = uuid.uuid4().hex[:8]
RECEIVER_KEYS = ("lsl_t", "clock_domain")


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOGDIR / "run.log", "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def make_layer(cfg: FrozenTrustConfig) -> StreamingTrustLayer:
    return StreamingTrustLayer(cfg, streaming=StreamingConfig(route="hypothesis", max_attempts=1))


def batch_equal(d, b: dict) -> bool:
    gr = float(d.guard.risk) if d.guard is not None else float("nan")
    return (d.action.value == b["action"] and list(d.shown) == b["shown"] and float(d.inputs.p_top1) == float(b["p_top1"])
            and (gr == float(b["guard_risk"]) or (math.isnan(gr) and math.isnan(float(b["guard_risk"]))))
            and list(d.inputs.set_indices) == b["set"])


def days(trials: list[int], files: dict[int, list[dict]]) -> OrderedDict[str, list[int]]:
    by: OrderedDict[str, list[int]] = OrderedDict()
    for t in trials:
        by.setdefault(files[t][0]["meta"]["session.id"], []).append(t)
    return by


def strip(e: dict) -> dict:
    return {k: v for k, v in e.items() if k not in RECEIVER_KEYS}


# --- Part A ----------------------------------------------------------------------------------------

def part_a() -> dict:
    cfg = FrozenTrustConfig.load(CONFIG)
    batch = json.loads((DER / "batch-ours.json").read_text(encoding="utf-8"))
    trials = batch["trials"]
    files = {t: list(iter_events(HYP / f"trial-{t:04d}.jsonl")) for t in trials}
    by_day = days(trials, files)

    ref_layer = make_layer(cfg)
    ref: dict[int, object] = {}
    for sid, ts in by_day.items():
        for t in ts:
            got = []
            for ev in files[t]:
                got += ref_layer.push(ev, sid)
            got += ref_layer.end_of_utterance(sid)
            fin = [d for d in got if d.final]
            assert len(fin) == 1
            ref[t] = fin[0]

    layer = make_layer(cfg)
    lsl_dec: dict[int, object] = {}
    rx_hyp: list[dict] = []
    agg = {"events_sent": 0, "rejected": 0, "aborted": 0, "lost": 0, "bad_markers": 0, "late_releases": 0,
           "finals_per_day_ok": 0, "extra_decisions": 0}
    t0 = time.monotonic()
    for k, (sid, ts) in enumerate(by_day.items()):
        evs = [e for t in ts for e in files[t]]
        out = L.NTSOutlet(evs[0], name=f"p4-21-a-{RUN}-{k}", source_id=f"p4-21-a-{RUN}-{k}", frames=False)
        src = L.open_source(source_id=out.events_source_id, events="none", timeout=10.0,
                            mapping=L.LSLMapping(merge_window_s=0.05))
        orig_poll = src.poll

        def tapped(timeout: float = 0.05, _p=orig_poll):
            got = _p(timeout)
            rx_hyp.extend(e for e in got if e.get("type") == "hypothesis")
            return got

        src.poll = tapped  # type: ignore[method-assign]
        assert out.wait_for_consumers(10.0), "no consumer"
        time.sleep(0.05)
        runner = L.LSLTrustRunner(layer, src, session_id=sid, keep=True)
        for e in evs[1:]:
            out.push(e)
        agg["events_sent"] += len(evs) - 1
        tend = time.monotonic() + 60
        while runner.summary.final_decisions < len(ts) and time.monotonic() < tend:
            runner.step(0.02)
        runner.finish()
        if runner.summary.final_decisions < len(ts):
            runner.flush()
        finals = [d for d in runner.kept if d.final]
        agg["finals_per_day_ok"] += len(finals) == len(ts)
        agg["extra_decisions"] += max(0, len(finals) - len(ts))
        for t, d in zip(ts, finals):
            lsl_dec[t] = d
        st = src.stats.as_dict()
        agg["rejected"] += runner.summary.rejected_events
        agg["aborted"] += runner.summary.aborted_utterances
        agg["lost"] += int(st.get("lost", 0))
        agg["bad_markers"] += int(st.get("bad_markers", 0))
        agg["late_releases"] += int(st.get("late_releases", 0))
        src.close()
        out.close()
        log(f"A day {k + 1}/{len(by_day)}: {len(ts)} trials, {len(finals)} finals")
    wall = time.monotonic() - t0

    file_hyp = [e for t in trials for e in files[t] if e["type"] == "hypothesis"]
    order = [t for ts in by_day.values() for t in ts]
    file_hyp_day_order = [next(e for e in files[t] if e["type"] == "hypothesis") for t in order]
    eq_ref = sum(t in lsl_dec and lsl_dec[t].decision == ref[t].decision and lsl_dec[t].inputs == ref[t].inputs
                 for t in trials)
    eq_batch = sum(t in lsl_dec and batch_equal(lsl_dec[t], b) for t, b in zip(trials, batch["decisions"]))
    ref_batch = sum(batch_equal(ref[t], b) for t, b in zip(trials, batch["decisions"]))
    nb_eq = sum(a["nbest"] == b["nbest"] for a, b in zip(rx_hyp, file_hyp_day_order))
    acts: dict[str, int] = {}
    for d in lsl_dec.values():
        acts[d.action.value] = acts.get(d.action.value, 0) + 1
    n = len(trials)
    res = {"config_id": cfg.config_id, "trials": n, "sessions": len(by_day), "events_sent": agg["events_sent"],
           "wall_s": round(wall, 2), "final_decisions": len(lsl_dec), "days_with_one_final_per_trial":
           f"{agg['finals_per_day_ok']}/{len(by_day)}", "extra_final_decisions": agg["extra_decisions"],
           "lsl_equal_in_process_exact": f"{eq_ref}/{n}", "lsl_equal_batch_harness": f"{eq_batch}/{n}",
           "in_process_equal_batch_harness": f"{ref_batch}/{n}",
           "received_hypotheses": len(rx_hyp), "file_hypotheses": len(file_hyp),
           "received_nbest_equal_file": f"{nb_eq}/{n}", "rejected": agg["rejected"], "aborted": agg["aborted"],
           "lost": agg["lost"], "bad_markers": agg["bad_markers"], "late_releases": agg["late_releases"],
           "actions": dict(sorted(acts.items()))}
    res["pass"] = {
        "A1": len(lsl_dec) == n and agg["finals_per_day_ok"] == len(by_day) and agg["extra_decisions"] == 0,
        "A2": eq_ref == n, "A3": eq_batch == n,
        "A4": agg["rejected"] == agg["aborted"] == agg["lost"] == agg["bad_markers"] == 0,
        "A5": nb_eq == n and len(rx_hyp) == n,
    }
    return res


# --- Part B ----------------------------------------------------------------------------------------

def _row(v) -> np.ndarray:
    return np.asarray([-math.inf if x is None else float(x) for x in v], dtype=np.float64)


def part_b() -> dict:
    batch = json.loads((DER / "batch-ours.json").read_text(encoding="utf-8"))
    trials = batch["trials"]
    files = {t: list(iter_events(FRAMES / f"trial-{t:04d}.jsonl")) for t in trials}
    by_day = days(trials, files)
    agg = {"frames_sent": 0, "frames_received": 0, "rows_bit_equal": 0, "trials_frame_count_equal": 0,
           "trials_rows_all_equal": 0, "nonframe_sent": 0, "nonframe_received_after_first_header": 0,
           "nonframe_order_ok_days": 0, "headers_equal": 0, "headers_compared": 0, "ends_received": 0,
           "gaps": 0, "clamped": 0, "dropped": 0, "lost": 0, "late_releases": 0, "bad_markers": 0}
    t0 = time.monotonic()
    for k, (sid, ts) in enumerate(by_day.items()):
        evs = [e for t in ts for e in files[t]]
        head = evs[0]
        fp = float(head["frame_period"])
        out = L.NTSOutlet(head, name=f"p4-21-b-{RUN}-{k}", source_id=f"p4-21-b-{RUN}-{k}",
                          channel_format="double64", frames=True, events=True, heartbeat=True)
        src = L.open_source(source_id=out.frames_source_id, events="auto", timeout=10.0,
                            mapping=L.LSLMapping(merge_window_s=0.05))
        assert len(src.readers) == 2, "events stream not found"
        assert out.wait_for_consumers(10.0), "no consumer"
        time.sleep(0.05)
        n_frames = sum(e["type"] == "frame" for e in evs)
        recv: list[dict] = []
        rx = {"frames": 0}

        def produce() -> None:
            base = out.start_clock(0.0, pylsl.local_clock() + 0.1, 1.0)
            g = 0
            ts_last = base
            for e in evs[1:]:
                if e["type"] == "frame":
                    while g - rx["frames"] > 1000:
                        time.sleep(0.002)
                    ts_last = base + g * fp
                    g += 1
                    out.push(e, ts_last)
                else:
                    out.push(e, ts_last)

        th = threading.Thread(target=produce, daemon=True)
        th.start()
        n_end = sum(e["type"] == "end" for e in evs)
        tend = time.monotonic() + 600
        while time.monotonic() < tend:
            got = src.poll(0.02)
            recv += got
            rx["frames"] += sum(e.get("type") == "frame" for e in got)
            if rx["frames"] >= n_frames and sum(e.get("type") == "end" for e in recv) >= n_end and not th.is_alive():
                break
        recv += src.drain()
        th.join(5)
        st = src.stats.as_dict()
        for key, sk in (("gaps", "gaps"), ("clamped", "clamped"), ("dropped", "dropped_out_of_order"),
                        ("lost", "lost"), ("late_releases", "late_releases"), ("bad_markers", "bad_markers")):
            agg[key] += int(st.get(sk, 0))
        src.close()
        out.close()

        # Split both sides into trials at the 'end' events, compare frame rows and the other events.
        rx_body = [e for e in recv[1:] if e.get("type") not in (L.LSL_STATUS,)]  # recv[0] = built header
        file_body = evs[1:]
        rx_non = [e for e in rx_body if e["type"] != "frame"]
        fi_non = [e for e in file_body if e["type"] != "frame"]
        agg["nonframe_sent"] += len(fi_non)
        agg["nonframe_received_after_first_header"] += len(rx_non)
        agg["nonframe_order_ok_days"] += [e["type"] for e in rx_non] == [e["type"] for e in fi_non]
        for a, b in zip(rx_non, fi_non):
            if b["type"] == "header":
                agg["headers_compared"] += 1
                agg["headers_equal"] += strip(a) == b
            agg["ends_received"] += a["type"] == "end"

        def split(body: list[dict]) -> list[list[np.ndarray]]:
            per, cur = [], []
            for e in body:
                if e["type"] == "frame":
                    cur.append(_row(e["log_probs"]))
                elif e["type"] == "end":
                    per.append(cur)
                    cur = []
            return per

        rp, fpr = split(rx_body), split(file_body)
        for a, b in zip(rp, fpr):
            agg["trials_frame_count_equal"] += len(a) == len(b)
            eq = sum(x.shape == y.shape and np.array_equal(x, y) for x, y in zip(a, b))
            agg["rows_bit_equal"] += eq
            agg["trials_rows_all_equal"] += eq == len(b) == len(a)
        agg["frames_sent"] += n_frames
        agg["frames_received"] += rx["frames"]
        log(f"B day {k + 1}/{len(by_day)}: {len(ts)} trials, frames {rx['frames']}/{n_frames}")
    wall = time.monotonic() - t0
    n = len(trials)
    res = {"trials": n, "sessions": len(by_day), "channel_format": "double64", "wall_s": round(wall, 2),
           "frames_per_s": round(agg["frames_sent"] / wall, 1), **agg}
    res["pass"] = {
        "B1": agg["frames_received"] == agg["frames_sent"] and agg["trials_frame_count_equal"] == n,
        "B2": agg["rows_bit_equal"] == agg["frames_sent"] and agg["trials_rows_all_equal"] == n,
        "B3": agg["nonframe_order_ok_days"] == len(by_day) and agg["nonframe_received_after_first_header"]
              == agg["nonframe_sent"] and agg["headers_equal"] == agg["headers_compared"] == n - len(by_day)
              and agg["ends_received"] == n,
        "B4": agg["gaps"] == agg["clamped"] == agg["dropped"] == agg["lost"] == 0,
    }
    return res


def main() -> None:
    parts = sys.argv[1] if len(sys.argv) > 1 else "AB"
    LOGDIR.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    log(f"start run {RUN} parts {parts}; pylsl {pylsl.__version__}, liblsl {pylsl.library_version()}")
    res: dict = {"pylsl": pylsl.__version__, "liblsl": pylsl.library_version()}
    if "A" in parts:
        res["A"] = part_a()
        log(json.dumps(res["A"]))
    if "B" in parts:
        res["B"] = part_b()
        log(json.dumps(res["B"]))
    res["all_pass"] = all(all(res[p]["pass"].values()) for p in ("A", "B") if p in res)
    res["note"] = "aggregate counts only; the trial files and texts stay outside the repo"
    if parts == "AB":
        (OUT / "results.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
