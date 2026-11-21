"""Start P11-18 fully detached and hidden: 4 workers (z0, P01-P40, E01-E40), then the analysis (pattern: P11-17 launch.py).

The run uses a ``git archive`` snapshot of a committed revision (default HEAD) in
C:/Users/zhang/bci-data/derived/p11-18/code/, because other agents may change ``src/fidetype/``. The log and
results.json go to this folder's ``results/`` (env ``P1118_OUT``).

Process tree: this launcher (exits at once) -> ``launch.py --chain`` (detached) ->
4 x ``python -m fidetype.utils.isolation run --class background --threads 1 -- python -I <snapshot>/.../run.py worker <w> 4``
(in parallel), then ``run.py analyse``. Each worker holds a keep-awake (SetThreadExecutionState). CPU only; no GPU.

    .venv\\Scripts\\python.exe experiments/2026-11-21-p11-18-emg-above-alpha/launch.py [rev]

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p11-18/chain.log; count the draw-*.json files in
C:/Users/zhang/bci-data/derived/p11-18/; done when C:/Users/zhang/bci-data/derived/p11-18/DONE exists (written
only if all workers and the analysis exit 0).
Resume: run the same command again (finished draws are skipped; the memo persists). A sleep loses at most one draw per worker.
Stop: stop the python processes whose command line has ``p11-18-emg-above-alpha``.
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
OWN = Path("C:/Users/zhang/bci-data/derived/p11-18")
CODE = OWN / "code"
REL = HERE.relative_to(ROOT)
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
    e["P1118_OUT"] = str(HERE / "results")
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


def stage_cmd(*args: str) -> list[str]:
    return [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "1", "--",
            py(), "-I", str(CODE / REL / "run.py"), *args]


def chain() -> int:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    codes = {}
    procs, outs = [], []
    for w in range(NW):
        cmd = stage_cmd("worker", str(w), str(NW))
        chain_log(f"worker {w} start: {cmd}")
        out = open(OWN / f"worker{w}.out", "ab")
        outs.append(out)
        procs.append(subprocess.Popen(cmd, cwd=CODE, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                      stderr=subprocess.STDOUT, creationflags=flags))
    for w, p in enumerate(procs):
        codes[f"worker{w}"] = p.wait()
        chain_log(f"worker {w} exit {codes[f'worker{w}']}")
    for out in outs:
        out.close()
    if all(c == 0 for c in codes.values()):
        cmd = stage_cmd("analyse")
        chain_log(f"analyse start: {cmd}")
        with open(OWN / "analyse.out", "ab") as out:
            codes["analyse"] = subprocess.run(cmd, cwd=CODE, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                                              stderr=subprocess.STDOUT, creationflags=flags).returncode
        chain_log(f"analyse exit {codes['analyse']}")
    if "analyse" in codes and all(c == 0 for c in codes.values()):
        (OWN / "DONE").write_text(time.strftime("%Y-%m-%dT%H:%M:%S") + "
", encoding="utf-8")
        chain_log("all exit 0; DONE written")
    else:
        (OWN / "FAILED").write_text(f"{codes}
", encoding="utf-8")
        chain_log(f"chain end without DONE: {codes}")
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
