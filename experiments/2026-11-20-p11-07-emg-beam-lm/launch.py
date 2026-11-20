"""Start the P11-07 run fully detached and hidden (pattern: experiments/2026-11-20-p11-12-emg-nosignal-gate/launch.py).

    .venv\\Scripts\\python.exe experiments/2026-11-20-p11-07-emg-beam-lm/launch.py          # modellat, then all
    .venv\\Scripts\\python.exe experiments/2026-11-20-p11-07-emg-beam-lm/launch.py score    # some CPU stages only

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) ->
1. ``python -m fidetype.utils.isolation run --class timing --threads 4 -- <ROCm python> -I run.py modellat``
   (the only GPU step: acoustic model chunk forward on CPU and GPU);
2. ``python -m fidetype.utils.isolation run --class background --threads 1 -- <python> -I run.py all``
   (CPU; run.py starts 6 single-thread worker processes for the grid and the test decodes; the latency stage
   switches itself to the timing class).
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB. run.py holds a keep-awake
(SetThreadExecutionState).

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p11-07/run.out; done when
C:/Users/zhang/bci-data/derived/p11-07/DONE exists.
Resume: run the same command again (finished configs, sessions, arms and stages are skipped; per-unit files in
derived/p11-07/).
Stop: stop the python processes whose command line has ``p11-07-emg-beam-lm``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p11-07")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
ROCM = Path("C:/venvs/fidetype-rocm/Scripts/python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _log(msg: str) -> None:
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def drive(stages: list[str]) -> int:
    base = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    rc = 0
    if not stages:
        if not (OWN / "modellat.json").exists():
            cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "timing", "--threads", "4", "--",
                   str(ROCM), "-I", str(HERE / "run.py"), "modellat"]
            _log(f"driver start {cmd}")
            rc = subprocess.call(cmd, cwd=ROOT, env=base, stdin=subprocess.DEVNULL)
            _log(f"driver exit {rc} for modellat")
        stages = ["all"]
    env = dict(base, HIP_VISIBLE_DEVICES="", CUDA_VISIBLE_DEVICES="")
    cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1", "--",
           str(VENV), "-I", str(HERE / "run.py"), *stages]
    _log(f"driver start {cmd}")
    rc2 = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    _log(f"driver exit {rc2} for {stages}")
    return rc or rc2


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive(sys.argv[2:])
    stages = sys.argv[1:]
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
