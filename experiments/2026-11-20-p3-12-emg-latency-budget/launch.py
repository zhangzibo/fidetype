"""Start the P3-12 run fully detached and hidden (pattern: experiments/2026-11-20-p11-07-emg-beam-lm/launch.py).

    .venv\\Scripts\\python.exe experiments/2026-11-20-p3-12-emg-latency-budget/launch.py

Process tree: this launcher (exits at once) -> a hidden driver (this file, ``--drive``) -> in order:
1. ``python -m fidetype.utils.isolation run --class background --threads 1 -- python -I run.py check``
2. ``python -m fidetype.utils.isolation run --class timing --threads 1 --env-json derived/p3-12/iso-latency.json
   -- python -I run.py latency`` (if its record is not clean: once more as ``--tag latency2``)
3. ``... --class timing --threads 4 --env-json derived/p3-12/iso-latency4.json -- python -I run.py latency4``
4. ``... --class background --threads 1 -- python -I run.py score``, then the DONE file.
Flags: CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB (no window). run.py holds a
keep-awake (SetThreadExecutionState).

Check: tail results/run.log or C:/Users/zhang/bci-data/derived/p3-12/run.out; done when
C:/Users/zhang/bci-data/derived/p3-12/DONE exists.
Stop: create C:/Users/zhang/bci-data/derived/p3-12/STOP (the stages stop between windows; the driver stops).
Resume: delete STOP and run the same command (finished stages are skipped: their JSON files exist).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p3-12")
VENV = ROOT / ".venv" / "Scripts" / "python.exe"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _log(msg: str) -> None:
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def _run(cls: str, threads: int, args: list[str], env_json: str | None = None) -> int:
    if (OWN / "STOP").exists():
        _log(f"STOP file: skip {args}")
        return 3
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8", HIP_VISIBLE_DEVICES="",
               CUDA_VISIBLE_DEVICES="")
    cmd = [str(VENV), "-m", "fidetype.utils.isolation", "run", "--class", cls, "--threads", str(threads),
           "--wait", "1800", "--label", f"p3-12 {' '.join(args)}"]
    if env_json:
        cmd += ["--env-json", str(OWN / env_json)]
    cmd += ["--", str(VENV), "-I", str(HERE / "run.py"), *args]
    _log(f"driver start {cmd}")
    rc = subprocess.call(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    _log(f"driver exit {rc} for {args}")
    return rc


def drive() -> int:
    rc = _run("background", 1, ["check"])
    if rc:
        return rc
    rc = _run("timing", 1, ["latency"], "iso-latency.json")
    if rc:
        return rc
    rec = json.loads((OWN / "iso-latency.json").read_text(encoding="utf-8"))
    if not rec.get("clean") and not (OWN / "latency2.json").exists():
        _log(f"latency record not clean ({rec.get('clean_reasons')}): run once more (plan rule)")
        rc = _run("timing", 1, ["latency", "--tag", "latency2"], "iso-latency2.json")
        if rc:
            return rc
    rc = _run("timing", 4, ["latency4"], "iso-latency4.json")
    if rc:
        return rc
    rc = _run("background", 1, ["score"])
    if rc == 0:
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        _log("DONE")
    return rc


def main() -> int:
    if sys.argv[1:2] == ["--drive"]:
        return drive()
    OWN.mkdir(parents=True, exist_ok=True)
    out = open(OWN / "run.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    cmd = [str(VENV), str(HERE / "launch.py"), "--drive"]
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
