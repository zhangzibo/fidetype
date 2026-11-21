"""Start P11-16 fully detached and hidden (pattern: P11-17 launch.py).

The run uses a ``git archive`` snapshot of a committed revision (default HEAD) in
C:/Users/zhang/bci-data/derived/p11-16/code/, because other agents may change ``src/fidetype/``. The log and
results.json go to this folder's ``results/`` (env ``P1116_OUT``).

Process tree: this launcher (exits at once) -> ``launch.py --chain`` (detached) ->
``python -m fidetype.utils.isolation run --class background --threads 2 -- python -I <snapshot>/.../run.py all``.
run.py holds a keep-awake (SetThreadExecutionState). CPU only; no GPU.

    .venv\\Scripts\\python.exe experiments/2026-11-21-p11-16-emg-prefix-confidence/launch.py [rev]

Check: tail results/run.log, or C:/Users/zhang/bci-data/derived/p11-16/chain.log; count the draw-k*.json files in
C:/Users/zhang/bci-data/derived/p11-16/; done when C:/Users/zhang/bci-data/derived/p11-16/DONE exists (FAILED on a
non-zero exit).
Resume: run the same command again (finished stages, arms and draws are skipped; the memo persists).
Stop: stop the python processes whose command line has ``p11-16-emg-prefix-confidence``.
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
OWN = Path("C:/Users/zhang/bci-data/derived/p11-16")
CODE = OWN / "code"
REL = HERE.relative_to(ROOT)
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def py() -> str:
    v = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(v) if os.name == "nt" and v.exists() else sys.executable


def env() -> dict:
    e = dict(os.environ)
    e["PYTHONUNBUFFERED"] = "1"
    e["P1116_OUT"] = str(HERE / "results")
    e["HIP_VISIBLE_DEVICES"] = ""
    e["CUDA_VISIBLE_DEVICES"] = ""
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


def chain() -> int:
    flags = CREATE_NO_WINDOW if os.name == "nt" else 0
    cmd = [py(), "-m", "fidetype.utils.isolation", "run", "--class", "background", "--threads", "2", "--",
           py(), "-I", str(CODE / REL / "run.py"), "all"]
    chain_log(f"start: {cmd}")
    with open(OWN / "run.out", "ab") as out:
        code = subprocess.run(cmd, cwd=CODE, env=env(), stdin=subprocess.DEVNULL, stdout=out,
                              stderr=subprocess.STDOUT, creationflags=flags).returncode
    chain_log(f"exit {code}")
    if code == 0 and (OWN / "DONE").exists():
        chain_log("DONE present")
    else:
        (OWN / "FAILED").write_text(f"exit {code}\n", encoding="utf-8")
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
