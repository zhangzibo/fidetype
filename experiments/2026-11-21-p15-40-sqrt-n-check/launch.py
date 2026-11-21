"""Start the P15-40 main run fully detached and hidden (pattern: P15-37 launch.py).

    python launch.py main     one worker (2 threads), then the analysis; writes <OWN>/DONE only if both exit 0

Process tree: this launcher (exits at once) -> ``launch.py --chain main`` (detached; CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) -> ``python -m fidetype.utils.isolation run --class background
--threads 2 -- python -I run.py worker`` -> ``... run.py analyse``. Each run.py process holds a keep-awake. CPU only.
The run uses the code of the folder this file is in (a git archive snapshot, see plan.md).
Time limit: the worker starts no new draw after P1540_DEADLINE (set here to launch + 8 h on the first launch and kept
in <OWN>/deadline.txt, so a resume keeps the same limit).

Check: tail <OWN>/chain.log and results/run.log (in the snapshot); count <OWN>/draws/*.json.
Stop: create <OWN>/STOP (the worker stops after its current draw).
Resume: delete STOP and run ``launch.py main`` again (finished draws are skipped; caches persist).
OWN = C:/Users/zhang/bci-data/derived/p15-40
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-40")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("P1540_")}  # never a smoke setting
    e["PYTHONUNBUFFERED"] = "1"
    f = OWN / "deadline.txt"
    if not f.exists():
        f.write_text((dt.datetime.now() + dt.timedelta(hours=8)).isoformat(timespec="seconds") + "\n", encoding="utf-8")
    e["P1540_DEADLINE"] = f.read_text(encoding="utf-8").strip()
    return e


def chain_log(msg: str) -> None:
    with open(OWN / "chain.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def stage_cmd(*args: str) -> list[str]:
    return [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "2", "--",
            py(), "-I", str(HERE / "run.py"), *args]


def chain() -> int:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    codes = {}
    for stage in ("worker", "analyse"):
        if stage == "analyse" and (OWN / "STOP").exists():
            chain_log("stop file found: no analysis, no DONE")
            return 0
        with open(OWN / f"{stage}.out", "ab") as out:
            cmd = stage_cmd(stage)
            chain_log(f"{stage} start: {cmd}")
            codes[stage] = subprocess.run(cmd, cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                          stderr=subprocess.STDOUT, creationflags=flags).returncode
        chain_log(f"{stage} exit {codes[stage]}")
        if codes[stage] != 0:
            break
    if all(c == 0 for c in codes.values()) and len(codes) == 2:
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        chain_log("all exit 0; DONE written")
    else:
        chain_log(f"chain end without DONE: {codes}")
        (OWN / "FAILED").write_text(f"{codes}\n", encoding="utf-8")
    return 0


def main() -> int:
    OWN.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["--chain"]:
        return chain()
    if sys.argv[1:2] != ["main"]:
        raise SystemExit("usage: launch.py main")
    for f in ("DONE", "FAILED"):
        (OWN / f).unlink(missing_ok=True)
    cmd = [py(), str(Path(__file__).resolve()), "--chain", "main"]
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched chain main pid {p.pid}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
