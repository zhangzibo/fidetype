"""P5-02 rerun on the M4-13 T15 decoder (plan: plan.md). CPU only. Our own code.

The method code is the P5-02 run.py (imported, not changed): ``fidetype.trust.calibrate(..., target_precision=)``,
the held-out measures and the resampling check. Only the data change: calibration = M4-13 val_select (CPU decode),
held out = M4-13 val_eval (decoded by the M4-13 queue). The user's decode_fn is the P14-03 one (imported).

Run (repo root):
  .venv\\Scripts\\python.exe -m fidetype.utils.isolation run --class background --threads 4 --
      .venv\\Scripts\\python.exe -I experiments/2026-11-17-p5-02-precision-m4-13/run.py
Dry run (plumbing only, M4-12 subset): TRUST_RERUN_DRY=1 TRUST_RERUN_SOURCE=m4-12 ... run.py
Per-trial outputs: C:/Users/zhang/bci-data/derived/p5-02-precision-m4-13/ only. Repo: aggregates only.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "2026-11-17-trust-reruns-m4-13"))
import common as K  # noqa: E402

DRY = K.is_dry()
SRC = K.source_name()
if not DRY:
    assert SRC == "m4-13", "a real run uses the M4-13 outputs"
OUT = HERE / ("results/dryrun-" + SRC if DRY else "results")
OUT.mkdir(parents=True, exist_ok=True)

P = K.load_module("p5_02_run", REPO / "experiments/2026-11-16-p5-02-precision/run.py")
P.OWN = K.own("p5-02", DRY)
P.OUT = OUT
P.LOGF = OUT / "run.log"
if DRY:
    P.N_DRAWS = 40
    P.DRAW_SIZE = {"t15": 12}


def make_shim():
    m14 = P.load_p14_03()

    def data_t15():
        (cal, held) = K.load_t15(SRC, norm_text=False)
        dec, bt = K.word_decoder()
        cpm = bt.load_json("prep.json")["speech_rate_125k"]["chars_per_min"]
        split = {"calibration": f"val_select (even-index val trials), {SRC} log-probs",
                 "held_out": f"val_eval (odd-index val trials), {SRC} log-probs"}
        return cal, held, dec, cpm, split

    return types.SimpleNamespace(data_t15=data_t15, data_t12=None, make_decode_fn=m14.make_decode_fn)


def main() -> None:
    M = make_shim()
    path = OUT / "results.json"
    allr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    allr["fidetype_version"] = P.FT_VERSION
    allr["provenance"] = K.provenance(SRC)
    allr["dry_run"] = DRY
    if "t15" in allr and allr["t15"].get("seconds"):
        P.log("t15 done before, skip")
        return
    P.log(f"stage t15 start (source {SRC}, dry {DRY})")
    allr["t15"] = P.run_set("t15", M)
    path.write_text(json.dumps(allr, indent=1, default=str), encoding="utf-8")
    P.log("stage t15 done")


if __name__ == "__main__":
    main()
