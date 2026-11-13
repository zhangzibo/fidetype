"""M6-08: live end-to-end test BrainFlow Synthetic board -> LSL -> trust layer.

Two separate processes, as in real use:

- the bridge   ``fidetype lsl brainflow-bridge --board synthetic`` (BrainFlow board id -1,
  16 EEG channels, 250 Hz, fake data; a ``segment_end`` marker every 4 s);
- the consumer ``fidetype lsl run --signal-decoder toy-<mode> --decoder demo`` with the frozen
  demo config (``src/fidetype/demo/trust-config-demo.json``).

The toy signal decoder carries NO text information (``fidetype.decoders.toy_signal``).
So the correct output is: no COMMIT.

Timeline of one run (seconds after the consumer starts):

    0     consumer starts and waits for the stream (start order: consumer first)
    2     bridge #1 starts
    ~22   bridge #1 discards the board data for 3 s (simulated dropout -> gap)
    40    bridge #1 is killed (TerminateProcess / SIGKILL; no clean shutdown)
    44    bridge #2 starts (same source_id) -> the consumer reconnects
    ~64   bridge #2 stops cleanly (--duration 20)
    70    consumer stops (--duration 70)

Measured: decisions (action, reason, gaps), e2e latency (consumer clock at the decision - LSL time of
the segment_end marker), LSL transport latency, CPU time of the consumer and of the bridges.

Usage: python experiments/2026-11-13-m6-08-brainflow-live/run.py [--modes flat features] [--quick]
Needs: pip install "fidetype[lsl,brainflow]". CPU only. No participant data.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONFIG = ROOT / "src" / "fidetype" / "demo" / "trust-config-demo.json"
OUT = HERE / "out"


class Proc:
    """A child process in its own Windows job object.

    The venv ``python.exe`` can be a launcher that starts the real
    interpreter as a child, so the job (not the process) is measured and
    killed: CPU = user + kernel time of every process in the job. The
    process starts suspended, joins the job, then resumes (no race).
    On POSIX: a plain Popen; CPU from ``os.wait4``.
    """

    def __init__(self, args: list[str], stdout, stderr) -> None:
        self.job = None
        self.cpu_posix: float | None = None
        if os.name == "nt":
            import ctypes

            k32 = ctypes.windll.kernel32
            k32.CreateJobObjectW.restype = ctypes.c_void_p
            self.job = k32.CreateJobObjectW(None, None)
            self.p = subprocess.Popen(args, stdout=stdout, stderr=stderr, cwd=ROOT, creationflags=0x4)  # SUSPENDED
            h = ctypes.c_void_p(int(self.p._handle))  # type: ignore[attr-defined]
            if not k32.AssignProcessToJobObject(ctypes.c_void_p(self.job), h):
                raise OSError("AssignProcessToJobObject failed")
            ctypes.windll.ntdll.NtResumeProcess(h)
        else:
            self.p = subprocess.Popen(args, stdout=stdout, stderr=stderr, cwd=ROOT)

    def kill(self) -> None:
        if self.job is not None:
            import ctypes

            ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(self.job), 9)
        else:
            self.p.kill()

    def wait(self, timeout: float | None = None) -> int:
        if os.name != "nt" and self.cpu_posix is None:
            _, status, ru = os.wait4(self.p.pid, 0)
            self.cpu_posix = ru.ru_utime + ru.ru_stime
            self.p.returncode = os.waitstatus_to_exitcode(status)
            return self.p.returncode
        return self.p.wait(timeout)

    @property
    def returncode(self) -> int | None:
        return self.p.returncode

    def cpu_seconds(self) -> float | None:
        """User + kernel CPU seconds of all processes of the job (after they ended)."""
        if self.job is None:
            return self.cpu_posix
        import ctypes

        class Acct(ctypes.Structure):  # JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
            _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                        ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32),
                        ("ActiveProcesses", ctypes.c_uint32), ("TotalTerminatedProcesses", ctypes.c_uint32)]

        a = Acct()
        ok = ctypes.windll.kernel32.QueryInformationJobObject(ctypes.c_void_p(self.job), 1, ctypes.byref(a),
                                                              ctypes.sizeof(a), None)
        return (a.TotalUserTime + a.TotalKernelTime) / 1e7 if ok else None


def fidetype_cmd() -> list[str]:
    return [sys.executable, "-m", "fidetype.adapters.lsl"]


def start(args: list[str], log: Path) -> Proc:
    return Proc(fidetype_cmd() + args, subprocess.DEVNULL, open(log, "w", encoding="utf-8"))


def run_mode(mode: str, quick: bool) -> dict:
    k = 0.5 if quick else 1.0
    T = {"bridge1": 2 * k, "pause_at": 20 * k, "pause_for": 3.0 * k, "kill": 40 * k, "bridge2": 44 * k,
         "bridge2_dur": 20 * k, "consumer_dur": 70 * k}
    OUT.mkdir(exist_ok=True)
    dec_path, sum_path = OUT / f"{mode}-decisions.jsonl", OUT / f"{mode}-summary.json"
    name, sid = f"m608.{mode}", f"m608-{mode}-bridge"
    cons_args = ["run", "--config", str(CONFIG), "--stream-name", name, "--signal-decoder", f"toy-{mode}",
                 "--decoder", "demo", "--max-attempts", "1", "--duration", str(T["consumer_dur"]),
                 "--resolve-timeout", "20", "--summary", str(sum_path)]
    bridge_common = ["brainflow-bridge", "--board", "synthetic", "--name", name, "--source-id", sid, "--trial-s", "4"]
    t0 = time.monotonic()
    with open(dec_path, "w", encoding="utf-8") as dfh:
        cons = Proc(fidetype_cmd() + cons_args, dfh, open(OUT / f"{mode}-consumer.log", "w", encoding="utf-8"))
        events: list[dict] = []

        def at(t: float) -> None:
            dt = t0 + t - time.monotonic()
            if dt > 0:
                time.sleep(dt)

        at(T["bridge1"])
        b1 = start(bridge_common + ["--pause", f"{T['pause_at']}:{T['pause_for']}"], OUT / f"{mode}-bridge1.log")
        events.append({"t": round(time.monotonic() - t0, 2), "event": "bridge1 start"})
        at(T["kill"])
        b1.kill()
        b1.wait()
        events.append({"t": round(time.monotonic() - t0, 2), "event": "bridge1 killed"})
        at(T["bridge2"])
        b2 = start(bridge_common + ["--duration", str(T["bridge2_dur"]), "--stats", str(OUT / f"{mode}-bridge2.json")],
                   OUT / f"{mode}-bridge2.log")
        events.append({"t": round(time.monotonic() - t0, 2), "event": "bridge2 start"})
        b2.wait()
        events.append({"t": round(time.monotonic() - t0, 2), "event": f"bridge2 stopped (rc {b2.returncode})"})
        cons.wait(timeout=T["consumer_dur"] + 60)
        events.append({"t": round(time.monotonic() - t0, 2), "event": f"consumer stopped (rc {cons.returncode})"})
    wall = time.monotonic() - t0
    cpu = {"consumer_s": cons.cpu_seconds(), "bridge1_s": b1.cpu_seconds(), "bridge2_s": b2.cpu_seconds()}
    return analyse(mode, T, events, cpu, wall, cons.returncode, dec_path, sum_path)


def pct(xs: list[float], q: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    i = (len(s) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def analyse(mode, T, events, cpu, wall, rc, dec_path, sum_path) -> dict:
    decs = [json.loads(line) for line in open(dec_path, encoding="utf-8") if line.strip()]
    final = [d for d in decs if d.get("is_final", True)]
    actions: dict[str, int] = {}
    for d in final:
        actions[d["action"]] = actions.get(d["action"], 0) + 1
    lat = [1e3 * d["lsl"]["e2e_latency_s"] for d in final if "e2e_latency_s" in d.get("lsl", {})]
    # "steady": not next to a dropout. A decision is next to a dropout if its utterance has a gap, or if the
    # signal stops for > 1 s after it (the bridge sends a boundary inside a dropout trial_hold_s late).
    steady = []
    for i, d in enumerate(final):
        if "e2e_latency_s" not in d.get("lsl", {}) or d["lsl"]["utterance"].get("gaps", 0):
            continue
        nxt = final[i + 1]["input"]["t_range"][0] if i + 1 < len(final) else None
        if nxt is not None and nxt - d["input"]["t_range"][1] > 1.0:
            continue
        steady.append(1e3 * d["lsl"]["e2e_latency_s"])
    reasons: dict[str, int] = {}
    for d in final:
        r = re.sub(r"[0-9.]+", "#", str(d.get("reason", "")))
        reasons[r] = reasons.get(r, 0) + 1
    summ = json.loads(Path(sum_path).read_text(encoding="utf-8")) if Path(sum_path).exists() else {}
    log = (OUT / f"{mode}-consumer.log").read_text(encoding="utf-8", errors="replace")
    fl = [ln for ln in log.splitlines() if ln.startswith("[fidetype.lsl]")]
    guard = [d.get("guard_risk") for d in final]
    layer_ms = [1e3 * d["latency_s"] for d in final if isinstance(d.get("latency_s"), (int, float))]
    cons_cpu = cpu["consumer_s"]
    br_cpu = [c for c in (cpu["bridge1_s"], cpu["bridge2_s"]) if c is not None]
    bridge_time = (T["kill"] - T["bridge1"]) + T["bridge2_dur"]
    return {
        "mode": mode,
        "timeline_s": T,
        "events": events,
        "consumer_exit_code": rc,
        "wall_s": round(wall, 2),
        "final_decisions": len(final),
        "actions": actions,
        "commits": actions.get("COMMIT", 0),
        "reasons": reasons,
        "decisions_with_gap": sum(1 for d in final if d["lsl"]["utterance"].get("gaps", 0) > 0),
        "frames_per_decision": [d["lsl"]["utterance"]["frames"] for d in final],
        "guard_risk": guard,
        "p_top1": [round(d["p_top1"], 3) for d in final if isinstance(d.get("p_top1"), (int, float))],
        "trust_layer_latency_ms": {"p50": round(pct(layer_ms, .5), 1), "max": round(max(layer_ms), 1) if layer_ms
                                   else None},
        "e2e_latency_ms": {"n": len(lat), "p50": round(pct(lat, .5), 1), "p95": round(pct(lat, .95), 1),
                           "max": round(max(lat), 1) if lat else None},
        "e2e_latency_steady_ms": {"n": len(steady), "p50": round(pct(steady, .5), 1),
                                  "p95": round(pct(steady, .95), 1), "max": round(max(steady), 1) if steady else None},
        "e2e_latency_all_ms": [round(x, 1) for x in lat],
        "source": summ.get("source", {}),
        "aborted_utterances": summ.get("aborted_utterances"),
        "stop_reason": summ.get("stop_reason"),
        "consumer_log": fl,
        "cpu": {**cpu,
                "consumer_pct_of_one_core": round(100 * cons_cpu / T["consumer_dur"], 2) if cons_cpu else None,
                "bridge_pct_of_one_core": round(100 * sum(br_cpu) / bridge_time, 2) if br_cpu else None},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["flat", "features"])
    ap.add_argument("--quick", action="store_true", help="half-length timeline")
    a = ap.parse_args()
    import brainflow  # noqa: F401 - fail early
    import pylsl

    res = {"task": "M6-08", "date": time.strftime("%Y-%m-%d %H:%M"), "config": str(CONFIG.relative_to(ROOT)),
           "board": "BrainFlow Synthetic (id -1)", "platform": platform.platform(), "python": platform.python_version(),
           "pylsl": pylsl.__version__, "brainflow": __import__("importlib.metadata").metadata.version("brainflow"),
           "cpu_count": os.cpu_count(), "runs": []}
    for m in a.modes:
        print(f"run {m} ...", flush=True)
        r = run_mode(m, a.quick)
        print(json.dumps({k: r[k] for k in ("mode", "final_decisions", "actions", "e2e_latency_ms",
                                            "e2e_latency_steady_ms", "cpu")}), flush=True)
        res["runs"].append(r)
    (HERE / "results.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
