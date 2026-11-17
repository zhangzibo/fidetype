"""P15-02 replay smoke test on the recorded T12 pilot outputs (local data only; skipped elsewhere).

Runs ``experiments/2026-11-16-p15-02-hooks/smoke.py`` on 5 days into a temporary folder: the update
hook swaps the guard only on accepted updates, the negative controls are rejected, and the update
ledger verifies.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "2026-11-16-p15-02-hooks" / "smoke.py"
DATA = Path("C:/Users/zhang/bci-data/derived/f1-e2-pilot/replay")


@pytest.mark.skipif(not (DATA / "frozen" / "records-S08.pkl").exists(), reason="T12 pilot records not local")
def test_replay_smoke_on_t12_pilot_records(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--days", "5", "--out", str(tmp_path)], capture_output=True,
                       text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    s = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert s["ledger_verify_ok"] and s["every_proposal_decided"]
    assert s["n_proposed"] == s["n_accepted"] + s["n_rejected"] >= 3
    assert not s["negative_control"]["accepted"] and s["negative_control"]["guard_unchanged"]
    assert not s["negative_control_loop"]["accepted"] and s["negative_control_loop"]["guard_unchanged"]
    assert s["guard_unchanged_on_reject"] and s["guard_changed_on_accept"]
