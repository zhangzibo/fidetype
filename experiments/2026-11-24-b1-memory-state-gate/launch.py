r"""Start a B1 job fully detached, with no visible window (the A1 / P15-50 launcher pattern).

    python launch.py download     # download.py --out C:\Users\zhang\bci-data\raw\penn-ram-fr1
    python launch.py run [args]   # b1run.py all [args], CPU only, 4 worker threads, low priority

Check:  type C:\Users\zhang\bci-data\raw\penn-ram-fr1\download.log   (download)
        type C:\Users\zhang\bci-data\derived\b1-penn-ram-fr1\b1.log    (run; and run.out)
Stop:   download: taskkill /PID <pid in download.pid> /T /F (the next start resumes partial files)
        run: create the file C:\Users\zhang\bci-data\derived\b1-penn-ram-fr1\stop (exits after the current session)
Resume: run this launcher again (finished files / sessions / stages skip).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = Path(r"C:\Users\zhang\bci-data\raw\penn-ram-fr1")
OUT = Path(r"C:\Users\zhang\bci-data\derived\b1-penn-ram-fr1")
PY = Path(r"C:\venvs\fidetype-rocm\Scripts\python.exe")
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("download", "run"):
        print(__doc__)
        return 2
    job = sys.argv[1]
    env = dict(os.environ)
    if job == "download":
        work = RAW
        cmd = [str(PY), "-I", str(HERE / "download.py"), "--out", str(RAW), *sys.argv[2:]]
    else:
        work = OUT
        if (OUT / "stop").exists():
            print(f"{OUT / 'stop'} exists: remove it first", file=sys.stderr)
            return 2
        cmd = [str(PY), str(HERE / "b1run.py"), "all", *sys.argv[2:]]
        for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            env[k] = "4"
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["HIP_VISIBLE_DEVICES"] = ""
    work.mkdir(parents=True, exist_ok=True)
    out = open(work / f"{job}.out", "ab")
    flags = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | BELOW_NORMAL_PRIORITY_CLASS
    kw = dict(cwd=ROOT, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, close_fds=True, env=env)
    try:
        p = subprocess.Popen(cmd, creationflags=flags | CREATE_BREAKAWAY_FROM_JOB, **kw)
        breakaway = True
    except OSError:
        p = subprocess.Popen(cmd, creationflags=flags, **kw)
        breakaway = False
    (work / f"{job}.pid").write_text(str(p.pid), encoding="utf-8")
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {job} launched pid {p.pid} breakaway={breakaway}\n"
    with open(work / "launcher.log", "a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
