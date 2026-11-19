"""Start the P15-26 stages fully detached and hidden, one process per stage (pattern: P15-22 launch.py).

Process tree: this launcher (exits at once) -> ``launch.py --chain`` (detached; flags CREATE_NO_WINDOW |
CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB) -> for each stage, in order:
``python -m fidetype.utils.isolation run --class background --threads 4 -- python -I run.py <stage>``.
Each stage holds a keep-awake (SetThreadExecutionState). CPU only; no GPU.

    .venv\\Scripts\\python.exe experiments/2026-11-19-p15-26-replication/launch.py            # all stages
    .venv\\Scripts\\python.exe experiments/2026-11-19-p15-26-replication/launch.py c1 c2      # some stages

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p15-26/chain.log; done when
C:/Users/zhang/bci-data/derived/p15-26/DONE exists (written only if every stage exits 0).
Resume: run the same command again (finished arms and units are skipped; caches persist).
A stage that dies (for example killed for low memory) is NOT restarted: the chain logs its exit code and goes on.
Stop: stop the python processes whose command line has ``p15-26-replication``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWN = Path("C:/Users/zhang/bci-data/derived/p15-26")
ORDER = ["t12", "c0", "c1", "c2", "c3", "p1", "verdict"]
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    """The repo venv python; in a pinned snapshot of the repo (no .venv; see results.md) the calling python."""
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("P1526_")}  # never a smoke setting
    e["PYTHONUNBUFFERED"] = "1"
    return e


def chain_log(msg: str) -> None:
    with open(OWN / "chain.log", "a", encoding="utf-8") as fh:
        fh.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}\n")


def chain(stages: list[str]) -> int:
    codes = {}
    with open(OWN / "run.out", "ab") as out:
        for st in stages:
            cmd = [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "4", "--",
                   py(), "-I", str(HERE / "run.py"), st]
            chain_log(f"stage {st} start: {cmd}")
            rc = subprocess.run(cmd, cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                stderr=subprocess.STDOUT).returncode
            codes[st] = rc
            chain_log(f"stage {st} exit {rc}" + ("" if rc == 0 else " (not restarted; reported as not run)"))
    if stages == ORDER and all(c == 0 for c in codes.values()):
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "\n", encoding="utf-8")
        chain_log("all stages exit 0; DONE written")
    else:
        chain_log(f"chain end without DONE: {codes}")
    return 0


def main() -> int:
    OWN.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    if args[:1] == ["--chain"]:
        return chain(args[1:])
    stages = args or ORDER
    bad = [s for s in stages if s not in ORDER]
    if bad:
        raise SystemExit(f"unknown stage(s) {bad}; known: {ORDER}")
    cmd = [py(), str(Path(__file__).resolve()), "--chain", *stages]
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    kw = dict(cwd=ROOT, env=env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | (CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} launched chain pid {p.pid} stages={stages}\n"
    with open(OWN / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
