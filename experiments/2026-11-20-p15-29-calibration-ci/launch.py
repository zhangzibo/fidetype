"""Start P15-29 fully detached and hidden: two workers in parallel, then the analysis (pattern: P15-26 launch.py).

Process tree: this launcher (exits at once) -> ``launch.py --chain`` (detached; flags CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) -> two parallel processes
``python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py worker <w>``,
then ``run.py analyse``. Each process holds a keep-awake (SetThreadExecutionState). CPU only; no GPU.

    .venv\\Scripts\\python.exe experiments/2026-11-20-p15-29-calibration-ci/launch.py

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p15-29/chain.log; count the draw files in
C:/Users/zhang/bci-data/derived/p15-29/t15/ and t12/; done when C:/Users/zhang/bci-data/derived/p15-29/DONE exists
(written only if both workers and the analysis exit 0).
Resume: run the same command again (finished draws are skipped; caches persist). A sleep loses at most one draw.
Stop: stop the python processes whose command line has ``p15-29-calibration-ci``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-29")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("P1529_")}  # never a smoke setting
    e["PYTHONUNBUFFERED"] = "1"
    return e


def chain_log(msg: str) -> None:
    with open(OWN / "chain.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def stage_cmd(*args: str) -> list[str]:
    return [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
            py(), "-I", str(HERE / "run.py"), *args]


def chain() -> int:
    codes = {}
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    outs = {w: open(OWN / f"worker{w}.out", "ab") for w in (0, 1)}
    procs = {}
    for w in (0, 1):
        cmd = stage_cmd("worker", str(w))
        chain_log(f"worker {w} start: {cmd}")
        procs[w] = subprocess.Popen(cmd, cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=outs[w],
                                    stderr=subprocess.STDOUT, creationflags=flags)
        time.sleep(60)  # stagger the data loads (RAM peak)
    for w, p in procs.items():
        codes[f"worker{w}"] = p.wait()
        outs[w].close()
        chain_log(f"worker {w} exit {codes[f'worker{w}']}")
    with open(OWN / "analyse.out", "ab") as out:
        codes["analyse"] = subprocess.run(stage_cmd("analyse"), cwd=ROOT, env=env(), stdin=subprocess.DEVNULL,
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
        return chain()
    cmd = [py(), str(Path(__file__).resolve()), "--chain"]
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched chain pid {p.pid}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
