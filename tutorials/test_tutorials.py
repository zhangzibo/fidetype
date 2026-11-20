"""Smoke test of the 10-minute tutorials (roadmap P14-43): each one runs in synthetic mode and is timed.

    python -m pytest -q tutorials/          # not in the default test run (testpaths = tests)

Done criterion (pre-registered): every tutorial exits with code 0, prints its PASS line, and its wall
time is under 10 minutes. The times go to $FIDETYPE_TUTORIAL_TIMES (JSON, optional) and to the GitHub job
summary when $GITHUB_STEP_SUMMARY is set.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
LIMIT_S = 600.0  # 10 minutes
TUTORIALS = [
    ("1", "01_decode_pretrained.py"),
    ("2", "02_trust_and_safe_wpm.py"),
    ("3", "03_score_benchmark.py"),
]
TIMES: dict[str, float] = {}


@pytest.mark.parametrize(("num", "script"), TUTORIALS, ids=[s for _, s in TUTORIALS])
def test_tutorial_synthetic_under_10_minutes(num: str, script: str, tmp_path: Path) -> None:
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, str(HERE / script), "--out", str(tmp_path)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=LIMIT_S + 60,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    wall = time.perf_counter() - t0
    TIMES[script] = wall
    _record(script, wall, p.returncode)
    assert p.returncode == 0, f"{script} failed:\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}"
    assert f"TUTORIAL {num} PASS (synthetic)" in p.stdout, p.stdout[-2000:]
    assert wall < LIMIT_S, f"{script} took {wall:.1f} s (limit {LIMIT_S:.0f} s)"


def _record(script: str, wall: float, rc: int) -> None:
    line = f"| {script} | {wall:.1f} s | {'pass' if rc == 0 and wall < LIMIT_S else 'FAIL'} |"
    print(f"\n[tutorial timing] {script}: {wall:.1f} s (exit {rc})")
    out = os.environ.get("FIDETYPE_TUTORIAL_TIMES")
    if out:
        p = Path(out)
        d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {
            "python": platform.python_version(), "platform": platform.platform(), "limit_s": LIMIT_S, "runs": {}}
        d["runs"][script] = {"wall_s": round(wall, 2), "exit": rc}
        p.write_text(json.dumps(d, indent=1), encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            if not TIMES or len(TIMES) == 1:
                f.write(f"### Tutorials (synthetic mode), {platform.system()} py{platform.python_version()}\n\n"
                        "| Tutorial | Wall time | Under 10 min |\n|---|---|---|\n")
            f.write(line + "\n")
