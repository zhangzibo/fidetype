"""Helper: write the participant of every sEMG fit-pool sentence (pool = fit-A + fit-B order of R3) to the R4 cache."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common4 as Q  # noqa: E402

out = {}
for c in ("calib", "xsession", "xsubject"):
    cond = Q.C.emg_condition(c)
    out[c] = list(cond.fit_who)
(Q.CACHE4 / "emg-fit-who.json").write_text(json.dumps(out), encoding="utf-8")
print({k: len(v) for k, v in out.items()})
