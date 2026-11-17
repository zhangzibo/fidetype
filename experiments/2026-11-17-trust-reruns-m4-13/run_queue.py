r"""Trust-rerun queue on the M4-13 decoder (plan: plan.md). Waits for the M4-13 DONE marker, then runs the stages
one after the other. CPU only: no stage uses the GPU (the P11-01 waiter starts GPU training on the same marker).

Stages (a stage is done when DER/trust-reruns-m4-13/stage-<name>.done exists; a re-run skips done stages):
  check          DONE says ok=True; best.pt exists; the queue's val_eval decode (if any) used the same best.pt
  decode-eval    only if the M4-13 queue wrote no val_eval log-probs: CPU decode of val_eval (fallback)
  decode-select  CPU decode of val_select with best.pt (calibration set of every rerun)
  p5-02          experiments/2026-11-17-p5-02-precision-m4-13/run.py
  p15-03         experiments/2026-11-17-p15-03-f1-m4-13/run.py
  p15-05         experiments/2026-11-17-f2-m4-13/run.py p15-05
  p15-06         experiments/2026-11-17-f2-m4-13/run.py p15-06          (needs p15-05)
  p15-06-t12     experiments/2026-11-17-f2-m4-13/run.py p15-06-t12

Each stage runs as `python -m fidetype.utils.isolation run --class background --threads 4 -- <cmd>` with its own
log file in DER/trust-reruns-m4-13/logs/. Before a stage starts, the queue waits (max 60 min) until enough RAM is
free (per-stage limit below); else it stops with status "deferred" (re-run the launcher to resume).
Pause: create DER/trust-reruns-m4-13/pause (the queue stops after the current stage). A failed stage is logged;
stages that need it are skipped; the others still run. Writes DER/trust-reruns-m4-13/queue.DONE at the end.

    .venv\Scripts\python.exe experiments\2026-11-17-trust-reruns-m4-13\run_queue.py [--wait-for FILE] [--only S ...]
Start it hidden with launch.py (CREATE_NO_WINDOW), never with Start-Process -WindowStyle Hidden.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
VPY = REPO / ".venv" / "Scripts" / "python.exe"
TPY = Path(r"C:\venvs\fidetype-rocm\Scripts\python.exe")  # CPU torch for the decode (GPU hidden in the script)
DER = Path("C:/Users/zhang/bci-data/derived")
RUNS = Path("C:/Users/zhang/bci-data/runs")
Q = DER / "trust-reruns-m4-13"
DONE = RUNS / "m4-13-queue.DONE"
BEST = RUNS / "m4-13-long0" / "best.pt"
M413_EVAL = DER / "m4-13" / "logprobs-m4-13-long0-val_eval.npz"
M413_EVAL_META = DER / "m4-13" / "decode-m4-13-long0-val_eval.json"
EXP = "experiments"


def iso(*cmd: str) -> list[str]:
    return [str(VPY), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--", *cmd]


# name, command, free RAM needed in MB (measured peaks in plan.md + margin), stages it needs
STAGES = [
    ("decode-eval", iso(str(TPY), "-u", f"{EXP}/2026-11-17-trust-reruns-m4-13/decode_cpu.py", "--run", "m4-13-long0",
                        "--part", "val_eval"), 2500, ["check"]),
    ("decode-select", iso(str(TPY), "-u", f"{EXP}/2026-11-17-trust-reruns-m4-13/decode_cpu.py", "--run",
                          "m4-13-long0", "--part", "val_select"), 2500, ["check"]),
    ("p5-02", iso(str(VPY), "-I", f"{EXP}/2026-11-17-p5-02-precision-m4-13/run.py"), 2500,
     ["decode-select", "decode-eval"]),
    ("p15-03", iso(str(VPY), "-I", f"{EXP}/2026-11-17-p15-03-f1-m4-13/run.py"), 3000, ["decode-select", "decode-eval"]),
    ("p15-05", iso(str(VPY), "-I", f"{EXP}/2026-11-17-f2-m4-13/run.py", "p15-05"), 4500,
     ["decode-select", "decode-eval"]),
    ("p15-06", iso(str(VPY), "-I", f"{EXP}/2026-11-17-f2-m4-13/run.py", "p15-06"), 4500, ["p15-05"]),
    ("p15-06-t12", iso(str(VPY), "-I", f"{EXP}/2026-11-17-f2-m4-13/run.py", "p15-06-t12"), 6000, []),
]


RUN_ENV = {"TRUST_RERUN_DRY": "0", "TRUST_RERUN_SOURCE": "m4-13", "TRUST_RERUN_STUB_LLM": "0"}


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(Q / "queue.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def free_mb() -> int:
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + [
            (f, ctypes.c_ulonglong) for f in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                                              "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

    m = MS()
    m.dwLength = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return int(m.ullAvailPhys / 2**20)


def marker(name: str) -> Path:
    return Q / f"stage-{name}.done"


def sha256(p: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def check() -> bool:
    txt = DONE.read_text(encoding="ascii", errors="replace").strip()
    log(f"check: DONE file says {txt!r}")
    if not txt.startswith("ok=True"):
        log("check: M4-13 queue did not finish ok; stop (no rerun on a failed decoder)")
        return False
    if not BEST.exists():
        log(f"check: {BEST} missing; stop")
        return False
    sha = sha256(BEST)
    st = json.loads((BEST.parent / "status.json").read_text(encoding="utf-8"))
    info = {"best_sha256": sha, "status": st, "m4_13_eval": M413_EVAL.exists()}
    if M413_EVAL.exists():
        meta = json.loads(M413_EVAL_META.read_text(encoding="utf-8"))
        info["eval_meta_sha256"] = meta.get("checkpoint_sha256")
        if meta.get("checkpoint_sha256") != sha:
            log(f"check: the queue's val_eval decode used another checkpoint ({meta.get('checkpoint_sha256')} != {sha}); stop")
            return False
    else:
        log("check: the M4-13 queue wrote no val_eval log-probs: the CPU fallback decode will run")
    (Q / "check.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    log(f"check: ok {json.dumps(info)}")
    return True


def keep_awake(on: bool) -> None:
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if on else 0x80000000)
    except Exception:  # noqa: BLE001
        pass


def run_stage(name: str, cmd: list[str], need_mb: int) -> str:
    t_wait = time.time()
    while free_mb() < need_mb:
        if time.time() - t_wait > 3600:
            log(f"{name}: only {free_mb()} MB free after 60 min (needs {need_mb}); DEFERRED")
            return "deferred"
        if (Q / "pause").exists():
            return "paused"
        time.sleep(120)
    (Q / "logs").mkdir(exist_ok=True)
    out = Q / "logs" / f"{name}.log"
    env = dict(os.environ, PYTHONUNBUFFERED="1", **RUN_ENV)
    log(f"{name}: start ({free_mb()} MB free) {' '.join(cmd)}")
    t0 = time.time()
    with open(out, "ab") as fh:
        p = subprocess.run(cmd, cwd=REPO, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT, env=env,
                           creationflags=0x08000000)
    log(f"{name}: exit code {p.returncode} after {time.time() - t0:.0f} s (log {out})")
    if p.returncode == 0:
        marker(name).write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="ascii")
        return "done"
    return "failed"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-for", default=str(DONE))
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry", action="store_true", help="plumbing test: M4-12 subsets, stub LLM, no decode, no check")
    a = ap.parse_args()
    global Q
    if a.dry:
        Q = Q / "dryrun-queue"
        RUN_ENV.update(TRUST_RERUN_DRY="1", TRUST_RERUN_SOURCE="m4-12", TRUST_RERUN_STUB_LLM="1")
    Q.mkdir(parents=True, exist_ok=True)
    (Q / "queue.pid").write_text(str(os.getpid()), encoding="ascii")
    log(f"queue start pid {os.getpid()}; waiting for {a.wait_for}")
    w = Path(a.wait_for)
    while not w.exists():
        if (Q / "pause").exists() or (Q / "stop").exists():
            log("pause/stop file while waiting; exit")
            return 0
        time.sleep(60)
    keep_awake(True)
    try:
        if not a.dry and not marker("check").exists():
            if not check():
                (Q / "queue.FAILED").write_text("check failed", encoding="ascii")
                return 1
            marker("check").write_text(time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="ascii")
        status: dict[str, str] = {}

        def ok(d: str) -> bool:
            """A needed stage is satisfied: done now or before, or not needed."""
            if d == "check" or marker(d).exists():
                return True
            if d == "decode-eval" and M413_EVAL.exists():
                return True
            if a.dry and d.startswith("decode-"):
                return True
            return status.get(d, "") == "done"

        for name, cmd, need, deps in STAGES:
            if a.only and name not in a.only:
                continue
            if name == "decode-eval" and M413_EVAL.exists():
                status[name] = "not needed (queue GPU decode exists)"
                continue
            if a.dry and name.startswith("decode-"):
                status[name] = "not needed (dry run)"
                continue
            if marker(name).exists():
                status[name] = "done before"
                continue
            bad = [d for d in deps if not ok(d)]
            if bad:
                status[name] = f"skipped (needs {bad})"
                log(f"{name}: skipped, needs {bad}")
                continue
            if (Q / "pause").exists():
                log("pause file: stop before " + name)
                return 0
            status[name] = run_stage(name, cmd, need // 3 if a.dry else need)
            if status[name] in ("deferred", "paused"):
                log(f"queue {status[name]} at {name}; re-run the launcher to resume")
                return 0
        log(f"QUEUE DONE {json.dumps(status)}")
        (Q / "queue.DONE").write_text(json.dumps(status), encoding="utf-8")
        return 0 if all(not s.startswith("failed") for s in status.values()) else 1
    finally:
        keep_awake(False)


if __name__ == "__main__":
    raise SystemExit(main())
