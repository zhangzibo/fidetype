"""Start run.py fully detached and hidden (pattern: experiments/2026-11-19-p15-22-llm-learned/launch.py).

    .venv\\Scripts\\python.exe experiments/2026-11-19-p11-09-emg-trust/launch.py            # infer, then all
    .venv\\Scripts\\python.exe experiments/2026-11-19-p11-09-emg-trust/launch.py infer      # one stage group

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) -> per stage group
``python -m fidetype.utils.isolation run --class background --threads 4 -- <python> -I run.py <stages>``.
``infer`` runs with the torch venv (C:/venvs/fidetype-rocm, device cpu); the other stages with .venv.
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB. run.py holds a keep-awake.
CPU only; no GPU (HIP_VISIBLE_DEVICES is empty).

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p11-09/run.out; done when
C:/Users/zhang/bci-data/derived/p11-09/DONE exists.
Resume: run the same command again (finished stages and sessions are skipped; files in derived/p11-09).
Stop: stop the python processes whose command line has ``p11-09-emg-trust``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p11-09")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
TORCH_VENV = Path("C:/venvs/fidetype-rocm/Scripts/python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def groups(stages: list[str]) -> list[tuple[Path, list[str]]]:
    out = []
    if "infer" in stages:
        out.append((TORCH_VENV, ["infer"]))
    rest = [s for s in stages if s != "infer"]
    if rest:
        out.append((VENV, rest))
    return out


def drive(stages: list[str]) -> int:
    env = dict(os.environ, PYTHONUNBUFFERED="1", HIP_VISIBLE_DEVICES="", CUDA_VISIBLE_DEVICES="")
    for py, st in groups(stages):
        cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
               str(py), "-I", str(HERE / "run.py"), *st]
        with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} driver start {cmd}\n")
        rc = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
        with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} driver exit {rc} for {st}\n")
        if rc != 0:
            return rc
    return 0


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive(sys.argv[2:])
    stages = sys.argv[1:] or ["infer", "all"]
    OWN.mkdir(parents=True, exist_ok=True)
    out = open(OWN / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    cmd = [str(VENV), str(HERE / "launch.py"), "--drive", *stages]
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched driver pid {p.pid} cmd={cmd}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
