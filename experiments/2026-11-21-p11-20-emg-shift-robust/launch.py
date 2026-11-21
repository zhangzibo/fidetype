"""Start P11-20 fully detached and hidden (pattern: P11-18 launch.py). CPU only; no GPU; at most 4 threads.

The run uses a ``git archive`` snapshot of a committed revision (default HEAD) in
C:/Users/zhang/bci-data/derived/p11-20/code/, because other agents may change ``src/fidetype/``. The log and
results.json go to this folder's ``results/`` (env ``P1120_OUT``).

Chain (each step through ``python -m fidetype.utils.isolation run --class background``):
  1. ``run.py infer`` in the torch venv C:/venvs/fidetype-rocm (1 process x 4 threads; C2 check first)
  2. ``run.py prompts`` (C1 check)
  3. 4 x ``run.py worker 1 <w> 4`` (1 thread each): R01 (X5), M01-M40, P41-P80
  4. ``run.py margin``
  5. 4 x ``run.py worker 2 <w> 4``: S01-S40
  6. ``run.py analyse``
Every step must exit 0 before the next starts. Each Python step holds a keep-awake (SetThreadExecutionState).

    .venv\\Scripts\\python.exe experiments/2026-11-21-p11-20-emg-shift-robust/launch.py [rev]

Check: tail results/run.log or C:/Users/zhang/bci-data/derived/p11-20/chain.log; done when
C:/Users/zhang/bci-data/derived/p11-20/DONE exists (FAILED holds the exit codes otherwise).
Resume: run the same command again (finished log-prob files and draws are skipped; memos persist). A sleep loses at
most one draw per worker. Stop: stop the python processes whose command line has ``p11-20-emg-shift-robust``.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p11-20")
CODE = OWN / "code"
REL = HERE.relative_to(ROOT)
TORCH_PY = Path("C:/venvs/fidetype-rocm/Scripts/python.exe")
NW = 4
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONUNBUFFERED"] = "1"
    e["P1120_OUT"] = str(HERE / "results")
    return e


def chain_log(msg: str) -> None:
    with open(OWN / "chain.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def snapshot(rev: str) -> str:
    sha = subprocess.run(["git", "rev-parse", rev], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    stamp = CODE / "REVISION"
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == sha:
        return sha
    data = subprocess.run(["git", "archive", "--format=tar", sha], cwd=ROOT, capture_output=True, check=True).stdout
    CODE.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(CODE, filter="data")
    stamp.write_text(sha + "\n", encoding="utf-8")
    return sha


def stage_cmd(*args: str, threads: int = 1, interp: str | None = None) -> list[str]:
    return [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", str(threads), "--",
            interp or py(), "-I", str(CODE / REL / "run.py"), *args]


def run_one(tag: str, cmd: list[str]) -> int:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    chain_log(f"{tag} start: {cmd}")
    with open(OWN / f"{tag}.out", "ab") as out:
        rc = subprocess.run(cmd, cwd=CODE, env=env(), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                            creationflags=flags).returncode
    chain_log(f"{tag} exit {rc}")
    return rc


def run_workers(phase: int) -> dict:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    procs, outs, codes = [], [], {}
    for w in range(NW):
        cmd = stage_cmd("worker", str(phase), str(w), str(NW))
        chain_log(f"phase {phase} worker {w} start: {cmd}")
        out = open(OWN / f"worker{phase}-{w}.out", "ab")
        outs.append(out)
        procs.append(subprocess.Popen(cmd, cwd=CODE, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT, creationflags=flags))
    for w, p in enumerate(procs):
        codes[f"worker{phase}-{w}"] = p.wait()
        chain_log(f"phase {phase} worker {w} exit {codes[f'worker{phase}-{w}']}")
    for out in outs:
        out.close()
    return codes


def chain() -> int:
    codes: dict = {}
    steps = [
        ("infer", lambda: {"infer": run_one("infer", stage_cmd("infer", threads=4, interp=str(TORCH_PY)))}),
        ("prompts", lambda: {"prompts": run_one("prompts", stage_cmd("prompts"))}),
        ("phase1", lambda: run_workers(1)),
        ("margin", lambda: {"margin": run_one("margin", stage_cmd("margin"))}),
        ("phase2", lambda: run_workers(2)),
        ("analyse", lambda: {"analyse": run_one("analyse", stage_cmd("analyse"))}),
    ]
    for name, fn in steps:
        c = fn()
        codes.update(c)
        if any(v != 0 for v in c.values()):
            (OWN / "FAILED").write_text(f"{codes}\n", encoding="utf-8")
            chain_log(f"chain stop after {name}: {codes}")
            return 0
    (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
    chain_log("all exit 0; DONE written")
    return 0


def main() -> int:
    OWN.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["--chain"]:
        return chain()
    sha = snapshot(sys.argv[1] if len(sys.argv) > 1 else "HEAD")
    for f in ("DONE", "FAILED"):
        if (OWN / f).exists():
            (OWN / f).unlink()
    cmd = [py(), str(Path(__file__).resolve()), "--chain"]
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched chain pid {p.pid} (code {sha[:7]})\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
