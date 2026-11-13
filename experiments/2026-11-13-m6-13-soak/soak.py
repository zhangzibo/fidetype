"""M6-13: long soak test of the live path (BrainFlow Synthetic board -> LSL -> trust layer -> decisions on LSL -> consumer).

Processes (each in its own Windows job object; CPU only):

- ``bridge``   ``python -m fidetype.adapters.lsl brainflow-bridge --board synthetic`` (16 ch, 250 Hz,
  ``segment_end`` every 4 s). It is restarted every ``--cycle-s`` seconds: odd cycles stop cleanly
  (``--duration``), even cycles are killed (TerminateJobObject). Each bridge life has one 3-s dropout
  (``--pause``) at ``--pause-at`` seconds.
- ``trust``    ``trust_proc.py``: toy signal decoder -> StreamingTrustLayer (incremental, GC rule, shadow
  bounded-cache decoder) -> ``trust_decision`` events on the LSL outlet ``soak.decisions``.
- ``consumer`` ``consumer_proc.py``: reads the outlet and validates every event.

Commands (repo root, venv Python):

    python experiments/2026-11-13-m6-13-soak/soak.py supervise [--planned-s 25200] [--resume]
    python experiments/2026-11-13-m6-13-soak/soak.py status
    python experiments/2026-11-13-m6-13-soak/soak.py stop          # clean stop (children write final metrics)
    python experiments/2026-11-13-m6-13-soak/soak.py analyze       # results/summary.json + results/tables.md

``supervise`` is meant to run detached (see HANDOFF.md). ``--resume`` continues a stopped or crashed
run: leftover children are killed, new ones start with epoch + 1, and the run goes on until the active
time reaches ``--planned-s``. Metrics files are append-only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from common import JsonlWriter, log, now_iso  # noqa: E402

RUN_DIR = Path(os.environ.get("SOAK_RUN_DIR", r"C:\Users\zhang\bci-data\soak\m6-13"))
RESULTS = Path(os.environ.get("SOAK_RESULTS_DIR", str(HERE / "results")))


class Proc:
    """A child process in its own Windows job object (as in M6-08: the venv python can be a launcher)."""

    def __init__(self, args: list[str], log_path: Path) -> None:
        self.job = None
        self.args = args
        self.fh = open(log_path, "a", encoding="utf-8")
        if os.name == "nt":
            import ctypes

            k32 = ctypes.windll.kernel32
            k32.CreateJobObjectW.restype = ctypes.c_void_p
            self.job = k32.CreateJobObjectW(None, None)
            self.p = subprocess.Popen(args, stdout=self.fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                      cwd=ROOT, creationflags=0x4 | 0x08000000)  # SUSPENDED | NO_WINDOW
            h = ctypes.c_void_p(int(self.p._handle))  # type: ignore[attr-defined]
            if not k32.AssignProcessToJobObject(ctypes.c_void_p(self.job), h):
                raise OSError("AssignProcessToJobObject failed")
            ctypes.windll.ntdll.NtResumeProcess(h)
        else:
            self.p = subprocess.Popen(args, stdout=self.fh, stderr=subprocess.STDOUT, cwd=ROOT)

    @property
    def pid(self) -> int:
        return self.p.pid

    def alive(self) -> bool:
        return self.p.poll() is None

    def kill(self) -> None:
        if self.job is not None:
            import ctypes

            ctypes.windll.kernel32.TerminateJobObject(ctypes.c_void_p(self.job), 9)
        else:
            self.p.kill()

    def wait(self, timeout: float | None = None) -> int | None:
        try:
            return self.p.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def cpu_seconds(self) -> float | None:
        if self.job is None:
            return None
        import ctypes

        class Acct(ctypes.Structure):
            _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                        ("TotalPageFaultCount", ctypes.c_uint32), ("TotalProcesses", ctypes.c_uint32),
                        ("ActiveProcesses", ctypes.c_uint32), ("TotalTerminatedProcesses", ctypes.c_uint32)]

        acc = Acct()
        ok = ctypes.windll.kernel32.QueryInformationJobObject(ctypes.c_void_p(self.job), 1, ctypes.byref(acc),
                                                              ctypes.sizeof(acc), None)
        return (acc.TotalUserTime + acc.TotalKernelTime) / 1e7 if ok else None


def py() -> list[str]:
    return [sys.executable]


def load_state() -> dict[str, Any]:
    p = RUN_DIR / "state.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_state(st: dict[str, Any]) -> None:
    p = RUN_DIR / "state.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def kill_pid(pid: int) -> None:
    subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)


def supervise(a: argparse.Namespace) -> int:
    from fidetype.utils.power import keep_awake

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    stop_file, child_stop, done = RUN_DIR / "stop", RUN_DIR / "child.stop", RUN_DIR / "DONE"
    st = load_state()
    if a.resume and st:
        for k in ("trust_pid", "consumer_pid", "bridge_pid"):
            if st.get(k):
                kill_pid(int(st[k]))
        st["epoch"] = int(st.get("epoch", 0)) + 1
        st["resumes"] = int(st.get("resumes", 0)) + 1
    else:
        if st and not a.fresh:
            log("state.json exists: use --resume (continue) or --fresh (start over)")
            return 2
        for f in [*(RESULTS.glob("*.jsonl")), RUN_DIR / "events.jsonl"]:
            f.unlink(missing_ok=True)
        st = {"planned_s": a.planned_s, "active_s": 0.0, "started_iso": now_iso(), "cycle": 0, "epoch": 0,
              "resumes": 0, "args": vars(a)}
    for f in (stop_file, child_stop, done):
        f.unlink(missing_ok=True)
    (RUN_DIR / "supervisor.pid").write_text(str(os.getpid()))
    sup = JsonlWriter(RESULTS / "supervisor.jsonl")
    planned = float(st["planned_s"])
    ep = int(st["epoch"])
    sup.write({"event": "start" if ep == 0 else "resume", "t_iso": now_iso(), "epoch": ep, "planned_s": planned,
               "active_s": st["active_s"], "pid": os.getpid()})
    stream = "soak.eeg"
    common = ["--results-dir", str(RESULTS), "--stop-file", str(child_stop), "--window-s", str(a.window_s)]

    def start_consumer(epoch: int) -> Proc:
        p = Proc(py() + [str(HERE / "consumer_proc.py"), *common, "--events-file", str(RUN_DIR / "events.jsonl"),
                         "--epoch", str(epoch)], RUN_DIR / "consumer.log")
        sup.write({"event": "consumer start", "t_iso": now_iso(), "pid": p.pid, "epoch": epoch})
        return p

    def start_trust(epoch: int) -> Proc:
        p = Proc(py() + [str(HERE / "trust_proc.py"), *common, "--stream-name", stream, "--epoch", str(epoch)],
                 RUN_DIR / "trust.log")
        sup.write({"event": "trust start", "t_iso": now_iso(), "pid": p.pid, "epoch": epoch})
        return p

    with keep_awake(log=log):
        consumer = start_consumer(ep)
        time.sleep(1.0)
        trust = start_trust(ep)
        st.update(trust_pid=trust.pid, consumer_pid=consumer.pid)
        save_state(st)
        time.sleep(3.0)
        last = time.monotonic()
        stopped = False
        while st["active_s"] < planned and not stopped:
            k = int(st["cycle"])
            hard = k % 2 == 0
            life = min(a.cycle_s, planned - st["active_s"] + 30.0)
            bargs = py() + ["-m", "fidetype.adapters.lsl", "brainflow-bridge", "--board", "synthetic", "--name", stream,
                            "--source-id", "soak-bridge", "--trial-s", "4",
                            "--stats", str(RUN_DIR / f"bridge-{k:03d}.json")]
            if a.pause_at < life:
                bargs += ["--pause", f"{a.pause_at}:{a.pause_for}"]
            if not hard:
                bargs += ["--duration", str(life)]
            bridge = Proc(bargs, RUN_DIR / "bridge.log")
            st["bridge_pid"] = bridge.pid
            save_state(st)
            sup.write({"event": "bridge start", "t_iso": now_iso(), "cycle": k, "pid": bridge.pid,
                       "end": "kill" if hard else "clean", "life_s": life, "pause": a.pause_at < life})
            t_b = time.monotonic()
            next_hb = time.monotonic() + 60.0
            while True:
                time.sleep(2.0)
                now = time.monotonic()
                st["active_s"] += min(now - last, 60.0)  # a long gap (sleep) is not counted
                last = now
                if stop_file.exists():
                    stopped = True
                    break
                for name in ("trust", "consumer"):
                    p = trust if name == "trust" else consumer
                    if not p.alive():
                        rc = p.wait(1)
                        st["epoch"] = int(st["epoch"]) + 1
                        sup.write({"event": f"{name} died", "t_iso": now_iso(), "rc": rc, "cpu_s": p.cpu_seconds(),
                                   "active_s": st["active_s"], "restart_epoch": st["epoch"]})
                        if name == "trust":
                            trust = start_trust(int(st["epoch"]))
                            st["trust_pid"] = trust.pid
                        else:
                            consumer = start_consumer(int(st["epoch"]))
                            st["consumer_pid"] = consumer.pid
                if now >= next_hb:
                    next_hb = now + 60.0
                    sup.write({"event": "heartbeat", "t_iso": now_iso(), "active_s": round(st["active_s"], 1),
                               "cycle": k, "cpu_s": {"trust": trust.cpu_seconds(), "consumer": consumer.cpu_seconds(),
                                                     "bridge": bridge.cpu_seconds()}})
                    save_state(st)
                if not bridge.alive():
                    rc = bridge.wait(1)
                    sup.write({"event": "bridge exit", "t_iso": now_iso(), "cycle": k, "rc": rc,
                               "after_s": round(now - t_b, 1), "expected": (not hard) and now - t_b >= life - 5,
                               "cpu_s": bridge.cpu_seconds()})
                    break
                if hard and now - t_b >= life:
                    bridge.kill()
                    bridge.wait(10)
                    sup.write({"event": "bridge killed", "t_iso": now_iso(), "cycle": k, "after_s": round(now - t_b, 1),
                               "cpu_s": bridge.cpu_seconds()})
                    break
                if st["active_s"] >= planned:
                    break
            st["cycle"] = k + 1
            save_state(st)
            if st["active_s"] < planned and not stopped:
                time.sleep(a.gap_s)
                st["active_s"] += a.gap_s
                last = time.monotonic()
        # end: trust first (it closes the open utterance), then the consumer (drains), then the bridge
        child_stop.write_text("stop")
        rc_t = trust.wait(90)
        if rc_t is None:
            trust.kill()
        rc_c = consumer.wait(60)
        if rc_c is None:
            consumer.kill()
        if bridge.alive():
            bridge.kill()
            bridge.wait(10)
        sup.write({"event": "end", "t_iso": now_iso(), "reason": "stop file" if stopped else "planned time",
                   "active_s": st["active_s"], "trust_rc": rc_t, "consumer_rc": rc_c,
                   "cpu_s": {"trust": trust.cpu_seconds(), "consumer": consumer.cpu_seconds()}})
        st["finished_iso"] = now_iso()
        st["trust_pid"] = st["consumer_pid"] = st["bridge_pid"] = None
        save_state(st)
    done.write_text(now_iso())
    return 0


def status(_: argparse.Namespace) -> int:
    st = load_state()
    print(json.dumps({k: st.get(k) for k in ("started_iso", "planned_s", "active_s", "cycle", "epoch", "resumes",
                                             "finished_iso")}, indent=1))
    for name in ("metrics-trust.jsonl", "metrics-consumer.jsonl"):
        p = RESULTS / name
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines()
            if lines:
                r = json.loads(lines[-1])
                keep = {k: r.get(k) for k in ("t_iso", "epoch", "window", "rss_mb", "handles")}
                keep["push_ms"] = r.get("push_ms")
                keep["counts"] = r.get("counts")
                print(name, json.dumps(keep))
    print("DONE" if (RUN_DIR / "DONE").exists() else "not done")
    return 0


def stop(_: argparse.Namespace) -> int:
    (RUN_DIR / "stop").write_text("stop")
    print(f"stop file written: {RUN_DIR / 'stop'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("supervise")
    s.add_argument("--planned-s", type=float, default=25200.0)
    s.add_argument("--cycle-s", type=float, default=1800.0)
    s.add_argument("--pause-at", type=float, default=600.0)
    s.add_argument("--pause-for", type=float, default=3.0)
    s.add_argument("--gap-s", type=float, default=5.0)
    s.add_argument("--window-s", type=float, default=120.0)
    s.add_argument("--resume", action="store_true")
    s.add_argument("--fresh", action="store_true")
    sub.add_parser("status")
    sub.add_parser("stop")
    sub.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "supervise":
        return supervise(a)
    if a.cmd == "status":
        return status(a)
    if a.cmd == "stop":
        return stop(a)
    from analyze import analyze

    return analyze(RESULTS, RUN_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
