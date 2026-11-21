"""Start a P15-37 stage fully detached and hidden (pattern: P15-34 launch.py).

    python launch.py select   stage S alone (one process, 4 threads); writes <OWN>/SELECT_DONE on exit 0
    python launch.py main     two workers in parallel (2 threads each, 4 in total), then the analysis;
                              writes <OWN>/DONE only if both workers and the analysis exit 0

Process tree: this launcher (exits at once) -> ``launch.py --chain <stage>`` (detached; CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) -> ``python -m fidetype.utils.isolation run --class background
--threads N -- python -I run.py <stage args>``. Each run.py process holds a keep-awake. CPU only; no GPU.
The run uses the code of the folder this file is in (a git archive snapshot, see plan.md).

Check: tail <OWN>/chain.log and results/run.log (in the snapshot); count <OWN>/t15/draw-*.json.
Stop: create <OWN>/STOP (each worker stops after its current draw).
Resume: delete STOP and run ``launch.py main`` again (finished draws are skipped; caches persist).
OWN = C:/Users/zhang/bci-data/derived/p15-37
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-37")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("P1537_")}  # never a smoke setting
    e["PYTHONUNBUFFERED"] = "1"
    return e


def chain_log(msg: str) -> None:
    with open(OWN / "chain.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def stage_cmd(threads: int, *args: str) -> list[str]:
    return [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", str(threads), "--",
            py(), "-I", str(HERE / "run.py"), *args]


def chain(stage: str) -> int:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    if stage == "select":
        with open(OWN / "select.out", "ab") as out:
            cmd = stage_cmd(4, "select")
            chain_log(f"select start: {cmd}")
            code = subprocess.run(cmd, cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                  stderr=subprocess.STDOUT, creationflags=flags).returncode
        chain_log(f"select exit {code}")
        if code == 0:
            (OWN / "SELECT_DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        return 0
    codes = {}
    outs = {w: open(OWN / f"worker{w}.out", "ab") for w in (0, 1)}
    procs = {}
    for w in (0, 1):
        cmd = stage_cmd(2, "worker", str(w))
        chain_log(f"worker {w} start: {cmd}")
        procs[w] = subprocess.Popen(cmd, cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=outs[w],
                                    stderr=subprocess.STDOUT, creationflags=flags)
        time.sleep(90)  # stagger the data loads (RAM peak)
    for w, p in procs.items():
        codes[f"worker{w}"] = p.wait()
        outs[w].close()
        chain_log(f"worker {w} exit {codes[f'worker{w}']}")
    if (OWN / "STOP").exists():
        chain_log("stop file found: no analysis, no DONE")
        return 0
    with open(OWN / "analyse.out", "ab") as out:
        codes["analyse"] = subprocess.run(stage_cmd(2, "analyse"), cwd=ROOT, env=env(), stdin=subprocess.DEVNULL,
                                          stdout=out, stderr=subprocess.STDOUT, creationflags=flags).returncode
    chain_log(f"analyse exit {codes['analyse']}")
    if all(c == 0 for c in codes.values()):
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        chain_log("all exit 0; DONE written")
    else:
        chain_log(f"chain end without DONE: {codes}")
    return 0


def main() -> int:
    OWN.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:2] == ["--chain"]:
        return chain(sys.argv[2])
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    if stage not in ("select", "main"):
        raise SystemExit("usage: launch.py select | main")
    cmd = [py(), str(Path(__file__).resolve()), "--chain", stage]
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched chain {stage} pid {p.pid}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
